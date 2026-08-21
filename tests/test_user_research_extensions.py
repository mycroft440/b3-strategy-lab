from __future__ import annotations

from dataclasses import replace

import pytest

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


def test_research_extensions_are_auto_registered() -> None:
    assert "momentum_12_1" in available_indicators()
    assert "tsmom_ensemble_score" in available_indicators()
    assert "realized_volatility_63" in available_indicators()
    assert "absolute_momentum_12_1" in available_strategies()
    assert "time_series_momentum_3_6_12" in available_strategies()


def test_absolute_momentum_12_1_uses_only_lagged_information() -> None:
    candles = _candles([100.0 + index for index in range(320)])
    original = build_signals("absolute_momentum_12_1", candles)

    changed = list(candles)
    changed[-1] = replace(changed[-1], close=1_000_000.0)
    mutated = build_signals("absolute_momentum_12_1", changed)

    # skip=21: the current candle cannot affect the current 12-1 signal.
    assert original[-1] == mutated[-1] == 1
    assert original[:-1] == mutated[:-1]


def test_time_series_momentum_ensemble_requires_majority_positive() -> None:
    rising = _candles([100.0 + index for index in range(320)])
    falling = _candles([500.0 - index for index in range(320)])

    assert build_signals("time_series_momentum_3_6_12", rising)[-1] == 1
    assert build_signals("time_series_momentum_3_6_12", falling)[-1] == 0


def test_indicator_lengths_and_warmups() -> None:
    candles = _candles([100.0 + index * 0.1 for index in range(320)])

    mom = build_indicator("momentum_12_1", candles)
    tsmom = build_indicator("tsmom_ensemble_score", candles)
    vol = build_indicator("realized_volatility_63", candles)

    assert len(mom) == len(tsmom) == len(vol) == len(candles)
    assert mom[272] is None
    assert mom[273] is not None
    assert tsmom[251] is None
    assert tsmom[252] is not None
    assert vol[62] is None
    assert vol[63] is not None


def test_invalid_time_series_parameters_fail_fast() -> None:
    candles = _candles([100.0 + index for index in range(320)])
    with pytest.raises(ValueError):
        build_signals(
            "time_series_momentum_3_6_12",
            candles,
            short_window=126,
            medium_window=63,
            long_window=252,
        )
    with pytest.raises(ValueError):
        build_signals("absolute_momentum_12_1", candles, skip=-1)
