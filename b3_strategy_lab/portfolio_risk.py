from __future__ import annotations

import math
import statistics
from typing import Any


def _return_map(data: Any, ticker: str) -> dict[str, float]:
    cache = getattr(data, "portfolio_return_map_cache", None)
    if cache is None:
        cache = {}
        setattr(data, "portfolio_return_map_cache", cache)
    if ticker in cache:
        return cache[ticker]

    candles = data.candles[ticker]
    prices = data.signal_prices[ticker]
    if len(candles) != len(prices):
        raise ValueError(f"{ticker}: candle/price length mismatch for portfolio risk.")
    result: dict[str, float] = {}
    for index in range(1, len(prices)):
        previous = float(prices[index - 1])
        current = float(prices[index])
        if previous <= 0 or current <= 0 or not math.isfinite(previous) or not math.isfinite(current):
            continue
        result[candles[index].date] = current / previous - 1.0
    cache[ticker] = result
    return result


def _covariance_matrix(
    data: Any,
    current_date: str,
    tickers: tuple[str, ...],
    window: int,
) -> tuple[tuple[float, ...], ...] | None:
    if window < 2 or not tickers:
        return None
    cache = getattr(data, "portfolio_covariance_cache", None)
    if cache is None:
        cache = {}
        setattr(data, "portfolio_covariance_cache", cache)
    key = (current_date, tickers, int(window))
    if key in cache:
        return cache[key]

    maps = {ticker: _return_map(data, ticker) for ticker in tickers}
    common_dates = set(maps[tickers[0]])
    for ticker in tickers[1:]:
        common_dates.intersection_update(maps[ticker])
    ordered = sorted(day for day in common_dates if day <= current_date)
    if len(ordered) < window:
        cache[key] = None
        return None
    ordered = ordered[-window:]
    series = {
        ticker: [maps[ticker][day] for day in ordered]
        for ticker in tickers
    }
    matrix: list[tuple[float, ...]] = []
    for left in tickers:
        row: list[float] = []
        for right in tickers:
            if left == right:
                value = statistics.variance(series[left])
            else:
                value = statistics.covariance(series[left], series[right])
            if not math.isfinite(value):
                cache[key] = None
                return None
            row.append(value)
        matrix.append(tuple(row))
    result = tuple(matrix)
    cache[key] = result
    return result


def historical_portfolio_volatility(
    data: Any,
    current_date: str,
    weights: dict[str, float],
    window: int,
) -> float | None:
    """Annualized ex-ante volatility from aligned historical portfolio returns.

    Only returns dated at or before ``current_date`` are used. Cash is implicitly
    zero-volatility when weights sum to less than one. A missing common history is
    returned as ``None`` so callers can fail closed instead of assuming zero
    correlation.
    """

    cleaned = {
        ticker: float(weight)
        for ticker, weight in weights.items()
        if weight > 0 and math.isfinite(float(weight))
    }
    if not cleaned:
        return 0.0
    tickers = tuple(sorted(cleaned))
    matrix = _covariance_matrix(data, current_date, tickers, window)
    if matrix is None:
        return None
    vector = [cleaned[ticker] for ticker in tickers]
    variance = 0.0
    for i, left_weight in enumerate(vector):
        for j, right_weight in enumerate(vector):
            variance += left_weight * right_weight * matrix[i][j]
    if variance < -1e-12 or not math.isfinite(variance):
        return None
    return math.sqrt(max(0.0, variance)) * math.sqrt(252.0)


def covariance_target_weights(
    data: Any,
    current_date: str,
    config: Any,
    *,
    eligible_tickers: set[str] | None = None,
) -> dict[str, float]:
    """Drop-in replacement for research_portfolio_allocation._target_weights."""

    from scripts import research_portfolio_allocation_core as core

    candidates = []
    for ticker in data.tickers:
        if eligible_tickers is not None and ticker not in eligible_tickers:
            continue
        index = data.index_by_date[ticker].get(current_date)
        if index is None:
            continue
        profile = core._candidate_profile(data, ticker, index, config)
        if profile is not None:
            candidates.append(profile)

    if not candidates:
        return {}
    if config.score == "all":
        selected = candidates
    else:
        candidates.sort(key=lambda item: item["score"], reverse=True)
        selected = candidates[: config.top_n]

    weights = core._weights(selected, config)
    weights = core._cap_weights(weights, config.max_weight)

    if config.target_vol > 0 and weights:
        estimated_vol = historical_portfolio_volatility(
            data,
            current_date,
            weights,
            config.vol_window,
        )
        if estimated_vol is None:
            return {}
        if estimated_vol > 0:
            scale = min(1.0, float(config.target_vol) / estimated_vol)
            weights = {ticker: weight * scale for ticker, weight in weights.items()}

    return weights
