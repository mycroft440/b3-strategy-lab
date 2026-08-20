from __future__ import annotations

import math
import unittest
from argparse import Namespace
from datetime import date, timedelta

from b3_strategy_lab.candles import Candle
from b3_strategy_lab.cli import _strategy_params_from_args
from b3_strategy_lab.extended_strategies import EXTENDED_STRATEGIES
from b3_strategy_lab.strategies import build_signals, strategy_parameters


def candle(
    index: int,
    close: float,
    *,
    high: float | None = None,
    low: float | None = None,
    volume: int = 1_000,
) -> Candle:
    session = date(2024, 1, 1) + timedelta(days=index)
    high = close + 0.4 if high is None else high
    low = close - 0.4 if low is None else low
    return Candle(
        date=session.isoformat(),
        ticker="TEST3",
        source_symbol="TEST3.SA",
        open=close,
        high=high,
        low=low,
        close=close,
        adj_close=close,
        volume=volume,
        raw_open=close,
        raw_high=high,
        raw_low=low,
        raw_close=close,
        adjustment_factor=1.0,
    )


def rich_market_candles(length: int = 620) -> list[Candle]:
    start = date(2020, 1, 1)
    result: list[Candle] = []
    previous = 100.0
    for index in range(length):
        close = max(5.0, 100 + 0.025 * index + 9 * math.sin(index / 9) + 5 * math.sin(index / 31))
        open_ = previous * (1 + 0.006 * math.sin(index / 5))
        spread = 0.008 + 0.006 * (1 + math.sin(index / 13))
        high = max(open_, close) * (1 + spread)
        low = min(open_, close) * (1 - spread)
        volume = max(1_000, int(1_000_000 * (1 + 0.45 * math.sin(index / 7) + 0.2 * math.cos(index / 19))))
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
        previous = close
    return result


