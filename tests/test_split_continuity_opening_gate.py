from __future__ import annotations

import unittest
from types import SimpleNamespace

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


class SplitContinuityOpeningGateTests(unittest.TestCase):
    def test_continuity_gate_uses_event_boundary_open_not_full_session_close(self) -> None:
        rows = _event_continuity_audit(
            [
                _quote("2024-08-26", open_=0.05, close=0.05),
                _quote("2024-08-27", open_=5.20, close=7.00),
            ],
            [_event()],
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertAlmostEqual(row["split_neutral_raw_open_gap"], 0.04, places=12)
        self.assertAlmostEqual(row["split_neutral_raw_close_return"], 0.40, places=12)
        self.assertEqual(_excessive_event_continuity(rows), [])
        self.assertEqual(SPLIT_NEUTRAL_OPEN_GAP_LIMIT, 0.35)

    def test_continuity_gate_remains_fail_closed_for_bad_adjusted_opening_gap(self) -> None:
        rows = _event_continuity_audit(
            [
                _quote("2024-08-26", open_=0.05, close=0.05),
                _quote("2024-08-27", open_=7.00, close=5.00),
            ],
            [_event()],
        )

        self.assertAlmostEqual(rows[0]["split_neutral_raw_open_gap"], 0.40, places=12)
        self.assertAlmostEqual(rows[0]["split_neutral_raw_close_return"], 0.0, places=12)
        self.assertEqual(_excessive_event_continuity(rows), rows)


if __name__ == "__main__":
    unittest.main()
