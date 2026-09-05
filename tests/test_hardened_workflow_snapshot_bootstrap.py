from pathlib import Path
import unittest


WORKFLOW = Path(".github/workflows/full-matrix-backtest-hardened.yml")


class HardenedWorkflowSnapshotBootstrapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        marker = "- name: Resolver período e preparar dados point-in-time"
        start = cls.text.index(marker)
        end = cls.text.index("- name: Auditar prontidão realista e nível de certificação", start)
        cls.block = cls.text[start:end]

    def test_missing_snapshot_bootstraps_from_certified_builders(self):
        self.assertIn('snapshot_exists=false', self.block)
        self.assertIn('checksum_exists=false', self.block)
        self.assertIn('if [ "$snapshot_exists" != "$checksum_exists" ]; then', self.block)
        self.assertIn('if [ "$snapshot_exists" = "false" ]; then', self.block)
        self.assertIn('scripts/build_survivorship_safe_realistic_universe.py', self.block)
        self.assertIn('scripts/build_ticker_transitions.py', self.block)
        self.assertIn('scripts/sync_point_in_time_universe_realistic.py', self.block)

    def test_reuse_path_keeps_checksum_and_pit_cutoff_gates(self):
        self.assertIn('sha256sum -c REALISTIC_INPUT_SNAPSHOT.sha256', self.block)
        self.assertIn('selected_as_of', self.block)
        self.assertIn('selection_end', self.block)
        self.assertIn('SNAPSHOT_PERIOD_MATCH=false', self.block)
        self.assertIn('if [ "$SNAPSHOT_PERIOD_MATCH" = "true" ]; then', self.block)
        self.assertIn('Snapshot PIT corresponde exatamente ao período $REAL_START..$REAL_END; reutilizando.', self.block)
        self.assertIn('Snapshot PIT certificado pertence a outra janela ou é estruturalmente incompatível; reconstruindo pelas fontes oficiais.', self.block)
        self.assertIn('BUILD_REALISTIC_DATA=true', self.block)

    def test_bootstrap_does_not_bypass_certification_gate(self):
        following = self.text[self.text.index("- name: Auditar prontidão realista e nível de certificação"):]
        self.assertIn('scripts/audit_realistic_backtest_inputs.py', following)
        self.assertIn('ready_for_certified_market_inputs', following)
        self.assertIn('sha256sum REALISTIC_INPUT_SNAPSHOT.tar.gz', following)


if __name__ == "__main__":
    unittest.main()
