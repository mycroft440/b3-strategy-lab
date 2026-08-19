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
DEFAULT_ALLOWED_UNIVERSE = Path("data/universes/fixed_40_2018.json")
EXCLUDED_TICKERS = {"BOAC34"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build weekly realistic inputs using only the pre-existing project stock "
            "universe. No replacement symbols are added when an asset is excluded."
        )
    )
    parser.add_argument("--years", nargs="+", default=[f"2017:{date.today().year}"])
    parser.add_argument("--archives-dir", type=Path, default=Path(".cache/cotahist"))
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--start", default="2018-01-02")
    parser.add_argument("--end")
    parser.add_argument("--lookback-sessions", type=int, default=252)
    parser.add_argument("--top-n", type=int, default=40)
    parser.add_argument("--minimum-presence", type=float, default=0.90)
    parser.add_argument("--allowed-universe", type=Path, default=DEFAULT_ALLOWED_UNIVERSE)
    parser.add_argument("--snapshots-output", type=Path, default=DEFAULT_SNAPSHOTS)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--execution-output", type=Path, default=DEFAULT_EXECUTION)
    args = parser.parse_args(argv)

    if args.lookback_sessions <= 20 or args.top_n <= 0:
        parser.error("lookback-sessions must be >20 and top-n must be positive.")
    if not 0 < args.minimum_presence <= 1:
        parser.error("minimum-presence must be in (0, 1].")

    allowed_payload = json.loads(args.allowed_universe.read_text(encoding="utf-8"))
    allowed_tickers = {
        str(ticker).strip().upper()
        for ticker in allowed_payload.get("tickers", [])
        if str(ticker).strip()
    }
    allowed_tickers.difference_update(EXCLUDED_TICKERS)
    if not allowed_tickers:
        parser.error("The pre-existing allowed universe is empty after exclusions.")
    if args.top_n > len(allowed_tickers):
        args.top_n = len(allowed_tickers)

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
        standard_quotes.extend(
            quote
            for quote in read_standard_company_equity_cotahist(archive)
            if quote.ticker.upper() in allowed_tickers
        )
        fractional_quotes.extend(
            quote
            for quote in read_fractional_cotahist(archive)
            if base_fractional_ticker(quote.ticker) in allowed_tickers
        )

    if not standard_quotes:
        raise ValueError("No standard-lot quotes remain for the pre-existing stock universe.")

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
    unexpected = selected_set - allowed_tickers
    if unexpected:
        raise ValueError(f"Unexpected symbols escaped fixed-universe filter: {sorted(unexpected)}")

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
        and quote.ticker.upper() in allowed_tickers
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
        "schema_version": 3,
        "id": "existing_project_stock_universe_no_replacements",
        "selection_mode": "fixed_existing_project_universe_weekly_trailing_information",
        "selected_as_of": args.start,
        "warmup_start": f"{min(years):04d}-01-01",
        "survivorship_safe": False,
        "point_in_time": True,
        "snapshot_file": str(args.snapshots_output),
        "allowed_universe_file": str(args.allowed_universe),
        "excluded_tickers": sorted(EXCLUDED_TICKERS),
        "no_replacements": True,
        "selection_rules": {
            "source": "B3_COTAHIST_full_market",
            "instrument_filter": "existing_project_tickers_only; BDI02 market010 ON/PN/UNT; no BDRs",
            "lookback_sessions": args.lookback_sessions,
            "minimum_presence": args.minimum_presence,
            "top_n": args.top_n,
            "issuer_deduplication": True,
            "decision_frequency": "weekly",
            "future_continuity_filter": False,
            "replacement_policy": "none"
        },
        "execution_sources": {
            "standard": {"market_type": "010", "bdi_code": "02"},
            "fractional": {"market_type": "020", "bdi_code": "96"}
        },
        "tickers": selected_union,
        "market_data_tickers": market_data_tickers,
        "continuity_only_tickers": sorted(market_data_set - selected_set),
        "continuity_rule": "same_isin_only_within_existing_allowed_universe",
        "issuing_company_by_ticker": issuer_by_ticker,
        "issuer_name_by_ticker": issuer_names,
        "isins_by_ticker": {ticker: sorted(values) for ticker, values in isin_by_ticker.items()},
        "bias_disclosure": (
            "The candidate universe is intentionally frozen to the project's pre-existing "
            "fixed_40_2018 list at the user's request. No outside symbol is added as a "
            "replacement. This preserves the historical selection/survivorship bias of "
            "that list, so results are a retrospective replay of the chosen universe, not "
            "a survivorship-safe claim that these names could have been selected ex ante."
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
    print(f"Allowed pre-existing symbols: {len(allowed_tickers)}")
    print(f"Explicit exclusions: {', '.join(sorted(EXCLUDED_TICKERS))}")
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
