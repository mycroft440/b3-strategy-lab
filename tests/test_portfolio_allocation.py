from __future__ import annotations

import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from b3_strategy_lab.candles import Candle
from b3_strategy_lab.strategies import portfolio_strategies
from scripts.backtest_strategy_management_combinations import (
    DEFAULT_UNIVERSE_MANIFEST,
    _build_eligibility,
    _load_universe,
    _yearly_returns as matrix_yearly_returns,
)
from scripts.research_portfolio_allocation import (
    MarketData,
    PortfolioConfig,
    _configs,
    _target_weights,
    _yearly_returns,
    run_portfolio,
)


def candle(day: str, ticker: str, price: float) -> Candle:
    return Candle(
        date=day,
        ticker=ticker,
        source_symbol=f"{ticker}.SA",
        open=price,
        high=price,
        low=price,
        close=price,
        adj_close=price,
        volume=1_000,
        raw_open=price,
        raw_high=price,
        raw_low=price,
        raw_close=price,
        adjustment_factor=1.0,
    )


def market_data() -> MarketData:
    data = MarketData.__new__(MarketData)
    data.tickers = ["FAST3", "SLOW3"]
    fast = [
        candle("2024-01-01", "FAST3", 10.0),
        candle("2024-01-02", "FAST3", 11.0),
        candle("2024-01-03", "FAST3", 14.0),
        candle("2024-01-04", "FAST3", 15.0),
    ]
    slow = [
        candle("2024-01-01", "SLOW3", 10.0),
        candle("2024-01-02", "SLOW3", 10.5),
        candle("2024-01-03", "SLOW3", 11.0),
        candle("2024-01-04", "SLOW3", 11.5),
    ]
    data.interval = "1d"
    data.signal_mode = "raw"
    data.candles = {"FAST3": fast, "SLOW3": slow}
    data.by_date = {
        ticker: {item.date: item for item in items}
        for ticker, items in data.candles.items()
    }
    data.index_by_date = {
        ticker: {item.date: index for index, item in enumerate(items)}
        for ticker, items in data.candles.items()
    }
    data.signal_prices = {
        ticker: [item.raw_close for item in items]
        for ticker, items in data.candles.items()
    }
    data.raw_returns = {
        ticker: [
            0.0,
            *[
                items[index].raw_close / items[index - 1].raw_close - 1
                for index in range(1, len(items))
            ],
        ]
        for ticker, items in data.candles.items()
    }
    data.dates = [item.date for item in fast]
    data.candidate_profile_cache = {}
    return data


