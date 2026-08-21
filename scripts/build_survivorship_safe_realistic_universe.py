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
    base_fractional_ticker,
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
            "Build a survivorship-safe weekly B3 ON/PN share universe from the full "
            "historical eligible-share market using only information available by each "
            "decision date."
        )
    )
    parser.add_argument(
        "--years",
        nargs="+",
        help=(
            "Explicit COTAHIST years/ranges. When omitted, infer one warm-up year before "
            "--start through the year of --end (or the current year)."
        ),
    )
    parser.add_argument("--archives-dir", type=Path, default=Path(".cache/cotahist"))
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--start", default="2018-01-02")
    parser.add_argument("--end")
    parser.add_argument("--lookback-sessions", type=int, default=252)
    parser.add_argument("--top-n", type=int, default=40)
    parser.add_argument("--minimum-presence", type=float, default=0.90)
    parser.add_argument("--snapshots-output", type=Path, default=DEFAULT_SNAPSHOTS)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--execution-output", type=Path, default=DEFAULT_EXECUTION)
    args = parser.parse_args(argv)

    if args.lookback_sessions <= 20 or args.top_n <= 0:
        parser.error("lookback-sessions must be >20 and top-n must be positive.")
    if not 0 < args.minimum_presence <= 1:
        parser.error("minimum-presence must be in (0, 1].")

    start_year = int(args.start[:4])
    end_year = int(args.end[:4]) if args.end else date.today().year
    if end_year < start_year:
        parser.error("--end cannot precede --start")
    requested_years = args.years or [f"{start_year - 1}:{end_year}"]
    years = parse_years(requested_years)
    if min(years) >= start_year:
        parser.error("At least one pre-start year is required for causal warm-up.")
    if max(years) < end_year:
        parser.error("COTAHIST years do not cover the requested --end year.")

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
                f"{path} is missing; use --download or provide the official COTAHIST archive."
            )
        archives.append(path)

    standard_quotes = []
    fractional_quotes = []
    for archive in archives:
        standard_quotes.extend(read_standard_company_equity_cotahist(archive))
        fractional_quotes.extend(read_fractional_cotahist(archive))

    standard_quotes = [quote for quote in standard_quotes if is_company_equity(quote)]
    if not standard_quotes:
        raise ValueError("No B3 ON/PN company-share quotes were found.")
    requested_end = args.end or max(quote.date for quote in standard_quotes)
    eligible_end_dates = [quote.date for quote in standard_quotes if quote.date <= requested_end]
    if not eligible_end_dates:
        parser.error("No B3 ON/PN market session exists at or before --end.")
    end = max(eligible_end_dates)

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

    selected_union = sorted({str(row["ticker"]).upper() for row in snapshots})
    selected_set = set(selected_union)

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
            isin_by_ticker[ticker].add(quote.isin.strip().upper())

    missing_issuer = sorted(market_data_set - set(issuer_by_ticker))
    if missing_issuer:
        raise ValueError(f"Missing issuer metadata for historical tickers: {missing_issuer}")

    snapshot_sizes: dict[str, int] = defaultdict(int)
    for row in snapshots:
        snapshot_sizes[str(row["effective_date"])] += 1
    if min(snapshot_sizes.values()) != args.top_n:
        raise ValueError("Survivorship-safe universe unexpectedly contains incomplete snapshots.")

    manifest = {
        "schema_version": 7,
        "id": "full_b3_on_pn_survivorship_safe_weekly_top_liquidity",
        "selection_mode": "full_b3_on_pn_trailing_liquidity_point_in_time",
        "selected_as_of": args.start,
        "selection_end": end,
        "requested_end": args.end,
        "warmup_start": f"{min(years):04d}-01-01",
        "source_years": years,
        "survivorship_safe": True,
        "point_in_time": True,
        "snapshot_file": str(args.snapshots_output),
        "allowed_universe_file": "",
        "excluded_tickers": [],
        "excluded_instrument_classes": ["UNT", "BDR", "ETF", "funds", "rights", "receipts"],
        "tax_instrument_scope": "ON_PN_SHARES_ONLY",
        "no_replacements": False,
        "selection_rules": {
            "source": "B3_COTAHIST_full_historical_ON_PN_share_market",
            "instrument_filter": (
                "company shares only; BDI02 market010 ON/PN classes. UNITS are excluded "
                "from the certified R$20k tax scope because B3 classifies them as "
                "deposit certificates and no Receita source is assumed to extend the "
                "share-only exemption automatically"
            ),
            "lookback_sessions": args.lookback_sessions,
            "minimum_presence": args.minimum_presence,
            "weekly_candidates": args.top_n,
            "issuer_deduplication": True,
            "decision_frequency": "weekly",
            "ranking_metric": "trailing_average_financial_volume",
            "future_continuity_filter": False,
            "future_return_filter": False,
            "replacement_policy": "full historical eligible-share market re-ranked from trailing data only",
        },
        "execution_sources": {
            "standard": {"market_type": "010", "bdi_code": "02"},
            "fractional": {"market_type": "020", "bdi_code": "96"},
        },
        "tickers": selected_union,
        "market_data_tickers": market_data_tickers,
        "continuity_only_tickers": sorted(market_data_set - selected_set),
        "continuity_rule": "same_isin_ON_PN_history_only; never grants selection eligibility",
        "issuing_company_by_ticker": issuer_by_ticker,
        "issuer_name_by_ticker": issuer_names,
        "isins_by_ticker": {ticker: sorted(values) for ticker, values in isin_by_ticker.items()},
        "bias_disclosure": (
            "Each weekly candidate set is reconstructed from the full historical B3 "
            "ON/PN company-share COTAHIST scope using only trailing observations available "
            "by that decision date. No requirement uses future survival, future returns, "
            "current index membership, or the project's later fixed-40 list. Strategy/model "
            "selection can still be retrospective and is reported separately from universe "
            "validity. UNITS and other instrument classes are intentionally out of this "
            "certified share-tax scope."
        ),
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_output.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    standard_filtered = [
        quote for quote in standard_quotes if quote.ticker.upper() in market_data_set
    ]
    fractional_filtered = [
        quote
        for quote in fractional_quotes
        if base_fractional_ticker(quote.ticker) in market_data_set
    ]
    executions = execution_rows(
        standard_filtered,
        fractional_filtered,
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
    if standard_count == 0 or fractional_count == 0:
        raise ValueError("Both standard and fractional execution books are required.")

    print(f"COTAHIST years: {years[0]}..{years[-1]}")
    if args.end and end != args.end:
        print(f"Requested end {args.end} normalized to last B3 session {end}")
    print(f"Survivorship-safe weekly ON/PN snapshots: {len(snapshot_sizes)}")
    print(f"Selectable historical ON/PN union: {len(selected_union)} tickers")
    print(f"Continuity-only symbols: {len(market_data_set - selected_set)}")
    print(f"Execution rows: standard={standard_count}, fractional={fractional_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
