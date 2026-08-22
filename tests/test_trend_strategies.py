from __future__ import annotations

import math
import unittest
from datetime import date, timedelta

from b3_strategy_lab.candles import Candle
from b3_strategy_lab.strategies import build_signals, portfolio_strategies, strategy_parameters
from b3_strategy_lab.trend_strategies import TREND_STRATEGIES


def synthetic_candles(length: int = 440) -> list[Candle]:
    start = date(2022, 1, 3)
    candles: list[Candle] = []
    previous = 20.0
    for index in range(length):
        regime = 0.0016 if (index // 85) % 2 == 0 else -0.00035
        cycle = math.sin(index / 9.0) * 0.012 + math.sin(index / 31.0) * 0.006
        close = max(2.0, previous * (1.0 + regime + cycle))
        spread = 0.007 + 0.005 * abs(math.sin(index / 6.0))
        high = max(previous, close) * (1.0 + spread)
        low = min(previous, close) * (1.0 - spread)
        volume = int(90_000 + 45_000 * (1.0 + math.sin(index / 5.0)) + (index % 23) * 1_300)
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
                trades=200 + index,
                financial_volume=volume * close,
                market_type="010",
            )
        )
        previous = close
    return candles


class TrendStrategyTests(unittest.TestCase):
    def test_catalog_has_exactly_20_new_unique_trend_strategies(self) -> None:
        names = [item.name for item in TREND_STRATEGIES]
        self.assertEqual(len(names), 20)
        self.assertEqual(len(set(names)), 20)
        self.assertTrue(set(names) <= set(portfolio_strategies()))
        self.assertTrue(all(item.family == "tendencia" for item in TREND_STRATEGIES))

    def test_all_trend_strategies_run_with_documented_defaults(self) -> None:
        candles = synthetic_candles()
        for item in TREND_STRATEGIES:
            with self.subTest(strategy=item.name):
                signals = build_signals(
                    item.name,
                    candles,
                    **strategy_parameters(item.name),
                )
                self.assertEqual(len(signals), len(candles))
                self.assertTrue(all(signal in (0, 1) for signal in signals))

    def test_all_trend_strategies_are_prefix_causal(self) -> None:
        candles = synthetic_candles()
        for item in TREND_STRATEGIES:
            params = strategy_parameters(item.name)
            full = build_signals(item.name, candles, **params)
            for cutoff in (220, 320, 420):
                with self.subTest(strategy=item.name, cutoff=cutoff):
                    prefix = build_signals(item.name, candles[:cutoff], **params)
                    self.assertEqual(prefix, full[:cutoff])


if __name__ == "__main__":
    unittest.main()
