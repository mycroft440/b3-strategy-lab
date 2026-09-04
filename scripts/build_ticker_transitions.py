from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.cotahist import download_cotahist  # noqa: E402
from b3_strategy_lab.instrument_transitions import load_transition_reviews  # noqa: E402
from b3_strategy_lab.point_in_time import read_standard_company_equity_cotahist  # noqa: E402
from b3_strategy_lab.realistic_certification import sha256_file  # noqa: E402
from scripts.sync_official_universe import _parse_years  # noqa: E402


DEFAULT_UNIVERSE = Path("data/universes/point_in_time_union.json")
DEFAULT_OUTPUT = Path("data/corporate_actions/ticker_transitions.csv")
DEFAULT_MANIFEST = Path("data/corporate_actions/ticker_transitions.manifest.json")
DEFAULT_UNRESOLVED = Path("reports/unresolved_historical_delistings.csv")
DEFAULT_REVIEWS = Path("data/corporate_actions/instrument_transition_reviews.json")
EXCLUDED_TICKERS = {"BOAC34"}
RECENT_STALE_DAYS = 45


def _write(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _stale_category(last_quote_date: str, coverage_end: str, *, transitioned: bool) -> str:
    """Classify an unexplained end-of-history gap without silently approving it.

    A recent gap can be a temporary suspension or merely low liquidity, while an old
    gap is more suggestive of a delisting/corporate event. Neither is evidence of a
    resolved state. Certified replay therefore blocks on both categories until a
    same-ISIN transition or another explicit source-backed event explains the gap.
    """

    if transitioned or last_quote_date >= coverage_end:
        return ""
    age = (date.fromisoformat(coverage_end) - date.fromisoformat(last_quote_date)).days
    return "recent_stale_symbol" if age <= RECENT_STALE_DAYS else "unresolved_disappearance"



def _same_isin_transition_rows(items: list, isin: str) -> list[dict[str, object]]:
    """Return unambiguous 1:1 ticker renames for one ISIN.

    Two different symbols carrying the same ISIN on the same session are not enough
    evidence to order a rename. The previous implementation depended on input ordering
    and could manufacture A->B->A transitions. Such overlap now fails closed.
    """
    ordered = sorted(items, key=lambda item: (item.date, item.ticker.upper()))
    if not ordered:
        return []
    tickers_by_date: dict[str, set[str]] = defaultdict(set)
    for item in ordered:
        tickers_by_date[item.date].add(item.ticker.upper())
    simultaneous = {
        day: sorted(names) for day, names in tickers_by_date.items() if len(names) > 1
    }
    if simultaneous:
        raise ValueError(
            f"{isin}: simultaneous same-ISIN symbols make automatic rename ambiguous: "
            f"{simultaneous}"
        )

    rows: list[dict[str, object]] = []
    previous_ticker = ordered[0].ticker.upper()
    previous_date = ordered[0].date
    for item in ordered[1:]:
        ticker = item.ticker.upper()
        if ticker != previous_ticker:
            if not previous_date < item.date:
                raise ValueError(
                    f"{isin}: rename boundary is not strictly chronological: "
                    f"{previous_ticker}@{previous_date} -> {ticker}@{item.date}"
                )
            rows.append(
                {
                    "effective_date": item.date,
                    "old_ticker": previous_ticker,
                    "new_ticker": ticker,
                    "share_ratio": "1",
                    "cash_per_old_share": "0",
                    "evidence": "same_isin_continuity",
                    "isin": isin,
                    "last_old_quote": previous_date,
                    "first_new_quote": item.date,
                }
            )
        previous_ticker = ticker
        previous_date = item.date
    return rows

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Detect deterministic ticker renames relevant to the point-in-time "
            "backtest. Same-ISIN continuity is auto-approved; every other relevant "
            "end-of-history gap remains fail-closed. No quote after --end is used."
        )
    )
    parser.add_argument("--universe-manifest", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--years", nargs="+", default=[f"2017:{date.today().year}"])
    parser.add_argument("--end")
    parser.add_argument("--archives-dir", type=Path, default=Path(".cache/cotahist"))
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--unresolved-output", type=Path, default=DEFAULT_UNRESOLVED)
    parser.add_argument("--transition-reviews", type=Path, default=DEFAULT_REVIEWS)
    args = parser.parse_args(argv)

    universe = json.loads(args.universe_manifest.read_text(encoding="utf-8"))
    relevant_tickers = {
        str(ticker).strip().upper()
        for ticker in universe.get("market_data_tickers", universe.get("tickers", []))
        if str(ticker).strip()
    }
    relevant_tickers.difference_update(EXCLUDED_TICKERS)
    if not relevant_tickers:
        parser.error("Point-in-time universe contains no relevant market-data tickers.")

    years = _parse_years(args.years)
    all_quotes = []
    for year in years:
        archive = args.archives_dir / f"COTAHIST_A{year}.ZIP"
        if args.download:
            archive = download_cotahist(
                year,
                args.archives_dir,
                refresh=year == date.today().year,
            )
        if not archive.exists():
            raise FileNotFoundError(f"{archive} missing; use --download.")
        all_quotes.extend(
            quote
            for quote in read_standard_company_equity_cotahist(archive)
            if quote.ticker.strip().upper() not in EXCLUDED_TICKERS
        )
    if not all_quotes:
        raise ValueError("No eligible COTAHIST rows found in requested archive window.")

    requested_end = args.end or str(universe.get("selection_end", "")).strip() or max(
        quote.date for quote in all_quotes
    )
    eligible_dates = [quote.date for quote in all_quotes if quote.date <= requested_end]
    if not eligible_dates:
        parser.error("No B3 market session exists at or before --end.")
    coverage_end = max(eligible_dates)
    quotes = [quote for quote in all_quotes if quote.date <= coverage_end]

    by_isin: dict[str, list] = defaultdict(list)
    by_ticker: dict[str, list] = defaultdict(list)
    for quote in quotes:
        ticker = quote.ticker.strip().upper()
        if ticker in EXCLUDED_TICKERS or not ticker or not quote.isin:
            continue
        by_isin[quote.isin.strip().upper()].append(quote)
        if ticker in relevant_tickers:
            by_ticker[ticker].append(quote)

    relevant_isins = {
        isin
        for isin, items in by_isin.items()
        if any(item.ticker.upper() in relevant_tickers for item in items)
    }

    transitions: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for isin in sorted(relevant_isins):
        eligible_items = [
            item for item in by_isin[isin] if item.ticker.upper() not in EXCLUDED_TICKERS
        ]
        for row in _same_isin_transition_rows(eligible_items, isin):
            key = (
                str(row["effective_date"]),
                str(row["old_ticker"]),
                str(row["new_ticker"]),
            )
            if key in seen:
                continue
            seen.add(key)
            transitions.append(row)

    manual_transitions = 0
    for item in load_transition_reviews(args.transition_reviews):
        if item.certification_status != "certified" or item.effective_date > coverage_end:
            continue
        if item.old_ticker not in relevant_tickers:
            continue
        if item.new_ticker and item.new_ticker not in relevant_tickers:
            raise ValueError(
                f"Certified transition successor {item.new_ticker} is absent from the market-data scope."
            )
        key = (item.effective_date, item.old_ticker, item.new_ticker)
        if key in seen:
            continue
        seen.add(key)
        transitions.append(
            {
                "effective_date": item.effective_date,
                "old_ticker": item.old_ticker,
                "new_ticker": item.new_ticker,
                "share_ratio": f"{item.share_ratio:.15g}",
                "cash_per_old_share": f"{item.cash_per_old_share:.15g}",
                "old_isin": item.old_isin,
                "new_isin": item.new_isin,
                "old_quotation_factor": item.old_quotation_factor,
                "new_quotation_factor": item.new_quotation_factor,
                "cutoff_date": item.cutoff_date,
                "first_successor_trade_date": item.first_successor_trade_date,
                "event_type": item.event_type,
                "fractional_treatment": item.fractional_treatment,
                "tax_basis_treatment": item.tax_basis_treatment,
                "source_authority": item.source_authority,
                "source_url": item.source_url,
                "source_reference": item.source_reference,
                "certification_status": item.certification_status,
                "evidence": "source_reviewed_instrument_transition",
                "isin": item.old_isin,
                "last_old_quote": item.cutoff_date,
                "first_new_quote": item.first_successor_trade_date,
            }
        )
        manual_transitions += 1

    transitions.sort(
        key=lambda row: (
            str(row["effective_date"]),
            str(row["old_ticker"]),
            str(row["new_ticker"]),
        )
    )
    _write(
        args.output,
        transitions,
        [
            "effective_date",
            "old_ticker",
            "new_ticker",
            "share_ratio",
            "cash_per_old_share",
            "old_isin",
            "new_isin",
            "old_quotation_factor",
            "new_quotation_factor",
            "cutoff_date",
            "first_successor_trade_date",
            "event_type",
            "fractional_treatment",
            "tax_basis_treatment",
            "source_authority",
            "source_url",
            "source_reference",
            "certification_status",
            "evidence",
            "isin",
            "last_old_quote",
            "first_new_quote",
        ],
    )

    relevant_quotes = [quote for quote in quotes if quote.ticker.upper() in relevant_tickers]
    if not relevant_quotes:
        raise ValueError("No COTAHIST rows found for relevant market-data tickers.")
    transitioned_old = {str(row["old_ticker"]) for row in transitions}
    blocking_gaps: list[dict[str, object]] = []
    recent_stale = 0
    old_unresolved = 0
    for ticker in sorted(relevant_tickers):
        items = by_ticker.get(ticker, [])
        if not items:
            old_unresolved += 1
            blocking_gaps.append(
                {
                    "ticker": ticker,
                    "last_quote_date": "",
                    "isin": "",
                    "issuer_name": "",
                    "category": "unresolved_disappearance",
                    "reason": "relevant ticker has no COTAHIST rows in requested replay window",
                }
            )
            continue
        ordered = sorted(items, key=lambda item: item.date)
        last = ordered[-1]
        category = _stale_category(
            last.date,
            coverage_end,
            transitioned=ticker in transitioned_old,
        )
        if not category:
            continue
        if category == "recent_stale_symbol":
            recent_stale += 1
            reason = (
                "relevant symbol has no quote through the replay horizon and the gap is "
                "recent; temporary suspension/illiquidity is possible, but no source-backed "
                "status or same-ISIN successor proves that the position remains correctly "
                "valued/executable"
            )
        else:
            old_unresolved += 1
            reason = (
                "relevant symbol disappeared before the replay horizon without an "
                "auto-approved same-ISIN successor known by that horizon; merger, "
                "cancellation, cash-out or other primary-source event must be supplied "
                "before a held position can be valued through this date"
            )
        blocking_gaps.append(
            {
                "ticker": ticker,
                "last_quote_date": last.date,
                "isin": last.isin,
                "issuer_name": last.issuer_name,
                "category": category,
                "reason": reason,
            }
        )
    _write(
        args.unresolved_output,
        blocking_gaps,
        ["ticker", "last_quote_date", "isin", "issuer_name", "category", "reason"],
    )

    manifest = {
        "schema_version": 6,
        "method": "same_isin_continuity_plus_source_reviewed_instrument_transitions",
        "instrument_transition_review_file": str(args.transition_reviews),
        "instrument_transition_review_sha256": sha256_file(args.transition_reviews) if args.transition_reviews.exists() else "",
        "source_reviewed_transitions": manual_transitions,
        "scope": "point_in_time_market_data_tickers",
        "universe_manifest": str(args.universe_manifest),
        "source_years": years,
        "requested_end": args.end,
        "coverage_end": coverage_end,
        "transition_file": str(args.output),
        "transition_csv_sha256": sha256_file(args.output),
        "transition_row_count": len(transitions),
        "excluded_tickers": sorted(EXCLUDED_TICKERS),
        "scoped_ticker_count": len(relevant_tickers),
        "market_data_tickers": sorted(relevant_tickers),
        "auto_approved_transitions": len(transitions),
        "recent_stale_symbols": recent_stale,
        "older_unresolved_disappearances": old_unresolved,
        "unresolved_disappearances": len(blocking_gaps),
        "complete": len(blocking_gaps) == 0,
        "policy": (
            "Same-ISIN ticker changes are treated as 1:1 renames. Completeness is assessed "
            "only with information dated at or before coverage_end. Only symbols needed by "
            "the point-in-time account are used to determine completeness. Explicitly "
            "excluded tickers are never eligible for transition or valuation. Any relevant "
            "symbol whose quote history ends before coverage_end without a same-ISIN successor "
            "is a blocker; a <=45-day gap is labeled recent_stale_symbol rather than silently "
            "treated as resolved. The CSV bytes and row count are bound into this manifest."
        ),
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Transition coverage end: {coverage_end}")
    print(f"Scoped market-data tickers: {len(relevant_tickers)}")
    print(f"Explicitly excluded tickers: {', '.join(sorted(EXCLUDED_TICKERS))}")
    print(f"Transition rows: {len(transitions)} (source-reviewed={manual_transitions})")
    print(f"Transition CSV SHA256: {manifest['transition_csv_sha256']}")
    print(f"Recent unexplained stale symbols: {recent_stale}")
    print(f"Older unresolved disappearances: {old_unresolved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
