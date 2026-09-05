from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / ".github/workflows/full-matrix-backtest-hardened.yml"


class ExAnteProductionWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = PRODUCTION.read_text(encoding="utf-8")

    def test_same_period_realistic_top10_is_not_final_selection_gate(self) -> None:
        section = self.workflow.split("  realistic_validation:\n", 1)[1].split("\n  publish:\n", 1)[0]
        self.assertIn("Auditar PIT e congelar candidato prospectivo", section)
        self.assertIn("scripts/audit_point_in_time_validation.py", section)
        self.assertIn("scripts/freeze_ex_ante_candidate.py", section)
        self.assertNotIn("validate_matrix_top_realistic.py", section)
        self.assertNotIn("REALISTIC_TOP_10.json", section)
        self.assertNotIn("--holdout-start", section)
        self.assertIn('frozen["status"] == "PROSPECTIVE_FROZEN_PENDING"', section)

    def test_workflow_cannot_promote_retrospective_success_as_certificate(self) -> None:
        self.assertNotIn("REALISTIC_RETROSPECTIVE_SUCCESS", self.workflow)
        self.assertNotIn("REALISTIC_POINT_IN_TIME_RETROSPECTIVE_FINALIST_REPLAY", self.workflow)
        self.assertIn("RESEARCH_SUCCESS_PROSPECTIVE_FROZEN", self.workflow)
        self.assertIn("RESEARCH_SUCCESS_POINT_IN_TIME_BLOCKED", self.workflow)
        self.assertIn("latest_freeze", self.workflow)
        self.assertIn("latest_certified remains untouched", self.workflow)

    def test_final_status_disallows_in_sample_winner_claim(self) -> None:
        self.assertIn('"validated_winner_available": False', self.workflow)
        self.assertIn('"in_sample_winner_claim_allowed": False', self.workflow)
        self.assertIn('"ex_ante_selection_claim_allowed": False', self.workflow)
        self.assertIn('"formal_multiple_testing_significance_claim_allowed": False', self.workflow)
        self.assertIn("wall_clock_prospective_freeze_no_historical_holdout_retrocertification", self.workflow)

    def test_pit_gate_is_bound_to_strict_runtime_inputs(self) -> None:
        self.assertIn("POINT_IN_TIME_VALIDATION.json", self.workflow)
        self.assertIn('pit.get("point_in_time_validation_complete") is True', self.workflow)
        self.assertIn('pit.get("cash_announcement_timing_certified") is True', self.workflow)
        self.assertIn('pit.get("ticker_transition_binding_verified") is True', self.workflow)
        self.assertIn("data/candles_point_in_time", self.workflow)
        self.assertIn("data/actions_point_in_time", self.workflow)
        self.assertIn("data/manifests_point_in_time", self.workflow)
        self.assertIn("data/execution", self.workflow)

    def test_freeze_is_fail_closed_and_has_no_fallback(self) -> None:
        self.assertIn('frozen.get("fallback_candidate_allowed") is False', self.workflow)
        self.assertIn('frozen.get("future_result_may_change_candidate") is False', self.workflow)
        self.assertIn('frozen.get("historical_holdout_claim_allowed") is False', self.workflow)
        self.assertIn('frozen.get("information_cutoff") == manifest.get("end")', self.workflow)


if __name__ == "__main__":
    unittest.main()
