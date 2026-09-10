from __future__ import annotations

import unittest

from scripts import research_portfolio_allocation as research


class NaturaTransitionPolicyTests(unittest.TestCase):
    def test_natu3_to_ntco3_is_certified_unit_continuity(self) -> None:
        transitions = research._certified_unit_transitions()
        self.assertIn(("NATU3", "NTCO3"), transitions.get("2019-12-18", ()))


if __name__ == "__main__":
    unittest.main()
