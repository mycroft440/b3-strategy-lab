from __future__ import annotations

"""Fail-closed structural validation for official B3 corporate-action payloads.

The B3 downloader validates the top-level response, but cached or upstream payloads
can still contain a malformed ``stockDividends`` member. The canonical extractor
historically treated non-list containers and non-mapping rows as an empty/no-op
stream, which can turn source corruption into a false "zero share-count events"
result. This compatibility shim validates that boundary before delegating to the
canonical extractor.
"""

from . import b3_official as _official


_ORIGINAL_ATTR = "_payload_hardening_original_extract_official_split_events"
_PREVIOUS_WRAPPER = globals().get("_extract_official_split_events_fail_closed")
_current = _official.extract_official_split_events

# Import/reload-safe canonical capture. A normal reload of this patch sees its own
# previous wrapper and keeps the canonical function already stored on b3_official.
# If b3_official itself was reloaded, ``_current`` is a fresh canonical function;
# refresh the stored reference instead of reviving a stale pre-reload function.
if (
    not hasattr(_official, _ORIGINAL_ATTR)
    or (_PREVIOUS_WRAPPER is not None and _current is not _PREVIOUS_WRAPPER)
):
    setattr(_official, _ORIGINAL_ATTR, _current)
_ORIGINAL_EXTRACT = getattr(_official, _ORIGINAL_ATTR)


def _validate_stock_dividend_structure(
    payload: object,
    *,
    ticker: str,
    issuing_company: str,
) -> None:
    normalized_ticker = str(ticker).strip().upper() or "<vazio>"
    normalized_issuer = str(issuing_company).strip().upper() or "<vazio>"
    if not isinstance(payload, list) or not payload:
        raise _official.B3CorporateActionError(
            f"{normalized_ticker}: resposta B3 invalida para {normalized_issuer}."
        )
    if not all(isinstance(item, dict) for item in payload):
        raise _official.B3CorporateActionError(
            f"{normalized_ticker}: resposta B3 contem companhia invalida para {normalized_issuer}."
        )

    company = next(
        (
            item
            for item in payload
            if str(item.get("code", "")).strip().upper() == normalized_issuer
        ),
        payload[0] if len(payload) == 1 else None,
    )
    # Let the canonical extractor preserve its existing, more specific error for a
    # missing company. Structural validation only hardens a company we can identify.
    if company is None:
        return

    stock_dividends = company.get("stockDividends")
    if stock_dividends is None:
        return
    if not isinstance(stock_dividends, list):
        raise _official.B3CorporateActionError(
            f"{normalized_ticker}: stockDividends B3 precisa ser uma lista."
        )
    for index, raw_event in enumerate(stock_dividends):
        if not isinstance(raw_event, dict):
            raise _official.B3CorporateActionError(
                f"{normalized_ticker}: stockDividends B3 contem registro invalido no indice {index}."
            )


def _extract_official_split_events_fail_closed(
    payload,
    *,
    ticker: str,
    issuing_company: str,
    quote_dates,
    quote_isins,
    coverage_start: str,
):
    _validate_stock_dividend_structure(
        payload,
        ticker=ticker,
        issuing_company=issuing_company,
    )
    return _ORIGINAL_EXTRACT(
        payload,
        ticker=ticker,
        issuing_company=issuing_company,
        quote_dates=quote_dates,
        quote_isins=quote_isins,
        coverage_start=coverage_start,
    )


_official.extract_official_split_events = _extract_official_split_events_fail_closed
