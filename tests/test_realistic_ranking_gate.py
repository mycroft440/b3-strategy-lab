from __future__ import annotations

import unittest

from scripts.audit_matrix_results import _real_money_blockers
from scripts.validate_matrix_top_realistic import _validation_issues


class MatrixRealMoneyGateTests(unittest.TestCase):
    def test_retrospective_matrix_can_never_be_promoted_to_real_money(self) -> None:
        manifest = {
            "result_classification": "RETROSPECTIVE_PRICE_ONLY_RESEARCH",
            "real_money_claim_allowed": False,
            "evaluation_scope": "full_period",
            "universe": {"survivorship_safe": False},
            "dividends_jcp": "excluded",
            "limitations": [
                "taxes_excluded",
                "standard_market_open_used_for_integer_share_research_execution",
            ],
        }
        blockers = _real_money_blockers(manifest)
        self.assertIn("manifest_forbids_real_money_claim", blockers)
        self.assertIn("strategy_and_management_selected_on_full_period", blockers)
        self.assertIn("universe_is_not_survivorship_safe", blockers)
        self.assertIn("dividends_and_jcp_are_not_certified_in_matrix", blockers)
        self.assertIn("taxes_are_excluded", blockers)
        self.assertIn("fractional_market_execution_is_not_modeled", blockers)

    def test_realistic_finalist_gate_accepts_only_complete_account_inputs(self) -> None:
        payload = {
            "validity": "REALISTIC_POINT_IN_TIME__RETROSPECTIVE_SELECTION",
            "survivorship_safe": True,
            "cash_events_complete": True,
            "ticker_transition_binding_verified": True,
            "bonus_tax_basis_affects_realized_gain": False,
            "fee_quality": "official",
            "selection_status": "retrospective_hypothesis_replay",
            "final_equity": 1234.56,
        }
        self.assertEqual(_validation_issues(payload), [])

    def test_realistic_finalist_gate_fails_closed_on_uncertified_inputs(self) -> None:
        payload = {
            "validity": (
                "REALISTIC_POINT_IN_TIME__UNCERTIFIED_CASH_EVENTS"
                "__UNBOUND_TICKER_TRANSITIONS__BONUS_TAX_BASIS_UNCERTIFIED"
            ),
            "survivorship_safe": False,
            "cash_events_complete": False,
            "ticker_transition_binding_verified": False,
            "bonus_tax_basis_affects_realized_gain": True,
            "fee_quality": "modeled",
            "selection_status": "retrospective_hypothesis_replay",
            "final_equity": 1000.0,
        }
        issues = _validation_issues(payload)
        self.assertIn("validity:UNCERTIFIED_CASH_EVENTS", issues)
        self.assertIn("validity:UNBOUND_TICKER_TRANSITIONS", issues)
        self.assertIn("validity:BONUS_TAX_BASIS_UNCERTIFIED", issues)
        self.assertIn("survivorship_safe=false", issues)
        self.assertIn("cash_events_complete=false", issues)
        self.assertIn("ticker_transition_binding_verified=false", issues)
        self.assertIn("bonus_tax_basis_affects_realized_gain=true", issues)
        self.assertIn("fee_quality=modeled", issues)


if __name__ == "__main__":
    unittest.main()
