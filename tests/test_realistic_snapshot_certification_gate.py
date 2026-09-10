from __future__ import annotations

import unittest
from pathlib import Path


WORKFLOW = Path(".github/workflows/full-matrix-backtest-hardened.yml")


class RealisticSnapshotCertificationGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_realistic_input_audit_has_stable_step_id(self) -> None:
        marker = (
            "- name: Auditar prontidão realista e nível de certificação price-only\n"
            "        id: realistic_audit"
        )
        self.assertIn(marker, self.text)

    def test_estimate_requires_structural_readiness(self) -> None:
        self.assertIn('estimate_ready = not audit["estimate_blockers"]', self.text)
        self.assertIn('output.write("estimate_ready=true\\n")', self.text)
        self.assertIn('audit["cash_distributions_scope"] = "OUT_OF_SCOPE_BY_USER"', self.text)
        self.assertIn('audit["cash_distributions_used"] = False', self.text)

    def test_snapshot_requires_explicit_certified_output(self) -> None:
        condition = (
            "if: ${{ always() && steps.realistic_data.outcome == 'success' "
            "&& steps.realistic_audit.outputs.certified == 'true' }}"
        )
        self.assertIn(condition, self.text)
        self.assertNotIn(
            "steps.realistic_audit.outcome == 'success' }}\n        run: |\n          set -euo pipefail\n          tar",
            self.text,
        )

    def test_price_only_snapshot_excludes_dividend_jcp_ledgers(self) -> None:
        snapshot = self.text.split(
            "- name: Empacotar snapshot exato dos insumos realistas price-only", 1
        )[1].split("- name: Reexecutar Top 10 price-only", 1)[0]
        self.assertNotIn("point_in_time_cash_distributions.csv", snapshot)
        self.assertNotIn("cash_distribution_coverage_certification.json", snapshot)
        self.assertIn("point_in_time_split_evidence.json", snapshot)
        self.assertIn("ticker_transitions.csv", snapshot)
        self.assertIn("b3_equity_fee_schedule.json", snapshot)

    def test_uncertified_finalists_publish_rejection_diagnostics_not_certificate(self) -> None:
        self.assertIn("REALISTIC_TOP_10_REJECTED.json", self.text)
        self.assertIn("RESEARCH_SUCCESS_REALISTIC_BLOCKED", self.text)
        self.assertIn('if [ "$STATUS" = "REALISTIC_RETROSPECTIVE_SUCCESS" ]; then', self.text)
        self.assertIn(
            'if status["status"] != "REALISTIC_RETROSPECTIVE_SUCCESS":', self.text
        )


if __name__ == "__main__":
    unittest.main()
