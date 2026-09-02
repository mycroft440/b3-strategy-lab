from __future__ import annotations

import unittest
from pathlib import Path


class WorkflowIntegrityContractTests(unittest.TestCase):
    def test_recovery_uses_original_calculation_commit_as_filesystem(self) -> None:
        text = Path(".github/workflows/recover-backtest-merge-hardened.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("CALCULATION_SHA=", text)
        self.assertIn('git worktree add --detach "$SOURCE_DIR" "$CALCULATION_SHA"', text)
        self.assertIn("sourceRun.data.head_sha !== process.env.CALCULATION_SHA", text)
        self.assertIn(".github/workflows/full-matrix-backtest-hardened.yml", text)
        self.assertIn("verified-market-data-${{ env.SOURCE_RUN_ID }}", text)
        self.assertIn('SOURCE_DATA="$GITHUB_WORKSPACE/recovery-source-data"', text)
        self.assertIn('cp -a "$SOURCE_DATA/candles" "$SOURCE_DIR/data/candles"', text)
        self.assertGreaterEqual(text.count('cd "$SOURCE_DIR"'), 3)

    def test_snapshot_checksum_asymmetry_is_fail_closed_everywhere(self) -> None:
        recovery = Path(".github/workflows/recover-backtest-merge-hardened.yml").read_text(
            encoding="utf-8"
        )
        matrix = Path(".github/workflows/full-matrix-backtest-hardened.yml").read_text(
            encoding="utf-8"
        )
        marker = "snapshot/checksum realista assimétricos em backtest-results"
        self.assertIn(marker, recovery)
        self.assertGreaterEqual(matrix.count(marker), 2)


if __name__ == "__main__":
    unittest.main()
