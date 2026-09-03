from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts.sync_official_universe import (
    SPLIT_NEUTRAL_OPEN_GAP_LIMIT,
    _event_continuity_audit,
    _excessive_event_continuity,
)


def _quote(date: str, *, open_: float, close: float):
    return SimpleNamespace(date=date, open=open_, close=close)


def _event(*, ratio: float = 0.01):
    return SimpleNamespace(
        ticker="AMER3",
        ex_date="2024-08-27",
        split_ratio=ratio,
        source_authority="B3",
        source_url="https://example.invalid/b3",
    )


def test_continuity_gate_uses_event_boundary_open_not_full_session_close() -> None:
    rows = _event_continuity_audit(
        [
            _quote("2024-08-26", open_=0.05, close=0.05),
            _quote("2024-08-27", open_=5.20, close=7.00),
        ],
        [_event()],
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["split_neutral_raw_open_gap"] == pytest.approx(0.04)
    assert row["split_neutral_raw_close_return"] == pytest.approx(0.40)
    assert _excessive_event_continuity(rows) == []
    assert SPLIT_NEUTRAL_OPEN_GAP_LIMIT == 0.35


def test_continuity_gate_remains_fail_closed_for_bad_adjusted_opening_gap() -> None:
    rows = _event_continuity_audit(
        [
            _quote("2024-08-26", open_=0.05, close=0.05),
            _quote("2024-08-27", open_=7.00, close=5.00),
        ],
        [_event()],
    )

    assert rows[0]["split_neutral_raw_open_gap"] == pytest.approx(0.40)
    assert rows[0]["split_neutral_raw_close_return"] == pytest.approx(0.0)
    assert _excessive_event_continuity(rows) == rows
