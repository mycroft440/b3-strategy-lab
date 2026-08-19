from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.cotahist import download_cotahist, read_cotahist  # noqa: E402
from scripts.sync_official_universe import _parse_years  # noqa: E402


DEFAULT_UNIVERSE = Path("data/universes/point_in_time_union.json")
DEFAULT_OUTPUT = Path("data/corporate_actions/ticker_transitions.csv")
DEFAULT_MANIFEST = Path("data/corporate_actions/ticker_transitions.manifest.json")
DEFAULT_UNRESOLVED = Path("reports/unresolved_historical_delistings.csv")


def _write(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Detect deterministic ticker renames relevant to the point-in-time "
            "backtest. Same-ISIN continuity is auto-approved; other disappearances "
            "of relevant symbols remain fail-closed."
        )
    )
    parser.add_argument("--universe-manifest", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--years", nargs="+", default=[f"2017:{date.today().year}"])
    parser.add_argument("--archives-dir", type=Path, default=Path(".cache/cotahist"))
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--unresolved-output", type=Path, default=DEFAULT_UNRESOLVED)
    args = parser.parse_args(argv)

    universe = json.loads(args.universe_manifest.read_text(encoding="utf-8"))
    relevant_tickers = {
        str(ticker).upper()
        for ticker in universe.get("market_data_tickers", universe.get("tickers", []))
    }
    if not relevant_tickers:
        parser.error("Point-in-time universe contains no relevant market-data tickers.")

    quotes = []
    for year in _parse_years(args.years):
        archive = args.archives_dir / f"COTAHIST_A{year}.ZIP"
        if args.download:
            archive = download_cotahist(
                year,
                args.archives_dir,
                refresh=year == date.today().year,
            )
        if not archive.exists():
            raise FileNotFoundError(f"{archive} missing; use --download.")
        quotes.extend(read_cotahist(archive))

    by_isin: dict[str, list] = defaultdict(list)
    by_ticker: dict[str, list] = defaultdict(list)
    for quote in quotes:
        ticker = quote.ticker.strip().upper()
        if not ticker or not quote.isin:
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
        ordered = sorted(by_isin[isin], key=lambda item: item.date)
        previous_ticker = ordered[0].ticker.upper()
        previous_date = ordered[0].date
        for item in ordered[1:]:
            ticker = item.ticker.upper()
            if ticker != previous_ticker:
                key = (item.date, previous_ticker, ticker)
                if key not in seen:
                    transitions.append(
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
                    seen.add(key)
            previous_ticker = ticker
            previous_date = item.date

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
            "evidence",
            "isin",
            "last_old_quote",
            "first_new_quote",
        ],
    )

    relevant_quotes = [quote for quote in quotes if quote.ticker.upper() in relevant_tickers]
    if not relevant_quotes:
        raise ValueError("No COTAHIST rows found for relevant market-data tickers.")
    last_market_date = max(quote.date for quote in quotes)
    cutoff = date.fromisoformat(last_market_date) - timedelta(days=45)
    transitioned_old = {str(row["old_ticker"]) for row in transitions}
    unresolved: list[dict[str, object]] = []
    for ticker in sorted(relevant_tickers):
        items = by_ticker.get(ticker, [])
        if not items:
            unresolved.append(
                {
                    "ticker": ticker,
                    "last_quote_date": "",
                    "isin": "",
                    "issuer_name": "",
                    "reason": "relevant ticker has no COTAHIST rows in requested archive window",
                }
            )
            continue
        ordered = sorted(items, key=lambda item: item.date)
        last = ordered[-1]
        if date.fromisoformat(last.date) >= cutoff or ticker in transitioned_old:
            continue
        unresolved.append(
            {
                "ticker": ticker,
                "last_quote_date": last.date,
                "isin": last.isin,
                "issuer_name": last.issuer_name,
                "reason": (
                    "relevant symbol disappeared before the end of the archive without "
                    "an auto-approved same-ISIN successor; merger, cancellation, cash-out "
                    "or other primary-source event must be supplied before a held "
                    "position can be valued through this date"
                ),
            }
        )
    _write(
        args.unresolved_output,
        unresolved,
        ["ticker", "last_quote_date", "isin", "issuer_name", "reason"],
    )

    manifest = {
        "schema_version": 2,
        "method": "same_isin_continuity_only",
        "scope": "point_in_time_market_data_tickers",
        "universe_manifest": str(args.universe_manifest),
        "scoped_ticker_count": len(relevant_tickers),
        "auto_approved_transitions": len(transitions),
        "unresolved_disappearances": len(unresolved),
        "complete": len(unresolved) == 0,
        "policy": (
            "Same-ISIN ticker changes are treated as 1:1 renames. Only symbols needed "
            "by the point-in-time account are used to determine completeness. A relevant "
            "symbol disappearance without same-ISIN continuity remains unresolved; the "
            "backtest must fail if such a symbol is held instead of assuming a sale price "
            "or forward-filling its last quote."
        ),
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Scoped market-data tickers: {len(relevant_tickers)}")
    print(f"Auto-approved ticker transitions: {len(transitions)}")
    print(f"Unresolved relevant disappearances: {len(unresolved)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
