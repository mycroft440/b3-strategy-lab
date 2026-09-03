from __future__ import annotations

import math
from bisect import bisect_left

from . import realistic_core as _core


DEFAULT_LIQUIDITY_LOOKBACK_SESSIONS = 20


_original_legs = _core.ExecutionPriceBook.legs
_original_from_csv = _core.ExecutionPriceBook.from_csv


def _normalized_ticker(ticker: str, market_type: str) -> str:
    value = ticker.strip().upper()
    if market_type == _core.FRACTIONAL_MARKET:
        return _core._base_fractional_ticker(value)
    return value


def _market_dates(book: _core.ExecutionPriceBook) -> list[str]:
    cached = getattr(book, "_causal_liquidity_market_dates", None)
    if cached is None:
        cached = sorted({key[0] for key in book._quotes})
        setattr(book, "_causal_liquidity_market_dates", cached)
    return cached


def _reference_cache(book: _core.ExecutionPriceBook) -> dict[tuple[str, str, str, int], float]:
    cached = getattr(book, "_causal_liquidity_reference_cache", None)
    if cached is None:
        cached = {}
        setattr(book, "_causal_liquidity_reference_cache", cached)
    return cached


def prior_liquidity_reference(
    book: _core.ExecutionPriceBook,
    value_date: str,
    ticker: str,
    market_type: str,
    *,
    lookback_sessions: int = DEFAULT_LIQUIDITY_LOOKBACK_SESSIONS,
) -> float:
    """Return a causal ADV-like liquidity reference known before ``value_date``.

    COTAHIST ``VOLTOT`` is a full-session total. An opening fill therefore must not
    use the same session's final financial volume. Missing ticker/market quotations
    inside the trailing market-session window count as zero liquidity instead of
    being silently dropped, which keeps sparse fractional trading conservative.
    """

    if lookback_sessions <= 0:
        raise ValueError("lookback_sessions must be positive.")

    normalized = _normalized_ticker(ticker, market_type)
    cache = _reference_cache(book)
    cache_key = (value_date, normalized, market_type, int(lookback_sessions))
    if cache_key in cache:
        return cache[cache_key]

    dates = _market_dates(book)
    end = bisect_left(dates, value_date)
    prior_dates = dates[max(0, end - lookback_sessions) : end]
    if not prior_dates:
        raise ValueError(
            f"{value_date}/{ticker}/{market_type}: no prior market session is available "
            "for causal liquidity-aware slippage."
        )

    total = 0.0
    for prior_date in prior_dates:
        quote = book._quotes.get((prior_date, normalized, market_type))
        if quote is None:
            continue
        volume = float(quote.financial_volume)
        if not math.isfinite(volume) or volume < 0:
            raise ValueError(
                f"{prior_date}/{normalized}/{market_type}: invalid historical financial volume."
            )
        total += volume

    reference = total / len(prior_dates)
    if reference <= 0 or not math.isfinite(reference):
        raise ValueError(
            f"{value_date}/{normalized}/{market_type}: trailing causal financial volume is zero; "
            "refusing to price an opening fill from same-day/future liquidity."
        )
    cache[cache_key] = reference
    return reference


def enable_causal_liquidity(
    book: _core.ExecutionPriceBook,
    *,
    lookback_sessions: int = DEFAULT_LIQUIDITY_LOOKBACK_SESSIONS,
) -> _core.ExecutionPriceBook:
    if lookback_sessions <= 0:
        raise ValueError("lookback_sessions must be positive.")
    setattr(book, "_causal_liquidity_enabled", True)
    setattr(book, "_causal_liquidity_lookback_sessions", int(lookback_sessions))
    _reference_cache(book)
    return book


def _causal_legs(
    self: _core.ExecutionPriceBook,
    value_date: str,
    ticker: str,
    quantity: int,
):
    legs = _original_legs(self, value_date, ticker, quantity)
    if not getattr(self, "_causal_liquidity_enabled", False):
        return legs

    lookback = int(
        getattr(
            self,
            "_causal_liquidity_lookback_sessions",
            DEFAULT_LIQUIDITY_LOOKBACK_SESSIONS,
        )
    )
    result = []
    for qty, quote in legs:
        reference = prior_liquidity_reference(
            self,
            value_date,
            ticker,
            quote.market_type,
            lookback_sessions=lookback,
        )
        result.append(
            (
                qty,
                _core.ExecutionQuote(
                    date=quote.date,
                    ticker=quote.ticker,
                    market_type=quote.market_type,
                    open=quote.open,
                    close=quote.close,
                    financial_volume=reference,
                ),
            )
        )
    return result


def _causal_from_csv(cls, path, standard_lot: int = _core.STANDARD_LOT):
    book = _original_from_csv(path, standard_lot=standard_lot)
    return enable_causal_liquidity(book)


def install() -> None:
    if getattr(_core.ExecutionPriceBook, "_causal_liquidity_patch_installed", False):
        return
    _core.ExecutionPriceBook.legs = _causal_legs
    _core.ExecutionPriceBook.from_csv = classmethod(_causal_from_csv)
    _core.ExecutionPriceBook.causal_liquidity_reference = prior_liquidity_reference
    _core.ExecutionPriceBook.enable_causal_liquidity = enable_causal_liquidity
    _core.ExecutionPriceBook._causal_liquidity_patch_installed = True


install()
