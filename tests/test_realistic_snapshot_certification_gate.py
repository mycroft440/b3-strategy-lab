from __future__ import annotations

import unittest
from pathlib import Path


WORKFLOW = Path(".github/workflows/full-matrix-backtest-hardened.yml")


class RealisticSnapshotCertificationGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_realistic_input_audit_has_stable_step_id(self) -> None:
        marker = "- name: Auditar prontidão realista e nível de certificação\n        id: realistic_audit"
        self.assertIn(marker, self.text)

    def test_estimate_requires_structural_readiness(self) -> None:
        self.assertIn('audit.get("ready_for_realistic_estimate") is not True', self.text)
        self.assertIn('output.write("estimate_ready=true\\n")', self.text)

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

    def test_uncertified_finalists_publish_rejection_diagnostics_not_certificate(self) -> None:
        self.assertIn("REALISTIC_TOP_10_REJECTED.json", self.text)
        self.assertIn("RESEARCH_SUCCESS_REALISTIC_BLOCKED", self.text)
        self.assertIn('if [ "$STATUS" = "REALISTIC_RETROSPECTIVE_SUCCESS" ]; then', self.text)


if __name__ == "__main__":
    unittest.main()
