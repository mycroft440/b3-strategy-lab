from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"{label}: expected source block not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# 1) Keep the low-level BDI58 validator aligned with the point-in-time share
# ticker contract. Valid issuer roots may contain a digit (for example B3SA3).
cotahist = ROOT / "b3_strategy_lab/cotahist.py"
replace_once(
    cotahist,
    '_COMPANY_SHARE_TICKER_RE = re.compile(r"^[A-Z]{4}\\d{1,2}$")',
    '_COMPANY_SHARE_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9]{3}\\d{1,2}$")',
    "BDI58 alphanumeric ticker regex",
)

bdi_test = ROOT / "tests/test_bdi58_goll4_regression.py"
bdi_text = bdi_test.read_text(encoding="utf-8")
if "test_bdi58_keeps_alphanumeric_company_share_root" not in bdi_text:
    anchor = '\n\nif __name__ == "__main__":\n    unittest.main()\n'
    addition = '''\n\n    def test_bdi58_keeps_alphanumeric_company_share_root(self) -> None:\n        rows = [\n            _record(\n                day="2025-01-02",\n                bdi="58",\n                ticker="B3SA3",\n                spec="ON NM",\n                close=12.34,\n                isin="BRB3SAACNOR6",\n            ),\n        ]\n        with tempfile.TemporaryDirectory() as directory:\n            quotes = read_standard_company_equity_cotahist(_archive(rows, Path(directory)))\n        self.assertEqual([(q.ticker, q.bdi_code) for q in quotes], [("B3SA3", "58")])\n'''
    if anchor not in bdi_text:
        raise SystemExit("BDI58 test anchor missing")
    bdi_test.write_text(bdi_text.replace(anchor, addition + anchor, 1), encoding="utf-8")


# 2) Production matrix workflow: long runs must not cancel each other. A realistic
# estimate may run when structural inputs are ready even if documentary market-input
# certification is incomplete; only fully certified runs can build/promote a snapshot.
workflow = ROOT / ".github/workflows/full-matrix-backtest-hardened.yml"
replace_once(
    workflow,
    "  cancel-in-progress: true\n",
    "  cancel-in-progress: false\n",
    "backtest concurrency cancellation",
)

old_audit = '''      - name: Exigir insumos realistas certificados
        id: realistic_audit
        run: |
          set -euo pipefail
          python scripts/audit_realistic_backtest_inputs.py
          python - <<'PY'
          import json
          from pathlib import Path
          audit = json.loads(Path("reports/realistic_input_audit.json").read_text())
          if audit.get("ready_for_certified_market_inputs") is not True:
              raise SystemExit(
                  "realistic inputs are not certified: "
                  + repr(audit.get("certified_market_input_blockers"))
              )
          PY
'''
new_audit = '''      - name: Auditar prontidão realista e nível de certificação
        id: realistic_audit
        run: |
          set -euo pipefail
          set +e
          python scripts/audit_realistic_backtest_inputs.py
          AUDIT_RC=$?
          set -e
          python - "$GITHUB_OUTPUT" "$AUDIT_RC" <<'PY'
          import json, sys
          from pathlib import Path
          audit = json.loads(Path("reports/realistic_input_audit.json").read_text())
          audit_rc = int(sys.argv[2])
          if audit_rc not in {0, 2}:
              raise SystemExit(f"realistic input audit crashed with exit code {audit_rc}")
          if audit.get("ready_for_realistic_estimate") is not True:
              raise SystemExit(
                  "realistic structural inputs are not ready: "
                  + repr(audit.get("estimate_blockers"))
              )
          certified = audit.get("ready_for_certified_market_inputs") is True
          with Path(sys.argv[1]).open("a", encoding="utf-8") as output:
              output.write("estimate_ready=true\\n")
              output.write(f"certified={'true' if certified else 'false'}\\n")
          if not certified:
              print(
                  "::warning::realistic estimate can run, but documentary market-input "
                  "certification is incomplete: "
                  + repr(audit.get("certified_market_input_blockers"))
              )
          PY
'''
replace_once(workflow, old_audit, new_audit, "realistic audit classification")

replace_once(
    workflow,
    "        if: ${{ always() && steps.realistic_data.outcome == 'success' && steps.realistic_audit.outcome == 'success' }}\n",
    "        if: ${{ always() && steps.realistic_data.outcome == 'success' && steps.realistic_audit.outputs.certified == 'true' }}\n",
    "certified snapshot condition",
)

