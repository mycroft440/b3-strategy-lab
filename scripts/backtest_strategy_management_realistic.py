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
    write_dataclass_csv,
)
from b3_strategy_lab.corporate_settlements import load_corporate_settlements  # noqa: E402
from b3_strategy_lab.realistic_certification import (  # noqa: E402
    bonus_tax_basis_dependencies,
    terminal_month_tax_policy,
    transition_binding_issues,
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
DEFAULT_CASH_CERTIFICATION = Path(
    "data/corporate_actions/cash_distribution_coverage_certification.json"
)
DEFAULT_DATA = Path("data/candles_point_in_time")
DEFAULT_ACTIONS = Path("data/actions_point_in_time")
DEFAULT_MANIFESTS = Path("data/manifests_point_in_time")
DEFAULT_SPLIT_EVIDENCE = Path("data/corporate_actions/point_in_time_split_evidence.json")
DEFAULT_FEES = Path("data/fees/b3_equity_fee_schedule.json")
DEFAULT_OUTPUT = Path("reports/realistic_account_summary.json")
DEFAULT_CURVE = Path("reports/realistic_account_curve.csv")
DEFAULT_TRADES = Path("reports/realistic_account_trades.csv")
DEFAULT_CASH_LEDGER = Path("reports/realistic_account_distributions.csv")
DEFAULT_TAX = Path("reports/realistic_account_tax.csv")
DEFAULT_TRANSITIONS = Path("data/corporate_actions/ticker_transitions.csv")
DEFAULT_TRANSITION_MANIFEST = Path("data/corporate_actions/ticker_transitions.manifest.json")

_load_transitions = load_transitions


def _config_by_name(name: str, signal_mode: str = "adjusted") -> PortfolioConfig:
    matches = [config for config in _configs(signal_mode, "all") if config.name == name]
    if len(matches) != 1:
        raise ValueError(f"Management config not found or ambiguous: {name}")
    return matches[0]


def _report_progress(completed: int, total: int, current_date: str) -> None:
    print(f"BACKTEST_PROGRESS {completed} {total} {current_date}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Realistic B3 price-only replay: historical snapshots, official "
            "standard/fractional openings, monthly Brazilian trading-tax accounting, "
            "liquidity-aware slippage and no stale-price fallback. Dividends/JCP are "
            "explicitly outside this replay scope."
        )
    )
    parser.add_argument("--universe-manifest", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--snapshots", type=Path, default=DEFAULT_SNAPSHOTS)
    parser.add_argument("--execution-prices", type=Path, default=DEFAULT_EXECUTION)
    # Retained only for CLI compatibility with older callers. These inputs are not
    # read, certified, credited or used in signal generation in price-only mode.
    parser.add_argument("--cash-events", type=Path, default=DEFAULT_CASH_EVENTS)
    parser.add_argument("--cash-manifest", type=Path, default=DEFAULT_CASH_MANIFEST)
    parser.add_argument(
        "--cash-certification",
        type=Path,
        default=DEFAULT_CASH_CERTIFICATION,
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--actions-dir", type=Path, default=DEFAULT_ACTIONS)
    parser.add_argument("--manifests-dir", type=Path, default=DEFAULT_MANIFESTS)
    parser.add_argument("--split-evidence", type=Path, default=DEFAULT_SPLIT_EVIDENCE)
    parser.add_argument("--fee-schedule", type=Path, default=DEFAULT_FEES)
    parser.add_argument("--ticker-transitions", type=Path, default=DEFAULT_TRANSITIONS)
    parser.add_argument(
        "--ticker-transition-manifest",
        type=Path,
        default=DEFAULT_TRANSITION_MANIFEST,
    )
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
    parser.add_argument("--max-causal-adv-participation", type=float, default=0.01)
    parser.add_argument("--require-certified-inputs", action="store_true")
    parser.add_argument("--orders-output", type=Path)
    parser.add_argument("--corporate-settlements", type=Path)
    # Retained as a compatibility flag, but deliberately ignored in price-only mode.
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
    universe = PointInTimeUniverse.from_csv(args.snapshots)
    selectable = {str(item).upper() for item in manifest["tickers"]}
    if universe.union != selectable:
        parser.error("Snapshot union differs from selectable universe manifest.")
    market_data_tickers = sorted(
        {
            str(item).strip().upper()
            for item in manifest.get("market_data_tickers", manifest["tickers"])
            if str(item).strip()
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
        data_dir=args.data_dir,
        actions_dir=args.actions_dir,
        manifests_dir=args.manifests_dir,
        split_evidence_path=args.split_evidence,
    )
    requested_end = args.end or max(data.dates)
    eligible_end_dates = [value for value in data.dates if value <= requested_end]
    if not eligible_end_dates:
        parser.error("No market session exists at or before --end.")
    end = max(eligible_end_dates)

    transition_issues = transition_binding_issues(
        args.ticker_transitions,
        args.ticker_transition_manifest,
        expected_end=end,
    )
    if args.require_certified_inputs and transition_issues:
        parser.error("Maximum fidelity requires bound ticker transitions.")

    # Explicit user scope: dividends and JCP do not participate in this experiment.
    # An empty event set makes both cash accounting and gap-sensitive signal generation
    # price-only while keeping trading taxes, fees, splits and transitions active.
    cash_events: list = []
    cash_events_complete = True
    summary, curve, account = run_realistic(
        data=data,
        universe=universe,
        pricebook=ExecutionPriceBook.from_csv(args.execution_prices),
        cash_events=cash_events,
        fee_schedule=FeeSchedule.from_json(args.fee_schedule),
        strategy=args.strategy.strip().lower(),
        config=_config_by_name(args.management, "adjusted"),
        start=args.start,
        end=end,
        initial_cash=args.initial_cash,
        base_slippage_bps=args.base_slippage_bps,
        participation_bps_at_1pct=args.participation_bps_at_1pct,
        max_slippage_bps=args.max_slippage_bps,
        max_causal_adv_participation=args.max_causal_adv_participation,
        corporate_settlement_rules=(load_corporate_settlements(args.corporate_settlements)
                                    if args.corporate_settlements else None),
        transitions=load_transitions(args.ticker_transitions),
        economic_gap_adjustment=False,
        selection_status=args.selection_status,
        survivorship_safe=bool(manifest.get("survivorship_safe")),
        cash_events_complete=cash_events_complete,
        progress_callback=_report_progress,
    )

    payload = asdict(summary)
    # Dividend/JCP completeness is not a certification claim in price-only mode.
    payload["cash_events_complete"] = None
    payload["ticker_transition_binding_verified"] = not transition_issues
    payload["ticker_transition_binding_issues"] = transition_issues
    if transition_issues and "__UNBOUND_TICKER_TRANSITIONS" not in str(payload["validity"]):
        payload["validity"] = str(payload["validity"]) + "__UNBOUND_TICKER_TRANSITIONS"

    bonus_dependencies = bonus_tax_basis_dependencies(
        args.split_evidence,
        account.trade_ledger,
        start=args.start,
        end=end,
        transition_csv_path=args.ticker_transitions,
    )
    payload["bonus_tax_basis_affects_realized_gain"] = bool(bonus_dependencies)
    if args.require_certified_inputs and bonus_dependencies:
        parser.error("Maximum fidelity cannot publish realized gains with unsupported stock-bonus tax basis.")
    payload["bonus_tax_basis_dependencies"] = bonus_dependencies[:100]
    payload["bonus_tax_basis_policy"] = (
        "Receita Federal distinguishes stock bonuses from ordinary splits for acquisition "
        "cost. The current engine does not yet apply issuer-specific bonus cost to weighted "
        "average tax basis. Certification is therefore blocked only when the simulated "
        "account actually held the affected position across the bonus date and later sells "
        "those shares, following source-backed 1:1 ticker renames. A bonus before the replay "
        "or before the first simulated purchase does not taint later-acquired shares."
    )
    payload["execution_model"] = {
        "order_sizing": "previous_close_frozen_quantities",
        "unfilled_order_policy": "partial_fill_then_cancel_remainder",
        "max_causal_adv_participation": args.max_causal_adv_participation,
        "execution_prices": str(args.execution_prices),
        "fee_schedule": str(args.fee_schedule),
        "base_slippage_bps": float(args.base_slippage_bps),
        "participation_bps_at_1pct": float(args.participation_bps_at_1pct),
        "max_slippage_bps": float(args.max_slippage_bps),
    }
    if bonus_dependencies and "__BONUS_TAX_BASIS_UNCERTIFIED" not in str(payload["validity"]):
        payload["validity"] = str(payload["validity"]) + "__BONUS_TAX_BASIS_UNCERTIFIED"

    payload.update(terminal_month_tax_policy(end))

    outstanding_tax = float(
        getattr(account, "outstanding_tax_liability", lambda: 0.0)()
    )
    if outstanding_tax < -1e-9:
        raise RuntimeError("Outstanding tax liability cannot be negative.")

    net_after_accrued_tax = float(payload["final_equity"])
    if net_after_accrued_tax <= 0:
        raise RuntimeError("Net final equity must be positive.")
    brokerage_equity = net_after_accrued_tax + max(0.0, outstanding_tax)

    payload["brokerage_final_equity"] = brokerage_equity
    payload["outstanding_accrued_tax_liability"] = outstanding_tax
    payload["net_equity_after_accrued_tax"] = net_after_accrued_tax
    payload["unpaid_distribution_receivable"] = 0.0
    payload["cash_distributions_scope"] = "OUT_OF_SCOPE_BY_USER"
    payload["cash_distributions_used"] = False
    payload["cash_distributions_certification_required"] = False
    payload["cash_manifest_scope_matches_market_data"] = None
    payload["market_data_directory"] = str(args.data_dir)
    payload["action_directory"] = str(args.actions_dir)
    payload["market_data_manifest_directory"] = str(args.manifests_dir)
    payload["split_evidence_file"] = str(args.split_evidence)
    payload["distribution_cash_availability_policy"] = "OUT_OF_SCOPE_BY_USER"
    payload["ordinary_irrf_withheld"] = float(
        getattr(account, "ordinary_irrf_withheld", 0.0)
    )
    payload["darf_paid"] = float(getattr(account, "darf_paid", 0.0))
    payload["tax_cash_timing_policy"] = (
        "ordinary stock tax is accrued monthly into non-investable economic escrow; "
        "DARF is recorded as paid on the final B3 session of the following month; "
        "amounts below R$10 accumulate until the payment threshold is reached"
    )
    payload["cpf_wide_annual_minimum_tax_scope"] = "OUT_OF_SCOPE"
    payload["cpf_wide_annual_minimum_tax_note"] = (
        "For calendar year 2026 onward, Brazil's annual minimum tax for high-income "
        "individuals depends on the person's total CPF-wide annual income and taxes. "
        "This isolated brokerage replay cannot infer salary, rent, other dividends, "
        "other portfolios or other income, so that annual personal adjustment is not "
        "modeled or claimed as exact."
    )

    payload["universe_survivorship_safe"] = bool(manifest.get("survivorship_safe"))
    if payload["survivorship_safe"] != payload["universe_survivorship_safe"]:
        raise RuntimeError("Realistic summary survivorship flag diverges from universe manifest.")
    payload["universe_selection_mode"] = manifest.get("selection_mode")
    payload["tax_instrument_scope"] = manifest.get("tax_instrument_scope", "")
    payload["no_replacements"] = bool(manifest.get("no_replacements"))
    payload["excluded_tickers"] = manifest.get("excluded_tickers", [])
    payload["excluded_instrument_classes"] = manifest.get("excluded_instrument_classes", [])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    orders_path = args.orders_output or args.output.with_suffix(".orders.json")
    orders_path.parent.mkdir(parents=True, exist_ok=True)
    orders = getattr(account, "order_ledger", [])
    orders_path.write_text(json.dumps(orders, indent=2) + "\n", encoding="utf-8")
    payload["order_ledger_file"] = str(orders_path)
    payload["corporate_settlements_file"] = str(args.corporate_settlements) if args.corporate_settlements else None
    payload["corporate_settlement_ledger"] = getattr(account, "corporate_action_ledger", [])
    payload["unpaid_corporate_receivable"] = getattr(account, "_corporate_receivable_value", 0.0)
    payload["partially_filled_orders"] = sum(row["status"] == "PARTIAL" for row in orders)
    payload["cancelled_orders"] = sum(row["status"] == "CANCELLED" for row in orders)
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
