from pathlib import Path


def replace_all(path: str, old: str, new: str, expected_min: int = 1) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count < expected_min:
        raise SystemExit(f"{path}: expected at least {expected_min} replacements, found {count}: {old!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement, found {count}: {old!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


workflow = ".github/workflows/full-matrix-backtest-hardened.yml"

# `latest_attempt` is the mutable pointer for any run. `latest_certified` is immutable
# unless all research, realistic and final certification gates pass in the same run.
replace_all(workflow, "reports/latest_backtest", "reports/latest_attempt")

# Snapshot reuse must come only from a previously certified run, never from an aborted
# attempt. The first two reads occur in announce/realistic-data; the final publish stage
# also reads the prior certified pointer.
p = Path(workflow)
text = p.read_text(encoding="utf-8")
text = text.replace(
    "SNAPSHOT=reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT.tar.gz",
    "SNAPSHOT=reports/latest_certified/REALISTIC_INPUT_SNAPSHOT.tar.gz",
)
text = text.replace(
    "CHECKSUM=reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT.sha256",
    "CHECKSUM=reports/latest_certified/REALISTIC_INPUT_SNAPSHOT.sha256",
)
text = text.replace(
    "PREVIOUS_SNAPSHOT=reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT.tar.gz",
    "PREVIOUS_SNAPSHOT=reports/latest_certified/REALISTIC_INPUT_SNAPSHOT.tar.gz",
)
text = text.replace(
    "PREVIOUS_CHECKSUM=reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT.sha256",
    "PREVIOUS_CHECKSUM=reports/latest_certified/REALISTIC_INPUT_SNAPSHOT.sha256",
)
p.write_text(text, encoding="utf-8")

# A failed/current attempt must not silently publish the previous certified snapshot as
# if it belonged to this run. Remove the fallback copy entirely.
replace_once(
    workflow,
    '''          elif [ -f previous-realistic-snapshot/REALISTIC_INPUT_SNAPSHOT.tar.gz ]; then
            cp previous-realistic-snapshot/REALISTIC_INPUT_SNAPSHOT.tar.gz reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT.tar.gz
            cp previous-realistic-snapshot/REALISTIC_INPUT_SNAPSHOT.sha256 reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT.sha256
            REALISTIC_SNAPSHOT_PUBLISHED=true
          fi
''',
    '''          fi
''',
)

# Split bias semantics instead of claiming the point-in-time universe itself still has
# survivorship bias. Retrospective strategy selection remains research-only.
replace_once(
    workflow,
    '''              "selection_bias_remaining": True,
              "selection_validation_runner": "scripts/walk_forward_certified.py --all-strategies --require-full-scope",
''',
    '''              "universe_selection_bias_remaining": False,
              "strategy_selection_bias_remaining": True,
              "selection_bias_remaining": True,
              "selection_validation_runner": "scripts/walk_forward_certified.py --all-strategies --require-full-scope",
''',
)

# Paths in status must reflect attempt semantics.
replace_all(workflow, '"reports/latest_attempt/MATRIX.csv.gz"', '"reports/latest_attempt/MATRIX.csv.gz"')

# Replace the publication step with atomic staging of the attempt, and promote a
# complete directory to latest_certified only after the current status is fully green.
replace_once(
    workflow,
    '''      - name: Gravar latest em backtest-results
        env:
          PREPARE_RESULT: ${{ needs.prepare.result }}
        run: |
          set -euo pipefail
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add -- reports/latest_attempt
          if [ "$PREPARE_RESULT" = "success" ]; then
            git add -- \
              reports/backtest_data_audit_40.json \
              data/candles \
              data/manifests \
              data/corporate_actions \
              data/universes/fixed_40_2018.json \
              data/quality_reviews.json
          fi
          git commit -m "Backtest ${{ github.run_number }}: publicar resultado [skip ci]"
          git push --force origin HEAD:backtest-results
''',
    '''      - name: Publicar tentativa e promover certificado atomicamente
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

          # Stage the whole attempt under a temporary directory first. A partial copy
          # is never the canonical pointer.
          rm -rf reports/.latest_attempt_staging
          cp -a reports/latest_attempt reports/.latest_attempt_staging
          rm -rf reports/latest_attempt
          mv reports/.latest_attempt_staging reports/latest_attempt

          if [ "$STATUS" = "REALISTIC_RETROSPECTIVE_SUCCESS" ]; then
            test -f reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT.tar.gz
            test -f reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT.sha256
            test -f reports/latest_attempt/TOP_10.json
            test -f reports/latest_attempt/STATUS.json
            (
              cd reports/latest_attempt
              sha256sum -c REALISTIC_INPUT_SNAPSHOT.sha256
            )
            rm -rf reports/.latest_certified_staging
            cp -a reports/latest_attempt reports/.latest_certified_staging
            rm -rf reports/latest_certified
            mv reports/.latest_certified_staging reports/latest_certified
          fi

          git add -- reports/latest_attempt
          if [ "$STATUS" = "REALISTIC_RETROSPECTIVE_SUCCESS" ]; then
            git add -A -- reports/latest_certified
          fi
          if [ "$PREPARE_RESULT" = "success" ]; then
            git add -- \
              reports/backtest_data_audit_40.json \
              data/candles \
              data/manifests \
              data/corporate_actions \
              data/universes/fixed_40_2018.json \
              data/quality_reviews.json
          fi
          git commit -m "Backtest ${{ github.run_number }}: publish attempt/certified pointers [skip ci]"
          git push --force origin HEAD:backtest-results
''',
)

# The final assertion reads the attempt, never aliases a failed attempt as certified.
replace_once(
    workflow,
    '          status = json.loads(Path("reports/latest_attempt/STATUS.json").read_text())\n',
    '          status = json.loads(Path("reports/latest_attempt/STATUS.json").read_text())\n',
)
