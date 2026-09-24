from __future__ import annotations

import math
import unittest

from b3_strategy_lab.additional_strategies import _cci, _cci_trend, _sma
from b3_strategy_lab.strategies import build_signals, strategy_parameters
from tests.test_indicator_strategies import synthetic_candles


def _transitions(signals: list[int]) -> list[tuple[int, int]]:
    return [(index, signals[index]) for index in range(1, len(signals)) if signals[index] != signals[index - 1]]


class CciTrendSignalTest(unittest.TestCase):
    def setUp(self) -> None:
        self.candles = synthetic_candles(400)
        self.closes = [item.close for item in self.candles]

    def test_pullback_setup_buys_weakness_and_sells_strength(self) -> None:
        cci = _cci(self.candles, 14)
        trend = _sma(self.closes, 50)
        signals = _cci_trend(self.candles, period=14, entry_level=-100.0, exit_level=100.0, trend_window=50)

        transitions = _transitions(signals)
        self.assertTrue(any(value == 1 for _, value in transitions))
        for index, value in transitions:
            trend_ok = self.closes[index] > trend[index]
            if value == 1:
                self.assertTrue(trend_ok)
                self.assertLessEqual(cci[index], -100.0)
            else:
                self.assertTrue(not trend_ok or cci[index] >= 100.0)

    def test_pullback_setup_does_not_flip_every_session(self) -> None:
        # Regression: momentum comparisons with entry=-100 < exit=100 re-entered on
        # any CCI >= -100 and left on the next CCI <= 100, alternating 1, 0, 1, 0.
        for name in ("cci_trend_10_m100_100_sma50", "cci_trend_14_m100_100_sma100"):
            signals = build_signals(name, self.candles, **strategy_parameters(name))
            alternations = sum(
                1
                for index in range(2, len(signals))
                if signals[index - 2] == signals[index] != signals[index - 1]
            )
            self.assertLess(alternations, max(1, len(_transitions(signals)) // 4), name)

    def test_momentum_setup_keeps_breakout_comparisons(self) -> None:
        cci = _cci(self.candles, 10)
        trend = _sma(self.closes, 50)
        signals = _cci_trend(self.candles, period=10, entry_level=0.0, exit_level=-100.0, trend_window=50)

        transitions = _transitions(signals)
        self.assertTrue(any(value == 1 for _, value in transitions))
        for index, value in transitions:
            trend_ok = self.closes[index] > trend[index]
            if value == 1:
                self.assertTrue(trend_ok)
                self.assertGreaterEqual(cci[index], 0.0)
            else:
                self.assertTrue(not trend_ok or cci[index] <= -100.0)


if __name__ == "__main__":
    unittest.main()
