from __future__ import annotations

import unittest

from b3_strategy_lab.cli import _actions_for_candles
from b3_strategy_lab.candles import Candle, CorporateAction


def candle(day: str, open_: float, close: float) -> Candle:
    return Candle(
        date=day,
        ticker="TEST3",
        source_symbol="TEST3.SA",
        open=open_,
        high=max(open_, close),
        low=min(open_, close),
        close=close,
        adj_close=close,
        volume=1000,
        raw_open=open_,
        raw_high=max(open_, close),
        raw_low=min(open_, close),
        raw_close=close,
        adjustment_factor=1.0,
    )


class CliWindowTests(unittest.TestCase):
    def test_weekly_action_filter_keeps_actions_inside_last_weekly_candle(self) -> None:
        candles = [
            candle("2024-01-01", 100.0, 100.0),
            candle("2024-01-08", 100.0, 100.0),
        ]
        actions = [
            CorporateAction("2024-01-10", "TEST3", "TEST3.SA", dividend=1.0, split_ratio=1.0),
            CorporateAction("2024-01-15", "TEST3", "TEST3.SA", dividend=2.0, split_ratio=1.0),
        ]

        filtered = _actions_for_candles(actions, candles, "1wk")

        self.assertEqual([action.date for action in filtered], ["2024-01-10"])

    def test_daily_action_filter_stops_on_last_daily_candle(self) -> None:
        candles = [
            candle("2024-01-01", 100.0, 100.0),
            candle("2024-01-02", 100.0, 100.0),
        ]
        actions = [
            CorporateAction("2024-01-02", "TEST3", "TEST3.SA", dividend=1.0, split_ratio=1.0),
            CorporateAction("2024-01-03", "TEST3", "TEST3.SA", dividend=2.0, split_ratio=1.0),
        ]

        filtered = _actions_for_candles(actions, candles, "1d")

        self.assertEqual([action.date for action in filtered], ["2024-01-02"])


if __name__ == "__main__":
    unittest.main()
