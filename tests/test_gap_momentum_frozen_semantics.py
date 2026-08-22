from __future__ import annotations

import math
import unittest
from datetime import date, timedelta

from b3_strategy_lab.candles import Candle
from b3_strategy_lab.strategies import build_signals, strategy_parameters


def reference_gap_momentum(candles: list[Candle], period: int = 40, signal_period: int = 20) -> list[int]:
    """Independent reference for the frozen Perry Kaufman Gap Momentum contract."""
    gaps = [0.0]
    gaps.extend(candles[index].open - candles[index - 1].close for index in range(1, len(candles)))
    up = [max(value, 0.0) for value in gaps]
    down = [max(-value, 0.0) for value in gaps]

    ratios: list[float | None] = []
    for index in range(len(candles)):
        if index + 1 < period:
            ratios.append(None)
            continue
        up_sum = sum(up[index + 1 - period : index + 1])
        down_sum = sum(down[index + 1 - period : index + 1])
        ratios.append(1.0 if down_sum == 0 else 100.0 * up_sum / down_sum)

    signal: list[float | None] = []
    for index in range(len(ratios)):
        if index + 1 < signal_period:
            signal.append(None)
            continue
        sample = ratios[index + 1 - signal_period : index + 1]
        if any(value is None for value in sample):
            signal.append(None)
        else:
            signal.append(sum(float(value) for value in sample) / signal_period)

    position = 0
    previous: float | None = None
    result: list[int] = []
    for value in signal:
        if value is not None:
            if previous is not None:
                if value > previous:
                    position = 1
                elif value < previous:
                    position = 0
            previous = value
        result.append(position)
    return result


def synthetic_gap_candles(length: int = 180) -> list[Candle]:
    start = date(2021, 1, 4)
    candles: list[Candle] = []
    previous_close = 25.0
    for index in range(length):
        gap = 0.18 * math.sin(index / 4.0) + 0.07 * math.sin(index / 11.0)
        open_price = max(1.0, previous_close + gap)
        close = max(1.0, open_price * (1.0 + 0.003 * math.sin(index / 7.0)))
        high = max(open_price, close) + 0.12
        low = min(open_price, close) - 0.12
        volume = 100_000 + index * 137
        candles.append(
            Candle(
                date=(start + timedelta(days=index)).isoformat(),
                ticker="TEST3",
                source_symbol="TEST3.SA",
                open=open_price,
                high=high,
                low=low,
                close=close,
                adj_close=close,
                volume=volume,
                raw_open=open_price,
                raw_high=high,
                raw_low=low,
                raw_close=close,
                adjustment_factor=1.0,
                raw_volume=volume,
                trades=500 + index,
                financial_volume=volume * close,
                market_type="010",
            )
        )
        previous_close = close
    return candles


class FrozenGapMomentumSemanticsTests(unittest.TestCase):
    def test_runtime_defaults_remain_frozen_40_20(self) -> None:
        self.assertEqual(strategy_parameters("gap_momentum"), {"period": 40, "signal_period": 20})

    def test_runtime_matches_independent_reference_signal_by_signal(self) -> None:
        candles = synthetic_gap_candles()
        expected = reference_gap_momentum(candles, period=40, signal_period=20)
        actual = build_signals("gap_momentum", candles, period=40, signal_period=20)
        self.assertEqual(actual, expected)
        self.assertTrue(any(actual))
        self.assertTrue(any(signal == 0 for signal in actual[60:]))

    def test_frozen_signal_is_prefix_causal(self) -> None:
        candles = synthetic_gap_candles()
        full = build_signals("gap_momentum", candles, period=40, signal_period=20)
        for cutoff in (80, 120, 160):
            with self.subTest(cutoff=cutoff):
                prefix = build_signals("gap_momentum", candles[:cutoff], period=40, signal_period=20)
                self.assertEqual(prefix, full[:cutoff])


if __name__ == "__main__":
    unittest.main()
