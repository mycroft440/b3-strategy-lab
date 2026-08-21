from __future__ import annotations

import unittest

from scripts.build_ticker_transitions import _stale_category


class TickerTransitionHorizonTests(unittest.TestCase):
    def test_quote_on_coverage_end_is_current(self) -> None:
        self.assertEqual(
            _stale_category("2026-08-20", "2026-08-20", transitioned=False),
            "",
        )

    def test_recent_unexplained_gap_is_not_silently_approved(self) -> None:
        self.assertEqual(
            _stale_category("2026-08-01", "2026-08-20", transitioned=False),
            "recent_stale_symbol",
        )

    def test_old_unexplained_gap_is_unresolved_disappearance(self) -> None:
        self.assertEqual(
            _stale_category("2026-05-01", "2026-08-20", transitioned=False),
            "unresolved_disappearance",
        )

    def test_same_isin_transition_resolves_prior_ticker_gap(self) -> None:
        self.assertEqual(
            _stale_category("2026-05-01", "2026-08-20", transitioned=True),
            "",
        )


if __name__ == "__main__":
    unittest.main()
