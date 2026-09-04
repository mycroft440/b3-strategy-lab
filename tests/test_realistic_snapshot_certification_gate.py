from __future__ import annotations

import unittest
from pathlib import Path


WORKFLOW = Path(".github/workflows/full-matrix-backtest-hardened.yml")


class RealisticSnapshotCertificationGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_realistic_input_audit_has_stable_step_id(self) -> None:
        marker = "- name: Exigir insumos realistas certificados\n        id: realistic_audit"
        self.assertIn(marker, self.text)

    def test_snapshot_requires_successful_data_build_and_certification_audit(self) -> None:
        condition = (
            "if: ${{ always() && steps.realistic_data.outcome == 'success' "
            "&& steps.realistic_audit.outcome == 'success' }}"
        )
        self.assertIn(condition, self.text)

    def test_snapshot_cannot_depend_on_data_step_alone(self) -> None:
        unsafe = "if: ${{ always() && steps.realistic_data.outcome == 'success' }}"
        self.assertNotIn(unsafe, self.text)


if __name__ == "__main__":
    unittest.main()
