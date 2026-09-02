from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.validate_matrix_top_realistic import _artifact_binding_issues


class RealisticArtifactReconciliationTests(unittest.TestCase):
    def _fixture(self, root: Path):
        curve = root / "curve.csv"
        trades = root / "trades.csv"
        cash = root / "cash.csv"
        tax = root / "tax.csv"
        curve.write_text(
            "date,equity,tax_paid\n"
            "2023-12-29,1000,1\n"
            "2024-01-02,1000,1\n",
            encoding="utf-8",
        )
        trades.write_text("date,fee\n", encoding="utf-8")
        cash.write_text("date,net,tax\n", encoding="utf-8")
        tax.write_text(
            "month,tax_due,irrf_withheld_month\n"
            "2023-12,10,1\n"
            "2024-01,5,0\n",
            encoding="utf-8",
        )
        payload = {
            "start": "2023-12-29",
            "end": "2024-01-02",
            "initial_cash": 1000.0,
            "final_equity": 1000.0,
            "annual_volatility": 0.0,
            "sharpe": 0.0,
            "average_annual_return": 0.0,
            "trades": 0,
            "fees_paid": 0.0,
            "distributions_net": 0.0,
            "distribution_tax_paid": 0.0,
            "ordinary_income_tax_paid": 1.0,
            "ordinary_irrf_withheld": 1.0,
            "darf_paid": 0.0,
            "outstanding_accrued_tax_liability": 15.0,
        }
        return payload, curve, trades, cash, tax

    def test_gate_recomputes_curve_metrics_and_reconciles_tax_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            payload, curve, trades, cash, tax = self._fixture(Path(temporary))
            self.assertEqual(
                _artifact_binding_issues(
                    payload,
                    curve_path=curve,
                    trades_path=trades,
                    cash_path=cash,
                    tax_path=tax,
                ),
                [],
            )

    def test_curve_metric_mismatches_are_blocking(self) -> None:
        cases = {
            "annual_volatility": "curve_annual_volatility_mismatch",
            "sharpe": "curve_sharpe_mismatch",
            "average_annual_return": "curve_average_annual_return_mismatch",
        }
        with tempfile.TemporaryDirectory() as temporary:
            payload, curve, trades, cash, tax = self._fixture(Path(temporary))
            for field, expected_issue in cases.items():
                with self.subTest(field=field):
                    mutated = dict(payload)
                    mutated[field] = 0.25
                    issues = _artifact_binding_issues(
                        mutated,
                        curve_path=curve,
                        trades_path=trades,
                        cash_path=cash,
                        tax_path=tax,
                    )
                    self.assertIn(expected_issue, issues)

    def test_ordinary_tax_must_match_fiscal_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            payload, curve, trades, cash, tax = self._fixture(Path(temporary))
            payload["ordinary_income_tax_paid"] = 2.0
            self.assertIn(
                "tax_ledger_ordinary_income_tax_paid_mismatch",
                _artifact_binding_issues(
                    payload,
                    curve_path=curve,
                    trades_path=trades,
                    cash_path=cash,
                    tax_path=tax,
                ),
            )


    def test_empty_tax_ledger_is_blocking_even_when_summary_tax_is_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            payload, curve, trades, cash, tax = self._fixture(Path(temporary))
            tax.write_text("month,tax_due,irrf_withheld_month\n", encoding="utf-8")
            payload["ordinary_income_tax_paid"] = 0.0
            payload["ordinary_irrf_withheld"] = 0.0
            payload["outstanding_accrued_tax_liability"] = 0.0
            issues = _artifact_binding_issues(
                payload,
                curve_path=curve,
                trades_path=trades,
                cash_path=cash,
                tax_path=tax,
            )
            self.assertIn("empty_tax_ledger", issues)

    def test_missing_irrf_column_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            payload, curve, trades, cash, tax = self._fixture(Path(temporary))
            tax.write_text(
                "month,tax_due\n2023-12,10\n2024-01,5\n",
                encoding="utf-8",
            )
            issues = _artifact_binding_issues(
                payload,
                curve_path=curve,
                trades_path=trades,
                cash_path=cash,
                tax_path=tax,
            )
            self.assertIn("tax_ledger_missing_columns", issues)
            self.assertIn("invalid_tax_ledger", issues)

    def test_tax_ledger_must_cover_each_curve_month_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            payload, curve, trades, cash, tax = self._fixture(Path(temporary))
            tax.write_text(
                "month,tax_due,irrf_withheld_month\n"
                "2023-12,10,1\n"
                "2023-12,5,0\n",
                encoding="utf-8",
            )
            issues = _artifact_binding_issues(
                payload,
                curve_path=curve,
                trades_path=trades,
                cash_path=cash,
                tax_path=tax,
            )
            self.assertIn("tax_ledger_duplicate_month", issues)
            self.assertIn("tax_ledger_month_coverage_mismatch", issues)


if __name__ == "__main__":
    unittest.main()