class ExtendedStrategyTests(unittest.TestCase):
    def test_catalog_contains_exactly_the_twenty_one_new_engines(self) -> None:
        expected = {
            "fisher_transform_reversal",
            "laguerre_rsi_reversal",
            "ichimoku_cloud",
            "parabolic_sar_trend",
            "aroon_trend",
            "trix_signal",
            "schaff_trend_cycle",
            "coppock_curve",
            "know_sure_thing",
            "true_strength_index",
            "awesome_oscillator",
            "choppiness_breakout",
            "elder_force_index",
            "ease_of_movement",
            "negative_volume_index",
            "klinger_volume_oscillator",
            "mass_index_reversal",
            "vertical_horizontal_filter",
            "nr7_breakout",
            "inside_bar_breakout",
            "halloween_effect",
        }

        self.assertEqual({strategy.name for strategy in EXTENDED_STRATEGIES}, expected)

    def test_every_new_engine_has_observable_entries_and_exits(self) -> None:
        candles = rich_market_candles()

        for strategy in EXTENDED_STRATEGIES:
            with self.subTest(strategy=strategy.name):
                signals = build_signals(strategy.name, candles, **strategy_parameters(strategy.name))
                changes = sum(left != right for left, right in zip(signals, signals[1:]))
                self.assertEqual(len(signals), len(candles))
                self.assertTrue(all(signal in (0, 1) for signal in signals))
                self.assertIn(1, signals)
                self.assertGreaterEqual(changes, 2)

    def test_price_engines_do_not_rewrite_past_signals(self) -> None:
        candles = rich_market_candles()

        for strategy in EXTENDED_STRATEGIES:
            with self.subTest(strategy=strategy.name):
                complete = build_signals(strategy.name, candles, **strategy_parameters(strategy.name))
                prefix = build_signals(strategy.name, candles[:-1], **strategy_parameters(strategy.name))
                self.assertEqual(complete[:-1], prefix)

    def test_parabolic_sar_flips_in_both_directions(self) -> None:
        closes = [10, 11, 12, 8, 7, 11, 12]
        highs = [11, 12, 13, 9, 8, 12, 13]
        lows = [9, 10, 11, 7, 6, 10, 11]
        candles = [candle(index, close, high=highs[index], low=lows[index]) for index, close in enumerate(closes)]

        signals = build_signals("parabolic_sar_trend", candles)

        self.assertEqual(signals, [0, 1, 1, 0, 0, 0, 1])

    def test_aroon_uses_the_most_recent_extreme_on_ties(self) -> None:
        candles = [candle(index, close) for index, close in enumerate([10, 11, 12, 11, 10, 9, 8])]

        signals = build_signals("aroon_trend", candles, period=2, strong_level=70)

        self.assertEqual(signals, [0, 0, 1, 0, 0, 0, 0])

    def test_negative_volume_index_ignores_a_high_volume_collapse(self) -> None:
        closes = [10, 11, 12, 6, 3]
        volumes = [100, 90, 80, 100, 90]
        candles = [candle(index, close, volume=volumes[index]) for index, close in enumerate(closes)]

        signals = build_signals("negative_volume_index", candles, ema_period=2)

        self.assertEqual(signals, [0, 1, 1, 1, 0])

    def test_vertical_horizontal_filter_enters_trend_then_exits_flat_regime(self) -> None:
        candles = [candle(index, close) for index, close in enumerate([1, 2, 3, 4, 4, 4, 4])]

        signals = build_signals(
            "vertical_horizontal_filter",
            candles,
            period=3,
            entry_level=0.6,
            exit_level=0.2,
            trend_window=2,
        )

        self.assertEqual(signals, [0, 0, 0, 1, 1, 0, 0])

    def test_nr7_breakout_uses_setup_high_and_low(self) -> None:
        closes = [10, 10, 10, 12, 8]
        highs = [12, 11.5, 10.5, 13, 9]
        lows = [8, 8.5, 9.5, 11, 7]
        candles = [candle(index, close, high=highs[index], low=lows[index]) for index, close in enumerate(closes)]

        signals = build_signals(
            "nr7_breakout",
            candles,
            setup_period=3,
            expiry=3,
            atr_period=2,
            atr_mult=100,
            hold_limit=10,
        )

        self.assertEqual(signals, [0, 0, 0, 1, 0])

    def test_inside_bar_breakout_uses_mother_bar_boundaries(self) -> None:
        closes = [10, 10, 13, 9]
        highs = [12, 11, 14, 10]
        lows = [8, 9, 12, 8]
        candles = [candle(index, close, high=highs[index], low=lows[index]) for index, close in enumerate(closes)]

        signals = build_signals(
            "inside_bar_breakout",
            candles,
            expiry=3,
            atr_period=2,
            atr_mult=100,
            hold_limit=10,
        )

        self.assertEqual(signals, [0, 0, 1, 0])

    def test_halloween_effect_targets_the_next_session_open(self) -> None:
        sessions = ["2024-10-31", "2024-11-01", "2025-04-30", "2025-05-02", "2025-10-31", "2025-11-03"]
        candles = []
        for index, session in enumerate(sessions):
            item = candle(index, 10)
            candles.append(Candle(**{**item.__dict__, "date": session}))

        signals = build_signals("halloween_effect", candles)

        self.assertEqual(signals, [1, 1, 0, 0, 1, 1])

        prefix = build_signals("halloween_effect", candles[:-1])
        self.assertEqual(prefix, signals[:-1])

    def test_invalid_indicator_contracts_are_rejected(self) -> None:
        candles = [candle(0, 10), candle(1, 11)]

        with self.assertRaisesRegex(ValueError, "tenkan_period"):
            build_signals("ichimoku_cloud", candles, tenkan_period=30, kijun_period=20)
        with self.assertRaisesRegex(ValueError, "fast_period"):
            build_signals("schaff_trend_cycle", candles, fast_period=60, slow_period=50)
        with self.assertRaisesRegex(ValueError, "trigger_level"):
            build_signals("mass_index_reversal", candles, bulge_level=26, trigger_level=27)

    def test_cli_records_canonical_and_overridden_new_parameters(self) -> None:
        canonical = _strategy_params_from_args(Namespace(strategy="ichimoku_cloud", strategy_param=[]))
        overridden = _strategy_params_from_args(
            Namespace(strategy="ichimoku_cloud", strategy_param=["displacement=20"])
        )

        self.assertEqual(canonical, strategy_parameters("ichimoku_cloud"))
        self.assertEqual(overridden["displacement"], 20)
        self.assertEqual(overridden["tenkan_period"], 9)


if __name__ == "__main__":
    unittest.main()
