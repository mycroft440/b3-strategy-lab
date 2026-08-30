from __future__ import annotations

import math
import unittest
from argparse import Namespace
from datetime import date, timedelta
from unittest.mock import patch

from b3_strategy_lab.candles import Candle
from b3_strategy_lab.cli import _parameter_grid, _strategy_params_from_args, main
from b3_strategy_lab.researched_strategies import (
    RESEARCHED_STRATEGIES,
    _heikin_ashi_open_close,
    _high_pass,
    _weighted_four,
)
from b3_strategy_lab.strategies import build_signals, strategy_parameters


def candle(
    session: str,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: int = 1_000,
) -> Candle:
    return Candle(
        date=session,
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


def price_candles(closes: list[float]) -> list[Candle]:
    start = date(2024, 1, 1)
    result = []
    previous = closes[0]
    for index, close in enumerate(closes):
        open_ = previous
        result.append(
            candle(
                (start + timedelta(days=index)).isoformat(),
                open_,
                max(open_, close) + 0.5,
                min(open_, close) - 0.5,
                close,
                1_000 + index,
            )
        )
        previous = close
    return result


class ResearchedStrategyTests(unittest.TestCase):
    def test_catalog_contains_the_twelve_distinct_engines(self) -> None:
        expected = {
            "precision_trend_ehlers",
            "ultimate_oscillator_ehlers",
            "gap_momentum",
            "heikin_ashi_stochastic",
            "vortex_trend",
            "kama_trend",
            "frama_trend",
            "rvi_reversal",
            "chaikin_money_flow",
            "squeeze_breakout",
            "turtle_soup",
            "turn_of_month",
        }

        self.assertEqual({strategy.name for strategy in RESEARCHED_STRATEGIES}, expected)

    def test_ehlers_high_pass_matches_published_recurrence(self) -> None:
        values = [10.0, 11.0, 13.0, 12.0, 15.0]
        period = 20.0
        result = _high_pass(values, period)
        a1 = math.exp(-1.414 * math.pi / period)
        c2 = 2 * a1 * math.cos(1.414 * math.pi / period)
        c3 = -(a1**2)
        c1 = (1 + c2 - c3) / 4
        expected_three = c1 * (values[3] - 2 * values[2] + values[1])
        expected_four = c1 * (values[4] - 2 * values[3] + values[2]) + c2 * expected_three

        self.assertEqual(result[:3], [0.0, 0.0, 0.0])
        self.assertAlmostEqual(result[3], expected_three)
        self.assertAlmostEqual(result[4], expected_four)

    def test_gap_momentum_enters_on_rising_signal_and_exits_on_falling_signal(self) -> None:
        opens = [10.0, 11.0, 9.0, 12.0, 8.0, 13.0]
        candles = [
            candle(f"2024-01-{index + 1:02d}", open_, max(open_, 10.0), min(open_, 10.0), 10.0)
            for index, open_ in enumerate(opens)
        ]

        signals = build_signals("gap_momentum", candles, period=2, signal_period=2)

        self.assertEqual(signals, [0, 0, 0, 1, 1, 0])

    def test_heikin_ashi_uses_recursive_open(self) -> None:
        candles = [
            candle("2024-01-01", 10, 13, 9, 12),
            candle("2024-01-02", 12, 14, 10, 11),
        ]

        ha_open, ha_close = _heikin_ashi_open_close(candles)

        self.assertEqual(ha_open[0], 11)
        self.assertEqual(ha_close[0], 11)
        self.assertEqual(ha_open[1], 11)
        self.assertEqual(ha_close[1], 11.75)

    def test_vortex_follows_positive_then_negative_flow(self) -> None:
        candles = [
            candle("2024-01-01", 10, 11, 9, 10),
            candle("2024-01-02", 10, 12, 10, 11),
            candle("2024-01-03", 11, 13, 11, 12),
            candle("2024-01-04", 12, 12, 8, 9),
        ]

        signals = build_signals("vortex_trend", candles, period=2)

        self.assertEqual(signals, [0, 0, 1, 0])

    def test_kama_requires_price_and_average_to_rise(self) -> None:
        candles = price_candles([10, 11, 12, 13, 14, 8, 7])

        signals = build_signals(
            "kama_trend",
            candles,
            er_period=2,
            fast_period=2,
            slow_period=5,
        )

        self.assertEqual(signals, [0, 0, 0, 1, 1, 0, 0])

    def test_rvi_uses_symmetric_four_bar_weights(self) -> None:
        values = _weighted_four([1.0, 2.0, 3.0, 4.0])

        self.assertEqual(values[:3], [None, None, None])
        self.assertAlmostEqual(values[3], 2.5)

    def test_chaikin_enters_and_exits_on_zero_crosses(self) -> None:
        closes = [5, 0, 10, 10, 0, 0]
        candles = [
            candle(f"2024-01-{index + 1:02d}", close, 10, 0, close)
            for index, close in enumerate(closes)
        ]

        signals = build_signals("chaikin_money_flow", candles, period=2, trend_window=0)

        self.assertEqual(signals, [0, 0, 0, 1, 1, 0])

    def test_squeeze_enters_only_on_release_and_exits_below_middle(self) -> None:
        candles = [
            candle(f"2024-01-{index + 1:02d}", 10, 11, 9, 10)
            for index in range(5)
        ]
        candles.extend(
            [
                candle("2024-01-06", 10, 20, 10, 20),
                candle("2024-01-07", 20, 20, 13, 14),
            ]
        )

        signals = build_signals(
            "squeeze_breakout",
            candles,
            window=3,
            num_std=1,
            atr_period=2,
            keltner_mult=1,
            squeeze_bars=2,
            atr_mult=3,
        )

        self.assertEqual(signals, [0, 0, 0, 0, 0, 1, 0])

    def test_turtle_soup_confirms_false_break_and_honors_hold_limit(self) -> None:
        candles = [
            candle("2024-01-01", 10, 11, 9, 10),
            candle("2024-01-02", 10, 11, 9.5, 10.5),
            candle("2024-01-03", 10.5, 11.5, 10, 11),
            candle("2024-01-04", 9, 9.5, 8.5, 9.2),
            candle("2024-01-05", 9.2, 9.3, 8.6, 8.8),
            candle("2024-01-06", 8.8, 9, 8.6, 8.7),
        ]

        signals = build_signals(
            "turtle_soup",
            candles,
            lookback=3,
            sma_window=2,
            atr_period=2,
            stop_atr=0,
            hold_limit=2,
        )

        self.assertEqual(signals, [0, 0, 0, 1, 1, 0])

    def test_turn_of_month_targets_next_open_without_using_future_prices(self) -> None:
        sessions = [
            "2024-01-29",
            "2024-01-30",
            "2024-01-31",
            "2024-02-01",
            "2024-02-02",
            "2024-02-05",
            "2024-02-06",
        ]
        candles = [candle(session, 10, 11, 9, 10) for session in sessions]

        signals = build_signals(
            "turn_of_month", candles, session_calendar=sessions
        )

        self.assertEqual(signals, [0, 1, 1, 1, 1, 0, 0])
        self.assertEqual(
            build_signals(
                "turn_of_month",
                candles[:3],
                session_calendar=sessions,
            ),
            signals[:3],
        )

    def test_turn_of_month_is_prefix_causal_at_every_calendar_boundary(self) -> None:
        current = date(2023, 1, 2)
        final = date(2025, 1, 15)
        sessions = []
        while current <= final:
            if current.weekday() < 5:
                sessions.append(current.isoformat())
            current += timedelta(days=1)
        candles = [candle(session, 10, 11, 9, 10) for session in sessions]
        complete = build_signals(
            "turn_of_month", candles, session_calendar=sessions
        )

        boundary_prefixes = {
            index + 1
            for index in range(len(sessions) - 1)
            if sessions[index][:7] != sessions[index + 1][:7]
        }
        self.assertGreaterEqual(len(boundary_prefixes), 20)
        for prefix_length in sorted(boundary_prefixes):
            with self.subTest(prefix_length=prefix_length):
                prefix = build_signals(
                    "turn_of_month",
                    candles[:prefix_length],
                    session_calendar=sessions,
                )
                self.assertEqual(prefix, complete[:prefix_length])

    def test_price_based_strategies_do_not_rewrite_past_signals(self) -> None:
        closes = [100 + 0.04 * index + 4 * math.sin(index / 7) for index in range(320)]
        candles = price_candles(closes)
        session_calendar = [item.date for item in candles]

        for strategy in RESEARCHED_STRATEGIES:
            with self.subTest(strategy=strategy.name):
                params = strategy_parameters(strategy.name)
                complete = build_signals(
                    strategy.name,
                    candles,
                    session_calendar=session_calendar,
                    **params,
                )
                prefix = build_signals(
                    strategy.name,
                    candles[:-1],
                    session_calendar=session_calendar,
                    **params,
                )
                self.assertEqual(complete[:-1], prefix)

    def test_cli_sweep_falls_back_to_canonical_parameters(self) -> None:
        args = Namespace(strategy="frama_trend")

        self.assertEqual(list(_parameter_grid(args)), [strategy_parameters("frama_trend")])

    def test_cli_backtest_does_not_replace_strategy_specific_defaults(self) -> None:
        captured = {}

        def command(args: Namespace) -> int:
            captured.update(vars(args))
            return 0

        with patch("b3_strategy_lab.cli._backtest_command", side_effect=command):
            result = main(["backtest", "--strategy", "heikin_ashi_stochastic", "--tickers", "TEST3"])

        self.assertEqual(result, 0)
        self.assertIsNone(captured["lower"])
        self.assertIsNone(captured["upper"])
        self.assertIsNone(captured["window"])

    def test_cli_accepts_typed_strategy_specific_override(self) -> None:
        args = Namespace(strategy="frama_trend", strategy_param=["window=24"])

        params = _strategy_params_from_args(args)

        self.assertEqual(params["window"], 24)

    def test_cli_rejects_unknown_strategy_specific_override(self) -> None:
        args = Namespace(strategy="frama_trend", strategy_param=["unknown=24"])

        with self.assertRaisesRegex(ValueError, "Parametro desconhecido"):
            _strategy_params_from_args(args)

    def test_parameter_validation_rejects_invalid_adaptive_windows(self) -> None:
        candles = price_candles([10, 11, 12, 13])

        with self.assertRaisesRegex(ValueError, "window precisa ser par"):
            build_signals("frama_trend", candles, window=5)
        with self.assertRaisesRegex(ValueError, "fast_period precisa ser menor"):
            build_signals("kama_trend", candles, fast_period=30, slow_period=2)


if __name__ == "__main__":
    unittest.main()
