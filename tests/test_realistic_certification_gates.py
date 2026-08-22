from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from b3_strategy_lab.realistic_certification import (
    bonus_tax_basis_dependencies,
    sha256_file,
    terminal_month_tax_policy,
    transition_binding_issues,
)


class RealisticCertificationGateTests(unittest.TestCase):
    def test_transition_manifest_is_bound_to_exact_csv_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transitions = root / "ticker_transitions.csv"
            manifest = root / "ticker_transitions.manifest.json"
            with transitions.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=["effective_date", "old_ticker", "new_ticker"],
                    lineterminator="\n",
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "effective_date": "2020-01-02",
                        "old_ticker": "AAA3",
                        "new_ticker": "BBB3",
                    }
                )
            manifest.write_text(
                json.dumps(
                    {
                        "complete": True,
                        "coverage_end": "2020-12-30",
                        "transition_file": str(transitions),
                        "transition_csv_sha256": sha256_file(transitions),
                        "transition_row_count": 1,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                transition_binding_issues(
                    transitions, manifest, expected_end="2020-12-30"
                ),
                [],
            )

            transitions.write_text(
                transitions.read_text(encoding="utf-8") + "2020-02-01,BBB3,CCC3\n",
                encoding="utf-8",
            )
            issues = transition_binding_issues(
                transitions, manifest, expected_end="2020-12-30"
            )
            self.assertIn("ticker_transition_csv_sha256_mismatch", issues)
            self.assertIn("ticker_transition_row_count_mismatch", issues)

    def test_sale_after_stock_bonus_blocks_certified_tax_basis(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "splits.json"
            evidence.write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "ticker": "AAA3",
                                "ex_date": "2021-04-05",
                                "event": "BONIFICACAO",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            dependencies = bonus_tax_basis_dependencies(
                evidence,
                [{"date": "2021-04-06", "side": "SELL", "ticker": "AAA3"}],
                start="2021-01-01",
                end="2021-12-30",
            )
            self.assertEqual(len(dependencies), 1)
            self.assertEqual(
                dependencies[0]["reason"],
                "stock_bonus_tax_basis_not_applied_by_engine",
            )

    def test_candidate_bonus_basis_field_does_not_bypass_unimplemented_engine_rule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "splits.json"
            evidence.write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "ticker": "AAA3",
                                "ex_date": "2021-04-05",
                                "event": "BONIFICACAO",
                                "tax_basis_per_new_share": 2.5,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            dependencies = bonus_tax_basis_dependencies(
                evidence,
                [{"date": "2021-04-06", "side": "SELL", "ticker": "AAA3"}],
                start="2021-01-01",
                end="2021-12-30",
            )
            self.assertEqual(len(dependencies), 1)
            self.assertEqual(
                dependencies[0]["reason"],
                "stock_bonus_tax_basis_not_applied_by_engine",
            )

    def test_bonus_basis_risk_follows_source_backed_ticker_rename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = root / "splits.json"
            transitions = root / "transitions.csv"
            evidence.write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "ticker": "AAA3",
                                "ex_date": "2021-04-05",
                                "event": "BONIFICACAO",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with transitions.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=["effective_date", "old_ticker", "new_ticker"],
                    lineterminator="\n",
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "effective_date": "2021-06-01",
                        "old_ticker": "AAA3",
                        "new_ticker": "BBB3",
                    }
                )
            dependencies = bonus_tax_basis_dependencies(
                evidence,
                [{"date": "2021-07-01", "side": "SELL", "ticker": "BBB3"}],
                start="2021-01-01",
                end="2021-12-30",
                transition_csv_path=transitions,
            )
            self.assertEqual(len(dependencies), 1)
            self.assertEqual(dependencies[0]["original_bonus_ticker"], "AAA3")
            self.assertEqual(dependencies[0]["ticker"], "BBB3")

    def test_terminal_month_policy_discloses_no_later_trade_assumption(self) -> None:
        policy = terminal_month_tax_policy("2026-08-21")
        self.assertEqual(policy["terminal_tax_month"], "2026-08")
        self.assertEqual(policy["terminal_tax_finalized_through"], "2026-08-21")
        self.assertFalse(policy["terminal_month_full_calendar_activity_known"])
        self.assertIn("no additional strategy trades", policy["terminal_month_assumption"])


if __name__ == "__main__":
    unittest.main()
