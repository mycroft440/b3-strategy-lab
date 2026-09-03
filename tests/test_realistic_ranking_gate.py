from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

from scripts.audit_matrix_results import _real_money_blockers
from scripts.audit_realistic_backtest_inputs import _execution_values_valid
from scripts.validate_matrix_top_realistic import (
    _artifact_binding_issues,
    _validation_issues,
)


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
            "point_in_time_universe": True,
            "fractional_execution": True,
            "start": "2023-01-01",
            "end": "2024-01-01",
            "initial_cash": 1000.0,
            "final_equity": 1234.56,
            "total_return": 0.23456,
            "cagr": 1.23456 ** (365.25 / 365.0) - 1.0,
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
            "point_in_time_universe": True,
            "fractional_execution": True,
            "start": "2023-01-01",
            "end": "2024-01-01",
            "initial_cash": 1000.0,
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
            "point_in_time_universe": True,
            "fractional_execution": True,
            "start": "2023-01-01",
            "end": "2024-01-01",
            "initial_cash": 1000.0,
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
            "point_in_time_universe": True,
            "fractional_execution": True,
            "start": "2023-01-01",
            "end": "2024-01-01",
            "initial_cash": 1000.0,
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

    def test_realistic_gate_rejects_finite_but_incoherent_economics_and_binding(self) -> None:
        payload = {
            "validity": "NOT_REALISTIC",
            "survivorship_safe": True,
            "cash_events_complete": True,
            "ticker_transition_binding_verified": True,
            "bonus_tax_basis_affects_realized_gain": False,
            "fee_quality": "official",
            "selection_status": "retrospective_hypothesis_replay",
            "point_in_time_universe": False,
            "fractional_execution": False,
            "strategy": "wrong",
            "management": "wrong",
            "start": "2018-01-03",
            "end": "2018-12-27",
            "initial_cash": 1000.0,
            "final_equity": 1000.0,
            "total_return": 999.0,
            "cagr": 777.0,
            "max_drawdown": 0.42,
            "annual_volatility": -0.15,
            "sharpe": 0.8,
            "average_annual_return": 0.11,
            "trades": 10,
            "fees_paid": -2.0,
            "ordinary_income_tax_paid": -1.0,
            "distribution_tax_paid": -1.0,
            "distributions_net": -10.0,
        }
        issues = _validation_issues(
            payload,
            expected_strategy="gap_momentum",
            expected_management="expected-management",
            expected_start="2018-01-02",
            expected_end="2018-12-28",
            expected_initial_cash=2000.0,
        )
        self.assertIn("unexpected_validity_class", issues)
        self.assertIn("point_in_time_universe=false", issues)
        self.assertIn("fractional_execution=false", issues)
        self.assertIn("total_return_equity_identity_mismatch", issues)
        self.assertIn("cagr_equity_period_identity_mismatch", issues)
        self.assertIn("max_drawdown_out_of_range", issues)
        self.assertIn("negative_metric:annual_volatility", issues)
        self.assertIn("negative_metric:fees_paid", issues)
        self.assertIn("candidate_binding_mismatch:strategy", issues)
        self.assertIn("candidate_binding_mismatch:management", issues)
        self.assertIn("candidate_binding_mismatch:start", issues)
        self.assertIn("candidate_binding_mismatch:end", issues)
        self.assertIn("candidate_binding_mismatch:initial_cash", issues)

    def test_realistic_summary_is_bound_to_curve_and_ledgers(self) -> None:
        payload = {
            "start": "2018-01-02",
            "end": "2018-01-03",
            "final_equity": 1100.0,
            "trades": 2,
            "fees_paid": 3.0,
            "distributions_net": 5.0,
            "distribution_tax_paid": 0.0,
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            curve = root / "curve.csv"
            trades = root / "trades.csv"
            cash = root / "cash.csv"
            curve.write_text(
                "date,equity\n2018-01-02,1000\n2018-01-03,1100\n",
                encoding="utf-8",
            )
            trades.write_text(
                "date,side,ticker,shares,market_type,raw_open,execution_price,notional,fee,slippage_bps,realized_gain\n"
                "2018-01-02,BUY,AAA3,10,020,10,10.01,100.1,1,10,0\n"
                "2018-01-03,SELL,AAA3,10,020,11,10.989,109.89,2,10,7.89\n",
                encoding="utf-8",
            )
            cash.write_text(
                "date,ticker,label,shares_entitled,gross,tax,net\n"
                "2018-01-03,AAA3,DIVIDENDO,10,5,0,5\n",
                encoding="utf-8",
            )
            self.assertEqual(
                _artifact_binding_issues(
                    payload,
                    curve_path=curve,
                    trades_path=trades,
                    cash_path=cash,
                ),
                [],
            )
            curve.write_text(
                "date,equity\n2018-01-02,1000\n2018-01-03,1099\n",
                encoding="utf-8",
            )
            self.assertIn(
                "curve_final_equity_mismatch",
                _artifact_binding_issues(
                    payload,
                    curve_path=curve,
                    trades_path=trades,
                    cash_path=cash,
                ),
            )


if __name__ == "__main__":
    unittest.main()
