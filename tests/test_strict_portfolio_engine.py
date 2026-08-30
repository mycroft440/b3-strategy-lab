from __future__ import annotations

import unittest
from types import SimpleNamespace

from scripts.backtest_strategy_management_strict import (
    common_dates,
    rebalance_atomic,
    run_strict,
)
from scripts.research_portfolio_allocation import PortfolioConfig


class StrictPortfolioEngineTests(unittest.TestCase):
    def test_rejects_invalid_economic_assumptions_before_loading_dates(self) -> None:
        data = SimpleNamespace(tickers=[])
        config = PortfolioConfig(name="validation")
        defaults = {
            "initial_cash": 100.0,
            "cost_bps": 0.0,
            "slippage_bps": 0.0,
            "lot_size": 1,
        }
        invalid_cases = (
            ("initial_cash", 0.0),
            ("initial_cash", float("nan")),
            ("cost_bps", -1.0),
            ("cost_bps", float("inf")),
            ("slippage_bps", -1.0),
            ("slippage_bps", float("nan")),
            ("slippage_bps", 10_000.0),
            ("lot_size", -1),
        )
        for field, value in invalid_cases:
            with self.subTest(field=field, value=value):
                assumptions = {**defaults, field: value}
                with self.assertRaises(ValueError):
                    run_strict(
                        data,
                        config,
                        start="2024-01-01",
                        end="2024-01-02",
                        eligibility={},
                        **assumptions,
                    )

    def test_missing_target_open_rolls_back_entire_rebalance(self) -> None:
        shares = {"AAA3": 10.0, "BBB3": 0.0}
        candles = {"AAA3": SimpleNamespace(open=10.0, close=10.5)}
        before = dict(shares)

        cash, trades, _turnover, _fees, _slip, ok, reason, ledger = rebalance_atomic(
            "2024-01-08",
            ["AAA3", "BBB3"],
            candles,
            shares,
            100.0,
            {"BBB3": 1.0},
            0.0003,
            0.001,
            1,
        )

        self.assertFalse(ok)
        self.assertIn("BBB3", reason)
        self.assertEqual(shares, before)
        self.assertEqual(cash, 100.0)
        self.assertEqual(trades, 0)
        self.assertEqual(ledger, [])

    def test_missing_held_open_rolls_back_entire_rebalance(self) -> None:
        shares = {"AAA3": 10.0, "BBB3": 0.0}
        candles = {"BBB3": SimpleNamespace(open=20.0, close=20.5)}
        before = dict(shares)

        result = rebalance_atomic(
            "2024-01-08",
            ["AAA3", "BBB3"],
            candles,
            shares,
            100.0,
            {"BBB3": 1.0},
            0.0003,
            0.001,
            1,
        )

        self.assertFalse(result[5])
        self.assertEqual(shares, before)
        self.assertEqual(result[0], 100.0)

    def test_valid_top1_rotation_keeps_cash_nonnegative(self) -> None:
        shares = {"AAA3": 10.0, "BBB3": 0.0}
        candles = {
            "AAA3": SimpleNamespace(open=10.0, close=10.0),
            "BBB3": SimpleNamespace(open=20.0, close=20.0),
        }

        cash, trades, _turnover, fees, slip, ok, reason, ledger = rebalance_atomic(
            "2024-01-08",
            ["AAA3", "BBB3"],
            candles,
            shares,
            0.0,
            {"BBB3": 1.0},
            0.0003,
            0.001,
            1,
        )

        self.assertTrue(ok, reason)
        self.assertEqual(shares["AAA3"], 0.0)
        self.assertGreater(shares["BBB3"], 0.0)
        self.assertGreaterEqual(cash, -1e-8)
        self.assertEqual(trades, len(ledger))
        self.assertGreater(fees, 0.0)
        self.assertGreater(slip, 0.0)

    def test_common_dates_use_intersection_not_union(self) -> None:
        data = SimpleNamespace(
            tickers=["AAA3", "BBB3"],
            by_date={
                "AAA3": {"2024-01-02": object(), "2024-01-03": object()},
                "BBB3": {"2024-01-03": object(), "2024-01-04": object()},
            },
        )

        self.assertEqual(common_dates(data), ["2024-01-03"])

    def test_strategy_signal_changes_execute_next_open_between_rebalances(self) -> None:
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
        candles = {
            value_date: SimpleNamespace(open=price, close=price)
            for value_date, price in zip(dates, prices)
        }
        data = SimpleNamespace(
            tickers=["AAA3"],
            by_date={"AAA3": candles},
            index_by_date={
                "AAA3": {value_date: index for index, value_date in enumerate(dates)}
            },
            signal_prices={"AAA3": prices},
            raw_returns={
                "AAA3": [
                    0.0,
                    *[
                        prices[index] / prices[index - 1] - 1.0
                        for index in range(1, len(prices))
                    ],
                ]
            },
            candidate_profile_cache={},
        )
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

        summary, ledger = run_strict(
            data,
            config,
            start="2024-01-02",
            end="2024-01-05",
            initial_cash=100.0,
            cost_bps=0.0,
            slippage_bps=0.0,
            lot_size=1,
            eligibility=eligibility,
            collect_trades=True,
        )

        self.assertEqual(summary.trades, 3)
        self.assertEqual(
            [(row["date"], row["side"]) for row in ledger],
            [
                ("2024-01-02", "BUY"),
                ("2024-01-04", "SELL"),
                ("2024-01-05", "BUY"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
