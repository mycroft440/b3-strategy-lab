from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.cotahist import download_cotahist  # noqa: E402
from b3_strategy_lab.point_in_time import (  # noqa: E402
    execution_rows,
    is_company_equity,
    parse_years,
    read_fractional_cotahist,
    read_standard_company_equity_cotahist,
    snapshot_rows,
    write_csv,
)


DEFAULT_SNAPSHOTS = Path("data/universes/point_in_time_weekly.csv")
DEFAULT_MANIFEST = Path("data/universes/point_in_time_union.json")
DEFAULT_EXECUTION = Path("data/execution/b3_standard_fractional_open.csv")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a survivorship-safe weekly stock universe from full B3 COTAHIST "
            "using only trailing information, plus standard and fractional opening books."
        )
    )
    parser.add_argument("--years", nargs="+", default=[f"2017:{date.today().year}"])
    parser.add_argument("--archives-dir", type=Path, default=Path(".cache/cotahist"))
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--start", default="2018-01-02")
    parser.add_argument("--end")
    parser.add_argument("--lookback-sessions", type=int, default=252)
    parser.add_argument("--top-n", type=int, default=39)
    parser.add_argument("--minimum-presence", type=float, default=0.90)
    parser.add_argument("--snapshots-output", type=Path, default=DEFAULT_SNAPSHOTS)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--execution-output", type=Path, default=DEFAULT_EXECUTION)
    args = parser.parse_args(argv)

    if args.lookback_sessions <= 20 or args.top_n <= 0:
        parser.error("lookback-sessions must be >20 and top-n must be positive.")
    if not 0 < args.minimum_presence <= 1:
        parser.error("minimum-presence must be in (0, 1].")

    years = parse_years(args.years)
    archives: list[Path] = []
    for year in years:
        path = args.archives_dir / f"COTAHIST_A{year}.ZIP"
        if args.download:
            path = download_cotahist(
                year,
                args.archives_dir,
                refresh=year == date.today().year,
            )
        if not path.exists():
            raise FileNotFoundError(
                f"{path} is missing; use --download or provide the full COTAHIST archive."
            )
        archives.append(path)

    standard_quotes = []
    fractional_quotes = []
    for archive in archives:
        standard_quotes.extend(read_standard_company_equity_cotahist(archive))
        fractional_quotes.extend(read_fractional_cotahist(archive))

    end = args.end or max(quote.date for quote in standard_quotes)
    snapshots = snapshot_rows(
        standard_quotes,
        start=args.start,
        end=end,
        lookback_sessions=args.lookback_sessions,
        top_n=args.top_n,
        minimum_presence=args.minimum_presence,
    )
    write_csv(
        args.snapshots_output,
        snapshots,
        [
            "effective_date",
            "ticker",
            "rank",
            "presence",
            "avg_financial_volume",
            "issuer_name",
            "issuer_code",
            "lookback_sessions",
        ],
    )

    selected_union = sorted({str(row["ticker"]) for row in snapshots})
    selected_set = set(selected_union)

    # A selected symbol may later change ticker while preserving the same ISIN.
    # Those related symbols are required market data for continuity of an already
    # held position, but they are NOT added to point-in-time candidate snapshots.
    selected_isins = {
        quote.isin.strip().upper()
        for quote in standard_quotes
        if quote.ticker.upper() in selected_set and quote.isin
    }
    continuity_set = {
        quote.ticker.upper()
        for quote in standard_quotes
        if quote.isin
        and quote.isin.strip().upper() in selected_isins
        and is_company_equity(quote)
    }
    market_data_set = selected_set | continuity_set
    market_data_tickers = sorted(market_data_set)

    issuer_by_ticker: dict[str, str] = {}
    issuer_names: dict[str, str] = {}
    isin_by_ticker: dict[str, set[str]] = defaultdict(set)
    for quote in standard_quotes:
        ticker = quote.ticker.upper()
        if ticker not in market_data_set:
            continue
        issuer_by_ticker[ticker] = ticker[:4]
        issuer_names[ticker] = quote.issuer_name.strip().upper()
        if quote.isin:
            isin_by_ticker[ticker].add(quote.isin)

    manifest = {
        "schema_version": 2,
        "id": "point_in_time_trailing_liquidity_weekly",
        "selection_mode": "weekly_trailing_liquidity_only_past_information",
        "selected_as_of": args.start,
        "warmup_start": f"{min(years):04d}-01-01",
        "survivorship_safe": True,
        "point_in_time": True,
        "snapshot_file": str(args.snapshots_output),
        "selection_rules": {
            "source": "B3_COTAHIST_full_market",
            "instrument_filter": "BDI02_market010_and_specification_ON_PN_UNT",
            "lookback_sessions": args.lookback_sessions,
            "minimum_presence": args.minimum_presence,
            "top_n": args.top_n,
            "issuer_deduplication": True,
            "decision_frequency": "weekly",
            "future_continuity_filter": False
        },
        "execution_sources": {
            "standard": {"market_type": "010", "bdi_code": "02"},
            "fractional": {"market_type": "020", "bdi_code": "96"}
        },
        "tickers": selected_union,
        "market_data_tickers": market_data_tickers,
        "continuity_only_tickers": sorted(market_data_set - selected_set),
        "continuity_rule": "same_isin_as_any_point_in_time_selected_symbol",
        "issuing_company_by_ticker": issuer_by_ticker,
        "issuer_name_by_ticker": issuer_names,
        "isins_by_ticker": {ticker: sorted(values) for ticker, values in isin_by_ticker.items()},
        "bias_disclosure": (
            "Each snapshot is selected only from COTAHIST observations at or before "
            "its effective_date. Historical symbols are not removed because they later "
            "delist or cease satisfying liquidity rules. Same-ISIN related tickers may "
            "be loaded only for continuity of held positions; they are not investable "
            "unless they independently appear in a point-in-time snapshot."
        ),
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_output.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    executions = execution_rows(
        standard_quotes,
        fractional_quotes,
        union=market_data_set,
        start=args.start,
        end=end,
    )
    write_csv(
        args.execution_output,
        executions,
        ["date", "ticker", "market_type", "open", "close", "financial_volume"],
    )

    standard_count = sum(row["market_type"] == "010" for row in executions)
    fractional_count = sum(row["market_type"] == "020" for row in executions)
    if fractional_count == 0:
        raise ValueError(
            "Fractional execution book is empty. COTAHIST market 020/BDI 96 coverage "
            "is required for an R$1,000 realistic account."
        )
    print(f"Snapshots: {args.snapshots_output} ({len(snapshots)} rows)")
    print(
        f"Universe: {args.manifest_output} ({len(selected_union)} selectable + "
        f"{len(market_data_set - selected_set)} continuity-only symbols)"
    )
    print(
        f"Execution quotes: {args.execution_output} "
        f"({standard_count} standard + {fractional_count} fractional rows)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
