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
            f"{path}: expected exactly one old fragment, found {count}: {old[:180]!r}"
        )
    file.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"fixed: {path}")


# Matrix provenance excludes generated report files from git_dirty.
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
ensure_replace(
    "scripts/backtest_strategy_management_combinations.py",
    '''        "ranking": "total_return_desc_then_cagr_desc_then_strategy_management_asc",
        "evaluation_scope": "full_period",
''',
    '''        "ranking": "total_return_desc_then_cagr_desc_then_strategy_management_asc",
        "execution_missing_price_policy": "fail_closed_fresh_open_and_close_required",
        "buy_allocation_policy": "target_shares_at_market_open_then_common_scale_for_costs",
        "evaluation_scope": "full_period",
''',
)

# Global merge uses the exact same deterministic ranking key.
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

# Audit validates deterministic ordering and fail-closed execution policy.
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
    '''        "ranking_is_total_return_then_cagr_desc": sorted_as_declared,
        "all_numeric_metrics_are_finite": metrics_are_finite,
''',
    '''        "ranking_is_deterministic_total_return_cagr_names": sorted_as_declared,
        "execution_policy_is_fail_closed": (
            manifest.get("execution_missing_price_policy")
            == "fail_closed_fresh_open_and_close_required"
        ),
        "buy_allocation_policy_is_declared": (
            manifest.get("buy_allocation_policy")
            == "target_shares_at_market_open_then_common_scale_for_costs"
        ),
        "all_numeric_metrics_are_finite": metrics_are_finite,
''',
)

# Legacy research rebalance: target share counts are based on the market open, not
# the slipped fill price. If costs make the basket unaffordable, all intended buys
# are scaled together before execution instead of starving later tickers.
ensure_replace(
    "scripts/research_portfolio_allocation.py",
    '''        execution_price = _slipped_price(price, "SELL", slippage_rate)
        shares_to_sell = min(shares[ticker], (current_value - target_value) / execution_price)
        shares_to_sell = _floor_lot(shares_to_sell, lot_size)
''',
    '''        execution_price = _slipped_price(price, "SELL", slippage_rate)
        shares_to_sell = min(shares[ticker], (current_value - target_value) / price)
        shares_to_sell = _floor_lot(shares_to_sell, lot_size)
''',
)
ensure_replace(
    "scripts/research_portfolio_allocation.py",
    '''    for ticker, weight in target_weights.items():
        price = prices.get(ticker)
        if price is None or weight <= 0:
            continue
        execution_price = _slipped_price(price, "BUY", slippage_rate)
        current_value = shares[ticker] * price
        target_value = equity * weight
        desired_value = max(0.0, target_value - current_value)
        affordable_shares = cash / (execution_price * (1 + cost_rate)) if execution_price > 0 else 0.0
        shares_to_buy = min(desired_value / execution_price, affordable_shares)
        shares_to_buy = _floor_lot(shares_to_buy, lot_size)
        if shares_to_buy <= 0:
            continue
        cash -= shares_to_buy * execution_price * (1 + cost_rate)
        shares[ticker] += shares_to_buy
        traded_notional += shares_to_buy * execution_price
        trade_count += 1
''',
    '''    buy_plan: dict[str, float] = {}
    execution_prices: dict[str, float] = {}
    for ticker, weight in target_weights.items():
        price = prices.get(ticker)
        if price is None or weight <= 0:
            continue
        execution_price = _slipped_price(price, "BUY", slippage_rate)
        current_value = shares[ticker] * price
        target_value = equity * weight
        desired_shares = max(0.0, target_value - current_value) / price
        planned_shares = _floor_lot(desired_shares, lot_size)
        if planned_shares <= 0:
            continue
        buy_plan[ticker] = planned_shares
        execution_prices[ticker] = execution_price

    planned_cost = sum(
        quantity * execution_prices[ticker] * (1 + cost_rate)
        for ticker, quantity in buy_plan.items()
    )
    if planned_cost > cash + 1e-9 and planned_cost > 0:
        scale = max(0.0, min(1.0, cash / planned_cost))
        buy_plan = {
            ticker: _floor_lot(quantity * scale, lot_size)
            for ticker, quantity in buy_plan.items()
        }

    for ticker in sorted(buy_plan):
        shares_to_buy = buy_plan[ticker]
        if shares_to_buy <= 0:
            continue
        execution_price = execution_prices[ticker]
        debit = shares_to_buy * execution_price * (1 + cost_rate)
        if debit > cash + 1e-9:
            raise ValueError(
                f"{current_date}/{ticker}: plano proporcional excedeu o caixa disponivel."
            )
        cash -= debit
        shares[ticker] += shares_to_buy
        traded_notional += shares_to_buy * execution_price
        trade_count += 1
''',
)

# Realistic engine: truthful survivorship metadata and proportional multi-asset buy plan.
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

# Walk-forward works with the project's explicitly retrospective fixed/no-replacement
# universe, labels that limitation, and respects --end.
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

# Clean-clone pipeline downloads official archives by default and forwards --end.
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

