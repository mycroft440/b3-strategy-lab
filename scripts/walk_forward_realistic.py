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
from b3_strategy_lab.realistic_portfolio import load_transitions, run_realistic  # noqa: E402
from b3_strategy_lab.strategies import portfolio_strategies  # noqa: E402
from scripts.backtest_strategy_management_realistic import (  # noqa: E402
    DEFAULT_CASH_EVENTS,
    DEFAULT_CASH_MANIFEST,
    DEFAULT_EXECUTION,
    DEFAULT_FEES,
    DEFAULT_MANIFESTS,
    DEFAULT_SNAPSHOTS,
    DEFAULT_SPLIT_EVIDENCE,
    DEFAULT_TRANSITIONS,
    DEFAULT_UNIVERSE,
)
from scripts.research_portfolio_allocation import MarketData, _configs  # noqa: E402


DEFAULT_OUTPUT = Path("reports/realistic_walk_forward.csv")
DEFAULT_SUMMARY = Path("reports/realistic_walk_forward_summary.json")


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
            "Use --all-strategies to reproduce the full strategy-management "
            "multiple-testing scope instead of validating only a frozen hypothesis."
        )
    )
    parser.add_argument("--universe-manifest", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--snapshots", type=Path, default=DEFAULT_SNAPSHOTS)
    parser.add_argument("--execution-prices", type=Path, default=DEFAULT_EXECUTION)
    parser.add_argument("--cash-events", type=Path, default=DEFAULT_CASH_EVENTS)
    parser.add_argument("--cash-manifest", type=Path, default=DEFAULT_CASH_MANIFEST)
    parser.add_argument("--manifests-dir", type=Path, default=DEFAULT_MANIFESTS)
    parser.add_argument("--split-evidence", type=Path, default=DEFAULT_SPLIT_EVIDENCE)
    parser.add_argument("--fee-schedule", type=Path, default=DEFAULT_FEES)
    parser.add_argument("--ticker-transitions", type=Path, default=DEFAULT_TRANSITIONS)
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
    parser.add_argument("--base-slippage-bps", type=float, default=10.0)
    parser.add_argument("--participation-bps-at-1pct", type=float, default=5.0)
    parser.add_argument("--max-slippage-bps", type=float, default=100.0)
    parser.add_argument("--economic-gap-adjustment", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY)
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

        test_summary, _curve, _account = run_realistic(
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
    positive = sum(1 for row in rows if float(row["test_total_return"]) > 0)
    summary = {
        "schema_version": 3,
        "method": "expanding_window_walk_forward",
        "selection_scope": selection_scope,
        "strategy_count": len(strategies),
        "management_count": len(configs),
        "full_multiple_testing_scope": full_multiple_testing_scope,
        "selection_uses_test_data": False,
        "survivorship_safe_universe": survivorship_safe,
        "ex_ante_selection_claim_allowed": survivorship_safe,
        "market_data_manifest_directory": str(args.manifests_dir),
        "split_evidence_file": str(args.split_evidence),
        "test_accounts_are_independent": True,
        "continuous_tax_account_claim": False,
        "folds": len(rows),
        "positive_test_folds": positive,
        "positive_test_fraction": positive / len(rows) if rows else 0.0,
        "average_oos_return": (
            sum(float(row["test_total_return"]) for row in rows) / len(rows)
            if rows
            else 0.0
        ),
        "selection_bias_interpretation": (
            "The original across-strategy multiple-testing bias is addressed only when "
            "full_multiple_testing_scope=true. A gap_momentum-only run validates the "
            "frozen hypothesis/management selection, not the historical choice among "
            "the full strategy catalog."
        ),
        "note": (
            "Each fold starts from the same standardized initial cash because integer "
            "shares, the R$20k monthly sales threshold and tax-loss carry make a simple "
            "multiplication of yearly returns an invalid reconstruction of one live account."
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
