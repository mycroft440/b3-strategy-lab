from __future__ import annotations

"""Canonical entry point for the certified deterministic public-data replay.

The historical file name `run_exact_realistic_reconstruction.py` remains as a
backward-compatible implementation module, but its outputs no longer claim exact
counterfactual fills. Exact labels are reserved for actual broker-source
reconciliation in `reconcile_actual_personal_account.py`.
"""

from scripts.run_exact_realistic_reconstruction import main


if __name__ == "__main__":
    raise SystemExit(main())
