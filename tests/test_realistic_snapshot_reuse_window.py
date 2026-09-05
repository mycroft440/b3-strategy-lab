from __future__ import annotations

import unittest
from pathlib import Path


WORKFLOW = Path(".github/workflows/full-matrix-backtest-hardened.yml")


class RealisticSnapshotReuseWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        start = text.index("- name: Resolver período e preparar dados point-in-time")
        end = text.index("- name: Auditar prontidão realista e nível de certificação", start)
        cls.block = text[start:end]

    def test_snapshot_matches_both_start_and_end_before_reuse(self) -> None:
        self.assertIn('payload.get("selected_as_of")', self.block)
        self.assertIn('payload.get("selection_end")', self.block)
        self.assertIn('"$REAL_START" "$REAL_END"', self.block)
        self.assertIn('SNAPSHOT_PERIOD_MATCH=false', self.block)
        self.assertIn('SNAPSHOT_PERIOD_MATCH=true', self.block)

    def test_snapshot_manifest_is_extracted_to_file_not_piped_into_python_stdin(self) -> None:
        self.assertIn('SNAPSHOT_UNIVERSE=reports/snapshot_point_in_time_union.json', self.block)
        self.assertIn('> "$SNAPSHOT_UNIVERSE" 2>/dev/null', self.block)
        self.assertIn('python - "$SNAPSHOT_UNIVERSE" "$REAL_START" "$REAL_END"', self.block)
        self.assertNotIn('| python - "$REAL_START" "$REAL_END"', self.block)

    def test_mismatch_rebuilds_instead_of_extracting_stale_snapshot(self) -> None:
        match_branch = self.block.index('if [ "$SNAPSHOT_PERIOD_MATCH" = "true" ]; then')
        extraction = self.block.index('tar -xzf reports/REALISTIC_INPUT_SNAPSHOT.tar.gz', match_branch)
        mismatch = self.block.index('BUILD_REALISTIC_DATA=true', extraction)
        self.assertLess(match_branch, extraction)
        self.assertLess(extraction, mismatch)
        self.assertIn('estruturalmente incompatível; reconstruindo pelas fontes oficiais', self.block)

    def test_checksum_still_precedes_window_inspection(self) -> None:
        checksum = self.block.index('sha256sum -c REALISTIC_INPUT_SNAPSHOT.sha256')
        inspect = self.block.index('SNAPSHOT_UNIVERSE=reports/snapshot_point_in_time_union.json')
        self.assertLess(checksum, inspect)


if __name__ == "__main__":
    unittest.main()
