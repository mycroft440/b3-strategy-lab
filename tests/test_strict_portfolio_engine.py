from __future__ import annotations

import unittest
from types import SimpleNamespace

from scripts.backtest_strategy_management_strict import common_dates, rebalance_atomic


class StrictPortfolioEngineTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
