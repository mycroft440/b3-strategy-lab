from __future__ import annotations

from pathlib import Path


def ensure_replace(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        print(f"already fixed: {path}")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{path}: expected exactly one old fragment, found {count}: {old[:160]!r}"
        )
    file.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"fixed: {path}")


# Manifest reproducibility: report source/data dirtiness, not generated reports.
ensure_replace(
    "scripts/backtest_strategy_management_combinations.py",
    '''        status = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
''',
    '''        status = subprocess.check_output(
            [
                "git",
                "status",
                "--porcelain",
                "--untracked-files=all",
                "--",
                "b3_strategy_lab",
                "scripts",
                "data",
                ".github/workflows",
            ],
            cwd=PROJECT_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
''',
)

# Deterministic shard merge uses the same key as the matrix runner.
ensure_replace(
    "scripts/merge_matrix_shards.py",
    "from scripts.backtest_strategy_management_combinations import _write_results\n",
    "from scripts.backtest_strategy_management_combinations import _ranking_key, _write_results\n",
)
ensure_replace(
    "scripts/merge_matrix_shards.py",
    '''    all_rows.sort(
        key=lambda row: (float(row["total_return"]), float(row["cagr"])),
        reverse=True,
    )
''',
    "    all_rows.sort(key=_ranking_key)\n",
)

# Auditor verifies the deterministic tie-break as well.
ensure_replace(
    "scripts/audit_matrix_results.py",
    "    previous_sort_key: tuple[float, float] | None = None\n",
    "    previous_sort_key: tuple[float, float, str, str] | None = None\n",
)
ensure_replace(
    "scripts/audit_matrix_results.py",
    '''            sort_key = (values["total_return"], values["cagr"])
            if previous_sort_key is not None:
                sorted_as_declared &= previous_sort_key >= sort_key
            previous_sort_key = sort_key
''',
    '''            sort_key = (
                -values["total_return"],
                -values["cagr"],
                row["trading_strategy"],
                row["management_strategy"],
            )
            if previous_sort_key is not None:
                sorted_as_declared &= previous_sort_key <= sort_key
            previous_sort_key = sort_key
''',
)
ensure_replace(
    "scripts/audit_matrix_results.py",
    '        "ranking_is_total_return_then_cagr_desc": sorted_as_declared,\n',
    '        "ranking_is_deterministic_total_return_cagr_names": sorted_as_declared,\n',
)

# Realistic engine: propagate true survivorship status.
ensure_replace(
    "b3_strategy_lab/realistic_portfolio.py",
    '''    economic_gap_adjustment: bool,
    selection_status: str = "retrospective_hypothesis_replay",
    progress_callback=None,
''',
    '''    economic_gap_adjustment: bool,
    selection_status: str = "retrospective_hypothesis_replay",
    survivorship_safe: bool = False,
    progress_callback=None,
''',
)

# Precompute a proportional buy plan before sending orders. This makes the final
# quantities independent of alphabetical execution order when fees/slippage make
# the theoretical target basket slightly unaffordable.
ensure_replace(
    "b3_strategy_lab/realistic_portfolio.py",
    '''    for ticker in sorted(targets):
        wanted = desired_shares.get(ticker, 0) - trial.shares(ticker)
        if wanted <= 0:
            continue
        affordable = _max_affordable(trial, pricebook, current, ticker, wanted)
        if affordable <= 0:
            continue
        for qty, quote in pricebook.legs(current, ticker, affordable):
            trial.buy_leg(current, ticker, qty, quote)
''',
    '''    wanted_by_ticker = {
        ticker: max(0, desired_shares.get(ticker, 0) - trial.shares(ticker))
        for ticker in targets
    }
    wanted_by_ticker = {
        ticker: quantity for ticker, quantity in wanted_by_ticker.items() if quantity > 0
    }
    reserved_tax = _provisional_ordinary_tax(trial, current)
    available_cash = max(0.0, trial.cash - reserved_tax)

    def total_buy_cost(plan: dict[str, int]) -> float:
        return sum(
            _estimate_buy_cost(trial, pricebook, current, ticker, quantity)
            for ticker, quantity in plan.items()
            if quantity > 0
        )

    buy_plan = dict(wanted_by_ticker)
    if wanted_by_ticker and total_buy_cost(buy_plan) > available_cash + 1e-9:
        low, high = 0.0, 1.0
        best = {ticker: 0 for ticker in wanted_by_ticker}
        for _ in range(48):
            scale = (low + high) / 2
            candidate = {
                ticker: int(math.floor(quantity * scale))
                for ticker, quantity in wanted_by_ticker.items()
            }
            if total_buy_cost(candidate) <= available_cash + 1e-9:
                best = candidate
                low = scale
            else:
                high = scale
        buy_plan = best

    for ticker in sorted(buy_plan):
        quantity = buy_plan[ticker]
        if quantity <= 0:
            continue
        for qty, quote in pricebook.legs(current, ticker, quantity):
            trial.buy_leg(current, ticker, qty, quote)
''',
)
ensure_replace(
    "b3_strategy_lab/realistic_portfolio.py",
    '''    if selection_status == "retrospective_hypothesis_replay":
        validity += "__RETROSPECTIVE_SELECTION"
''',
    '''    if not survivorship_safe:
        validity += "__RETROSPECTIVE_UNIVERSE"
    if selection_status == "retrospective_hypothesis_replay":
        validity += "__RETROSPECTIVE_SELECTION"
''',
)
ensure_replace(
    "b3_strategy_lab/realistic_portfolio.py",
    "        survivorship_safe=True,\n",
    "        survivorship_safe=survivorship_safe,\n",
)