class PortfolioCombinationTests(unittest.TestCase):
    def test_yearly_returns_use_prior_year_end_as_next_year_start(self) -> None:
        dates = ["2020-12-31", "2021-01-04", "2021-12-30"]
        equities = [100.0, 110.0, 121.0]

        portfolio_returns = _yearly_returns(equities, dates, 100.0)
        self.assertAlmostEqual(portfolio_returns[2020], 0.0)
        self.assertAlmostEqual(portfolio_returns[2021], 0.21)
        curve = [
            type("Point", (), {"date": day, "equity": equity})()
            for day, equity in zip(dates, equities)
        ]
        matrix_returns = matrix_yearly_returns(curve, 100.0)
        self.assertAlmostEqual(matrix_returns[2020], 0.0)
        self.assertAlmostEqual(matrix_returns[2021], 0.21)

    def test_market_data_cuts_all_indicator_history_at_verified_start(self) -> None:
        candles = [
            candle("2023-12-29", "FAST3", 9.0),
            candle("2024-01-02", "FAST3", 10.0),
            candle("2024-01-03", "FAST3", 11.0),
        ]
        with patch(
            "scripts.research_portfolio_allocation.load_verified_candles",
            return_value=(candles[1:], object()),
        ) as loader:
            data = MarketData(
                ["FAST3"],
                "1d",
                "adjusted",
                require_verified_splits_from="2024-01-01",
                history_start="2024-01-01",
            )

        loader.assert_called_once_with(
            "FAST3",
            "1d",
            start="2024-01-01",
            require_verified_splits_from="2024-01-01",
        )
        self.assertEqual(data.dates, ["2024-01-02", "2024-01-03"])

    def test_default_universe_discloses_selection_and_survivorship_bias(self) -> None:
        universe = _load_universe(DEFAULT_UNIVERSE_MANIFEST)

        self.assertEqual(universe["selected_as_of"], "2018-01-02")
        self.assertEqual(universe["warmup_start"], "2017-01-01")
        self.assertFalse(universe["survivorship_safe"])
        self.assertEqual(len(universe["tickers"]), 40)
        self.assertEqual(len(universe["original_tickers"]), 10)
        self.assertEqual(len(universe["added_tickers"]), 30)
        self.assertTrue(set(universe["original_tickers"]).issubset(universe["tickers"]))

    def test_full_matrix_cli_does_not_advertise_unused_train_ratio(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                "scripts/backtest_strategy_management_combinations.py",
                "--help",
            ],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertNotIn("--train-ratio", result.stdout)

    def test_full_matrix_cli_rejects_duplicate_strategies_before_loading_data(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                "scripts/backtest_strategy_management_combinations.py",
                "--strategies",
                "buy_and_hold",
                "buy_and_hold",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Estrategias duplicadas", result.stderr)

    def test_full_matrix_cli_rejects_nonfinite_money_inputs(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                "scripts/backtest_strategy_management_combinations.py",
                "--initial-cash",
                "nan",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--initial-cash precisa ser maior que zero", result.stderr)

    def test_full_matrix_cli_rejects_slippage_that_makes_sell_price_nonpositive(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                "scripts/backtest_strategy_management_combinations.py",
                "--slippage-bps",
                "10000",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("menor que 10000", result.stderr)

    def test_catalog_has_478_management_strategies(self) -> None:
        configs = _configs("raw", "all")
        self.assertEqual(len(configs), 478)
        self.assertEqual(len({config.name for config in configs}), 478)

    def test_default_matrix_really_exceeds_one_hundred_thousand_pairs(self) -> None:
        strategies = portfolio_strategies()
        configs = _configs("adjusted", "all")
        self.assertGreaterEqual(len(strategies), 234)
        self.assertGreater(len(strategies) * len(configs), 100_000)
        self.assertEqual(len(strategies), len(set(strategies)))
        self.assertEqual(len(configs), len({config.name for config in configs}))

    def test_default_matrix_includes_buy_and_hold(self) -> None:
        self.assertIn("buy_and_hold", portfolio_strategies())

    def test_buy_and_hold_preserves_pure_management_result(self) -> None:
        data = market_data()
        config = PortfolioConfig(
            name="equal",
            lookback=1,
            top_n=99,
            vol_window=2,
            rebalance="daily",
            score="all",
            weighting="equal",
            absolute_momentum=False,
            signal_mode="raw",
        )
        eligibility = _build_eligibility(data, ["buy_and_hold"], "raw")[
            "buy_and_hold"
        ]

        unrestricted = run_portfolio(
            data,
            config,
            initial_cash=100.0,
            lot_size=0,
        )
        buy_and_hold = run_portfolio(
            data,
            config,
            initial_cash=100.0,
            lot_size=0,
            eligibility=eligibility,
        )

        self.assertEqual(buy_and_hold, unrestricted)

    def test_eligibility_never_uses_history_before_verified_warmup(self) -> None:
        data = market_data()

        eligibility = _build_eligibility(
            data,
            ["buy_and_hold"],
            "adjusted",
            signal_start="2024-01-03",
        )["buy_and_hold"]

        self.assertEqual(eligibility["FAST3"], [0, 0, 1, 1])
        self.assertEqual(eligibility["SLOW3"], [0, 0, 1, 1])

    def test_target_weights_rank_only_eligible_tickers(self) -> None:
        data = market_data()
        config = PortfolioConfig(
            name="test",
            lookback=1,
            top_n=1,
            vol_window=2,
            score="momentum",
            weighting="equal",
            absolute_momentum=True,
            signal_mode="raw",
        )

        unrestricted = _target_weights(data, "2024-01-03", config)
        restricted = _target_weights(
            data,
            "2024-01-03",
            config,
            eligible_tickers={"SLOW3"},
        )

        self.assertEqual(unrestricted, {"FAST3": 1.0})
        self.assertEqual(restricted, {"SLOW3": 1.0})

    def test_run_portfolio_uses_trading_strategy_as_eligibility_filter(self) -> None:
        data = market_data()
        config = PortfolioConfig(
            name="equal",
            lookback=1,
            top_n=99,
            vol_window=2,
            rebalance="daily",
            score="all",
            weighting="equal",
            absolute_momentum=False,
            signal_mode="raw",
        )
        eligibility = {
            "FAST3": [0, 0, 0, 0],
            "SLOW3": [1, 1, 1, 1],
        }

        summary, curve = run_portfolio(
            data,
            config,
            initial_cash=100.0,
            cost_bps=0.0,
            slippage_bps=0.0,
            lot_size=0,
            eligibility=eligibility,
        )

        self.assertGreater(summary.exposure, 0)
        self.assertTrue(
            all("FAST3" not in point.selected for point in curve),
        )
        self.assertTrue(any("SLOW3" in point.selected for point in curve))
        self.assertTrue(all(point.dividend_cash == 0.0 for point in curve))

    def test_strategy_exit_and_reentry_execute_at_next_open_between_rebalances(self) -> None:
        data = MarketData.__new__(MarketData)
        data.tickers = ["AAA3"]
        data.interval = "1d"
        data.signal_mode = "adjusted"
        dates = [
            "2023-12-27",
            "2023-12-28",
            "2023-12-29",
            "2024-01-02",
            "2024-01-03",
            "2024-01-04",
            "2024-01-05",
        ]
        prices = [10.0, 11.0, 13.0, 14.0, 15.0, 16.0, 17.0]
        candles = [
            candle(value_date, "AAA3", price)
            for value_date, price in zip(dates, prices)
        ]
        data.candles = {"AAA3": candles}
        data.by_date = {"AAA3": {item.date: item for item in candles}}
        data.index_by_date = {
            "AAA3": {item.date: index for index, item in enumerate(candles)}
        }
        data.signal_prices = {"AAA3": prices}
        data.raw_returns = {
            "AAA3": [
                0.0,
                *[
                    prices[index] / prices[index - 1] - 1.0
                    for index in range(1, len(prices))
                ],
            ]
        }
        data.dates = dates
        data.candidate_profile_cache = {}

        config = PortfolioConfig(
            name="monthly_signal_contract",
            lookback=1,
            top_n=1,
            vol_window=2,
            rebalance="monthly",
            score="all",
            weighting="equal",
            absolute_momentum=False,
            signal_mode="adjusted",
        )
        eligibility = {"AAA3": [0, 0, 1, 1, 0, 1, 1]}

        summary, curve = run_portfolio(
            data,
            config,
            start="2024-01-02",
            end="2024-01-05",
            initial_cash=100.0,
            cost_bps=0.0,
            slippage_bps=0.0,
            lot_size=1,
            eligibility=eligibility,
        )

        self.assertEqual(
            [point.selected for point in curve],
            ["AAA3", "AAA3", "", "AAA3"],
        )
        # Three strategy/management trades plus the mandatory terminal liquidation.
        self.assertEqual(summary.trades, 4)

    def test_portfolio_executes_and_marks_on_split_normalized_prices(self) -> None:
        data = market_data()
        data.candles = {
            ticker: [
                replace(
                    item,
                    raw_open=item.open * 100,
                    raw_high=item.high * 100,
                    raw_low=item.low * 100,
                    raw_close=item.close * 100,
                    adjustment_factor=0.01,
                )
                for item in items
            ]
            for ticker, items in data.candles.items()
        }
        data.by_date = {
            ticker: {item.date: item for item in items}
            for ticker, items in data.candles.items()
        }
        config = PortfolioConfig(
            name="equal",
            lookback=1,
            top_n=99,
            vol_window=2,
            rebalance="daily",
            score="all",
            weighting="equal",
            absolute_momentum=False,
            signal_mode="adjusted",
        )

        summary, _curve = run_portfolio(
            data,
            config,
            initial_cash=100.0,
            lot_size=1,
        )

        self.assertGreater(summary.exposure, 0.0)


if __name__ == "__main__":
    unittest.main()
