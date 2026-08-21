from __future__ import annotations

import math
import statistics
from typing import Any


def _price_map(data: Any, ticker: str) -> dict[str, float]:
    cache = getattr(data, "portfolio_price_map_cache", None)
    if cache is None:
        cache = {}
        setattr(data, "portfolio_price_map_cache", cache)
    if ticker in cache:
        return cache[ticker]

    candles = data.candles[ticker]
    prices = data.signal_prices[ticker]
    if len(candles) != len(prices):
        raise ValueError(f"{ticker}: candle/price length mismatch for portfolio risk.")
    result: dict[str, float] = {}
    for candle, raw_price in zip(candles, prices):
        price = float(raw_price)
        if price <= 0 or not math.isfinite(price):
            continue
        if candle.date in result:
            raise ValueError(f"{ticker}: duplicate date in portfolio risk input: {candle.date}")
        result[candle.date] = price
    cache[ticker] = result
    return result


def _market_dates(data: Any) -> tuple[str, ...]:
    cache = getattr(data, "portfolio_market_dates_cache", None)
    if cache is not None:
        return cache
    if hasattr(data, "dates"):
        values = sorted({str(day) for day in data.dates})
    else:
        values = sorted(
            {
                candle.date
                for candles in data.candles.values()
                for candle in candles
            }
        )
    result = tuple(values)
    setattr(data, "portfolio_market_dates_cache", result)
    return result


def _aligned_return_series(
    data: Any,
    current_date: str,
    tickers: tuple[str, ...],
    window: int,
) -> dict[str, list[float]] | None:
    """Return exactly ``window`` consecutive fresh market-session returns.

    The prior implementation intersected return *end dates*. A suspended/missing
    ticker could therefore contribute a multi-session return on a date where a
    continuously traded ticker contributed a one-session return. That is not a
    valid covariance observation. We now require every selected ticker to have a
    fresh price on the same ``window + 1`` consecutive global market sessions.
    """

    if window < 2 or not tickers:
        return None
    dates = [day for day in _market_dates(data) if day <= current_date]
    if len(dates) < window + 1:
        return None
    observation_dates = dates[-(window + 1) :]
    if observation_dates[-1] != current_date:
        # Risk at a decision date must include a fresh price on the decision session.
        return None

    prices = {ticker: _price_map(data, ticker) for ticker in tickers}
    for ticker in tickers:
        if any(day not in prices[ticker] for day in observation_dates):
            return None

    series: dict[str, list[float]] = {}
    for ticker in tickers:
        values: list[float] = []
        mapping = prices[ticker]
        for previous_day, day in zip(observation_dates, observation_dates[1:]):
            previous = mapping[previous_day]
            current = mapping[day]
            if previous <= 0 or current <= 0:
                return None
            value = current / previous - 1.0
            if not math.isfinite(value):
                return None
            values.append(value)
        series[ticker] = values
    return series


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

    series = _aligned_return_series(data, current_date, tickers, window)
    if series is None:
        cache[key] = None
        return None

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
    """Annualized ex-ante volatility from consecutive aligned daily returns.

    Only sessions at or before ``current_date`` are used. Cash is implicitly
    zero-volatility when weights sum to less than one. Missing/stale history is
    returned as ``None`` so callers fail closed instead of manufacturing a
    diversification benefit from mismatched observations.
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