# Single realistic backtest passes and cross-checks the universe flag.
ensure_replace(
    "scripts/backtest_strategy_management_realistic.py",
    '''        selection_status=args.selection_status,
        progress_callback=_report_progress,
''',
    '''        selection_status=args.selection_status,
        survivorship_safe=bool(manifest.get("survivorship_safe")),
        progress_callback=_report_progress,
''',
)
ensure_replace(
    "scripts/backtest_strategy_management_realistic.py",
    '    payload["universe_survivorship_safe"] = bool(manifest.get("survivorship_safe"))\n',
    '''    payload["universe_survivorship_safe"] = bool(manifest.get("survivorship_safe"))
    if payload["survivorship_safe"] != payload["universe_survivorship_safe"]:
        raise RuntimeError("Realistic summary survivorship flag diverges from universe manifest.")
''',
)

# Walk-forward accepts the explicitly retrospective fixed/no-replacement universe,
# labels it honestly, and honors a requested end date including partial final years.
ensure_replace(
    "scripts/walk_forward_realistic.py",
    '''    parser.add_argument("--start", default="2018-01-02")
    parser.add_argument("--first-test-year", type=int, default=2021)
''',
    '''    parser.add_argument("--start", default="2018-01-02")
    parser.add_argument("--end")
    parser.add_argument("--first-test-year", type=int, default=2021)
''',
)
ensure_replace(
    "scripts/walk_forward_realistic.py",
    '''    manifest = json.loads(args.universe_manifest.read_text(encoding="utf-8"))
    if manifest.get("point_in_time") is not True or manifest.get("survivorship_safe") is not True:
        parser.error("Walk-forward requires a point-in-time survivorship-safe universe.")
''',
    '''    manifest = json.loads(args.universe_manifest.read_text(encoding="utf-8"))
    if manifest.get("point_in_time") is not True:
        parser.error("Walk-forward requires a point-in-time universe.")
    survivorship_safe = manifest.get("survivorship_safe") is True
    if not survivorship_safe and manifest.get("no_replacements") is not True:
        parser.error(
            "A non-survivorship-safe walk-forward is accepted only for the "
            "explicit retrospective fixed/no-replacements universe."
        )
''',
)
ensure_replace(
    "scripts/walk_forward_realistic.py",
    "    pricebook = ExecutionPriceBook.from_csv(args.execution_prices)\n",
    '''    evaluation_dates = [
        value
        for value in data.dates
        if value >= args.start and (not args.end or value <= args.end)
    ]
    if len(evaluation_dates) < 2:
        parser.error("Insufficient market sessions inside the requested walk-forward window.")
    pricebook = ExecutionPriceBook.from_csv(args.execution_prices)
''',
)
ensure_replace(
    "scripts/walk_forward_realistic.py",
    "    last_available_year = int(max(data.dates)[:4])\n",
    "    last_available_year = int(max(evaluation_dates)[:4])\n",
)
ensure_replace(
    "scripts/walk_forward_realistic.py",
    "        bounds = _year_bounds(data.dates, test_year)\n",
    "        bounds = _year_bounds(evaluation_dates, test_year)\n",
)
ensure_replace(
    "scripts/walk_forward_realistic.py",
    "        prior_dates = [value for value in data.dates if args.start <= value < test_start]\n",
    "        prior_dates = [value for value in evaluation_dates if value < test_start]\n",
)
ensure_replace(
    "scripts/walk_forward_realistic.py",
    '''                    selection_status="retrospective_hypothesis_replay",
                )
''',
    '''                    selection_status="retrospective_hypothesis_replay",
                    survivorship_safe=survivorship_safe,
                )
''',
)
ensure_replace(
    "scripts/walk_forward_realistic.py",
    '''            selection_status="walk_forward_out_of_sample",
        )
''',
    '''            selection_status="walk_forward_out_of_sample",
            survivorship_safe=survivorship_safe,
        )
''',
)
ensure_replace(
    "scripts/walk_forward_realistic.py",
    '''        "selection_uses_test_data": False,
        "test_accounts_are_independent": True,
''',
    '''        "selection_uses_test_data": False,
        "survivorship_safe_universe": survivorship_safe,
        "ex_ante_selection_claim_allowed": survivorship_safe,
        "test_accounts_are_independent": True,
''',
)