TEST_CONTENT = r'''from __future__ import annotations

import gzip
import math
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
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
from b3_strategy_lab.strategies import build_signals, portfolio_strategies, strategy_parameters
from scripts.backtest_strategy_management_combinations import _ranking_key
from scripts.research_portfolio_allocation import PortfolioConfig, _rebalance, run_portfolio

ROOT = Path(__file__).resolve().parents[1]


def candle(day: str, ticker: str, price: float, *, volume: int = 1_000_000) -> Candle:
    return Candle(
        date=day,
        ticker=ticker,
        source_symbol=ticker,
        open=price,
        high=price * 1.01,
        low=price * 0.99,
        close=price,
        adj_close=price,
        volume=volume,
        raw_open=price,
        raw_high=price * 1.01,
        raw_low=price * 0.99,
        raw_close=price,
        adjustment_factor=1.0,
        raw_volume=volume,
        trades=100,
        financial_volume=float(volume) * price,
        market_type="010",
    )


def synthetic_candles(count: int = 1000) -> list[Candle]:
    start = date(2018, 1, 1)
    result = []
    for index in range(count):
        base = 100.0 + index * 0.03 + 4.0 * math.sin(index / 13.0) + 2.0 * math.sin(index / 37.0)
        open_price = base * (1.0 + 0.002 * math.sin(index / 5.0))
        high = max(base, open_price) * (1.01 + 0.002 * abs(math.sin(index / 11.0)))
        low = min(base, open_price) * (0.99 - 0.001 * abs(math.cos(index / 17.0)))
        volume = 1_000_000 + (index % 97) * 10_000
        day = (start + timedelta(days=index)).isoformat()
        result.append(
            Candle(
                date=day,
                ticker="TEST3",
                source_symbol="TEST3",
                open=open_price,
                high=high,
                low=low,
                close=base,
                adj_close=base,
                volume=volume,
                raw_open=open_price,
                raw_high=high,
                raw_low=low,
                raw_close=base,
                adjustment_factor=1.0,
                raw_volume=volume,
                trades=100 + index % 31,
                financial_volume=volume * base,
                market_type="010",
            )
        )
    return result


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

    def test_rebalance_scales_equal_targets_without_alphabetical_starvation(self) -> None:
        shares = {"AAA3": 0.0, "ZZZ3": 0.0}
        trades, _turnover, cash = _rebalance(
            "2024-01-02",
            ["AAA3", "ZZZ3"],
            {
                "AAA3": candle("2024-01-02", "AAA3", 10.0),
                "ZZZ3": candle("2024-01-02", "ZZZ3", 10.0),
            },
            {},
            shares,
            1000.0,
            {"AAA3": 0.5, "ZZZ3": 0.5},
            0.01,
            0.0,
            1,
        )
        self.assertEqual(trades, 2)
        self.assertEqual(shares["AAA3"], shares["ZZZ3"])
        self.assertEqual(shares["AAA3"], 49)
        self.assertGreaterEqual(cash, 0.0)

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
            run_portfolio(data, config, initial_cash=1000.0, lot_size=1, eligibility=eligibility)

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


class StrategyCausalityTests(unittest.TestCase):
    def test_every_portfolio_strategy_is_prefix_causal_and_deterministic(self) -> None:
        candles = synthetic_candles()
        catalog = portfolio_strategies()
        self.assertGreaterEqual(len(catalog), 190)
        for strategy in catalog:
            params = strategy_parameters(strategy)
            with self.subTest(strategy=strategy):
                prefix = candles[:800]
                one_more = candles[:801]
                first = build_signals(strategy, prefix, **params)
                repeated = build_signals(strategy, prefix, **params)
                extended = build_signals(strategy, one_more, **params)
                self.assertEqual(first, repeated)
                self.assertEqual(first, extended[: len(first)])


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


@unittest.skipIf((os.cpu_count() or 1) < 2, "parallel smoke requires at least 2 CPUs")
class MatrixParallelDeterminismTests(unittest.TestCase):
    def test_serial_and_parallel_small_matrix_are_identical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            serial = Path(directory) / "serial.csv.gz"
            parallel = Path(directory) / "parallel.csv.gz"
            common = [
                sys.executable,
                "scripts/backtest_strategy_management_combinations.py",
                "--strategies", "buy_and_hold", "gap_momentum",
                "--config-set", "base",
                "--start", "2024-01-02",
                "--end", "2024-06-28",
                "--initial-cash", "1000",
                "--lot-size", "1",
                "--top", "3",
            ]
            subprocess.run([*common, "--workers", "1", "--output", str(serial)], cwd=ROOT, check=True)
            subprocess.run([*common, "--workers", "2", "--output", str(parallel)], cwd=ROOT, check=True)
            self.assertEqual(serial.read_bytes(), parallel.read_bytes())
            serial_annual = serial.with_suffix("").with_suffix("").with_name("serial_top3_annual.md")
            parallel_annual = parallel.with_suffix("").with_suffix("").with_name("parallel_top3_annual.md")
            self.assertEqual(serial_annual.read_bytes(), parallel_annual.read_bytes())


if __name__ == "__main__":
    unittest.main()
'''

test_path = Path("tests/test_execution_hardening.py")
if not test_path.exists() or test_path.read_text(encoding="utf-8") != TEST_CONTENT:
    test_path.write_text(TEST_CONTENT, encoding="utf-8")
    print("fixed: tests/test_execution_hardening.py")
else:
    print("already fixed: tests/test_execution_hardening.py")

print("source hardening complete")
