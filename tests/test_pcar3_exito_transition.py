from __future__ import annotations

import unittest

from b3_strategy_lab.instrument_transitions import load_transition_reviews
from scripts import build_ticker_transitions
from scripts import research_portfolio_allocation as research


class Pcar3ExitoTransitionTests(unittest.TestCase):
    def setUp(self) -> None:
        research._certified_unit_transitions.cache_clear()
        research._certified_unsupported_transition_boundaries.cache_clear()

    def test_exito_spin_off_review_is_loaded_from_registry_shard(self) -> None:
        reviews = load_transition_reviews(research._TRANSITION_REVIEWS)
        event = next(
            item
            for item in reviews
            if item.effective_date == "2023-08-23"
            and item.old_ticker == "PCAR3"
            and item.event_type == "spin_off"
        )
        self.assertEqual(event.new_ticker, "PCAR3")
        self.assertEqual(event.distributed_ticker, "EXCO32")
        self.assertAlmostEqual(event.distributed_share_ratio, 1.0)
        self.assertAlmostEqual(event.distributed_basis_fraction, 0.5858295139)
        self.assertEqual(event.cash_per_old_share, 0.0)

    def test_research_does_not_treat_spin_off_as_unit_alias(self) -> None:
        transitions = research._certified_unit_transitions()
        self.assertNotIn(("PCAR3", "PCAR3"), transitions.get("2023-08-23", ()))

    def test_held_pcar3_crossing_spin_off_is_failed_closed(self) -> None:
        reason = research._unsupported_held_transition_reason(
            "2023-09-01", {"PCAR3": 100.0}
        )
        self.assertIsNotNone(reason)
        self.assertIn("PCAR3->PCAR3:spin_off", reason)
        self.assertIn(
            "CERTIFIED_COMPLEX_TRANSITION_UNSUPPORTED_IN_PRICE_ONLY_RESEARCH",
            reason,
        )
        self.assertEqual(research._research_invalid_transition_reason(reason), reason)

    def test_unheld_spin_off_does_not_poison_unrelated_portfolios(self) -> None:
        self.assertIsNone(
            research._unsupported_held_transition_reason(
                "2023-09-01", {"PCAR3": 0.0, "PETR4": 100.0}
            )
        )

    def test_pcar3_remains_available_to_transition_builder_only_as_market_data(self) -> None:
        self.assertNotIn("PCAR3", build_ticker_transitions.EXCLUDED_TICKERS)


if __name__ == "__main__":
    unittest.main()
