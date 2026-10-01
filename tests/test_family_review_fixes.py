from __future__ import annotations

import unittest

from b3_strategy_lab import additional_strategies as add
from b3_strategy_lab import smi_ergodic_strategies as smi
from b3_strategy_lab.strategies import build_signals, strategy_parameters
from tests.test_indicator_strategies import synthetic_candles


def _wilder_reference(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    current = sum(values[:period]) / period
    out[period - 1] = current
    for index in range(period, len(values)):
        current = (current * (period - 1) + values[index]) / period
        out[index] = current
    return out


def _adx_reference(candles, period: int) -> list[float | None]:
    tr, plus_dm, minus_dm = [candles[0].high - candles[0].low], [0.0], [0.0]
    for index in range(1, len(candles)):
        candle, previous = candles[index], candles[index - 1]
        up, down = candle.high - previous.high, previous.low - candle.low
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
        tr.append(max(candle.high - candle.low, abs(candle.high - previous.close), abs(candle.low - previous.close)))
    atr, plus, minus = (_wilder_reference(series, period) for series in (tr, plus_dm, minus_dm))
    dx = []
    for a, p, m in zip(atr, plus, minus):
        if a is None:
            continue
        pdi, mdi = 100 * p / a, 100 * m / a
        dx.append(100 * abs(pdi - mdi) / (pdi + mdi) if pdi + mdi else 0.0)
    adx = _wilder_reference(dx, period)
    return [None] * (len(candles) - len(dx)) + adx


class WilderAdxTest(unittest.TestCase):
    def test_additional_adx_is_wilders_adx(self) -> None:
        # Regression: the adx_trend and multi_indicator families averaged TR, DM and
        # DX with simple means, a different indicator from the ADX their thresholds
        # (15/20/25) refer to and from the project's own SMI Ergodic ADX.
        candles = synthetic_candles(400)
        mine, _plus, _minus = add._adx(candles, 14)
        reference = _adx_reference(candles, 14)
        project = smi._adx(candles, 14)
        for index in range(100, len(candles)):
            self.assertAlmostEqual(mine[index], reference[index], places=9)
            self.assertAlmostEqual(mine[index], project[index], places=9)


class PullbackArmingTest(unittest.TestCase):
    def _assert_armed_inside_current_trend(self, signals, oscillator, trend_ok, lower) -> int:
        entries = 0
        for index in range(1, len(signals)):
            if signals[index] == 1 and signals[index - 1] == 0:
                entries += 1
                start = index
                while start > 0 and trend_ok[start - 1] and signals[start - 1] == 0:
                    start -= 1
                window = range(start, index + 1)
                self.assertTrue(
                    any(oscillator[item] is not None and oscillator[item] <= lower for item in window),
                    f"entry at {index} was armed before the current trend began",
                )
        return entries

    def test_stochastic_pullback_must_belong_to_the_current_trend(self) -> None:
        # Regression: the arming survived trend breaks, so 12% of entries were
        # triggered by a pullback from a trend that had already ended.
        candles = synthetic_candles(1500)
        closes = [item.close for item in candles]
        for name in ("sma50_stochastic_14_20_80", "ema50_stochastic_21_30_75"):
            params = strategy_parameters(name)
            signals = build_signals(name, candles, **params)
            average = add._ema if params["average_type"] == "ema" else add._sma
            trend = average(closes, params["trend_window"])
            trend_ok = [value is not None and close > value for close, value in zip(closes, trend)]
            stochastic = add._stochastic(candles, params["k_period"])
            self.assertGreater(self._assert_armed_inside_current_trend(signals, stochastic, trend_ok, params["lower"]), 0, name)

    def test_supertrend_pullback_must_belong_to_the_current_uptrend(self) -> None:
        candles = synthetic_candles(1500)
        for name in ("supertrend_stochastic_21_4_21", "supertrend_rsi_10_2_14"):
            params = strategy_parameters(name)
            signals = build_signals(name, candles, **params)
            trend_ok = [value == 1 for value in add._supertrend(candles, params["atr_period"], params["atr_mult"])]
            oscillator = (
                add._stochastic(candles, params["oscillator_period"])
                if params["oscillator"] == "stochastic"
                else add._rsi([item.close for item in candles], params["oscillator_period"])
            )
            self.assertGreater(self._assert_armed_inside_current_trend(signals, oscillator, trend_ok, params["lower"]), 0, name)


if __name__ == "__main__":
    unittest.main()
