from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_WORKFLOW = Path(".github/workflows/full-matrix-backtest-hardened.yml")


REALISTIC_JOB = r'''  realistic_validation:
    name: Auditar PIT e congelar candidato prospectivo
    needs: [prepare, merge]
    runs-on: ubuntu-latest
    timeout-minutes: 120
    outputs:
      snapshot_ready: ${{ steps.realistic_snapshot.outputs.ready || 'false' }}
      pit_ready: ${{ steps.pit_audit.outputs.ready || 'false' }}
      freeze_ready: ${{ steps.freeze.outputs.ready || 'false' }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Baixar matriz de pesquisa
        uses: actions/download-artifact@v4
        with:
          name: b3-strategy-lab-research-top10-${{ github.run_number }}
          path: research-artifact

      - name: Baixar snapshot PIT produzido nesta execução
        uses: actions/download-artifact@v4
        with:
          name: verified-market-data-${{ github.run_id }}
          path: data

      - name: Preparar artefatos da seleção
        run: |
          set -euo pipefail
          mkdir -p reports
          cp research-artifact/TOP_10.json reports/TOP_10.json
          cp research-artifact/strategy_management_combinations_40_adjusted_no_dividends_1d.manifest.json \
            reports/strategy_management_combinations_40_adjusted_no_dividends_1d.manifest.json

      - name: Auditar informação point-in-time de forma fail-closed
        id: pit_audit
        run: |
          set -euo pipefail
          PERIOD_START="$(python - <<'PY'
          import json
          from pathlib import Path
          payload = json.loads(Path("reports/TOP_10.json").read_text())
          print(payload["period"]["start"])
          PY
          )"
          PERIOD_END="$(python - <<'PY'
          import json
          from pathlib import Path
          payload = json.loads(Path("reports/TOP_10.json").read_text())
          print(payload["period"]["end"])
          PY
          )"
          set +e
          python scripts/audit_point_in_time_validation.py \
            --start "$PERIOD_START" \
            --end "$PERIOD_END" \
            --output reports/POINT_IN_TIME_VALIDATION.json
          PIT_RC=$?
          set -e
          if [ "$PIT_RC" -eq 0 ]; then
            echo "ready=true" >> "$GITHUB_OUTPUT"
          elif [ "$PIT_RC" -eq 2 ]; then
            echo "ready=false" >> "$GITHUB_OUTPUT"
            echo "::warning::point-in-time validation is blocked; no candidate will be frozen"
          else
            echo "::error::point-in-time audit crashed with exit code $PIT_RC"
            exit "$PIT_RC"
          fi

      - name: Congelar rank 1 somente para validação futura
        id: freeze
        if: ${{ steps.pit_audit.outputs.ready == 'true' }}
        run: |
          set -euo pipefail
          python scripts/freeze_ex_ante_candidate.py \
            --candidates reports/TOP_10.json \
            --matrix-manifest reports/strategy_management_combinations_40_adjusted_no_dividends_1d.manifest.json \
            --pit-audit reports/POINT_IN_TIME_VALIDATION.json \
            --output reports/FROZEN_CANDIDATE.json
          python - <<'PY'
          import json
          from pathlib import Path
          frozen = json.loads(Path("reports/FROZEN_CANDIDATE.json").read_text())
          assert frozen["status"] == "PROSPECTIVE_FROZEN_PENDING"
          assert frozen["fallback_candidate_allowed"] is False
          assert frozen["future_result_may_change_candidate"] is False
          assert frozen["historical_holdout_claim_allowed"] is False
          assert frozen["validated_winner_available"] is False
          PY
          echo "ready=true" >> "$GITHUB_OUTPUT"

      - name: Empacotar snapshot exato dos insumos PIT do congelamento
        id: realistic_snapshot
        if: ${{ steps.pit_audit.outputs.ready == 'true' && steps.freeze.outputs.ready == 'true' }}
        run: |
          set -euo pipefail
          tar \
            --sort=name \
            --mtime='UTC 1970-01-01' \
            --owner=0 --group=0 --numeric-owner \
            -czf reports/REALISTIC_INPUT_SNAPSHOT.tar.gz \
            data/candles_point_in_time \
            data/actions_point_in_time \
            data/manifests_point_in_time \
            data/universes/point_in_time_union.json \
            data/universes/point_in_time_weekly.csv \
            data/execution/b3_standard_fractional_open.csv \
            data/corporate_actions/point_in_time_cash_distributions.csv \
            data/corporate_actions/point_in_time_cash_distributions.manifest.json \
            data/corporate_actions/cash_distribution_coverage_certification.json \
            data/corporate_actions/point_in_time_split_evidence.json \
            data/corporate_actions/ticker_transitions.csv \
            data/corporate_actions/ticker_transitions.manifest.json \
            data/fees/b3_equity_fee_schedule.json
          (
            cd reports
            sha256sum REALISTIC_INPUT_SNAPSHOT.tar.gz > REALISTIC_INPUT_SNAPSHOT.sha256
          )
          echo "ready=true" >> "$GITHUB_OUTPUT"

      - name: Publicar auditoria PIT e congelamento prospectivo
        if: ${{ always() }}
        uses: actions/upload-artifact@v4
        with:
          name: b3-strategy-lab-realistic-top10-${{ github.run_number }}
          path: |
            reports/POINT_IN_TIME_VALIDATION.json
            reports/FROZEN_CANDIDATE.json
            reports/REALISTIC_INPUT_SNAPSHOT.tar.gz
            reports/REALISTIC_INPUT_SNAPSHOT.sha256
          if-no-files-found: warn
          retention-days: 90

'''


