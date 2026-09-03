from __future__ import annotations

import json
import math
import tempfile
import unittest
from datetime import date
from pathlib import Path

from b3_strategy_lab.cash_distributions import build_cash_events
from b3_strategy_lab.realistic_certification import bonus_tax_basis_dependencies
from scripts.audit_backtest_readiness import _weekday_gap
from scripts.build_ticker_transitions import _same_isin_transition_rows
from scripts.research_portfolio_allocation_core import _portfolio_metrics
from scripts.validate_matrix_top_realistic import _required_valid_count, _validation_issues


class ComprehensiveAuditFixTests(unittest.TestCase):
    def test_first_session_loss_is_in_all_risk_metrics(self):
        metrics = _portfolio_metrics(
            [900.0, 900.0, 900.0],
            ["2024-01-02", "2024-01-03", "2024-01-04"],
            1000.0,
        )
        self.assertAlmostEqual(metrics["total_return"], -0.1)
        self.assertAlmostEqual(metrics["max_drawdown"], -0.1)
        self.assertGreater(metrics["annual_volatility"], 0.0)
        self.assertTrue(math.isfinite(metrics["sharpe"]))

    def test_historical_cash_placeholder_is_blocking_not_zero_events(self):
        class Quote:
            date = "2024-01-02"
            isin = "BRAAAACNOR0"

        rows, issues = build_cash_events(
            ["AAA3"],
            {"AAA3": "AAAA"},
            {
                "AAAA": [
                    {
                        "code": "AAAA",
                        "stockDividends": [],
                        "_cash_dividends_source_available": False,
                    }
                ]
            },
            {"AAA3": [Quote()]},
        )
        self.assertEqual(rows, [])
        self.assertIn(
            "historical_cash_dividend_source_unavailable",
            {item.get("issue") for item in issues},
        )

    def test_top_ten_compatibility_flag_cannot_weaken_all_finalists_gate(self):
        self.assertEqual(_required_valid_count(10, 1), 10)
        self.assertEqual(_required_valid_count(10, 10), 10)


    def test_candidate_runtime_failure_is_excluded_not_misparsed(self):
        self.assertEqual(
            _validation_issues({"_candidate_execution_error": "exit_code=2"}),
            ["candidate_execution_failed:exit_code=2"],
        )

    def test_pre_start_bonus_does_not_poison_later_purchase(self):
        with tempfile.TemporaryDirectory() as tmp:
            split = Path(tmp) / "split.json"
            split.write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "event": "BONIFICACAO",
                                "ex_date": "2019-01-02",
                                "ticker": "AAA3",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            trades = [
                {"date": "2024-01-03", "side": "BUY", "ticker": "AAA3", "shares": 10},
                {"date": "2024-02-01", "side": "SELL", "ticker": "AAA3", "shares": 10},
            ]
            self.assertEqual(
                bonus_tax_basis_dependencies(
                    split, trades, start="2024-01-01", end="2024-12-31"
                ),
                [],
            )

    def test_bonus_only_blocks_when_position_crosses_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            split = Path(tmp) / "split.json"
            split.write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "event": "BONIFICACAO",
                                "ex_date": "2024-01-15",
                                "ticker": "AAA3",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            no_holding = [
                {"date": "2024-01-20", "side": "BUY", "ticker": "AAA3", "shares": 10},
                {"date": "2024-02-01", "side": "SELL", "ticker": "AAA3", "shares": 10},
            ]
            self.assertEqual(
                bonus_tax_basis_dependencies(
                    split, no_holding, start="2024-01-01", end="2024-12-31"
                ),
                [],
            )
            held = [
                {"date": "2024-01-03", "side": "BUY", "ticker": "AAA3", "shares": 10},
                {"date": "2024-02-01", "side": "SELL", "ticker": "AAA3", "shares": 10},
            ]
            issues = bonus_tax_basis_dependencies(
                split, held, start="2024-01-01", end="2024-12-31"
            )
            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0]["bonus_ex_date"], "2024-01-15")

    def test_same_isin_overlap_is_rejected(self):
        class Quote:
            def __init__(self, value_date, ticker):
                self.date = value_date
                self.ticker = ticker

        with self.assertRaisesRegex(ValueError, "simultaneous same-ISIN"):
            _same_isin_transition_rows(
                [Quote("2024-01-02", "AAA3"), Quote("2024-01-02", "BBB3")],
                "BRAAAACNOR0",
            )

    def test_same_isin_clean_rename_is_strictly_chronological(self):
        class Quote:
            def __init__(self, value_date, ticker):
                self.date = value_date
                self.ticker = ticker

        rows = _same_isin_transition_rows(
            [Quote("2024-01-02", "AAA3"), Quote("2024-01-03", "BBB3")],
            "BRAAAACNOR0",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["old_ticker"], "AAA3")
        self.assertEqual(rows[0]["new_ticker"], "BBB3")

    def test_long_weekend_does_not_look_five_days_stale(self):
        # Friday -> following Wednesday has five calendar-day age but only two
        # intervening weekdays (Monday/Tuesday). The audit can tolerate a long closure.
        self.assertEqual(_weekday_gap(date(2024, 3, 28), date(2024, 4, 2)), 2)


if __name__ == "__main__":
    unittest.main()
