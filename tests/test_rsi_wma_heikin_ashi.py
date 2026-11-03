from __future__ import annotations

import unittest

from b3_strategy_lab.rsi_wma_heikin_ashi import (
    _rsi,
    heikin_ashi_close,
    priority_flags,
    rsi_wma_heikin_ashi,
    wma,
)
from b3_strategy_lab.strategies import STRATEGIES, build_signals, rsi, strategy_parameters
from tests.test_trend_strategies import synthetic_candles


class RsiWmaHeikinAshiTests(unittest.TestCase):
    def test_registered_with_default_parameters(self) -> None:
        self.assertIn("rsi_wma_heikin_ashi", STRATEGIES)
        self.assertEqual(
            strategy_parameters("rsi_wma_heikin_ashi"),
            {"rsi_period": 14, "rsi_entry": 50.0, "rsi_exit": 50.0, "wma_period": 20},
        )

    def test_rsi_matches_catalog_rsi(self) -> None:
        closes = [candle.close for candle in synthetic_candles()]
        self.assertEqual(_rsi(closes, 14), rsi(closes, 14))

    def test_wma_weights_recent_values_more(self) -> None:
        self.assertEqual(wma([1.0, 2.0, 3.0], 3), [None, None, (1 + 4 + 9) / 6])

    def test_signal_follows_entry_and_exit_rules(self) -> None:
        candles = synthetic_candles()
        signals = build_signals("rsi_wma_heikin_ashi", candles)
        self.assertEqual(len(signals), len(candles))
        self.assertTrue(set(signals) <= {0, 1})
        self.assertIn(1, signals)
        closes = [candle.close for candle in candles]
        rsi_values = _rsi(closes, 14)
        ha_wma = wma(heikin_ashi_close(candles), 20)
        for index in range(1, len(candles)):
            if rsi_values[index] is None or ha_wma[index - 1] is None:
                self.assertEqual(signals[index], 0)
                continue
            rising = ha_wma[index] > ha_wma[index - 1]
            falling = ha_wma[index] < ha_wma[index - 1]
            if signals[index - 1] == 0 and signals[index] == 1:
                self.assertTrue(rsi_values[index] > 50 and rising)
            if signals[index - 1] == 1 and signals[index] == 0:
                self.assertTrue(rsi_values[index] < 50 or falling)
            if signals[index] == 1:
                self.assertFalse(rsi_values[index] < 50 or falling)

    def test_signal_and_priority_are_causal(self) -> None:
        candles = synthetic_candles()
        full = rsi_wma_heikin_ashi(candles)
        flags = priority_flags(candles)
        for cut in (30, 120, 260, 400):
            self.assertEqual(rsi_wma_heikin_ashi(candles[:cut]), full[:cut])
            self.assertEqual(priority_flags(candles[:cut]), flags[:cut])

    def test_priority_uses_price_or_sma20_above_sma50(self) -> None:
        candles = synthetic_candles()
        flags = priority_flags(candles)
        closes = [candle.close for candle in candles]
        for index in range(len(candles)):
            if index < 49:
                self.assertEqual(flags[index], 0)
                continue
            sma50 = sum(closes[index - 49 : index + 1]) / 50
            sma20 = sum(closes[index - 19 : index + 1]) / 20
            expected = int(closes[index] > sma50 or sma20 > sma50)
            self.assertEqual(flags[index], expected)


if __name__ == "__main__":
    unittest.main()
