from __future__ import annotations

import math
import unittest
from datetime import date, timedelta

from b3_strategy_lab.candles import Candle
from b3_strategy_lab.smi_ergodic_strategies import (
    SMI_ERGODIC_STRATEGIES,
    smi_ergodic_components,
    smi_ergodic_crossover,
)
from b3_strategy_lab.strategies import build_signals, portfolio_strategies, strategy_parameters


def _candles(count: int = 360) -> list[Candle]:
    start = date(2020, 1, 1)
    result: list[Candle] = []
    for index in range(count):
        close = 100.0 + 0.08 * index + 4.0 * math.sin(index / 8.0) + 1.5 * math.sin(index / 2.7)
        open_ = close - 0.15 * math.sin(index / 3.0)
        high = max(open_, close) + 1.0 + 0.1 * math.sin(index)
        low = min(open_, close) - 1.0 - 0.1 * math.cos(index)
        volume = 100_000 + (index % 17) * 12_000
        result.append(
            Candle(
                date=(start + timedelta(days=index)).isoformat(),
                ticker="TEST3",
                source_symbol="TEST3.SA",
                open=open_,
                high=high,
                low=low,
                close=close,
                adj_close=close,
                volume=volume,
                raw_open=open_,
                raw_high=high,
                raw_low=low,
                raw_close=close,
                adjustment_factor=1.0,
            )
        )
    return result


class SMIErgodicStrategyTests(unittest.TestCase):
    def test_catalog_contains_exactly_fifteen_unique_smi_strategies(self) -> None:
        names = [item.name for item in SMI_ERGODIC_STRATEGIES]
        self.assertEqual(len(names), 15)
        self.assertEqual(len(set(names)), 15)
        self.assertTrue(all(name.startswith("smi_ergodic_") for name in names))
        catalog = set(portfolio_strategies())
        self.assertTrue(set(names).issubset(catalog))

    def test_all_strategies_are_binary_and_match_candle_count(self) -> None:
        candles = _candles()
        for item in SMI_ERGODIC_STRATEGIES:
            with self.subTest(strategy=item.name):
                signals = build_signals(item.name, candles, **strategy_parameters(item.name))
                self.assertEqual(len(signals), len(candles))
                self.assertLessEqual(set(signals), {0, 1})

    def test_default_warmup_does_not_emit_crossover_positions(self) -> None:
        signals = smi_ergodic_crossover(_candles(100))
        self.assertEqual(signals[:20], [0] * 20)

    def test_components_are_prefix_causal(self) -> None:
        candles = _candles(220)
        full = smi_ergodic_components(candles, long_period=20, short_period=5, signal_period=5)
        for prefix_size in (60, 100, 160, 220):
            prefix = smi_ergodic_components(
                candles[:prefix_size],
                long_period=20,
                short_period=5,
                signal_period=5,
            )
            for full_series, prefix_series in zip(full, prefix):
                expected = full_series[prefix_size - 1]
                actual = prefix_series[-1]
                if expected is None:
                    self.assertIsNone(actual)
                else:
                    self.assertIsNotNone(actual)
                    assert actual is not None
                    self.assertAlmostEqual(actual, expected, places=12)

    def test_crossover_reacts_to_a_clear_momentum_reversal(self) -> None:
        start = date(2021, 1, 1)
        closes = [160.0 - index for index in range(80)] + [80.0 + 1.4 * index for index in range(100)]
        candles: list[Candle] = []
        for index, close in enumerate(closes):
            candles.append(
                Candle(
                    date=(start + timedelta(days=index)).isoformat(),
                    ticker="TEST3",
                    source_symbol="TEST3.SA",
                    open=close,
                    high=close + 1.0,
                    low=close - 1.0,
                    close=close,
                    adj_close=close,
                    volume=150_000,
                    raw_open=close,
                    raw_high=close + 1.0,
                    raw_low=close - 1.0,
                    raw_close=close,
                    adjustment_factor=1.0,
                )
            )
        signals = smi_ergodic_crossover(candles, long_period=10, short_period=3, signal_period=3)
        self.assertFalse(any(signals[25:75]))
        self.assertTrue(any(signals[85:]))

    def test_invalid_core_periods_fail_closed(self) -> None:
        candles = _candles(50)
        with self.assertRaises(ValueError):
            smi_ergodic_components(candles, long_period=5, short_period=5, signal_period=3)
        with self.assertRaises(ValueError):
            smi_ergodic_components(candles, long_period=20, short_period=5, signal_period=0)


if __name__ == "__main__":
    unittest.main()
