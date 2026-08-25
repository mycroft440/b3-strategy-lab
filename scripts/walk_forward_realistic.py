from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.realistic import (  # noqa: E402
    ExecutionPriceBook,
    FeeSchedule,
    LiquidityCapacityError,
    PointInTimeUniverse,
    cash_coverage_certification_issues,
    load_cash_distributions,
    write_dataclass_csv,
)
from b3_strategy_lab.catalog_contract import (  # noqa: E402
    DEFAULT_CATALOG_CONTRACT,
    validate_catalog_contract,
)
from b3_strategy_lab.realistic_certification import transition_binding_issues  # noqa: E402
from b3_strategy_lab.realistic_portfolio import (  # noqa: E402
    _gap_adjusted_eligibility,
    load_transitions,
    run_realistic,
)
from b3_strategy_lab.strategies import portfolio_strategies  # noqa: E402
from scripts.backtest_strategy_management_realistic import (  # noqa: E402
    DEFAULT_ACTIONS,
    DEFAULT_CASH_EVENTS,
    DEFAULT_CASH_CERTIFICATION,
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
DEFAULT_CONTINUOUS_TRADES = Path("reports/realistic_walk_forward_continuous_trades.csv")
DEFAULT_CONTINUOUS_CASH = Path("reports/realistic_walk_forward_continuous_distributions.csv")
DEFAULT_CONTINUOUS_TAX = Path("reports/realistic_walk_forward_continuous_tax.csv")


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


def _strategy_eligibility(
    data,
    strategy: str,
    events,
    *,
    economic_gap_adjustment: bool,
):
    from scripts.backtest_strategy_management_combinations import _build_eligibility

    if economic_gap_adjustment:
        return _gap_adjusted_eligibility(data, strategy, events, "adjusted")
    signal_start = min(
        candle.date for ticker in data.tickers for candle in data.candles[ticker]
    )
    return _build_eligibility(
        data,
        [strategy],
        "adjusted",
        signal_start=signal_start,
    )[strategy]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Expanding-window walk-forward using the real-money-oriented engine. "
            "Each test year is completely excluded from candidate selection. "
            "Use --all-strategies to reproduce the full strategy-management "
            "multiple-testing scope instead of validating only a frozen hypothesis."
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
            "This is computationally expensive but is the appropriate scope for "
            "auditing the original across-strategy selection bias."
        ),
    )
    parser.add_argument("--managements", nargs="+")
    parser.add_argument("--start", default="2018-01-02")
    parser.add_argument("--end")
    parser.add_argument("--first-test-year", type=int, default=2021)
    parser.add_argument("--last-test-year", type=int)
    parser.add_argument("--initial-cash", type=float, default=1_000.0)
    parser.add_argument("--objective", choices=["cagr", "total_return", "sharpe"], default="cagr")
    parser.add_argument("--min-train-trades", type=int, default=12)
    parser.add_argument("--base-slippage-bps", type=float, default=10.0)
    parser.add_argument("--participation-bps-at-1pct", type=float, default=5.0)
    parser.add_argument("--max-slippage-bps", type=float, default=100.0)
    parser.add_argument("--max-participation-rate", type=float, default=0.01)
    parser.add_argument("--economic-gap-adjustment", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--continuous-curve-output", type=Path, default=DEFAULT_CONTINUOUS_CURVE)
    parser.add_argument("--continuous-trades-output", type=Path, default=DEFAULT_CONTINUOUS_TRADES)
    parser.add_argument("--continuous-cash-output", type=Path, default=DEFAULT_CONTINUOUS_CASH)
    parser.add_argument("--continuous-tax-output", type=Path, default=DEFAULT_CONTINUOUS_TAX)
    parser.add_argument(
        "--catalog-contract",
        type=Path,
        default=DEFAULT_CATALOG_CONTRACT,
    )
    args = parser.parse_args(argv)

    if args.min_train_trades < 0:
        parser.error("--min-train-trades cannot be negative.")
    catalog_contract = validate_catalog_contract(args.catalog_contract)

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
    cash_certification: dict[str, object] = {}
    if args.cash_certification.exists():
        cash_certification = json.loads(
            args.cash_certification.read_text(encoding="utf-8")
        )

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

    cash_manifest_tickers = {
        str(item).strip().upper()
        for item in cash_manifest.get("market_data_tickers", [])
        if str(item).strip()
    }
    cash_certification_issues = cash_coverage_certification_issues(
        cash_certification,
        cash_events_path=args.cash_events,
        cash_manifest_path=args.cash_manifest,
        tickers=market_data_tickers,
        start=args.start,
        end=walk_end,
    ) if cash_certification else ["cash coverage certification file is missing"]
    cash_events_complete = (
        cash_manifest_tickers == set(market_data_tickers)
        and int(cash_manifest.get("market_data_ticker_count", -1))
        == len(cash_manifest_tickers)
        and not cash_certification_issues
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

    for test_year in range(args.first_test_year, last_test_year + 1):
        bounds = _year_bounds(evaluation_dates, test_year)
        if bounds is None:
            continue
        test_start, test_end = bounds
        prior_dates = [value for value in evaluation_dates if value < test_start]
        if not prior_dates:
            continue
        train_end = prior_dates[-1]

        ranked = []
        scanned_candidates = 0
        capacity_invalid_candidates = 0
        for strategy in strategies:
            eligibility = _strategy_eligibility(
                data,
                strategy,
                events,
                economic_gap_adjustment=args.economic_gap_adjustment,
            )
            for config in configs:
                scanned_candidates += 1
                try:
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
                        max_participation_rate=args.max_participation_rate,
                        transitions=transitions,
                        economic_gap_adjustment=args.economic_gap_adjustment,
                        selection_status="retrospective_hypothesis_replay",
                        survivorship_safe=survivorship_safe,
                        cash_events_complete=cash_events_complete,
                        eligibility_cache={strategy: eligibility},
                    )
                except LiquidityCapacityError:
                    capacity_invalid_candidates += 1
                    continue
                score = _metric(train, args.objective)
                if math.isfinite(score) and train.trades >= args.min_train_trades:
                    ranked.append((score, strategy, config, train))
        if not ranked:
            raise ValueError(
                f"{test_year}: no finite candidate satisfies "
                f"min_train_trades={args.min_train_trades}."
            )
        ranked.sort(key=lambda item: (-item[0], item[1], item[2].name))
        _score, winner_strategy, winner_config, train_summary = ranked[0]

        test_summary, _curve, _account = run_realistic(
            data=data,
            universe=universe,
            pricebook=pricebook,
            cash_events=events,
            fee_schedule=fee_schedule,
            strategy=winner_strategy,
            config=winner_config,
            start=train_end,
            end=test_end,
            initial_cash=args.initial_cash,
            base_slippage_bps=args.base_slippage_bps,
            participation_bps_at_1pct=args.participation_bps_at_1pct,
            max_slippage_bps=args.max_slippage_bps,
            max_participation_rate=args.max_participation_rate,
            transitions=transitions,
            economic_gap_adjustment=args.economic_gap_adjustment,
            selection_status="walk_forward_out_of_sample",
            survivorship_safe=survivorship_safe,
            cash_events_complete=cash_events_complete,
            eligibility_cache={winner_strategy: _strategy_eligibility(
                data,
                winner_strategy,
                events,
                economic_gap_adjustment=args.economic_gap_adjustment,
            )},
            model_schedule={train_end: (winner_strategy, winner_config)},
            metrics_start=test_start,
        )
        rows.append(
            {
                "test_year": test_year,
                "train_start": args.start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
                # A terminal dataset year is conservatively partial: without a later
                # official session we cannot prove that its final B3 session is present.
                # Earlier years are complete because the next year's official quotes
                # establish that the history crossed the boundary.
                "partial_test_year": not any(
                    value[:4] > f"{test_year:04d}" for value in evaluation_dates
                ),
                "objective": args.objective,
                "selection_scope": selection_scope,
                "full_multiple_testing_scope": full_multiple_testing_scope,
                "strategy_count": len(strategies),
                "management_count": len(configs),
                "candidate_count": scanned_candidates,
                "eligible_candidate_count": len(ranked),
                "capacity_invalid_candidate_count": capacity_invalid_candidates,
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
            f"scope={selection_scope} candidates={scanned_candidates} | "
            f"OOS {test_summary.total_return:.2%}",
            flush=True,
        )

    if not rows:
        raise ValueError("No walk-forward folds were generated.")

    schedule = {
        str(row["train_end"]): (
            str(row["trading_strategy"]),
            next(
                config
                for config in configs
                if config.name == str(row["management_strategy"])
            ),
        )
        for row in rows
    }
    selected_strategies = sorted({item[0] for item in schedule.values()})
    continuous_eligibility = {
        selected: _strategy_eligibility(
            data,
            selected,
            events,
            economic_gap_adjustment=args.economic_gap_adjustment,
        )
        for selected in selected_strategies
    }
    first_row = rows[0]
    first_strategy, first_config = schedule[str(first_row["train_end"])]
    continuous_summary, continuous_curve, continuous_account = run_realistic(
        data=data,
        universe=universe,
        pricebook=pricebook,
        cash_events=events,
        fee_schedule=fee_schedule,
        strategy=first_strategy,
        config=first_config,
        start=str(first_row["train_end"]),
        end=str(rows[-1]["test_end"]),
        initial_cash=args.initial_cash,
        base_slippage_bps=args.base_slippage_bps,
        participation_bps_at_1pct=args.participation_bps_at_1pct,
        max_slippage_bps=args.max_slippage_bps,
        max_participation_rate=args.max_participation_rate,
        transitions=transitions,
        economic_gap_adjustment=args.economic_gap_adjustment,
        selection_status="walk_forward_out_of_sample",
        survivorship_safe=survivorship_safe,
        cash_events_complete=cash_events_complete,
        model_schedule=schedule,
        eligibility_cache=continuous_eligibility,
        metrics_start=str(first_row["test_start"]),
    )
    curve_by_date = {row.date: row.equity for row in continuous_curve}
    for row in rows:
        fold_initial = curve_by_date[str(row["train_end"])]
        fold_final = curve_by_date[str(row["test_end"])]
        row["continuous_initial_equity"] = fold_initial
        row["continuous_final_equity"] = fold_final
        row["continuous_test_return"] = fold_final / fold_initial - 1.0

    oos_curve = [
        row for row in continuous_curve if row.date >= str(first_row["test_start"])
    ]
    _write_csv(args.output, rows)
    write_dataclass_csv(args.continuous_curve_output, oos_curve)
    write_dataclass_csv(args.continuous_trades_output, continuous_account.trade_ledger)
    write_dataclass_csv(args.continuous_cash_output, continuous_account.cash_ledger)
    write_dataclass_csv(args.continuous_tax_output, continuous_account.tax.finalized())
    positive = sum(
        1 for row in rows if float(row["continuous_test_return"]) > 0
    )
    broker_fee_qualities = {
        rule.broker_quality or "unverified" for rule in fee_schedule.rules
    }
    broker_profile_certified = broker_fee_qualities == {"certified"}
    strict_blockers: list[str] = []
    if not full_multiple_testing_scope:
        strict_blockers.append("original_full_catalog_selection_scope_not_replayed")
    if not survivorship_safe:
        strict_blockers.append("universe_is_not_survivorship_safe")
    if not cash_events_complete:
        strict_blockers.extend(cash_certification_issues)
    if not broker_profile_certified:
        strict_blockers.append("broker_profile_is_not_certified_zero_brokerage_assumed")
    noncausal_trade_dates = sorted(
        {
            trade.date
            for trade in continuous_account.trade_ledger
            if not trade.capacity_reference_end
            or trade.capacity_reference_end >= trade.date
        }
    )
    impossible_fill_dates = sorted(
        {
            trade.date
            for trade in continuous_account.trade_ledger
            if trade.fill_outside_daily_range
        }
    )
    if noncausal_trade_dates:
        strict_blockers.append("noncausal_or_missing_liquidity_reference_in_trade_ledger")
    if impossible_fill_dates:
        strict_blockers.append("modeled_fill_outside_official_daily_range")
    strict_blockers.append("pbo_dsr_psr_multiple_testing_statistics_not_computed")
    strict_blockers = sorted(set(strict_blockers))

    summary = {
        "schema_version": 6,
        "method": "expanding_window_selection_with_continuous_oos_account",
        "selection_scope": selection_scope,
        "strategy_count": len(strategies),
        "management_count": len(configs),
        "full_multiple_testing_scope": full_multiple_testing_scope,
        "catalog_contract": {
            "path": str(args.catalog_contract),
            "sha256": catalog_contract["catalog_sha256"],
            "runtime_strategy_count": catalog_contract["strategy_count"],
            "runtime_management_count": catalog_contract["management_count"],
            "runtime_candidate_count": catalog_contract["candidate_count"],
        },
        "minimum_train_trades": args.min_train_trades,
        "selection_uses_test_data": False,
        "survivorship_safe_universe": survivorship_safe,
        "ex_ante_selection_claim_allowed": not strict_blockers,
        "strict_blockers": strict_blockers,
        "certified_first_place": None,
        "diagnostic_rank_1_only": bool(strict_blockers),
        "noncausal_trade_dates": noncausal_trade_dates,
        "modeled_fill_outside_daily_range_dates": impossible_fill_dates,
        "market_data_directory": str(args.data_dir),
        "action_directory": str(args.actions_dir),
        "market_data_manifest_directory": str(args.manifests_dir),
        "split_evidence_file": str(args.split_evidence),
        "ticker_transition_file": str(args.ticker_transitions),
        "ticker_transition_manifest": str(args.ticker_transition_manifest),
        "ticker_transition_binding_verified": True,
        "cash_events_complete": cash_events_complete,
        "cash_certification_issues": cash_certification_issues,
        "broker_profile_certified": broker_profile_certified,
        "brokerage_assumption": continuous_summary.brokerage_assumption,
        "test_accounts_are_independent": True,
        "independent_test_accounts_are_diagnostic_only": True,
        "continuous_oos_account": True,
        "continuous_tax_account_claim": True,
        "continuous_summary": asdict(continuous_summary),
        "continuous_outputs": {
            "curve": str(args.continuous_curve_output),
            "trades": str(args.continuous_trades_output),
            "cash_distributions": str(args.continuous_cash_output),
            "tax": str(args.continuous_tax_output),
        },
        "frozen_model_schedule": [
            {
                "decision_date": decision_date,
                "strategy": model[0],
                "management": model[1].name,
                "executes_not_before": next(
                    value for value in evaluation_dates if value > decision_date
                ),
            }
            for decision_date, model in schedule.items()
        ],
        "folds": len(rows),
        "positive_test_folds": positive,
        "positive_test_fraction": positive / len(rows) if rows else 0.0,
        "average_oos_return": (
            sum(float(row["continuous_test_return"]) for row in rows) / len(rows)
            if rows
            else 0.0
        ),
        "average_independent_diagnostic_oos_return": (
            sum(float(row["test_total_return"]) for row in rows) / len(rows)
            if rows
            else 0.0
        ),
        "partial_test_years": [
            int(row["test_year"]) for row in rows if bool(row["partial_test_year"])
        ],
        "selection_bias_interpretation": (
            "The original across-strategy multiple-testing bias is addressed only when "
            "full_multiple_testing_scope=true. A gap_momentum-only run validates the "
            "frozen hypothesis/management selection, not the historical choice among "
            "the full strategy catalog."
        ),
        "note": (
            "Independent R$1,000 fold replays remain diagnostics. The primary OOS result "
            "is one continuous account: cash, positions, weighted tax basis, loss carry, "
            "IRRF credit, tax escrow, receivables and pending next-open targets cross every "
            "year boundary. A model selected through train_end is first executable after "
            "that close."
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
