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
            "Detect deterministic ticker renames from full historical COTAHIST. "
            "Only same-ISIN continuity is auto-approved. Other disappearances are "
            "reported and remain fail-closed in the realistic engine."
        )
    )
    parser.add_argument("--years", nargs="+", default=[f"2017:{date.today().year}"])
    parser.add_argument("--archives-dir", type=Path, default=Path(".cache/cotahist"))
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--unresolved-output", type=Path, default=DEFAULT_UNRESOLVED)
    args = parser.parse_args(argv)

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
        by_ticker[ticker].append(quote)

    transitions: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for isin, items in by_isin.items():
        ordered = sorted(items, key=lambda item: item.date)
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

    last_market_date = max(quote.date for quote in quotes)
    cutoff = date.fromisoformat(last_market_date) - timedelta(days=45)
    transitioned_old = {str(row["old_ticker"]) for row in transitions}
    unresolved: list[dict[str, object]] = []
    for ticker, items in sorted(by_ticker.items()):
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
                    "symbol disappeared before the end of the archive without an "
                    "auto-approved same-ISIN successor; merger, cancellation, cash-out "
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
        "schema_version": 1,
        "method": "same_isin_continuity_only",
        "auto_approved_transitions": len(transitions),
        "unresolved_disappearances": len(unresolved),
        "complete": len(unresolved) == 0,
        "policy": (
            "Same-ISIN ticker changes are treated as 1:1 renames. Any historical "
            "symbol disappearance without same-ISIN continuity remains unresolved; "
            "the realistic backtest must fail if such a symbol is held instead of "
            "assuming a sale price or forward-filling its last quote."
        ),
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Auto-approved ticker transitions: {len(transitions)}")
    print(f"Unresolved historical disappearances: {len(unresolved)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
