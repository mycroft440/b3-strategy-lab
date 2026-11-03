"""RSI + WMA sobre Heikin Ashi com sinal de prioridade por medias 20/50.

Regras (sinal no fechamento, execucao na abertura seguinte pelo simulador):

- Entrada (compra): RSI do fechamento acima de ``rsi_entry`` e a WMA calculada
  sobre o fechamento Heikin Ashi apontando para cima (WMA[t] > WMA[t-1]).
  Alem disso, a propria WMA de 20 (Heikin Ashi) precisa estar acima da SMA de
  ``entry_sma`` pregoes do fechamento (padrao 200). Com
  ``entry_wma_above_sma=False`` o filtro compara o fechamento com a SMA (regra
  anterior) e com ``entry_sma=0`` o filtro e desligado. Apenas a WMA usa Heikin
  Ashi; RSI e SMAs usam o candle normal.
- Saida (venda): basta UM dos dois: RSI abaixo de ``rsi_exit`` (linha 50) ou a
  WMA Heikin Ashi apontando para baixo (WMA[t] < WMA[t-1]). A SMA200 so filtra
  a entrada; a WMA cair abaixo dela nao gera venda.
- Prioridade: quando ha sinal de compra e o preco de fechamento OU a SMA de 20
  esta acima da SMA de 50, o sinal e marcado como prioritario.

O pedido original diz "RSI acima de 0". Como o RSI classico vai de 0 a 100 e a
saida usa a linha 50, o padrao interpreta o criterio como RSI centralizado
(RSI - 50 > 0), isto e, RSI > 50. A leitura literal pode ser testada com
``rsi_entry=0``.
"""

from __future__ import annotations

import math

from .candles import Candle

# Variacao relativa da WMA abaixo deste limite e tratada como media estavel
# (nem subindo nem caindo), evitando sinais gerados por ruido de ponto flutuante.
SLOPE_TOLERANCE = 1e-12


def _rsi(values: list[float], period: int) -> list[float | None]:
    """RSI de Wilder, identico a ``strategies.rsi`` (copiado para evitar import circular)."""
    if period <= 0:
        raise ValueError("period precisa ser maior que zero.")
    result: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return result
    gains = [max(values[i] - values[i - 1], 0.0) for i in range(1, period + 1)]
    losses = [max(values[i - 1] - values[i], 0.0) for i in range(1, period + 1)]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    result[period] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    for index in range(period + 1, len(values)):
        change = values[index] - values[index - 1]
        avg_gain = (avg_gain * (period - 1) + max(change, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, 0.0)) / period
        result[index] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    return result


def heikin_ashi_close(candles: list[Candle]) -> list[float]:
    """Fechamento Heikin Ashi: (open + high + low + close) / 4, causal."""
    return [(c.open + c.high + c.low + c.close) / 4 for c in candles]


def wma(values: list[float], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("period precisa ser maior que zero.")
    denominator = period * (period + 1) / 2
    result: list[float | None] = [None] * len(values)
    for index in range(period - 1, len(values)):
        sample = values[index + 1 - period : index + 1]
        result[index] = sum((weight + 1) * value for weight, value in enumerate(sample)) / denominator
    return result


def sma(values: list[float], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("period precisa ser maior que zero.")
    # Soma exata de cada janela (math.fsum): uma soma acumulada introduz erro de
    # arredondamento e altera comparacoes de igualdade como fechamento == SMA50.
    result: list[float | None] = [None] * len(values)
    for index in range(period - 1, len(values)):
        result[index] = math.fsum(values[index + 1 - period : index + 1]) / period
    return result


def ha_wma_slope(candles: list[Candle], wma_period: int) -> list[int]:
    """+1 quando a WMA Heikin Ashi sobe, -1 quando cai, 0 sem dado/estavel."""
    values = wma(heikin_ashi_close(candles), wma_period)
    slope = [0] * len(candles)
    for index in range(1, len(candles)):
        current, previous = values[index], values[index - 1]
        if current is None or previous is None:
            continue
        change = current - previous
        if abs(change) <= SLOPE_TOLERANCE * max(abs(current), abs(previous)):
            continue
        slope[index] = 1 if change > 0 else -1
    return slope


def rsi_wma_heikin_ashi(
    candles: list[Candle],
    *,
    rsi_period: int = 14,
    rsi_entry: float = 50.0,
    rsi_exit: float = 50.0,
    wma_period: int = 20,
    entry_sma: int = 200,
    entry_wma_above_sma: bool = True,
) -> list[int]:
    closes = [c.close for c in candles]
    rsi_values = _rsi(closes, rsi_period)
    ha_wma = wma(heikin_ashi_close(candles), wma_period)
    slope = ha_wma_slope(candles, wma_period)
    trend = sma(closes, entry_sma) if entry_sma > 0 else [None] * len(closes)
    reference = ha_wma if entry_wma_above_sma else closes
    signals: list[int] = []
    position = 0
    for index in range(len(candles)):
        value = rsi_values[index]
        if value is None:
            signals.append(0)
            continue
        level = reference[index]
        above_sma = entry_sma <= 0 or (
            trend[index] is not None and level is not None and level > trend[index]
        )
        if position == 0 and value > rsi_entry and slope[index] > 0 and above_sma:
            position = 1
        elif position == 1 and (value < rsi_exit or slope[index] < 0):
            position = 0
        signals.append(position)
    return signals


def priority_flags(
    candles: list[Candle],
    *,
    fast_period: int = 20,
    slow_period: int = 50,
) -> list[int]:
    """1 quando fechamento ou SMA rapida esta acima da SMA lenta."""
    closes = [c.close for c in candles]
    fast = sma(closes, fast_period)
    slow = sma(closes, slow_period)
    flags: list[int] = []
    for index, close in enumerate(closes):
        s = slow[index]
        f = fast[index]
        flags.append(int(s is not None and (close > s or (f is not None and f > s))))
    return flags
