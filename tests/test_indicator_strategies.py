from __future__ import annotations

import math
import unittest
from datetime import date, timedelta

from b3_strategy_lab.candles import Candle
from b3_strategy_lab.indicator_strategies import INDICATOR_STRATEGIES
from b3_strategy_lab.strategies import build_signals, portfolio_strategies, strategy_parameters


def synthetic_candles(length: int = 260) -> list[Candle]:
    start = date(2023, 1, 2)
    candles: list[Candle] = []
    previous = 25.0
    for index in range(length):
        cycle = math.sin(index / 7.0) * 0.025 + math.sin(index / 23.0) * 0.012
        drift = 0.0005 + cycle
        close = max(2.0, previous * (1.0 + drift))
        spread = 0.008 + 0.006 * abs(math.sin(index / 5.0))
        high = max(previous, close) * (1.0 + spread)
        low = min(previous, close) * (1.0 - spread)
        volume = int(80_000 + 55_000 * (1.0 + math.sin(index / 4.0)) + (index % 17) * 1_700)
        candles.append(
            Candle(
                date=(start + timedelta(days=index)).isoformat(),
                ticker="TEST3",
                source_symbol="TEST3.SA",
                open=previous,
                high=high,
                low=low,
                close=close,
                adj_close=close,
                volume=volume,
                raw_open=previous,
                raw_high=high,
                raw_low=low,
                raw_close=close,
                adjustment_factor=1.0,
                raw_volume=volume,
                trades=100 + index,
                financial_volume=volume * close,
                market_type="010",
            )
        )
        previous = close
    return candles


class IndicatorStrategyTests(unittest.TestCase):
    def test_catalog_has_exactly_24_new_unique_strategies(self) -> None:
        names = [item.name for item in INDICATOR_STRATEGIES]
        self.assertEqual(len(names), 24)
        self.assertEqual(len(set(names)), 24)
        self.assertTrue(set(names) <= set(portfolio_strategies()))

    def test_all_new_strategies_run_with_documented_defaults(self) -> None:
        candles = synthetic_candles()
        for item in INDICATOR_STRATEGIES:
            with self.subTest(strategy=item.name):
                signals = build_signals(
                    item.name,
                    candles,
                    **strategy_parameters(item.name),
                )
                self.assertEqual(len(signals), len(candles))
                self.assertTrue(all(signal in (0, 1) for signal in signals))

    def test_all_new_strategies_are_prefix_causal(self) -> None:
        candles = synthetic_candles()
        for item in INDICATOR_STRATEGIES:
            params = strategy_parameters(item.name)
            full = build_signals(item.name, candles, **params)
            for cutoff in (90, 150, 220):
                with self.subTest(strategy=item.name, cutoff=cutoff):
                    prefix = build_signals(item.name, candles[:cutoff], **params)
                    self.assertEqual(prefix, full[:cutoff])


if __name__ == "__main__":
    unittest.main()
