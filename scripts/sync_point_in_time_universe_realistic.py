from __future__ import annotations

"""Realistic point-in-time synchronization entry point.

The broad research catalog and the realistic replay deliberately share source
archives, but not generated candles, action ledgers or verification manifests.
This wrapper injects isolated storage roots before delegating to the base
synchronizer, so a short causal replay cannot truncate or invalidate research data.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import sync_point_in_time_universe as base  # noqa: E402


DEFAULT_REALISTIC_DATA = Path("data/candles_point_in_time")
DEFAULT_REALISTIC_ACTIONS = Path("data/actions_point_in_time")
DEFAULT_REALISTIC_MANIFESTS = Path("data/manifests_point_in_time")
DEFAULT_REALISTIC_SPLIT_EVIDENCE = Path(
    "data/corporate_actions/point_in_time_split_evidence.json"
)


def _option_value(arguments: list[str], option: str) -> str | None:
    for index, value in enumerate(arguments):
        if value == option and index + 1 < len(arguments):
            return arguments[index + 1]
        prefix = option + "="
        if value.startswith(prefix):
            return value[len(prefix) :]
    return None


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)

    defaults = (
        ("--data-dir", DEFAULT_REALISTIC_DATA),
        ("--actions-dir", DEFAULT_REALISTIC_ACTIONS),
        ("--manifests-dir", DEFAULT_REALISTIC_MANIFESTS),
    )
    for option, path in defaults:
        if _option_value(arguments, option) is None:
            arguments.extend([option, str(path)])

    split_evidence = (
        _option_value(arguments, "--split-evidence")
        or str(DEFAULT_REALISTIC_SPLIT_EVIDENCE)
    )
    if _option_value(arguments, "--split-evidence") is None:
        arguments.extend(["--split-evidence", split_evidence])

    # The evidence hashed into the point-in-time manifests must be the exact same
    # file that is later audited for the replay. A caller may override both paths,
    # but a single --split-evidence override remains sufficient and deterministic.
    if _option_value(arguments, "--dataset-split-evidence") is None:
        arguments.extend(["--dataset-split-evidence", split_evidence])

    return base.main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
