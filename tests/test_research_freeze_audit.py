from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from b3_strategy_lab.strategies import strategy_parameters
from scripts.audit_research_freezes import audit_freeze, main
from scripts.research_portfolio_allocation import _configs

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "data/research_freezes/gap_momentum_top1_2026-08-19.json"
REALISTIC_FREEZE = ROOT / "data/research_freezes/gap_momentum_realistic_point_in_time_2026-08-19.json"


class ResearchFreezeAuditTests(unittest.TestCase):
    def test_gap_momentum_freeze_matches_runtime_contract(self) -> None:
        frozen = json.loads(FREEZE.read_text(encoding="utf-8"))
        self.assertEqual(frozen["strategy"]["parameters"], {"period": 40, "signal_period": 20})
        self.assertEqual(
            strategy_parameters("gap_momentum"),
            frozen["strategy"]["parameters"],
        )
        configs = {config.name: config for config in _configs("adjusted", "all")}
        self.assertIn(frozen["management"]["name"], configs)
        audited = audit_freeze(FREEZE)
        self.assertEqual(audited["contract_type"], "retrospective_price_only")
        self.assertTrue(audited["ready"], audited)

    def test_realistic_gap_freeze_preserves_its_declared_subset_contract(self) -> None:
        audited = audit_freeze(REALISTIC_FREEZE)
        self.assertEqual(audited["contract_type"], "realistic_point_in_time")
        self.assertTrue(audited["checks"]["execution_is_next_session_open"])
        self.assertTrue(audited["checks"]["execution_market_contract_is_explicit"])
        self.assertTrue(audited["checks"]["accounting_fails_closed_on_stale_prices"])
        self.assertTrue(audited["ready"], audited)

    def test_audit_rejects_silent_parameter_change(self) -> None:
        frozen = json.loads(FREEZE.read_text(encoding="utf-8"))
        frozen["strategy"]["parameters"]["period"] = 41
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "changed.json"
            path.write_text(json.dumps(frozen), encoding="utf-8")
            audited = audit_freeze(path)
        self.assertFalse(audited["ready"])
        self.assertFalse(audited["checks"]["strategy_parameters_match_runtime_defaults"])

    def test_cli_writes_ready_report_for_repository_freezes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "audit.json"
            result = main(["--freeze-dir", str(FREEZE.parent), "--output", str(output)])
            payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result, 0)
        self.assertTrue(payload["ready"])
        self.assertEqual(payload["freeze_count"], 2)


if __name__ == "__main__":
    unittest.main()
