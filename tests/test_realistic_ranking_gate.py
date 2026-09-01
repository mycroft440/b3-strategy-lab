from __future__ import annotations

import math
import unittest

from scripts.audit_matrix_results import _real_money_blockers
from scripts.audit_realistic_backtest_inputs import _execution_values_valid
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
            "total_return": 0.23456,
            "cagr": 0.10,
            "max_drawdown": -0.20,
            "annual_volatility": 0.15,
            "sharpe": 0.8,
            "average_annual_return": 0.11,
            "trades": 10,
            "fees_paid": 2.0,
            "ordinary_income_tax_paid": 0.0,
            "distribution_tax_paid": 0.0,
            "distributions_net": 10.0,
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
            "total_return": 0.0,
            "cagr": 0.0,
            "max_drawdown": 0.0,
            "annual_volatility": 0.0,
            "sharpe": 0.0,
            "average_annual_return": 0.0,
            "trades": 0,
            "fees_paid": 0.0,
            "ordinary_income_tax_paid": 0.0,
            "distribution_tax_paid": 0.0,
            "distributions_net": 0.0,
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

    def test_realistic_finalist_gate_rejects_every_nonfinite_metric(self) -> None:
        base = {
            "validity": "REALISTIC_POINT_IN_TIME__RETROSPECTIVE_SELECTION",
            "survivorship_safe": True,
            "cash_events_complete": True,
            "ticker_transition_binding_verified": True,
            "bonus_tax_basis_affects_realized_gain": False,
            "fee_quality": "official",
            "selection_status": "retrospective_hypothesis_replay",
            "final_equity": 1000.0,
            "total_return": 0.0,
            "cagr": 0.0,
            "max_drawdown": 0.0,
            "annual_volatility": 0.0,
            "sharpe": 0.0,
            "average_annual_return": 0.0,
            "trades": 0,
            "fees_paid": 0.0,
            "ordinary_income_tax_paid": 0.0,
            "distribution_tax_paid": 0.0,
            "distributions_net": 0.0,
        }
        for field in (
            "final_equity",
            "total_return",
            "cagr",
            "max_drawdown",
            "annual_volatility",
            "sharpe",
            "average_annual_return",
            "fees_paid",
            "ordinary_income_tax_paid",
            "distribution_tax_paid",
            "distributions_net",
        ):
            with self.subTest(field=field):
                payload = dict(base)
                payload[field] = math.nan
                self.assertIn(f"nonfinite_metric:{field}", _validation_issues(payload))

    def test_realistic_gates_reject_nonfinite_execution_values_and_trade_counts(self) -> None:
        valid_row = {"open": "10", "close": "10.5", "financial_volume": "1000"}
        self.assertTrue(_execution_values_valid(valid_row))
        for field in valid_row:
            with self.subTest(field=field):
                row = dict(valid_row)
                row[field] = "inf"
                self.assertFalse(_execution_values_valid(row))

        payload = {
            "validity": "REALISTIC_POINT_IN_TIME__RETROSPECTIVE_SELECTION",
            "survivorship_safe": True,
            "cash_events_complete": True,
            "ticker_transition_binding_verified": True,
            "bonus_tax_basis_affects_realized_gain": False,
            "fee_quality": "official",
            "selection_status": "retrospective_hypothesis_replay",
            "final_equity": 1000.0,
            "total_return": 0.0,
            "cagr": 0.0,
            "max_drawdown": 0.0,
            "annual_volatility": 0.0,
            "sharpe": 0.0,
            "average_annual_return": 0.0,
            "trades": 1.5,
            "fees_paid": 0.0,
            "ordinary_income_tax_paid": 0.0,
            "distribution_tax_paid": 0.0,
            "distributions_net": 0.0,
        }
        self.assertIn("invalid_trades", _validation_issues(payload))


if __name__ == "__main__":
    unittest.main()
