from __future__ import annotations

import unittest
from datetime import date, timedelta

from b3_strategy_lab.additional_strategies import ADDITIONAL_STRATEGIES
from b3_strategy_lab.candles import Candle
from b3_strategy_lab.extended_strategies import EXTENDED_STRATEGIES
from b3_strategy_lab.researched_strategies import RESEARCHED_STRATEGIES
from b3_strategy_lab.strategies import (
    STRATEGIES,
    STRATEGY_INFO,
    build_signals,
    strategy_parameters,
    sweep_strategies,
)


def candle(day: int, open_: float, high: float, low: float, close: float, volume: int = 1000) -> Candle:
    return Candle(
        date=f"2024-01-{day:02d}",
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


class StrategyInterfaceTests(unittest.TestCase):
    def test_complete_catalog_preserves_168_and_adds_21_buy_strategies(self) -> None:
        self.assertEqual(len(ADDITIONAL_STRATEGIES), 130)
        self.assertEqual(len(RESEARCHED_STRATEGIES), 12)
        self.assertEqual(len(EXTENDED_STRATEGIES), 21)
        self.assertEqual(len(sweep_strategies()), 189)

        groups = [
            {strategy.name for strategy in ADDITIONAL_STRATEGIES},
            {strategy.name for strategy in RESEARCHED_STRATEGIES},
            {strategy.name for strategy in EXTENDED_STRATEGIES},
        ]
        self.assertTrue(all(group <= set(STRATEGIES) for group in groups))
        self.assertFalse(groups[0] & groups[1])
        self.assertFalse(groups[0] & groups[2])
        self.assertFalse(groups[1] & groups[2])

    def test_public_strategies_have_metadata_and_sweep_coverage(self) -> None:
        public = set(STRATEGIES) - {"sma"}

        self.assertEqual(set(STRATEGY_INFO), public)
        self.assertEqual(set(sweep_strategies()), public - {"buy_and_hold"})

    def test_new_strategies_return_binary_signal_for_each_candle(self) -> None:
        candles = [
            candle(1, 10, 11, 9, 10),
            candle(2, 10, 12, 9, 9.2),
            candle(3, 9.3, 10, 8.8, 8.9),
            candle(4, 9, 11, 8.9, 10.8),
            candle(5, 10.9, 12, 10.8, 11.8),
            candle(6, 11.9, 13, 11.6, 12.8),
            candle(7, 12.7, 14, 12.5, 13.9),
            candle(8, 13.8, 15, 13.7, 14.8),
        ]
        strategies = [
            ("ibs_reversion", {"ibs_lower": 0.3, "ibs_upper": 0.7, "max_hold": 3, "trend_window": 0}),
            (
                "rsi_ibs_reversion",
                {
                    "rsi_period": 2,
                    "lower": 30,
                    "upper": 70,
                    "ibs_lower": 0.4,
                    "ibs_upper": 0.8,
                    "trend_window": 0,
                    "max_hold": 3,
                },
            ),
            (
                "rsi2_trend_reversion",
                {"rsi_period": 2, "lower": 30, "upper": 70, "trend_window": 0, "sma_window": 3, "max_hold": 3},
            ),
            (
                "down_streak_reversion",
                {"streak_length": 2, "ibs_lower": 0.4, "ibs_upper": 0.8, "trend_window": 0, "max_hold": 3},
            ),
            (
                "range_expansion_breakout",
                {
                    "range_mult": 0.5,
                    "atr_period": 3,
                    "atr_mult": 2,
                    "trend_window": 0,
                    "volume_window": 0,
                    "volume_mult": 0,
                    "max_hold": 3,
                },
            ),
            (
                "chandelier_breakout",
                {"lookback": 3, "atr_period": 3, "atr_mult": 2, "volume_window": 0, "volume_mult": 0},
            ),
            ("supertrend_follow", {"atr_period": 3, "atr_mult": 2}),
            (
                "keltner_breakout",
                {"window": 3, "atr_period": 3, "atr_mult": 1.5, "exit_z": 0, "trend_window": 0},
            ),
        ]

        for strategy, params in strategies:
            with self.subTest(strategy=strategy):
                signals = build_signals(strategy, candles, **params)
                self.assertEqual(len(signals), len(candles))
                self.assertTrue(all(signal in (0, 1) for signal in signals))

    def test_time_series_momentum_anchors_lookback_to_current_candle(self) -> None:
        start = date(2024, 1, 1)
        closes = [100.0] * 274
        closes[0] = 200.0  # t-273: the old implementation incorrectly used this candle.
        closes[21] = 40.0  # t-252: documented lookback reference.
        closes[252] = 50.0  # t-21: recent price after skipping one month.
        candles = [
            Candle(
                date=(start + timedelta(days=index)).isoformat(),
                ticker="TEST3",
                source_symbol="TEST3.SA",
                open=close,
                high=close,
                low=close,
                close=close,
                adj_close=close,
                volume=1_000,
                raw_open=close,
                raw_high=close,
                raw_low=close,
                raw_close=close,
                adjustment_factor=1.0,
            )
            for index, close in enumerate(closes)
        ]

        signals = build_signals(
            "time_series_momentum_12m",
            candles,
            **strategy_parameters("time_series_momentum_12m"),
        )

        self.assertEqual(signals[-1], 1)

    def test_every_strategy_runs_with_its_documented_parameters(self) -> None:
        start = date(2022, 1, 1)
        candles = []
        price = 20.0
        for index in range(500):
            drift = 0.0008 + 0.012 * ((index % 31) - 15) / 15
            next_price = max(1.0, price * (1 + drift))
            candles.append(
                Candle(
                    date=(start + timedelta(days=index)).isoformat(),
                    ticker="TEST3",
                    source_symbol="TEST3.SA",
                    open=price,
                    high=max(price, next_price) * 1.01,
                    low=min(price, next_price) * 0.99,
                    close=next_price,
                    adj_close=next_price,
                    volume=1_000 + index * 7,
                    raw_open=price,
                    raw_high=max(price, next_price) * 1.01,
                    raw_low=min(price, next_price) * 0.99,
                    raw_close=next_price,
                    adjustment_factor=1.0,
                )
            )
            price = next_price

        for strategy in sweep_strategies():
            with self.subTest(strategy=strategy):
                signals = build_signals(
                    strategy,
                    candles,
                    **strategy_parameters(strategy),
                )
                self.assertEqual(len(signals), len(candles))
                self.assertTrue(all(signal in (0, 1) for signal in signals))


if __name__ == "__main__":
    unittest.main()
