from __future__ import annotations

from b3_strategy_lab.candles import Candle
from b3_strategy_lab.extensions import build_indicator
from b3_strategy_lab import research_indicators as _research_indicators  # noqa: F401


def _candle(index: int, *, close: float, volume: int, raw_volume: int | None = None, factor: float = 1.0) -> Candle:
    raw_close = close / factor
    return Candle(
        date=f"2026-01-{index + 1:02d}",
        ticker="TEST3",
        source_symbol="TEST3",
        open=close - 0.5,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        adj_close=close,
        volume=volume,
        raw_open=(close - 0.5) / factor,
        raw_high=(close + 1.0) / factor,
        raw_low=(close - 1.0) / factor,
        raw_close=raw_close,
        adjustment_factor=factor,
        raw_volume=volume if raw_volume is None else raw_volume,
        trades=10,
        financial_volume=(volume if raw_volume is None else raw_volume) * raw_close,
    )


def test_registered_volume_indicators_return_aligned_series() -> None:
    candles = [_candle(i, close=100 + i, volume=1000 + 10 * i) for i in range(30)]
    for name in (
        "typical_price",
        "money_flow_index",
        "chaikin_money_flow",
        "elder_force_index",
        "ease_of_movement",
        "negative_volume_index",
        "realized_volatility",
    ):
        values = build_indicator(name, candles)
        assert len(values) == len(candles)


def test_mfi_uses_split_normalized_volume_consistently() -> None:
    before = [_candle(i, close=50 + i, volume=2000 + i * 20, raw_volume=1000 + i * 10, factor=0.5) for i in range(20)]
    after = [_candle(i, close=50 + i, volume=2000 + i * 20, raw_volume=2000 + i * 20, factor=1.0) for i in range(20)]
    assert build_indicator("money_flow_index", before) == build_indicator("money_flow_index", after)


def test_negative_volume_index_changes_only_when_volume_falls() -> None:
    candles = [
        _candle(0, close=100, volume=1000),
        _candle(1, close=110, volume=1200),
        _candle(2, close=121, volume=900),
    ]
    values = build_indicator("negative_volume_index", candles)
    assert values[0] == 1000.0
    assert values[1] == 1000.0
    assert round(values[2] or 0.0, 10) == 1100.0
