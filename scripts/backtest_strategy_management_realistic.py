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
    cash_coverage_certification_issues,
    load_cash_distributions,
    write_dataclass_csv,
)
from b3_strategy_lab.realistic_certification import (  # noqa: E402
    bonus_tax_basis_dependencies,
    terminal_month_tax_policy,
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
    cash_certification: dict[str, object] = {}
    if args.cash_certification.exists():
        cash_certification = json.loads(
            args.cash_certification.read_text(encoding="utf-8")
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

    cash_manifest_tickers = {
        str(item).strip().upper()
        for item in cash_manifest.get("market_data_tickers", [])
        if str(item).strip()
    }
    market_data_set = set(market_data_tickers)
    cash_manifest_scope_matches = (
        cash_manifest_tickers == market_data_set
        and int(cash_manifest.get("market_data_ticker_count", -1)) == len(cash_manifest_tickers)
    )
    cash_events_complete = (
        cash_manifest_scope_matches
        and bool(cash_certification)
        and not cash_coverage_certification_issues(
            cash_certification,
            cash_events_path=args.cash_events,
            cash_manifest_path=args.cash_manifest,
            tickers=market_data_tickers,
            start=args.start,
            end=end,
        )
    )

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
        survivorship_safe=bool(manifest.get("survivorship_safe")),
        cash_events_complete=cash_events_complete,
        progress_callback=_report_progress,
    )

    payload = asdict(summary)
    bonus_dependencies = bonus_tax_basis_dependencies(
        args.split_evidence,
        account.trade_ledger,
        start=args.start,
        end=end,
    )
    payload["bonus_tax_basis_affects_realized_gain"] = bool(bonus_dependencies)
    payload["bonus_tax_basis_dependencies"] = bonus_dependencies[:100]
    payload["bonus_tax_basis_policy"] = (
        "Receita Federal distinguishes stock bonuses from ordinary splits for acquisition "
        "cost. Until an event supplies source-backed tax_basis_per_new_share, any sale on/"
        "after that ticker's bonus date is treated as tax-basis-uncertain and cannot support "
        "a certified deterministic replay."
    )
    if bonus_dependencies and "__BONUS_TAX_BASIS_UNCERTIFIED" not in str(payload["validity"]):
        payload["validity"] = str(payload["validity"]) + "__BONUS_TAX_BASIS_UNCERTIFIED"

    payload.update(terminal_month_tax_policy(end))

    outstanding_tax = float(
        getattr(account, "outstanding_tax_liability", lambda: 0.0)()
    )
    if outstanding_tax < -1e-9:
        raise RuntimeError("Outstanding tax liability cannot be negative.")
    receivable = float(
        getattr(account, "distribution_receivable_value", lambda: 0.0)()
    )
    if receivable < -1e-9:
        raise RuntimeError("Distribution receivable cannot be negative.")

    # ``final_equity`` is economic equity: accrued ordinary tax is already removed
    # from investable cash and an earned unpaid distribution is already included as
    # a non-spendable receivable. Add tax escrow back only to expose the gross broker
    # balance before the unpaid DARF legally leaves the account.
    net_after_accrued_tax = float(payload["final_equity"])
    if net_after_accrued_tax <= 0:
        raise RuntimeError("Net final equity must be positive.")
    brokerage_equity = net_after_accrued_tax + max(0.0, outstanding_tax)

    payload["brokerage_final_equity"] = brokerage_equity
    payload["outstanding_accrued_tax_liability"] = outstanding_tax
    payload["net_equity_after_accrued_tax"] = net_after_accrued_tax
    payload["unpaid_distribution_receivable"] = receivable
    payload["cash_certification_ticker_scope"] = "market_data_tickers_including_continuity_history"
    payload["cash_manifest_scope_matches_market_data"] = cash_manifest_scope_matches
    payload["market_data_directory"] = str(args.data_dir)
    payload["action_directory"] = str(args.actions_dir)
    payload["market_data_manifest_directory"] = str(args.manifests_dir)
    payload["split_evidence_file"] = str(args.split_evidence)
    payload["distribution_cash_availability_policy"] = (
        "the right is recognized as economic receivable only after the cum-right close; "
        "it is never spendable before payment; on payment the receivable is replaced by "
        "cash, and a non-trading payment date becomes cash at the next simulated B3 session"
    )
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