old_replay = '''      - name: Reexecutar Top 10 com fracionário, proventos, impostos e slippage causal
        run: |
          set -euo pipefail
          mkdir -p reports
          cp research-artifact/TOP_10.json reports/TOP_10.json
          python scripts/validate_matrix_top_realistic.py \\
            --candidates reports/TOP_10.json \\
            --output reports/REALISTIC_TOP_10.json \\
            --markdown-output reports/REALISTIC_TOP_10.md \\
            --workers 2 \\
            --require-valid "$TOP_N"
          cat reports/REALISTIC_TOP_10.md >> "$GITHUB_STEP_SUMMARY"
'''
new_replay = '''      - name: Reexecutar Top 10 com fracionário, proventos, impostos e slippage causal
        id: realistic_replay
        run: |
          set -euo pipefail
          mkdir -p reports
          cp research-artifact/TOP_10.json reports/TOP_10.json
          set +e
          python scripts/validate_matrix_top_realistic.py \\
            --candidates reports/TOP_10.json \\
            --output reports/REALISTIC_TOP_10.json \\
            --markdown-output reports/REALISTIC_TOP_10.md \\
            --workers 2 \\
            --require-valid "$TOP_N"
          REPLAY_RC=$?
          set -e
          if [ "$REPLAY_RC" -eq 0 ]; then
            echo "validation_passed=true" >> "$GITHUB_OUTPUT"
            cat reports/REALISTIC_TOP_10.md >> "$GITHUB_STEP_SUMMARY"
          else
            if [ ! -f reports/REALISTIC_TOP_10_REJECTED.json ]; then
              echo "::error::realistic finalist replay crashed before producing a fail-closed rejection artifact"
              exit "$REPLAY_RC"
            fi
            echo "validation_passed=false" >> "$GITHUB_OUTPUT"
            if [ -f reports/REALISTIC_TOP_10_REJECTED.md ]; then
              cat reports/REALISTIC_TOP_10_REJECTED.md >> "$GITHUB_STEP_SUMMARY"
            fi
            echo "::warning::realistic finalists were executed but rejected by certification gates"
          fi
'''
replace_once(workflow, old_replay, new_replay, "realistic replay blocked-result handling")

replace_once(
    workflow,
    "        if: ${{ always() && steps.realistic_snapshot.outputs.ready == 'true' }}\n        uses: actions/upload-artifact@v4\n",
    "        if: ${{ always() && steps.realistic_data.outcome == 'success' && steps.realistic_audit.outcome == 'success' }}\n        uses: actions/upload-artifact@v4\n",
    "realistic diagnostics upload condition",
)

replace_once(
    workflow,
    "        if: ${{ needs.realistic_validation.outputs.snapshot_ready == 'true' }}\n        uses: actions/download-artifact@v4\n        with:\n          name: b3-strategy-lab-realistic-top10-${{ github.run_number }}\n",
    "        if: ${{ needs.realistic_validation.result == 'success' }}\n        uses: actions/download-artifact@v4\n        with:\n          name: b3-strategy-lab-realistic-top10-${{ github.run_number }}\n",
    "realistic diagnostics download condition",
)

old_copy = '''          REALISTIC_SNAPSHOT_PUBLISHED=false
          if [ "$REALISTIC_SNAPSHOT_READY" = "true" ]; then
            cp realistic-artifact/REALISTIC_INPUT_SNAPSHOT.tar.gz reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT.tar.gz
            cp realistic-artifact/REALISTIC_INPUT_SNAPSHOT.sha256 reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT.sha256
            REALISTIC_SNAPSHOT_PUBLISHED=true
            if [ -f realistic-artifact/realistic_input_audit.json ]; then
              cp realistic-artifact/realistic_input_audit.json reports/latest_attempt/REALISTIC_INPUT_AUDIT.json
            fi
            if [ -f realistic-artifact/REALISTIC_TOP_10.json ]; then
              cp realistic-artifact/REALISTIC_TOP_10.md reports/latest_attempt/TOP_10.md
              cp realistic-artifact/REALISTIC_TOP_10.json reports/latest_attempt/TOP_10.json
            fi
          fi
'''
new_copy = '''          REALISTIC_SNAPSHOT_PUBLISHED=false
          if [ -d realistic-artifact ]; then
            if [ -f realistic-artifact/realistic_input_audit.json ]; then
              cp realistic-artifact/realistic_input_audit.json reports/latest_attempt/REALISTIC_INPUT_AUDIT.json
            fi
            if [ -f realistic-artifact/REALISTIC_TOP_10.json ]; then
              cp realistic-artifact/REALISTIC_TOP_10.md reports/latest_attempt/TOP_10.md
              cp realistic-artifact/REALISTIC_TOP_10.json reports/latest_attempt/TOP_10.json
            fi
            if [ -f realistic-artifact/REALISTIC_TOP_10_REJECTED.json ]; then
              cp realistic-artifact/REALISTIC_TOP_10_REJECTED.json reports/latest_attempt/REALISTIC_TOP_10_REJECTED.json
              if [ -f realistic-artifact/REALISTIC_TOP_10_REJECTED.md ]; then
                cp realistic-artifact/REALISTIC_TOP_10_REJECTED.md reports/latest_attempt/REALISTIC_TOP_10_REJECTED.md
              fi
            fi
          fi
          if [ "$REALISTIC_SNAPSHOT_READY" = "true" ]; then
            cp realistic-artifact/REALISTIC_INPUT_SNAPSHOT.tar.gz reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT.tar.gz
            cp realistic-artifact/REALISTIC_INPUT_SNAPSHOT.sha256 reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT.sha256
            REALISTIC_SNAPSHOT_PUBLISHED=true
          fi
'''
replace_once(workflow, old_copy, new_copy, "realistic blocked-result publication")