# End-to-end pipeline downloads required official archives by default and forwards
# the exact end boundary into walk-forward.
ensure_replace(
    "scripts/run_realistic_pipeline.py",
    '    parser.add_argument("--download", action="store_true")\n',
    '''    download_group = parser.add_mutually_exclusive_group()
    download_group.add_argument("--download", dest="download", action="store_true", default=True)
    download_group.add_argument("--no-download", dest="download", action="store_false")
''',
)
ensure_replace(
    "scripts/run_realistic_pipeline.py",
    '''                "--initial-cash",
                str(args.initial_cash),
                "--output",
''',
    '''                "--initial-cash",
                str(args.initial_cash),
                *common_end,
                "--output",
''',
)

# Full matrix is invalidated by material code/data changes and runs regression tests
# before spawning the 90k+ grid.
ensure_replace(
    ".github/workflows/full-matrix-backtest.yml",
    '''    paths:
      - ".github/workflows/full-matrix-backtest.yml"
''',
    '''    paths:
      - ".github/workflows/full-matrix-backtest.yml"
      - "scripts/backtest_strategy_management_combinations.py"
      - "scripts/research_portfolio_allocation.py"
      - "scripts/merge_matrix_shards.py"
      - "scripts/audit_matrix_results.py"
      - "b3_strategy_lab/strategies.py"
      - "b3_strategy_lab/additional_strategies.py"
      - "b3_strategy_lab/researched_strategies.py"
      - "b3_strategy_lab/extended_strategies.py"
      - "b3_strategy_lab/candles.py"
      - "b3_strategy_lab/cotahist.py"
      - "data/candles/**"
      - "data/manifests/**"
      - "data/corporate_actions/*_actions.csv"
      - "data/corporate_actions/split_evidence.json"
      - "data/universes/fixed_40_2018.json"
      - "tests/test_execution_hardening.py"
      - "tests/test_portfolio_allocation.py"
      - "tests/test_matrix_reports.py"
''',
)
ensure_replace(
    ".github/workflows/full-matrix-backtest.yml",
    '''      - name: Validar dados verificados
        run: python -m b3_strategy_lab verify-data --interval 1d
''',
    '''      - name: Testes de regressao de execucao
        run: |
          python -m unittest \\
            tests.test_portfolio_allocation \\
            tests.test_matrix_reports \\
            tests.test_realistic_accounting \\
            tests.test_execution_hardening -v

      - name: Validar dados verificados
        run: python -m b3_strategy_lab verify-data --interval 1d
''',
)

# Recovery no longer has a stale default run and publishes only to a diagnostic branch.
ensure_replace(
    ".github/workflows/recover-backtest-merge.yml",
    '''        required: true
        default: "32324507993"
        type: string
''',
    '''        required: true
        type: string
''',
)
ensure_replace(
    ".github/workflows/recover-backtest-merge.yml",
    "      SOURCE_RUN_ID: ${{ inputs.source_run_id || '32324507993' }}\n",
    "      SOURCE_RUN_ID: ${{ inputs.source_run_id }}\n",
)
ensure_replace(
    ".github/workflows/recover-backtest-merge.yml",
    '''              'source_sha': os.environ['GITHUB_SHA'],
              'strategy_count': 190,
              'management_count': 478,
              'combination_count': 90820,
''',
    '''              'recovery_sha': os.environ['GITHUB_SHA'],
              'calculation_git_commit': (
                  json.loads(Path('reports/strategy_management_combinations_40_adjusted_no_dividends_1d.manifest.json').read_text(encoding='utf-8')).get('git_commit')
                  if Path('reports/strategy_management_combinations_40_adjusted_no_dividends_1d.manifest.json').exists()
                  else None
              ),
              'strategy_count': int((audit or {}).get('strategy_count', 0)),
              'management_count': int((audit or {}).get('management_count', 0)),
              'combination_count': int((audit or {}).get('rows', 0)),
''',
)
ensure_replace(
    ".github/workflows/recover-backtest-merge.yml",
    "          git push --force origin HEAD:backtest-results\n",
    "          git push --force origin HEAD:backtest-recovery-results\n",
)

