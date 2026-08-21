from __future__ import annotations

import unittest
from dataclasses import replace

from b3_strategy_lab.candles import Candle
from b3_strategy_lab.extensions import available_indicators, build_indicator
from b3_strategy_lab.strategies import available_strategies, build_signals


def _candles(closes: list[float]) -> list[Candle]:
    result = []
    for index, close in enumerate(closes):
        result.append(
            Candle(
                date=f"2020-01-{(index % 28) + 1:02d}T{index:04d}",
                ticker="TEST3",
                source_symbol="TEST3",
                open=close,
                high=close * 1.01,
                low=close * 0.99,
                close=close,
                adj_close=close,
                volume=1_000_000,
                raw_open=close,
                raw_high=close * 1.01,
                raw_low=close * 0.99,
                raw_close=close,
                adjustment_factor=1.0,
                raw_volume=1_000_000,
                trades=1_000,
                financial_volume=close * 1_000_000,
            )
        )
    return result


class ResearchExtensionTests(unittest.TestCase):
    def test_research_extensions_are_auto_registered(self) -> None:
        self.assertIn("momentum_12_1", available_indicators())
        self.assertIn("tsmom_ensemble_score", available_indicators())
        self.assertIn("realized_volatility_63", available_indicators())
        self.assertIn("absolute_momentum_12_1", available_strategies())
        self.assertIn("time_series_momentum_3_6_12", available_strategies())

    def test_absolute_momentum_12_1_uses_only_lagged_information(self) -> None:
        candles = _candles([100.0 + index for index in range(320)])
        original = build_signals("absolute_momentum_12_1", candles)

        changed = list(candles)
        changed[-1] = replace(changed[-1], close=1_000_000.0)
        mutated = build_signals("absolute_momentum_12_1", changed)

        # skip=21: o candle atual nao pode alterar o sinal 12-1 atual.
        self.assertEqual(original[-1], 1)
        self.assertEqual(mutated[-1], 1)
        self.assertEqual(original[:-1], mutated[:-1])

    def test_time_series_momentum_ensemble_requires_majority_positive(self) -> None:
        rising = _candles([100.0 + index for index in range(320)])
        falling = _candles([500.0 - index for index in range(320)])

        self.assertEqual(build_signals("time_series_momentum_3_6_12", rising)[-1], 1)
        self.assertEqual(build_signals("time_series_momentum_3_6_12", falling)[-1], 0)

    def test_time_series_momentum_does_not_rewrite_past_signals(self) -> None:
        candles = _candles([100.0 + index for index in range(320)])
        original = build_signals("time_series_momentum_3_6_12", candles)
        changed = list(candles)
        changed[-1] = replace(changed[-1], close=1.0)
        mutated = build_signals("time_series_momentum_3_6_12", changed)
        self.assertEqual(original[:-1], mutated[:-1])

    def test_indicator_lengths_and_warmups(self) -> None:
        candles = _candles([100.0 + index * 0.1 for index in range(320)])

        mom = build_indicator("momentum_12_1", candles)
        tsmom = build_indicator("tsmom_ensemble_score", candles)
        vol = build_indicator("realized_volatility_63", candles)

        self.assertEqual(len(mom), len(candles))
        self.assertEqual(len(tsmom), len(candles))
        self.assertEqual(len(vol), len(candles))
        self.assertIsNone(mom[272])
        self.assertIsNotNone(mom[273])
        self.assertIsNone(tsmom[251])
        self.assertIsNotNone(tsmom[252])
        self.assertIsNone(vol[62])
        self.assertIsNotNone(vol[63])

    def test_invalid_time_series_parameters_fail_fast(self) -> None:
        candles = _candles([100.0 + index for index in range(320)])
        with self.assertRaises(ValueError):
            build_signals(
                "time_series_momentum_3_6_12",
                candles,
                short_window=126,
                medium_window=63,
                long_window=252,
            )
        with self.assertRaises(ValueError):
            build_signals("absolute_momentum_12_1", candles, skip=-1)


if __name__ == "__main__":
    unittest.main()