old_final = '''      - name: Exigir aprovação realista retrospectiva
        run: |
          python - <<'PY'
          import json
          from pathlib import Path
          status = json.loads(Path("reports/latest_attempt/STATUS.json").read_text())
          if status["status"] != "REALISTIC_RETROSPECTIVE_SUCCESS":
              raise SystemExit("full matrix realistic finalist validation not approved")
          PY
'''
new_final = '''      - name: Exigir classificação final consistente
        run: |
          python - <<'PY'
          import json
          from pathlib import Path
          status = json.loads(Path("reports/latest_attempt/STATUS.json").read_text())
          allowed = {
              "REALISTIC_RETROSPECTIVE_SUCCESS",
              "RESEARCH_SUCCESS_REALISTIC_BLOCKED",
          }
          if status["status"] not in allowed:
              raise SystemExit("full matrix publication failed its integrity classification")
          print("final classification:", status["status"])
          PY
'''
replace_once(workflow, old_final, new_final, "final publication classification gate")


# 3) Regression tests must state the new workflow contract explicitly.
snapshot_test = ROOT / "tests/test_realistic_snapshot_certification_gate.py"
snapshot_test.write_text(
    '''from __future__ import annotations

import unittest
from pathlib import Path


WORKFLOW = Path(".github/workflows/full-matrix-backtest-hardened.yml")


class RealisticSnapshotCertificationGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_realistic_input_audit_has_stable_step_id(self) -> None:
        marker = "- name: Auditar prontidão realista e nível de certificação\\n        id: realistic_audit"
        self.assertIn(marker, self.text)

    def test_estimate_requires_structural_readiness(self) -> None:
        self.assertIn('audit.get("ready_for_realistic_estimate") is not True', self.text)
        self.assertIn('output.write("estimate_ready=true\\\\n")', self.text)

    def test_snapshot_requires_explicit_certified_output(self) -> None:
        condition = (
            "if: ${{ always() && steps.realistic_data.outcome == 'success' "
            "&& steps.realistic_audit.outputs.certified == 'true' }}"
        )
        self.assertIn(condition, self.text)
        self.assertNotIn(
            "steps.realistic_audit.outcome == 'success' }}\\n        run: |\\n          set -euo pipefail\\n          tar",
            self.text,
        )

    def test_uncertified_finalists_publish_rejection_diagnostics_not_certificate(self) -> None:
        self.assertIn("REALISTIC_TOP_10_REJECTED.json", self.text)
        self.assertIn("RESEARCH_SUCCESS_REALISTIC_BLOCKED", self.text)
        self.assertIn('if [ "$STATUS" = "REALISTIC_RETROSPECTIVE_SUCCESS" ]; then', self.text)


if __name__ == "__main__":
    unittest.main()
''',
    encoding="utf-8",
)

performance_test = ROOT / "tests/test_hardened_backtest_performance_settings.py"
performance_text = performance_test.read_text(encoding="utf-8")
performance_text = performance_text.replace(
    '            "Exigir aprovação realista retrospectiva",',
    '            "Exigir classificação final consistente",',
)
if "test_long_backtests_are_not_cancelled_by_new_pushes" not in performance_text:
    anchor = "\n    def test_runner_cpu_cap_is_four_not_two(self) -> None:\n"
    addition = '''\n    def test_long_backtests_are_not_cancelled_by_new_pushes(self) -> None:\n        self.assertIn("cancel-in-progress: false", self.text)\n        self.assertNotIn("cancel-in-progress: true", self.text)\n\n'''
    if anchor not in performance_text:
        raise SystemExit("performance test anchor missing")
    performance_text = performance_text.replace(anchor, addition + anchor, 1)
performance_test.write_text(performance_text, encoding="utf-8")