# Realistic CI runs for main engine changes and includes the hardening regression tests.
ensure_replace(
    ".github/workflows/realistic-backtest-ci.yml",
    '''on:
  pull_request:
''',
    '''on:
  push:
    branches:
      - main
    paths:
      - "b3_strategy_lab/realistic.py"
      - "b3_strategy_lab/realistic_portfolio.py"
      - "scripts/*realistic*.py"
      - "scripts/run_realistic_pipeline.py"
      - "tests/test_realistic_accounting.py"
      - "tests/test_execution_hardening.py"
      - ".github/workflows/realistic-backtest-ci.yml"
  pull_request:
''',
)
ensure_replace(
    ".github/workflows/realistic-backtest-ci.yml",
    '''            tests.test_combination_control_panel -v
''',
    '''            tests.test_combination_control_panel \\
            tests.test_execution_hardening -v
''',
)

TEST_CONTENT = r'''from __future__ import annotations

import unittest
from types import SimpleNamespace

from b3_strategy_lab.candles import Candle
from b3_strategy_lab.realistic import (
    ExecutionPriceBook,
    ExecutionQuote,
    FeeRule,
    FeeSchedule,
    PointInTimeUniverse,
    RealCashAccount,
    SlippageModel,
    UniverseSnapshot,
)
from b3_strategy_lab.realistic_portfolio import rebalance_atomic, run_realistic
from scripts.backtest_strategy_management_combinations import _ranking_key
from scripts.research_portfolio_allocation import PortfolioConfig, _rebalance, run_portfolio


def candle(day: str, ticker: str, price: float) -> Candle:
    return Candle(
        date=day,
        ticker=ticker,
        source_symbol=ticker,
        open=price,
        high=price,
        low=price,
        close=price,
        adj_close=price,
        volume=1000,
        raw_open=price,
        raw_high=price,
        raw_low=price,
        raw_close=price,
        adjustment_factor=1.0,
        raw_volume=1000,
        trades=10,
        financial_volume=1_000_000.0,
        market_type="010",
    )


class StrictResearchExecutionTests(unittest.TestCase):
    def test_rebalance_refuses_missing_open_for_held_or_target_ticker(self) -> None:
        shares = {"AAA3": 10.0, "BBB3": 0.0}
        with self.assertRaisesRegex(ValueError, "abertura fresca obrigatoria"):
            _rebalance(
                "2024-01-02",
                ["AAA3", "BBB3"],
                {"BBB3": candle("2024-01-02", "BBB3", 10.0)},
                {"AAA3": 9.0},
                shares,
                0.0,
                {"BBB3": 1.0},
                0.0,
                0.0,
                1,
            )

    def test_portfolio_refuses_stale_close_for_held_position(self) -> None:
        dates = ["2024-01-29", "2024-01-30", "2024-01-31", "2024-02-01", "2024-02-02"]
        aaa = [candle(day, "AAA3", price) for day, price in zip(dates[:-1], [10.0, 11.0, 12.0, 13.0])]
        bbb = [candle(day, "BBB3", 20.0) for day in dates]
        data = SimpleNamespace(
            tickers=["AAA3", "BBB3"],
            dates=dates,
            candles={"AAA3": aaa, "BBB3": bbb},
            by_date={
                "AAA3": {item.date: item for item in aaa},
                "BBB3": {item.date: item for item in bbb},
            },
            index_by_date={
                "AAA3": {item.date: index for index, item in enumerate(aaa)},
                "BBB3": {item.date: index for index, item in enumerate(bbb)},
            },
            signal_prices={
                "AAA3": [10.0, 11.0, 12.0, 13.0],
                "BBB3": [20.0, 20.0, 20.0, 20.0, 20.0],
            },
            raw_returns={
                "AAA3": [0.0, 0.10, 0.05, 0.08],
                "BBB3": [0.0, 0.0, 0.0, 0.0, 0.0],
            },
            candidate_profile_cache={},
        )
        config = PortfolioConfig(
            name="strict",
            lookback=1,
            top_n=1,
            vol_window=2,
            rebalance="monthly",
            score="momentum",
            weighting="equal",
            absolute_momentum=True,
            signal_mode="adjusted",
        )
        eligibility = {
            "AAA3": [1, 1, 1, 1],
            "BBB3": [0, 0, 0, 0, 0],
        }
        with self.assertRaisesRegex(ValueError, "fechamento fresco obrigatorio"):
            run_portfolio(
                data,
                config,
                initial_cash=1000.0,
                lot_size=1,
                eligibility=eligibility,
            )

    def test_ranking_ties_are_name_deterministic(self) -> None:
        rows = [
            {"total_return": 1.0, "cagr": 0.2, "trading_strategy": "z", "management_strategy": "b"},
            {"total_return": 1.0, "cagr": 0.2, "trading_strategy": "a", "management_strategy": "z"},
            {"total_return": 1.0, "cagr": 0.2, "trading_strategy": "a", "management_strategy": "a"},
        ]
        ordered = sorted(rows, key=_ranking_key)
        self.assertEqual(
            [(row["trading_strategy"], row["management_strategy"]) for row in ordered],
            [("a", "a"), ("a", "z"), ("z", "b")],
        )


class RealisticExecutionHardeningTests(unittest.TestCase):
    def test_proportional_buy_plan_does_not_starve_later_ticker(self) -> None:
        account = RealCashAccount(
            1000.0,
            FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 0.0)]),
            SlippageModel(base_bps=100.0, participation_bps_at_1pct=0.0, max_bps=100.0),
        )
        pricebook = ExecutionPriceBook(
            [
                ExecutionQuote("2024-01-02", "AAA3F", "020", 10.0, 10.0, 1_000_000.0),
                ExecutionQuote("2024-01-02", "ZZZ3F", "020", 10.0, 10.0, 1_000_000.0),
            ]
        )
        data = SimpleNamespace(
            by_date={
                "AAA3": {"2024-01-02": candle("2024-01-02", "AAA3", 10.0)},
                "ZZZ3": {"2024-01-02": candle("2024-01-02", "ZZZ3", 10.0)},
            }
        )
        result = rebalance_atomic(
            account,
            data,
            pricebook,
            "2024-01-02",
            {"AAA3": 0.5, "ZZZ3": 0.5},
        )
        self.assertEqual(result.shares("AAA3"), result.shares("ZZZ3"))
        self.assertGreater(result.shares("AAA3"), 0)

    def test_realistic_summary_uses_supplied_survivorship_status(self) -> None:
        days = ["2024-01-02", "2024-01-03"]
        items = [candle(day, "AAA3", 10.0) for day in days]
        data = SimpleNamespace(
            tickers=["AAA3"],
            dates=days,
            candles={"AAA3": items},
            by_date={"AAA3": {item.date: item for item in items}},
            index_by_date={"AAA3": {item.date: index for index, item in enumerate(items)}},
            signal_prices={"AAA3": [10.0, 10.0]},
            raw_returns={"AAA3": [0.0, 0.0]},
            candidate_profile_cache={},
        )
        summary, _curve, _account = run_realistic(
            data=data,
            universe=PointInTimeUniverse([UniverseSnapshot("2024-01-02", frozenset({"AAA3"}))]),
            pricebook=ExecutionPriceBook([]),
            cash_events=[],
            fee_schedule=FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 0.0)]),
            strategy="buy_and_hold",
            config=PortfolioConfig(
                name="no_trade_short_window",
                lookback=1,
                top_n=1,
                vol_window=21,
                rebalance="daily",
                score="all",
                weighting="equal",
                absolute_momentum=False,
                signal_mode="adjusted",
            ),
            start=days[0],
            end=days[-1],
            initial_cash=1000.0,
            base_slippage_bps=0.0,
            participation_bps_at_1pct=0.0,
            max_slippage_bps=0.0,
            transitions={},
            economic_gap_adjustment=False,
            selection_status="retrospective_hypothesis_replay",
            survivorship_safe=False,
        )
        self.assertFalse(summary.survivorship_safe)
        self.assertIn("RETROSPECTIVE_UNIVERSE", summary.validity)


if __name__ == "__main__":
    unittest.main()
'''

test_path = Path("tests/test_execution_hardening.py")
if not test_path.exists() or test_path.read_text(encoding="utf-8") != TEST_CONTENT:
    test_path.write_text(TEST_CONTENT, encoding="utf-8")
    print("fixed: tests/test_execution_hardening.py")
else:
    print("already fixed: tests/test_execution_hardening.py")

print("phase2 complete")
