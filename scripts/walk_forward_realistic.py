from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.realistic import (  # noqa: E402
    ExecutionPriceBook,
    FeeSchedule,
    PointInTimeUniverse,
    load_cash_distributions,
)
from b3_strategy_lab.realistic_certification import transition_binding_issues  # noqa: E402
from b3_strategy_lab.realistic_portfolio import load_transitions, run_realistic  # noqa: E402
from b3_strategy_lab.statistical_validation import oos_evidence_summary  # noqa: E402
from b3_strategy_lab.strategies import portfolio_strategies  # noqa: E402
from scripts.backtest_strategy_management_realistic import (  # noqa: E402
    DEFAULT_ACTIONS,
    DEFAULT_CASH_EVENTS,
    DEFAULT_CASH_MANIFEST,
    DEFAULT_DATA,
    DEFAULT_EXECUTION,
    DEFAULT_FEES,
    DEFAULT_MANIFESTS,
    DEFAULT_SNAPSHOTS,
    DEFAULT_SPLIT_EVIDENCE,
    DEFAULT_TRANSITIONS,
    DEFAULT_TRANSITION_MANIFEST,
    DEFAULT_UNIVERSE,
)
from scripts.research_portfolio_allocation import MarketData, _configs  # noqa: E402


DEFAULT_OUTPUT = Path("reports/realistic_walk_forward.csv")
DEFAULT_SUMMARY = Path("reports/realistic_walk_forward_summary.json")
DEFAULT_CONTINUOUS_CURVE = Path("reports/realistic_walk_forward_continuous_curve.csv")


def _year_bounds(data_dates: list[str], year: int) -> tuple[str, str] | None:
    values = [value for value in data_dates if value.startswith(f"{year:04d}-")]
    if not values:
        return None
    return values[0], values[-1]


