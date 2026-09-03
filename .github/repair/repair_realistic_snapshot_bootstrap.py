from pathlib import Path

workflow = Path('.github/workflows/full-matrix-backtest-hardened.yml')
text = workflow.read_text(encoding='utf-8')
old = '''            git fetch origin backtest-results:refs/remotes/origin/backtest-results
            SNAPSHOT=reports/latest_backtest/REALISTIC_INPUT_SNAPSHOT.tar.gz
            CHECKSUM=reports/latest_backtest/REALISTIC_INPUT_SNAPSHOT.sha256
            if ! git cat-file -e "origin/backtest-results:${SNAPSHOT}" 2>/dev/null; then
              echo "::error::Snapshot point-in-time certificado ausente. Execute manualmente com refresh_data=true."
              exit 1
            fi
            mkdir -p reports
            git show "origin/backtest-results:${SNAPSHOT}" > reports/REALISTIC_INPUT_SNAPSHOT.tar.gz
            git show "origin/backtest-results:${CHECKSUM}" > reports/REALISTIC_INPUT_SNAPSHOT.sha256
            (
              cd reports
              sha256sum -c REALISTIC_INPUT_SNAPSHOT.sha256
            )
            tar -xzf reports/REALISTIC_INPUT_SNAPSHOT.tar.gz
            python - "$REAL_END" <<'PY'
          import json, sys
          from pathlib import Path
          universe = json.loads(Path("data/universes/point_in_time_union.json").read_text())
          if str(universe.get("selection_end")) != sys.argv[1]:
              raise SystemExit(
                  "snapshot PIT diverge do cutoff da matriz: "
                  f"{universe.get('selection_end')} != {sys.argv[1]}"
              )
          PY
'''
new = '''            git fetch origin backtest-results:refs/remotes/origin/backtest-results
            SNAPSHOT=reports/latest_backtest/REALISTIC_INPUT_SNAPSHOT.tar.gz
            CHECKSUM=reports/latest_backtest/REALISTIC_INPUT_SNAPSHOT.sha256
            snapshot_exists=false
            checksum_exists=false
            git cat-file -e "origin/backtest-results:${SNAPSHOT}" 2>/dev/null && snapshot_exists=true
            git cat-file -e "origin/backtest-results:${CHECKSUM}" 2>/dev/null && checksum_exists=true
            if [ "$snapshot_exists" != "$checksum_exists" ]; then
              echo "::error::snapshot/checksum realista assimétricos em backtest-results"
              exit 1
            fi
            if [ "$snapshot_exists" = "true" ]; then
              mkdir -p reports
              git show "origin/backtest-results:${SNAPSHOT}" > reports/REALISTIC_INPUT_SNAPSHOT.tar.gz
              git show "origin/backtest-results:${CHECKSUM}" > reports/REALISTIC_INPUT_SNAPSHOT.sha256
              (
                cd reports
                sha256sum -c REALISTIC_INPUT_SNAPSHOT.sha256
              )
              tar -xzf reports/REALISTIC_INPUT_SNAPSHOT.tar.gz
              python - "$REAL_END" <<'PY'
          import json, sys
          from pathlib import Path
          universe = json.loads(Path("data/universes/point_in_time_union.json").read_text())
          if str(universe.get("selection_end")) != sys.argv[1]:
              raise SystemExit(
                  "snapshot PIT diverge do cutoff da matriz: "
                  f"{universe.get('selection_end')} != {sys.argv[1]}"
              )
          PY
            else
              echo "Snapshot PIT certificado ainda não existe; bootstrap por fontes oficiais."
              python scripts/build_survivorship_safe_realistic_universe.py \\
                --start "$REAL_START" --end "$REAL_END" --years "$SOURCE_YEARS" --download
              python scripts/build_ticker_transitions.py --years "$SOURCE_YEARS" --download
              python scripts/sync_point_in_time_universe_realistic.py \\
                --years "$SOURCE_YEARS" --download --refresh-actions
            fi
'''
count = text.count(old)
if count != 1:
    raise SystemExit(f'expected exactly one bootstrap block, found {count}')
workflow.write_text(text.replace(old, new), encoding='utf-8')

test = Path('tests/test_full_matrix_workflow_bootstrap.py')
test.write_text('''from pathlib import Path\nimport unittest\n\n\nclass FullMatrixWorkflowBootstrapTests(unittest.TestCase):\n    @classmethod\n    def setUpClass(cls):\n        cls.text = Path(\".github/workflows/full-matrix-backtest-hardened.yml\").read_text(encoding=\"utf-8\")\n\n    def test_missing_snapshot_bootstraps_from_official_sources(self):\n        marker = \"Snapshot PIT certificado ainda não existe; bootstrap por fontes oficiais.\"\n        self.assertIn(marker, self.text)\n        section = self.text[self.text.index(marker):]\n        self.assertIn(\"scripts/build_survivorship_safe_realistic_universe.py\", section)\n        self.assertIn(\"scripts/build_ticker_transitions.py\", section)\n        self.assertIn(\"scripts/sync_point_in_time_universe_realistic.py\", section)\n        self.assertNotIn(\"Snapshot point-in-time certificado ausente. Execute manualmente com refresh_data=true.\", section[:1200])\n\n    def test_snapshot_checksum_pair_remains_fail_closed(self):\n        self.assertIn(\"snapshot_exists=false\", self.text)\n        self.assertIn(\"checksum_exists=false\", self.text)\n        self.assertIn('if [ \"$snapshot_exists\" != \"$checksum_exists\" ]; then', self.text)\n        self.assertIn(\"snapshot/checksum realista assimétricos em backtest-results\", self.text)\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n''', encoding='utf-8')

legacy_test = Path('tests/test_execution_hardening.py')
legacy = legacy_test.read_text(encoding='utf-8')
old_assert = "        self.assertIn('refresh_data=true', workflow)\n"
new_assert = (
    "        self.assertIn(\n"
    "            'Snapshot PIT certificado ainda não existe; bootstrap por fontes oficiais.',\n"
    "            workflow,\n"
    "        )\n"
)
if legacy.count(old_assert) != 1:
    raise SystemExit(f'expected one legacy refresh assertion, found {legacy.count(old_assert)}')
legacy_test.write_text(legacy.replace(old_assert, new_assert), encoding='utf-8')
