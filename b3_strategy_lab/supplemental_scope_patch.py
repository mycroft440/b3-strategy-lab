from __future__ import annotations

from typing import Iterable, Mapping

from . import b3_official as _official


# Keep a canonical parser reference on the target module, but refresh it whenever
# b3_official itself has been reloaded and therefore exposes its own implementation
# again. A reload of this patch alone sees our wrapper and keeps the existing
# canonical reference, avoiding wrapper stacking/recursion.
_ORIGINAL_ATTR = "_supplemental_scope_patch_original_parse"
_current_parse = _official.parse_supplemental_split_events
if getattr(_current_parse, "__module__", "") == _official.__name__:
    setattr(_official, _ORIGINAL_ATTR, _current_parse)
elif not hasattr(_official, _ORIGINAL_ATTR):
    raise RuntimeError(
        "Supplemental scope patch cannot identify the canonical B3 parser fail-closed."
    )
_ORIGINAL_PARSE_SUPPLEMENTAL = getattr(_official, _ORIGINAL_ATTR)


def _parse_supplemental_split_events_scoped(
    payload: object,
    *,
    tickers: Iterable[str],
    quote_dates_by_ticker: Mapping[str, Iterable[str]],
    coverage_start: str,
):
    """Limit a global supplemental registry to the selected ticker universe.

    The supplemental registry is shared by multiple universes. A valid event for
    another ticker is therefore unrelated input, not a corruption of the current
    universe. Records whose ticker cannot be safely classified are deliberately
    preserved so the canonical parser still rejects them fail-closed.
    """
    allowed = {str(ticker).strip().upper() for ticker in tickers}
    scoped_payload = payload
    if isinstance(payload, dict) and isinstance(payload.get("events"), list):
        scoped_events: list[object] = []
        for raw_event in payload["events"]:
            if not isinstance(raw_event, dict):
                scoped_events.append(raw_event)
                continue
            raw_ticker = raw_event.get("ticker")
            if not isinstance(raw_ticker, str):
                scoped_events.append(raw_event)
                continue
            ticker = raw_ticker.strip().upper()
            if not ticker or ticker in allowed:
                scoped_events.append(raw_event)
        scoped_payload = dict(payload)
        scoped_payload["events"] = scoped_events

    return _ORIGINAL_PARSE_SUPPLEMENTAL(
        scoped_payload,
        tickers=allowed,
        quote_dates_by_ticker=quote_dates_by_ticker,
        coverage_start=coverage_start,
    )


# Installation is idempotent because the wrapper always delegates directly to the
# canonical parser selected above rather than to any previously installed wrapper.
_official.parse_supplemental_split_events = _parse_supplemental_split_events_scoped
