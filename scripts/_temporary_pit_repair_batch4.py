from __future__ import annotations

import re
from pathlib import Path


workflow = Path(".github/workflows/full-matrix-backtest-hardened.yml")
text = workflow.read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


# This temporary migration is intentionally one-shot. Refuse to run against an
# already-migrated file so a rerun cannot stack or partially duplicate semantics.
require("reports/latest_backtest" in text, "workflow already migrated or source contract changed")
require("reports/latest_attempt" not in text, "partial latest_attempt migration detected")

# Every path produced by the current run is an attempt. Only an explicitly promoted
# successful attempt becomes the certified pointer.
text = text.replace("reports/latest_backtest", "reports/latest_attempt")

# Reuse/bootstrap is allowed only from the previous certified pointer. A failed
# attempt must never be a source of reusable realistic inputs.
for old, new in (
    (
        "SNAPSHOT=reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT.tar.gz",
        "SNAPSHOT=reports/latest_certified/REALISTIC_INPUT_SNAPSHOT.tar.gz",
    ),
    (
        "CHECKSUM=reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT.sha256",
        "CHECKSUM=reports/latest_certified/REALISTIC_INPUT_SNAPSHOT.sha256",
    ),
    (
        "PREVIOUS_SNAPSHOT=reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT.tar.gz",
        "PREVIOUS_SNAPSHOT=reports/latest_certified/REALISTIC_INPUT_SNAPSHOT.tar.gz",
    ),
    (
        "PREVIOUS_CHECKSUM=reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT.sha256",
        "PREVIOUS_CHECKSUM=reports/latest_certified/REALISTIC_INPUT_SNAPSHOT.sha256",
    ),
):
    require(old in text, f"missing certified snapshot migration anchor: {old}")
    text = text.replace(old, new)

# A blocked current run must not copy an old certified snapshot into the current
# attempt and then report it as if it had been produced by this run.
fallback_pattern = re.compile(
    r'''          elif \[ -f previous-realistic-snapshot/REALISTIC_INPUT_SNAPSHOT\.tar\.gz \]; then\n'''
    r'''            cp previous-realistic-snapshot/REALISTIC_INPUT_SNAPSHOT\.tar\.gz reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT\.tar\.gz\n'''
    r'''            cp previous-realistic-snapshot/REALISTIC_INPUT_SNAPSHOT\.sha256 reports/latest_attempt/REALISTIC_INPUT_SNAPSHOT\.sha256\n'''
    r'''            REALISTIC_SNAPSHOT_PUBLISHED=true\n'''
    r'''          fi\n'''
)
text, count = fallback_pattern.subn("          fi\n", text, count=1)
require(count == 1, f"expected exactly one stale snapshot fallback, found {count}")

# The point-in-time universe is survivorship-safe; retrospective strategy selection
# remains a separate bias and must stay explicitly disclosed.
bias_anchor = (
    '              "selection_bias_remaining": True,\n'
    '              "selection_validation_runner": "scripts/walk_forward_certified.py --all-strategies --require-full-scope",\n'
)
require(bias_anchor in text, "selection bias status anchor missing")
text = text.replace(
    bias_anchor,
    '              "universe_selection_bias_remaining": False,\n'
    '              "strategy_selection_bias_remaining": True,\n'
    '              "selection_bias_remaining": True,\n'
    '              "selection_validation_runner": "scripts/walk_forward_certified.py --all-strategies --require-full-scope",\n',
    1,
)

# Replace the complete publish step by anchors rather than whitespace-sensitive body
# matching. The next step name is preserved as the boundary.
start_marker = "      - name: Gravar latest em backtest-results\n"
end_marker = "      - name: Exigir aprovação realista retrospectiva\n"
start = text.find(start_marker)
end = text.find(end_marker, start + len(start_marker))
require(start >= 0 and end > start, "publication step anchors not found or ambiguous")

publication = '''      - name: Publicar tentativa e promover certificado atomicamente
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

          # Build the mutable attempt pointer as one complete directory before it is
          # staged. This keeps partial intermediate copies out of the commit.
          rm -rf reports/.latest_attempt_staging
          cp -a reports/latest_attempt reports/.latest_attempt_staging
          rm -rf reports/latest_attempt
          mv reports/.latest_attempt_staging reports/latest_attempt

          # Promote only a fully approved current run. A failed or research-only run
          # leaves latest_certified completely untouched.
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

          git add -A -- reports/latest_attempt
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

'''
text = text[:start] + publication + text[end:]

# Contract sanity checks after migration.
require("reports/latest_backtest" not in text, "legacy latest_backtest path survived migration")
require("reports/latest_attempt/STATUS.json" in text, "attempt status path missing")
require("reports/latest_certified/REALISTIC_INPUT_SNAPSHOT.tar.gz" in text, "certified snapshot source missing")
require("- name: Publicar tentativa e promover certificado atomicamente" in text, "atomic publication step missing")

workflow.write_text(text, encoding="utf-8")
