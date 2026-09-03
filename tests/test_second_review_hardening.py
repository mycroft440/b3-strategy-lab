from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.validate_matrix_top_realistic import (
    _artifact_binding_issues,
    _clear_previous_validation_outputs,
    _run_candidate,
    _validated_finalists,
)


class SecondReviewHardeningTests(unittest.TestCase):
    def _trade_fixture(self, root: Path):
        curve = root / "curve.csv"
        trades = root / "trades.csv"
        cash = root / "cash.csv"
        execution = root / "execution.csv"
        fees = root / "fees.json"
        curve.write_text(
            "date,equity\n2018-01-02,1000\n2018-01-03,1000\n",
            encoding="utf-8",
        )
        cash.write_text("", encoding="utf-8")
        source_open = 10.0
        shares = 10
        financial_volume = 100_000.0
        raw_notional = source_open * shares
        expected_slippage = 10.0 + 5.0 * ((raw_notional / financial_volume) / 0.01)
        execution_price = source_open * (1.0 + expected_slippage / 10_000)
        notional = shares * execution_price
        fee = notional * 3.2 / 10_000
        trades.write_text(
            "date,side,ticker,shares,market_type,raw_open,execution_price,notional,fee,slippage_bps,realized_gain\n"
            f"2018-01-02,BUY,AAA3,{shares},020,{source_open},{execution_price},{notional},{fee},{expected_slippage},0\n",
            encoding="utf-8",
        )
        execution.write_text(
            "date,ticker,market_type,open,close,financial_volume\n"
            f"2018-01-02,AAA3F,020,{source_open},10.1,{financial_volume}\n",
            encoding="utf-8",
        )
        fees.write_text(
            json.dumps(
                {
                    "rules": [
                        {
                            "start": "2018-01-01",
                            "end": "2018-12-31",
                            "b3_bps": 3.2,
                            "brokerage_fixed": 0.0,
                            "quality": "official",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        payload = {
            "start": "2018-01-02",
            "end": "2018-01-03",
            "final_equity": 1000.0,
            "trades": 1,
            "fees_paid": fee,
            "distributions_net": 0.0,
            "distribution_tax_paid": 0.0,
        }
        return payload, curve, trades, cash, execution, fees

    def _issues(self, fixture):
        payload, curve, trades, cash, execution, fees = fixture
        return _artifact_binding_issues(
            payload,
            curve_path=curve,
            trades_path=trades,
            cash_path=cash,
            execution_prices_path=execution,
            fee_schedule_path=fees,
        )

    def test_trade_leg_is_bound_to_source_slippage_notional_and_fee(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self._trade_fixture(Path(temporary))
            self.assertEqual(self._issues(fixture), [])

    def test_consistent_but_wrong_slippage_is_rejected_against_source_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self._trade_fixture(Path(temporary))
            payload, _curve, trades, _cash, _execution, _fees = fixture
            source_open = 10.0
            shares = 10
            bad_slippage = 20.0
            execution_price = source_open * (1 + bad_slippage / 10_000)
            notional = shares * execution_price
            bad_fee = notional * 3.2 / 10_000
            trades.write_text(
                "date,side,ticker,shares,market_type,raw_open,execution_price,notional,fee,slippage_bps,realized_gain\n"
                f"2018-01-02,BUY,AAA3,10,020,10,{execution_price},{notional},{bad_fee},{bad_slippage},0\n",
                encoding="utf-8",
            )
            payload["fees_paid"] = bad_fee
            self.assertIn("trade_slippage_model_mismatch", self._issues(fixture))

    def test_notional_lot_source_open_and_fee_tampering_are_each_blocking(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self._trade_fixture(root)
            payload, _curve, trades, _cash, _execution, _fees = fixture
            original = trades.read_text(encoding="utf-8")

            header, row = original.strip().split("\n")
            parts = row.split(",")
            parts[7] = str(float(parts[7]) + 1.0)
            trades.write_text(header + "\n" + ",".join(parts) + "\n", encoding="utf-8")
            self.assertIn("trade_notional_mismatch", self._issues(fixture))

            trades.write_text(original, encoding="utf-8")
            parts = row.split(",")
            parts[5] = "10.25"
            trades.write_text(header + "\n" + ",".join(parts) + "\n", encoding="utf-8")
            self.assertIn("trade_raw_open_source_mismatch", self._issues(fixture))

            trades.write_text(original, encoding="utf-8")
            parts = row.split(",")
            parts[8] = str(float(parts[8]) + 0.5)
            trades.write_text(header + "\n" + ",".join(parts) + "\n", encoding="utf-8")
            payload["fees_paid"] = float(parts[8])
            self.assertIn("trade_fee_schedule_mismatch", self._issues(fixture))

            standard = row.split(",")
            standard[4] = "010"
            standard[3] = "10"
            trades.write_text(header + "\n" + ",".join(standard) + "\n", encoding="utf-8")
            self.assertIn("invalid_standard_market_lot", self._issues(fixture))

    def test_cash_row_net_and_withholding_are_independently_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            curve = root / "curve.csv"
            trades = root / "trades.csv"
            cash = root / "cash.csv"
            curve.write_text(
                "date,equity\n2025-01-02,1000\n2025-01-03,1000\n",
                encoding="utf-8",
            )
            trades.write_text(
                "date,side,ticker,shares,market_type,raw_open,execution_price,notional,fee,slippage_bps,realized_gain\n",
                encoding="utf-8",
            )
            cash.write_text(
                "date,ticker,label,shares_entitled,gross,tax,net\n"
                "2025-01-03,AAA3,JCP,10,100,14,86\n",
                encoding="utf-8",
            )
            payload = {
                "start": "2025-01-02",
                "end": "2025-01-03",
                "final_equity": 1000.0,
                "trades": 0,
                "fees_paid": 0.0,
                "distributions_net": 86.0,
                "distribution_tax_paid": 14.0,
            }
            issues = _artifact_binding_issues(
                payload,
                curve_path=curve,
                trades_path=trades,
                cash_path=cash,
            )
            self.assertIn("cash_ledger_withholding_mismatch", issues)

    def test_tax_sales_and_realized_gain_are_bound_to_sell_ledger(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            curve = root / "curve.csv"
            trades = root / "trades.csv"
            cash = root / "cash.csv"
            tax = root / "tax.csv"
            curve.write_text(
                "date,equity\n2024-01-02,1000\n2024-01-03,1000\n",
                encoding="utf-8",
            )
            trades.write_text(
                "date,side,ticker,shares,market_type,raw_open,execution_price,notional,fee,slippage_bps,realized_gain\n"
                "2024-01-03,SELL,AAA3,10,020,10,9.99,99.9,0,10,5\n",
                encoding="utf-8",
            )
            cash.write_text("", encoding="utf-8")
            tax.write_text(
                "month,sales,realized_gain,tax_due,irrf_withheld_month\n"
                "2024-01,100,6,0,0\n",
                encoding="utf-8",
            )
            payload = {
                "start": "2024-01-02",
                "end": "2024-01-03",
                "initial_cash": 1000.0,
                "final_equity": 1000.0,
                "max_drawdown": 0.0,
                "annual_volatility": 0.0,
                "sharpe": 0.0,
                "average_annual_return": 0.0,
                "trades": 1,
                "fees_paid": 0.0,
                "distributions_net": 0.0,
                "distribution_tax_paid": 0.0,
                "ordinary_income_tax_paid": 0.0,
                "outstanding_accrued_tax_liability": 0.0,
            }
            issues = _artifact_binding_issues(
                payload,
                curve_path=curve,
                trades_path=trades,
                cash_path=cash,
                tax_path=tax,
            )
            self.assertIn("tax_ledger_sales_trade_mismatch", issues)
            self.assertIn("tax_ledger_realized_gain_trade_mismatch", issues)

    def test_finalist_rows_must_be_exact_unique_top_n(self):
        good = [
            {
                "rank": index,
                "trading_strategy": f"strategy_{index}",
                "management_strategy": f"management_{index}",
            }
            for index in range(1, 4)
        ]
        self.assertEqual(len(_validated_finalists(good, 3)), 3)
        duplicate = [dict(item) for item in good]
        duplicate[2]["trading_strategy"] = duplicate[1]["trading_strategy"]
        duplicate[2]["management_strategy"] = duplicate[1]["management_strategy"]
        with self.assertRaisesRegex(ValueError, "Duplicate finalist"):
            _validated_finalists(duplicate, 3)
        wrong_rank = [dict(item) for item in good]
        wrong_rank[1]["rank"] = 3
        with self.assertRaisesRegex(ValueError, "exactly 1..3"):
            _validated_finalists(wrong_rank, 3)

    def test_stale_candidate_summary_cannot_survive_success_without_new_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            stale = work / "candidate_01.json"
            stale.write_text('{"validity":"STALE"}', encoding="utf-8")
            with patch("scripts.validate_matrix_top_realistic.subprocess.run"):
                payload = _run_candidate(
                    rank=1,
                    strategy="buy_and_hold",
                    management="top1_momentum_lb63_skip0_trend0_vol21_equal_weekly_abs_cap1_adjusted",
                    start="2018-01-02",
                    end="2018-01-03",
                    initial_cash=1000.0,
                    output_dir=work,
                )
            self.assertEqual(payload.get("_candidate_artifact_error"), "FileNotFoundError")
            self.assertFalse(stale.exists())

    def test_canonical_and_rejected_outputs_are_cleared_before_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "REALISTIC_TOP_10.json"
            markdown = root / "REALISTIC_TOP_10.md"
            work = root / "candidates"
            work.mkdir()
            rejected = root / "REALISTIC_TOP_10_REJECTED.json"
            rejected_md = root / "REALISTIC_TOP_10_REJECTED.md"
            for path in (output, markdown, rejected, rejected_md, work / "candidate_old.json"):
                path.write_text("stale", encoding="utf-8")
            actual_rejected, actual_rejected_md = _clear_previous_validation_outputs(
                output, markdown, work
            )
            self.assertEqual(actual_rejected, rejected)
            self.assertEqual(actual_rejected_md, rejected_md)
            self.assertFalse(any(path.exists() for path in (output, markdown, rejected, rejected_md)))
            self.assertFalse((work / "candidate_old.json").exists())

    def test_production_workflow_matches_hardened_contract(self):
        workflow = Path(".github/workflows/full-matrix-backtest-hardened.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn('--require-valid "$TOP_N"', workflow)
        self.assertIn("reports/REALISTIC_TOP_10_REJECTED.json", workflow)
        self.assertIn("reports/REALISTIC_TOP_10_REJECTED.md", workflow)
        for obsolete in (
            ".github/workflows/fix-historical-issuer-refresh-once.yml",
            ".github/workflows/patch-freeze-preflight-once.yml",
            ".github/workflows/patch-pine-warmup-once.yml",
        ):
            self.assertFalse(Path(obsolete).exists(), obsolete)

    def test_bonus_policy_describes_only_held_through_bonus_risk(self):
        source = Path("scripts/backtest_strategy_management_realistic.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("actually held the affected position across the bonus date", source)
        self.assertIn('payload["execution_model"]', source)


if __name__ == "__main__":
    unittest.main()