PUBLISH_TAIL = r'''      - name: Montar status final sem promover vencedor in-sample
        env:
          RUN_ID: ${{ github.run_id }}
          RUN_NUMBER: ${{ github.run_number }}
          WORKFLOW_SHA: ${{ github.sha }}
          PREPARE_RESULT: ${{ needs.prepare.result }}
          ANNOUNCE_RESULT: ${{ needs.announce.result }}
          BACKTEST_RESULT: ${{ needs.backtest.result }}
          MERGE_RESULT: ${{ needs.merge.result }}
          REALISTIC_RESULT: ${{ needs.realistic_validation.result }}
          REALISTIC_SNAPSHOT_READY: ${{ needs.realistic_validation.outputs.snapshot_ready || 'false' }}
          PIT_READY: ${{ needs.realistic_validation.outputs.pit_ready || 'false' }}
          FREEZE_READY: ${{ needs.realistic_validation.outputs.freeze_ready || 'false' }}
          STRATEGY_COUNT: ${{ needs.prepare.outputs.strategy_count }}
          MANAGEMENT_COUNT: ${{ needs.prepare.outputs.management_count }}
          COMBINATION_COUNT: ${{ needs.prepare.outputs.combination_count }}
        run: |
          set -euo pipefail
          rm -rf reports/latest_attempt
          mkdir -p reports/latest_attempt
          if [ "$PREPARE_RESULT" = "success" ]; then
            cp readiness-artifact/backtest_data_audit_40.json reports/backtest_data_audit_40.json
            cp readiness-artifact/backtest_data_audit_40.json reports/latest_attempt/DATA_READINESS.json
          fi
          if [ "$MERGE_RESULT" = "success" ]; then
            cp research-artifact/TOP_10.md reports/latest_attempt/RESEARCH_TOP_10.md
            cp research-artifact/TOP_10.json reports/latest_attempt/RESEARCH_TOP_10.json
            cp research-artifact/strategy_management_combinations_40_adjusted_no_dividends_1d.audit.json reports/latest_attempt/AUDIT.json
            cp research-artifact/strategy_management_combinations_40_adjusted_no_dividends_1d.manifest.json reports/latest_attempt/MANIFEST.json
            cp research-artifact/strategy_management_combinations_40_adjusted_no_dividends_1d_top10_annual.md reports/latest_attempt/RESEARCH_TOP_10_ANNUAL.md
            cp research-artifact/strategy_management_combinations_40_adjusted_no_dividends_1d.csv.gz reports/latest_attempt/MATRIX.csv.gz
          fi
          if [ -d realistic-artifact ]; then
            if [ -f realistic-artifact/POINT_IN_TIME_VALIDATION.json ]; then
              cp realistic-artifact/POINT_IN_TIME_VALIDATION.json reports/latest_attempt/POINT_IN_TIME_VALIDATION.json
            fi
            if [ -f realistic-artifact/FROZEN_CANDIDATE.json ]; then
              cp realistic-artifact/FROZEN_CANDIDATE.json reports/latest_attempt/FROZEN_CANDIDATE.json
            fi
          fi
          REALISTIC_SNAPSHOT_PUBLISHED=false
          if [ "$REALISTIC_SNAPSHOT_READY" = "true" ]; then
            cp realistic-artifact/REALISTIC_INPUT_SNAPSHOT.tar.gz reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT.tar.gz
            cp realistic-artifact/REALISTIC_INPUT_SNAPSHOT.sha256 reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT.sha256
            (
              cd reports/latest_attempt
              sha256sum -c REALISTIC_INPUT_SNAPSHOT.sha256
            )
            REALISTIC_SNAPSHOT_PUBLISHED=true
          fi
          export REALISTIC_SNAPSHOT_PUBLISHED
          python - <<'PY'
          import json, os
          from datetime import datetime, timezone
          from pathlib import Path
          latest = Path("reports/latest_attempt")
          def read(name):
              path = latest / name
              return json.loads(path.read_text()) if path.exists() else None
          audit = read("AUDIT.json")
          manifest = read("MANIFEST.json")
          readiness = read("DATA_READINESS.json")
          pit = read("POINT_IN_TIME_VALIDATION.json")
          frozen = read("FROZEN_CANDIDATE.json")
          research_ok = bool(audit and audit.get("ready_for_research_ranking") is True)
          research_jobs_ok = all(os.environ[name] == "success" for name in (
              "PREPARE_RESULT", "ANNOUNCE_RESULT", "BACKTEST_RESULT", "MERGE_RESULT"
          ))
          source_matches = bool(manifest and manifest.get("git_commit") == os.environ["WORKFLOW_SHA"])
          pit_ok = bool(
              pit
              and pit.get("status") == "PASS"
              and pit.get("point_in_time_validation_complete") is True
              and pit.get("strict_signal_information_claim_allowed") is True
              and pit.get("cash_announcement_timing_certified") is True
              and pit.get("ticker_transition_binding_verified") is True
          )
          freeze_ok = bool(
              frozen
              and frozen.get("status") == "PROSPECTIVE_FROZEN_PENDING"
              and frozen.get("fallback_candidate_allowed") is False
              and frozen.get("future_result_may_change_candidate") is False
              and frozen.get("historical_holdout_claim_allowed") is False
              and frozen.get("validated_winner_available") is False
              and manifest
              and frozen.get("information_cutoff") == manifest.get("end")
          )
          gates_ok = (
              research_jobs_ok and research_ok and source_matches
              and os.environ["REALISTIC_RESULT"] == "success"
          )
          if gates_ok and pit_ok and freeze_ok:
              status = "RESEARCH_SUCCESS_PROSPECTIVE_FROZEN"
          elif research_jobs_ok and research_ok and source_matches:
              status = "RESEARCH_SUCCESS_POINT_IN_TIME_BLOCKED"
          else:
              status = "FAILED"
          payload = {
              "status": status,
              "generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "run_id": int(os.environ["RUN_ID"]),
              "run_number": int(os.environ["RUN_NUMBER"]),
              "workflow_sha": os.environ["WORKFLOW_SHA"],
              "calculation_sha": manifest.get("git_commit") if manifest else None,
              "source_sha_matches": source_matches,
              "jobs": {
                  "prepare": os.environ["PREPARE_RESULT"],
                  "announce": os.environ["ANNOUNCE_RESULT"],
                  "backtest": os.environ["BACKTEST_RESULT"],
                  "merge": os.environ["MERGE_RESULT"],
                  "point_in_time_and_freeze": os.environ["REALISTIC_RESULT"],
              },
              "strategy_count": int(manifest.get("strategy_count", 0)) if manifest else int(os.environ.get("STRATEGY_COUNT") or 0),
              "management_count": int(manifest.get("management_count", 0)) if manifest else int(os.environ.get("MANAGEMENT_COUNT") or 0),
              "combination_count": int(manifest.get("combinations", 0)) if manifest else int(os.environ.get("COMBINATION_COUNT") or 0),
              "research_ranking_ready": research_ok,
              "research_matrix_completed": bool(research_jobs_ok and research_ok and source_matches),
              "point_in_time_validation_complete": pit_ok,
              "prospective_candidate_frozen": freeze_ok,
              "validated_winner_available": False,
              "in_sample_winner_claim_allowed": False,
              "ex_ante_selection_claim_allowed": False,
              "prospective_validation_pending": freeze_ok,
              "data_snooping_control_active": freeze_ok,
              "data_snooping_control": (
                  "wall_clock_prospective_freeze_no_historical_holdout_retrocertification"
                  if freeze_ok else None
              ),
              "formal_multiple_testing_significance_claim_allowed": False,
              "retrospective_ranking_selection_bias_remaining": True,
              "real_money_claim_allowed": False,
              "counterfactual_execution_exact": False,
              "universe_selection_bias_remaining": False if pit_ok else None,
              "candidate": frozen.get("candidate") if frozen else None,
              "information_cutoff": frozen.get("information_cutoff") if frozen else None,
              "frozen_at_utc": frozen.get("frozen_at_utc") if frozen else None,
              "prospective_validation_must_start_after": (
                  frozen.get("prospective_validation_must_start_after") if frozen else None
              ),
              "result_classification": (
                  "PROSPECTIVE_CANDIDATE_FROZEN_PENDING_VALIDATION"
                  if status == "RESEARCH_SUCCESS_PROSPECTIVE_FROZEN"
                  else "POINT_IN_TIME_VALIDATION_BLOCKED"
                  if status == "RESEARCH_SUCCESS_POINT_IN_TIME_BLOCKED"
                  else "FAILED"
              ),
              "data_cutoff": readiness.get("evaluation_end") if readiness else None,
              "realistic_input_snapshot_path": (
                  "reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT.tar.gz"
                  if os.environ["REALISTIC_SNAPSHOT_PUBLISHED"] == "true" else None
              ),
          }
          (latest / "STATUS.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
          if status == "FAILED":
              (latest / "FAILURE.md").write_text("# Backtest não aprovado\n\n" + json.dumps(payload, indent=2) + "\n")
          elif status == "RESEARCH_SUCCESS_POINT_IN_TIME_BLOCKED":
              (latest / "POINT_IN_TIME_VALIDATION_BLOCKED.md").write_text(
                  "# Pesquisa concluída; validação point-in-time bloqueada\n\n"
                  + json.dumps(payload, indent=2) + "\n"
              )
          PY

      - name: Publicar tentativa e freeze sem fabricar certificado retrospectivo
        env:
          PREPARE_RESULT: ${{ needs.prepare.result }}
        run: |
          set -euo pipefail
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          STATUS="$(python - <<'PY'
          import json
          from pathlib import Path
          print(json.loads(Path("reports/latest_attempt/STATUS.json").read_text())["status"])
          PY
          )"
          rm -rf reports/.latest_attempt_staging
          cp -a reports/latest_attempt reports/.latest_attempt_staging
          rm -rf reports/latest_attempt
          mv reports/.latest_attempt_staging reports/latest_attempt

          # A prospective freeze is durable evidence, but it is deliberately not a
          # validated performance certificate. latest_certified remains untouched.
          if [ "$STATUS" = "RESEARCH_SUCCESS_PROSPECTIVE_FROZEN" ]; then
            test -f reports/latest_attempt/FROZEN_CANDIDATE.json
            test -f reports/latest_attempt/POINT_IN_TIME_VALIDATION.json
            test -f reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT.tar.gz
            test -f reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT.sha256
            rm -rf reports/.latest_freeze_staging
            cp -a reports/latest_attempt reports/.latest_freeze_staging
            rm -rf reports/latest_freeze
            mv reports/.latest_freeze_staging reports/latest_freeze
          fi

          git add -A -- reports/latest_attempt
          if [ "$STATUS" = "RESEARCH_SUCCESS_PROSPECTIVE_FROZEN" ]; then
            git add -A -- reports/latest_freeze
          fi
          if [ "$PREPARE_RESULT" = "success" ]; then
            git add -- \
              reports/backtest_data_audit_40.json \
              data/candles \
              data/manifests \
              data/corporate_actions \
              data/candles_point_in_time \
              data/actions_point_in_time \
              data/manifests_point_in_time \
              data/universes/point_in_time_union.json \
              data/universes/point_in_time_weekly.csv \
              data/quality_reviews.json
          fi
          git commit -m "Backtest ${{ github.run_number }}: publish research/PIT freeze [skip ci]"
          git push --force origin HEAD:backtest-results

      - name: Exigir classificação final consistente
        run: |
          python - <<'PY'
          import json
          from pathlib import Path
          status = json.loads(Path("reports/latest_attempt/STATUS.json").read_text())
          allowed = {
              "RESEARCH_SUCCESS_PROSPECTIVE_FROZEN",
              "RESEARCH_SUCCESS_POINT_IN_TIME_BLOCKED",
          }
          if status["status"] not in allowed:
              raise SystemExit("full matrix publication failed its integrity classification")
          if status["status"] == "RESEARCH_SUCCESS_PROSPECTIVE_FROZEN":
              assert status["point_in_time_validation_complete"] is True
              assert status["prospective_candidate_frozen"] is True
              assert status["validated_winner_available"] is False
              assert status["in_sample_winner_claim_allowed"] is False
          print("final classification:", status["status"])
          PY
'''


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def patch_workflow(text: str) -> str:
    text = _replace_once(
        text,
        "            scripts/run_realistic_pipeline.py\n",
        "            scripts/run_realistic_pipeline.py \\\n            b3_strategy_lab/ex_ante_validation.py \\\n            scripts/audit_point_in_time_validation.py \\\n            scripts/freeze_ex_ante_candidate.py \\\n            scripts/certify_ex_ante_holdout.py\n",
        "critical compile list",
    )
    text = _replace_once(
        text,
        "            data/corporate_actions\n            data/candles_point_in_time\n",
        "            data/corporate_actions\n            data/execution\n            data/candles_point_in_time\n",
        "verified data artifact",
    )

    start = text.index("  realistic_validation:\n")
    publish = text.index("  publish:\n", start)
    text = text[:start] + REALISTIC_JOB + text[publish:]

    marker = "      - name: Montar status final\n"
    status_start = text.index(marker, text.index("  publish:\n"))
    text = text[:status_start] + PUBLISH_TAIL
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_WORKFLOW)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    source = args.input.read_text(encoding="utf-8")
    patched = patch_workflow(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(patched, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
