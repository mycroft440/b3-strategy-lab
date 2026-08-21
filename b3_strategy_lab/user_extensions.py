"""Extensoes locais carregadas automaticamente pelo catalogo.

Este modulo e o ponto de entrada para estrategias/indicadores que nao precisam
alterar o registro central. As extensoes abaixo foram escolhidas porque usam
somente informacao historica disponivel nos candles diarios verificados e podem
ser executadas causalmente no fechamento, com ordem apenas na abertura seguinte.

Estrategias que exigem fundamentos point-in-time, cadeia historica de opcoes,
eventos com timestamp ou livro de ofertas nao pertencem a este modulo: adicionar
um sinal sem esses dados produziria um backtest enganoso.
"""

from __future__ import annotations

import math
import statistics

from .candles import Candle
from .extensions import indicator, strategy


def _validate_lookback(lookback: int, *, name: str) -> None:
    if lookback <= 0:
        raise ValueError(f"{name} precisa ser maior que zero.")


def _lagged_return_values(
    candles: list[Candle],
    *,
    lookback: int,
    skip: int = 0,
) -> list[float | None]:
    """Retorno causal encerrado ``skip`` sessoes antes do candle atual."""

    _validate_lookback(lookback, name="lookback")
    if skip < 0:
        raise ValueError("skip nao pode ser negativo.")

    closes = [float(candle.close) for candle in candles]
    values: list[float | None] = []
    for index in range(len(closes)):
        recent_index = index - skip
        past_index = recent_index - lookback
        if past_index < 0 or recent_index < 0:
            values.append(None)
            continue
        recent = closes[recent_index]
        past = closes[past_index]
        if recent <= 0 or past <= 0 or not math.isfinite(recent) or not math.isfinite(past):
            values.append(None)
            continue
        values.append(recent / past - 1.0)
    return values


@indicator("momentum_12_1")
def momentum_12_1(
    candles: list[Candle],
    lookback: int = 252,
    skip: int = 21,
) -> list[float | None]:
    """Retorno de aproximadamente 12 meses excluindo o ultimo mes."""

    return _lagged_return_values(candles, lookback=lookback, skip=skip)


@indicator("tsmom_ensemble_score")
def tsmom_ensemble_score(
    candles: list[Candle],
    short_window: int = 63,
    medium_window: int = 126,
    long_window: int = 252,
) -> list[float | None]:
    """Media dos retornos anualizados de 3/6/12 meses, usando apenas o passado."""

    windows = (short_window, medium_window, long_window)
    for window in windows:
        _validate_lookback(window, name="window")
    if len(set(windows)) != len(windows):
        raise ValueError("As janelas do ensemble precisam ser distintas.")
    if not short_window < medium_window < long_window:
        raise ValueError("Use short_window < medium_window < long_window.")

    per_window = [
        _lagged_return_values(candles, lookback=window)
        for window in windows
    ]
    result: list[float | None] = []
    for index in range(len(candles)):
        returns = [series[index] for series in per_window]
        if any(value is None for value in returns):
            result.append(None)
            continue
        annualized = [
            (1.0 + float(value)) ** (252.0 / window) - 1.0
            if float(value) > -1.0
            else -1.0
            for value, window in zip(returns, windows)
        ]
        result.append(statistics.mean(annualized))
    return result


@indicator("realized_volatility_63")
def realized_volatility_63(
    candles: list[Candle],
    window: int = 63,
) -> list[float | None]:
    """Volatilidade historica anualizada, sem usar o retorno do futuro."""

    if window <= 1:
        raise ValueError("window precisa ser maior que 1.")
    closes = [float(candle.close) for candle in candles]
    returns: list[float | None] = [None]
    for index in range(1, len(closes)):
        previous = closes[index - 1]
        current = closes[index]
        returns.append(current / previous - 1.0 if previous > 0 and current > 0 else None)

    result: list[float | None] = []
    for index in range(len(candles)):
        if index < window:
            result.append(None)
            continue
        sample = returns[index - window + 1 : index + 1]
        if any(value is None for value in sample):
            result.append(None)
            continue
        numeric = [float(value) for value in sample if value is not None]
        result.append(statistics.stdev(numeric) * math.sqrt(252.0))
    return result


@strategy(
    "absolute_momentum_12_1",
    family="momentum",
    description=(
        "Momentum absoluto 12-1: fica elegivel quando o retorno de 252 sessoes, "
        "encerrado 21 sessoes antes, e positivo."
    ),
)
def absolute_momentum_12_1(
    candles: list[Candle],
    lookback: int = 252,
    skip: int = 21,
) -> list[int]:
    values = momentum_12_1(candles, lookback=lookback, skip=skip)
    return [int(value is not None and value > 0.0) for value in values]


@strategy(
    "time_series_momentum_3_6_12",
    family="momentum",
    description=(
        "Time-series momentum multi-horizonte: fica comprado quando pelo menos "
        "dois dos retornos de 63, 126 e 252 sessoes sao positivos."
    ),
)
def time_series_momentum_3_6_12(
    candles: list[Candle],
    short_window: int = 63,
    medium_window: int = 126,
    long_window: int = 252,
    min_positive: int = 2,
) -> list[int]:
    windows = (short_window, medium_window, long_window)
    for window in windows:
        _validate_lookback(window, name="window")
    if not short_window < medium_window < long_window:
        raise ValueError("Use short_window < medium_window < long_window.")
    if min_positive < 1 or min_positive > len(windows):
        raise ValueError("min_positive precisa estar entre 1 e 3.")

    returns = [
        _lagged_return_values(candles, lookback=window)
        for window in windows
    ]
    signals: list[int] = []
    for index in range(len(candles)):
        values = [series[index] for series in returns]
        if any(value is None for value in values):
            signals.append(0)
            continue
        positives = sum(float(value) > 0.0 for value in values if value is not None)
        signals.append(int(positives >= min_positive))
    return signals
