from __future__ import annotations

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
