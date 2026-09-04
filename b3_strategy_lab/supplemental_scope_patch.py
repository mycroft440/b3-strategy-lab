from __future__ import annotations

from typing import Iterable, Mapping

from . import b3_official as _official


_ORIGINAL_PARSE_SUPPLEMENTAL = _official.parse_supplemental_split_events


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
    universe. Malformed records are deliberately preserved so the canonical
    parser still rejects them fail-closed.
    """
    allowed = {str(ticker).strip().upper() for ticker in tickers}
    scoped_payload = payload
    if isinstance(payload, dict) and isinstance(payload.get("events"), list):
        scoped_events: list[object] = []
        for raw_event in payload["events"]:
            if not isinstance(raw_event, dict):
                scoped_events.append(raw_event)
                continue
            ticker = str(raw_event.get("ticker", "")).strip().upper()
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


_official.parse_supplemental_split_events = _parse_supplemental_split_events_scoped
