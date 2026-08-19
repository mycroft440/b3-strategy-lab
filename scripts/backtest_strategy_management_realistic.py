from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.realistic import (  # noqa: E402
    ExecutionPriceBook,
    FeeSchedule,
    PointInTimeUniverse,
    load_cash_distributions,
    write_dataclass_csv,
)
from b3_strategy_lab.realistic_portfolio import (  # noqa: E402
    load_transitions,
    run_realistic,
)
from scripts.research_portfolio_allocation import MarketData, PortfolioConfig, _configs  # noqa: E402


DEFAULT_UNIVERSE = Path("data/universes/point_in_time_union.json")
DEFAULT_SNAPSHOTS = Path("data/universes/point_in_time_weekly.csv")
DEFAULT_EXECUTION = Path("data/execution/b3_standard_fractional_open.csv")
DEFAULT_CASH_EVENTS = Path("data/corporate_actions/point_in_time_cash_distributions.csv")
DEFAULT_CASH_MANIFEST = Path("data/corporate_actions/point_in_time_cash_distributions.manifest.json")
DEFAULT_FEES = Path("data/fees/b3_equity_fee_schedule.json")
DEFAULT_OUTPUT = Path("reports/realistic_account_summary.json")
DEFAULT_CURVE = Path("reports/realistic_account_curve.csv")
DEFAULT_TRADES = Path("reports/realistic_account_trades.csv")
DEFAULT_CASH_LEDGER = Path("reports/realistic_account_distributions.csv")
DEFAULT_TAX = Path("reports/realistic_account_tax.csv")
DEFAULT_TRANSITIONS = Path("data/corporate_actions/ticker_transitions.csv")

# Backward-compatible import used by older callers.
_load_transitions = load_transitions


def _config_by_name(name: str, signal_mode: str = "adjusted") -> PortfolioConfig:
    matches = [config for config in _configs(signal_mode, "all") if config.name == name]
    if len(matches) != 1:
        raise ValueError(f"Management config not found or ambiguous: {name}")
    return matches[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Real-money-oriented B3 backtest: historical snapshots, official "
            "standard/fractional openings, cash distributions, monthly Brazilian "
            "tax accounting, liquidity-aware slippage and no stale-price fallback."
        )
    )
    parser.add_argument("--universe-manifest", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--snapshots", type=Path, default=DEFAULT_SNAPSHOTS)
    parser.add_argument("--execution-prices", type=Path, default=DEFAULT_EXECUTION)
    parser.add_argument("--cash-events", type=Path, default=DEFAULT_CASH_EVENTS)
    parser.add_argument("--cash-manifest", type=Path, default=DEFAULT_CASH_MANIFEST)
    parser.add_argument("--fee-schedule", type=Path, default=DEFAULT_FEES)
    parser.add_argument("--ticker-transitions", type=Path, default=DEFAULT_TRANSITIONS)
    parser.add_argument("--strategy", default="gap_momentum")
    parser.add_argument(
        "--management",
        default="top1_momentum_lb63_skip0_trend0_vol21_equal_weekly_abs_cap1_adjusted",
    )
    parser.add_argument("--start", default="2018-01-02")
    parser.add_argument("--end")
    parser.add_argument("--initial-cash", type=float, default=1_000.0)
    parser.add_argument("--base-slippage-bps", type=float, default=10.0)
    parser.add_argument("--participation-bps-at-1pct", type=float, default=5.0)
    parser.add_argument("--max-slippage-bps", type=float, default=100.0)
    parser.add_argument("--economic-gap-adjustment", action="store_true")
    parser.add_argument(
        "--selection-status",
        choices=[
            "retrospective_hypothesis_replay",
            "walk_forward_out_of_sample",
            "prospective_frozen",
        ],
        default="retrospective_hypothesis_replay",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--curve-output", type=Path, default=DEFAULT_CURVE)
    parser.add_argument("--trades-output", type=Path, default=DEFAULT_TRADES)
    parser.add_argument("--cash-ledger-output", type=Path, default=DEFAULT_CASH_LEDGER)
    parser.add_argument("--tax-output", type=Path, default=DEFAULT_TAX)
    args = parser.parse_args(argv)

    manifest = json.loads(args.universe_manifest.read_text(encoding="utf-8"))
    if manifest.get("point_in_time") is not True:
        parser.error("Refusing realistic mode: historical snapshots must be point-in-time.")
    if manifest.get("survivorship_safe") is not True and args.selection_status != "retrospective_hypothesis_replay":
        parser.error(
            "A fixed/survivorship-biased universe is allowed only for a retrospective "
            "hypothesis replay; it cannot be labeled walk-forward or prospective."
        )
    cash_manifest = json.loads(args.cash_manifest.read_text(encoding="utf-8"))
    if cash_manifest.get("complete") is not True:
        parser.error("Refusing realistic mode: B3 cash-distribution response has unresolved parsing issues.")

    universe = PointInTimeUniverse.from_csv(args.snapshots)
    selectable = {str(item).upper() for item in manifest["tickers"]}
    if universe.union != selectable:
        parser.error("Snapshot union differs from selectable universe manifest.")
    market_data_tickers = sorted(
        {
            str(item).upper()
            for item in manifest.get("market_data_tickers", manifest["tickers"])
        }
    )
    if not selectable.issubset(market_data_tickers):
        parser.error("market_data_tickers must contain every selectable ticker.")

    data = MarketData(
        market_data_tickers,
        "1d",
        "adjusted",
        require_verified_splits_from=str(manifest["warmup_start"]),
        history_start=str(manifest["warmup_start"]),
    )
    requested_end = args.end or max(data.dates)
    eligible_end_dates = [value for value in data.dates if value <= requested_end]
    if not eligible_end_dates:
        parser.error("No market session exists at or before --end.")
    end = max(eligible_end_dates)

    summary, curve, account = run_realistic(
        data=data,
        universe=universe,
        pricebook=ExecutionPriceBook.from_csv(args.execution_prices),
        cash_events=load_cash_distributions(args.cash_events),
        fee_schedule=FeeSchedule.from_json(args.fee_schedule),
        strategy=args.strategy.strip().lower(),
        config=_config_by_name(args.management, "adjusted"),
        start=args.start,
        end=end,
        initial_cash=args.initial_cash,
        base_slippage_bps=args.base_slippage_bps,
        participation_bps_at_1pct=args.participation_bps_at_1pct,
        max_slippage_bps=args.max_slippage_bps,
        transitions=load_transitions(args.ticker_transitions),
        economic_gap_adjustment=args.economic_gap_adjustment,
        selection_status=args.selection_status,
    )

    payload = asdict(summary)
    payload["universe_survivorship_safe"] = bool(manifest.get("survivorship_safe"))
    payload["universe_selection_mode"] = manifest.get("selection_mode")
    payload["no_replacements"] = bool(manifest.get("no_replacements"))
    payload["excluded_tickers"] = manifest.get("excluded_tickers", [])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_dataclass_csv(args.curve_output, curve)
    write_dataclass_csv(args.trades_output, account.trade_ledger)
    write_dataclass_csv(args.cash_ledger_output, account.cash_ledger)
    write_dataclass_csv(args.tax_output, account.tax.finalized())

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"Curve: {args.curve_output}")
    print(f"Trades: {args.trades_output}")
    print(f"Tax: {args.tax_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
