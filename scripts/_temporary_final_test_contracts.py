from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = "- name: Exigir insumos realistas certificados"
NEW = "- name: Auditar prontidão realista e nível de certificação"

for relative in (
    "tests/test_hardened_workflow_snapshot_bootstrap.py",
    "tests/test_realistic_snapshot_reuse_window.py",
):
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    if OLD in text:
        text = text.replace(OLD, NEW)
    if OLD in text:
        raise SystemExit(f"stale realistic-audit step marker remains in {relative}")
    if NEW not in text:
        raise SystemExit(f"new realistic-audit step marker missing in {relative}")
    path.write_text(text, encoding="utf-8")
