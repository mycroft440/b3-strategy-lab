from __future__ import annotations

import unittest

from scripts import research_portfolio_allocation as research


class QuoteFactorTransitionFailClosedTests(unittest.TestCase):
    def setUp(self) -> None:
        research._certified_unit_transitions.cache_clear()
        research._certified_unsupported_transition_boundaries.cache_clear()

    def test_azul_quote_factor_reorganization_is_not_unit_alias(self) -> None:
        transitions = research._certified_unit_transitions()
        self.assertNotIn(("AZUL4", "AZUL54"), transitions.get("2025-12-23", ()))

    def test_azul_missing_price_is_classified_as_certified_unsupported_boundary(self) -> None:
        reason = research._research_invalid_transition_reason(
            "2025-12-23: fechamento fresco obrigatorio ausente para AZUL4"
        )
        self.assertIsNotNone(reason)
        self.assertIn("AZUL4->AZUL54:reorganization", reason)
        self.assertIn("CERTIFIED_COMPLEX_TRANSITION_UNSUPPORTED", reason)

    def test_plain_one_to_one_ticker_change_remains_supported(self) -> None:
        transitions = research._certified_unit_transitions()
        self.assertIn(("NATU3", "NTCO3"), transitions.get("2019-12-18", ()))


if __name__ == "__main__":
    unittest.main()