def _metric(summary, objective: str) -> float:
    if objective == "cagr":
        return float(summary.cagr)
    if objective == "total_return":
        return float(summary.total_return)
    if objective == "sharpe":
        return float(summary.sharpe)
    raise ValueError(objective)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Expanding-window walk-forward using the real-money-oriented engine. "
            "Each test year is completely excluded from candidate selection. "
            "Use --all-strategies to reproduce the full strategy-management search "
            "scope. Full scope prevents hiding tried candidates, but is not by itself "
            "a formal multiple-testing significance correction."
        )
    )
    parser.add_argument("--universe-manifest", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--snapshots", type=Path, default=DEFAULT_SNAPSHOTS)
    parser.add_argument("--execution-prices", type=Path, default=DEFAULT_EXECUTION)
    parser.add_argument("--cash-events", type=Path, default=DEFAULT_CASH_EVENTS)
    parser.add_argument("--cash-manifest", type=Path, default=DEFAULT_CASH_MANIFEST)
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
    strategy_group = parser.add_mutually_exclusive_group()
    strategy_group.add_argument("--strategies", nargs="+")
    strategy_group.add_argument(
        "--all-strategies",
        action="store_true",
        help=(
            "Test the full portfolio_strategies() catalog in every training fold. "
            "This is computationally expensive and makes the candidate-search scope "
            "explicit; it does not create statistical significance by itself."
        ),
    )
    parser.add_argument("--managements", nargs="+")
    parser.add_argument("--start", default="2018-01-02")
    parser.add_argument("--end")
    parser.add_argument("--first-test-year", type=int, default=2021)
    parser.add_argument("--last-test-year", type=int)
    parser.add_argument("--initial-cash", type=float, default=1_000.0)
    parser.add_argument("--objective", choices=["cagr", "total_return", "sharpe"], default="cagr")
    parser.add_argument("--base-slippage-bps", type=float, default=10.0)
    parser.add_argument("--participation-bps-at-1pct", type=float, default=5.0)
    parser.add_argument("--max-slippage-bps", type=float, default=100.0)
    parser.add_argument("--economic-gap-adjustment", action="store_true")
    parser.add_argument(
        "--continuous-oos-account",
        action="store_true",
        help=(
            "Carry the exact OOS account state across test years, including positions, "
            "tax-loss carry, IRRF credit, DARF escrow and distribution receivables."
        ),
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument(
        "--continuous-curve-output",
        type=Path,
        default=DEFAULT_CONTINUOUS_CURVE,
    )
    args = parser.parse_args(argv)

    manifest = json.loads(args.universe_manifest.read_text(encoding="utf-8"))
    if manifest.get("point_in_time") is not True:
        parser.error("Walk-forward requires a point-in-time universe.")
    survivorship_safe = manifest.get("survivorship_safe") is True
    if not survivorship_safe and manifest.get("no_replacements") is not True:
        parser.error(
            "A non-survivorship-safe walk-forward is accepted only for the "
            "explicit retrospective fixed/no-replacements universe."
        )
    cash_manifest = json.loads(args.cash_manifest.read_text(encoding="utf-8"))
    if cash_manifest.get("complete") is not True:
        parser.error("Walk-forward requires a cash ledger with no unresolved parse issue.")

    universe = PointInTimeUniverse.from_csv(args.snapshots)
    selectable = {str(item).upper() for item in manifest.get("tickers", [])}
    if universe.union != selectable:
        parser.error("Snapshot union differs from selectable universe manifest.")
    market_data_tickers = sorted(
        {
            str(item).upper()
            for item in manifest.get("market_data_tickers", manifest.get("tickers", []))
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
    evaluation_dates = [
        value
        for value in data.dates
        if value >= args.start and (not args.end or value <= args.end)
    ]
    if len(evaluation_dates) < 2:
        parser.error("Insufficient market sessions inside the requested walk-forward window.")

    walk_end = max(evaluation_dates)
    transition_issues = transition_binding_issues(
        args.ticker_transitions,
        args.ticker_transition_manifest,
        expected_end=walk_end,
    )
    if transition_issues:
        parser.error(
            "Walk-forward refuses unbound/incomplete ticker transitions: "
            + ", ".join(transition_issues)
        )

    pricebook = ExecutionPriceBook.from_csv(args.execution_prices)
    events = load_cash_distributions(args.cash_events)
    fee_schedule = FeeSchedule.from_json(args.fee_schedule)
    transitions = load_transitions(args.ticker_transitions)

    catalog = list(portfolio_strategies())
    if args.all_strategies:
        strategies = catalog
        selection_scope = "full_strategy_and_management_catalog"
    elif args.strategies:
        strategies = [item.strip().lower() for item in args.strategies]
        selection_scope = "explicit_strategy_subset"
    else:
        strategies = ["gap_momentum"]
        selection_scope = "frozen_gap_momentum_managements_only"

    unknown = sorted(set(strategies) - set(catalog))
    if unknown:
        parser.error(f"Unknown strategy names: {unknown}")
    configs = _configs("adjusted", "all")
    if args.managements:
        requested = set(args.managements)
        configs = [config for config in configs if config.name in requested]
        missing = requested - {config.name for config in configs}
        if missing:
            parser.error(f"Unknown management configs: {sorted(missing)}")
    if not configs:
        parser.error("No management configs selected.")

    full_strategy_scope = set(strategies) == set(catalog)
    full_management_scope = args.managements is None
    full_multiple_testing_scope = full_strategy_scope and full_management_scope

    last_available_year = int(max(evaluation_dates)[:4])
    last_test_year = args.last_test_year or last_available_year
    rows: list[dict[str, object]] = []
    continuous_account = None
    continuous_curve_rows: list[dict[str, object]] = []
    previous_continuous_year: int | None = None

    for test_year in range(args.first_test_year, last_test_year + 1):
        bounds = _year_bounds(evaluation_dates, test_year)
        if bounds is None:
            if args.continuous_oos_account and previous_continuous_year is not None:
                raise ValueError(
                    f"Continuous OOS account cannot skip missing test year {test_year}."
                )
            continue
        if (
            args.continuous_oos_account
            and previous_continuous_year is not None
            and test_year != previous_continuous_year + 1
        ):
            raise ValueError("Continuous OOS account requires consecutive test years.")

        test_start, test_end = bounds
        prior_dates = [value for value in evaluation_dates if value < test_start]
        if not prior_dates:
            continue
        train_end = prior_dates[-1]

        ranked = []
        for strategy in strategies:
            for config in configs:
                train, _curve, _account = run_realistic(
                    data=data,
                    universe=universe,
                    pricebook=pricebook,
                    cash_events=events,
                    fee_schedule=fee_schedule,
                    strategy=strategy,
                    config=config,
                    start=args.start,
                    end=train_end,
                    initial_cash=args.initial_cash,
                    base_slippage_bps=args.base_slippage_bps,
                    participation_bps_at_1pct=args.participation_bps_at_1pct,
                    max_slippage_bps=args.max_slippage_bps,
                    transitions=transitions,
                    economic_gap_adjustment=args.economic_gap_adjustment,
                    selection_status="retrospective_hypothesis_replay",
                    survivorship_safe=survivorship_safe,
                )
                ranked.append((_metric(train, args.objective), strategy, config, train))
        ranked.sort(key=lambda item: item[0], reverse=True)
        _score, winner_strategy, winner_config, train_summary = ranked[0]

        test_summary, test_curve, test_account = run_realistic(
            data=data,
            universe=universe,
            pricebook=pricebook,
            cash_events=events,
            fee_schedule=fee_schedule,
            strategy=winner_strategy,
            config=winner_config,
            start=test_start,
            end=test_end,
            initial_cash=args.initial_cash,
            base_slippage_bps=args.base_slippage_bps,
            participation_bps_at_1pct=args.participation_bps_at_1pct,
            max_slippage_bps=args.max_slippage_bps,
            transitions=transitions,
            economic_gap_adjustment=args.economic_gap_adjustment,
            selection_status="walk_forward_out_of_sample",
            survivorship_safe=survivorship_safe,
            existing_account=continuous_account if args.continuous_oos_account else None,
            force_initial_decision=args.continuous_oos_account,
        )
        if args.continuous_oos_account:
            continuous_account = test_account
            previous_continuous_year = test_year
            for point in test_curve:
                continuous_curve_rows.append(
                    {
                        "test_year": test_year,
                        "trading_strategy": winner_strategy,
                        "management_strategy": winner_config.name,
                        "date": point.date,
                        "equity": point.equity,
                        "cash": point.cash,
                        "selected": point.selected,
                        "positions": point.positions,
                        "tax_paid_cumulative": point.tax_paid,
                        "fees_paid_cumulative": point.fees_paid,
                    }
                )

        rows.append(
            {
                "test_year": test_year,
                "train_start": args.start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
                "objective": args.objective,
                "selection_scope": selection_scope,
                "full_multiple_testing_scope": full_multiple_testing_scope,
                "account_mode": (
                    "continuous_oos_account"
                    if args.continuous_oos_account
                    else "independent_standardized_fold"
                ),
                "strategy_count": len(strategies),
                "management_count": len(configs),
                "candidate_count": len(ranked),
                "trading_strategy": winner_strategy,
                "management_strategy": winner_config.name,
                "train_total_return": train_summary.total_return,
                "train_cagr": train_summary.cagr,
                "train_sharpe": train_summary.sharpe,
                "test_initial_cash": test_summary.initial_cash,
                "test_final_equity": test_summary.final_equity,
                "test_total_return": test_summary.total_return,
                "test_cagr": test_summary.cagr,
                "test_sharpe": test_summary.sharpe,
                "test_max_drawdown": test_summary.max_drawdown,
                "test_trades": test_summary.trades,
                "test_fees_paid": test_summary.fees_paid,
                "test_tax_paid": (
                    test_summary.ordinary_income_tax_paid
                    + test_summary.distribution_tax_paid
                ),
                "selection_status": test_summary.selection_status,
                "validity": test_summary.validity,
            }
        )
        print(
            f"{test_year}: {winner_strategy} + {winner_config.name} | "
            f"scope={selection_scope} candidates={len(ranked)} | "
            f"OOS {test_summary.total_return:.2%}",
            flush=True,
        )

    _write_csv(args.output, rows)
    if args.continuous_oos_account:
        _write_csv(args.continuous_curve_output, continuous_curve_rows)

    positive = sum(1 for row in rows if float(row["test_total_return"]) > 0)
    evidence = oos_evidence_summary(positive_folds=positive, folds=len(rows))
    research_claim_allowed = survivorship_safe
    continuous_final_equity = (
        float(rows[-1]["test_final_equity"])
        if args.continuous_oos_account and rows
        else None
    )
    continuous_total_return = (
        continuous_final_equity / float(args.initial_cash) - 1.0
        if continuous_final_equity is not None
        else None
    )
    summary = {
        "schema_version": 7,
        "method": "expanding_window_walk_forward",
        "selection_scope": selection_scope,
        "strategy_count": len(strategies),
        "management_count": len(configs),
        "full_multiple_testing_scope": full_multiple_testing_scope,
        "selection_uses_test_data": False,
        "survivorship_safe_universe": survivorship_safe,
        "research_claim_allowed": research_claim_allowed,
        "ex_ante_selection_claim_allowed": False,
        "formal_multiple_testing_significance_correction": False,
        "formal_multiple_testing_correction_required_for_ex_ante_claim": True,
        "market_data_directory": str(args.data_dir),
        "action_directory": str(args.actions_dir),
        "market_data_manifest_directory": str(args.manifests_dir),
        "split_evidence_file": str(args.split_evidence),
        "ticker_transition_file": str(args.ticker_transitions),
        "ticker_transition_manifest": str(args.ticker_transition_manifest),
        "ticker_transition_binding_verified": True,
        "test_accounts_are_independent": not args.continuous_oos_account,
        "continuous_tax_account_claim": args.continuous_oos_account,
        "continuous_oos_account": args.continuous_oos_account,
        "continuous_account_state_fields": (
            [
                "positions",
                "average_cost",
                "tax_loss_carry",
                "irrf_credit",
                "tax_escrow",
                "scheduled_darf",
                "distribution_receivables",
            ]
            if args.continuous_oos_account
            else []
        ),
        "continuous_curve_output": (
            str(args.continuous_curve_output) if args.continuous_oos_account else None
        ),
        "continuous_initial_cash": (
            float(args.initial_cash) if args.continuous_oos_account else None
        ),
        "continuous_final_equity": continuous_final_equity,
        "continuous_total_return": continuous_total_return,
        "folds": len(rows),
        "positive_test_folds": positive,
        "positive_test_fraction": positive / len(rows) if rows else 0.0,
        "average_oos_return": (
            sum(float(row["test_total_return"]) for row in rows) / len(rows)
            if rows
            else 0.0
        ),
        **evidence,
        "selection_bias_interpretation": (
            "Full candidate scope makes the training search explicit and untouched test "
            "folds prevent direct test-set leakage. It does not constitute a formal "
            "multiple-testing significance correction. Treat the result as OOS research "
            "evidence, not proof that the selected strategy is an ex-ante statistical winner."
        ),
        "note": (
            "With continuous_oos_account=true, one brokerage/tax state is carried through "
            "consecutive OOS years and each newly selected annual model is deployed causally "
            "at that fold's first session. Without it, folds are standardized independent "
            "diagnostics and must not be compounded into a live-account return."
        ),
    }
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Saved {args.output} and {args.summary_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
