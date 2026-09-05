from __future__ import annotations

import unittest
from pathlib import Path


WORKFLOW = Path(".github/workflows/full-matrix-backtest-hardened.yml")


class HardenedBacktestPerformanceSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_all_32_shards_are_allowed_to_run_concurrently(self) -> None:
        self.assertIn('SHARD_COUNT: "32"', self.text)
        self.assertIn("max-parallel: 32", self.text)
        self.assertNotIn("max-parallel: 16", self.text)

    def test_long_backtests_are_not_cancelled_by_new_pushes(self) -> None:
        self.assertIn("cancel-in-progress: false", self.text)
        self.assertNotIn("cancel-in-progress: true", self.text)


    def test_runner_cpu_cap_is_four_not_two(self) -> None:
        self.assertIn('if [ "$WORKERS" -gt 4 ]; then WORKERS=4; fi', self.text)
        self.assertNotIn('if [ "$WORKERS" -gt 2 ]; then WORKERS=2; fi', self.text)

    def test_shard_artifact_paths_are_bound_to_matrix_index(self) -> None:
        required_paths = (
            'reports/shards/shard_${{ matrix.index }}.csv.gz',
            'reports/shards/shard_${{ matrix.index }}.manifest.json',
            'reports/shards/shard_${{ matrix.index }}_top10_annual.md',
        )
        for path in required_paths:
            with self.subTest(path=path):
                self.assertIn(path, self.text)

    def test_realistic_finalists_use_bounded_parallelism(self) -> None:
        self.assertIn("scripts/validate_matrix_top_realistic.py", self.text)
        self.assertIn("--workers 2", self.text)
        self.assertIn("--require-valid \"$TOP_N\"", self.text)

    def test_original_and_frozen_validator_core_are_compiled(self) -> None:
        self.assertIn("scripts/validate_matrix_top_realistic.py", self.text)
        self.assertIn("scripts/validate_matrix_top_realistic_core.py", self.text)

    def test_integrity_audits_remain_in_the_workflow(self) -> None:
        required = (
            "audit_backtest_readiness.py",
            "audit_backtest_integrity.py",
            "audit_volume_indicators.py",
            "audit_realistic_backtest_inputs.py",
            "sha256sum -c REALISTIC_INPUT_SNAPSHOT.sha256",
            "Exigir classificação final consistente",
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.text)


if __name__ == "__main__":
    unittest.main()
