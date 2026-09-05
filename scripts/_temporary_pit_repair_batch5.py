from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one replacement, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


workflow = Path(".github/workflows/full-matrix-backtest-hardened.yml")
old = '''          rm -rf reports/latest_attempt
          mkdir -p reports/latest_attempt
          SNAPSHOT=reports/latest_certified/REALISTIC_INPUT_SNAPSHOT.tar.gz
          CHECKSUM=reports/latest_certified/REALISTIC_INPUT_SNAPSHOT.sha256
          snapshot_exists=false
          checksum_exists=false
          git cat-file -e "origin/backtest-results:${SNAPSHOT}" 2>/dev/null && snapshot_exists=true
          git cat-file -e "origin/backtest-results:${CHECKSUM}" 2>/dev/null && checksum_exists=true
          if [ "$snapshot_exists" != "$checksum_exists" ]; then
            echo "::error::snapshot/checksum realista assimétricos em backtest-results"
            exit 1
          fi
          if [ "$snapshot_exists" = "true" ]; then
            git show "origin/backtest-results:${SNAPSHOT}" > "$SNAPSHOT"
            git show "origin/backtest-results:${CHECKSUM}" > "$CHECKSUM"
            (
              cd reports/latest_attempt
              sha256sum -c REALISTIC_INPUT_SNAPSHOT.sha256
            )
          fi
'''
new = '''          rm -rf reports/latest_attempt previous-certified-snapshot
          mkdir -p reports/latest_attempt previous-certified-snapshot
          SNAPSHOT=reports/latest_certified/REALISTIC_INPUT_SNAPSHOT.tar.gz
          CHECKSUM=reports/latest_certified/REALISTIC_INPUT_SNAPSHOT.sha256
          snapshot_exists=false
          checksum_exists=false
          git cat-file -e "origin/backtest-results:${SNAPSHOT}" 2>/dev/null && snapshot_exists=true
          git cat-file -e "origin/backtest-results:${CHECKSUM}" 2>/dev/null && checksum_exists=true
          if [ "$snapshot_exists" != "$checksum_exists" ]; then
            echo "::error::snapshot/checksum realista assimétricos em backtest-results"
            exit 1
          fi
          if [ "$snapshot_exists" = "true" ]; then
            git show "origin/backtest-results:${SNAPSHOT}" \
              > previous-certified-snapshot/REALISTIC_INPUT_SNAPSHOT.tar.gz
            git show "origin/backtest-results:${CHECKSUM}" \
              > previous-certified-snapshot/REALISTIC_INPUT_SNAPSHOT.sha256
            (
              cd previous-certified-snapshot
              sha256sum -c REALISTIC_INPUT_SNAPSHOT.sha256
            )
          fi
'''
replace_once(workflow, old, new)

# Strengthen the workflow regression so source and local staging destinations can
# never be conflated again.
test_path = Path("tests/test_execution_hardening.py")
test_text = test_path.read_text(encoding="utf-8")
anchor = '''        self.assertIn(
            "SNAPSHOT=reports/latest_certified/REALISTIC_INPUT_SNAPSHOT.tar.gz",
            announce,
        )
'''
addition = anchor + '''        self.assertIn("mkdir -p reports/latest_attempt previous-certified-snapshot", announce)
        self.assertIn(
            '> previous-certified-snapshot/REALISTIC_INPUT_SNAPSHOT.tar.gz',
            announce,
        )
        self.assertIn("cd previous-certified-snapshot", announce)
        self.assertNotIn('git show "origin/backtest-results:${SNAPSHOT}" > "$SNAPSHOT"', announce)
'''
if anchor not in test_text:
    raise SystemExit("execution-hardening announce anchor missing")
test_path.write_text(test_text.replace(anchor, addition, 1), encoding="utf-8")
