from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_realistic_validator_runs_as_direct_script() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/validate_matrix_top_realistic.py", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "usage:" in completed.stdout.lower()
