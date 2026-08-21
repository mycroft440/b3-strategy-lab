from __future__ import annotations

"""Realistic point-in-time synchronization entry point.

The broad research catalog and the realistic replay deliberately share candle/action
files but not their verification manifests. This wrapper injects isolated manifest
and split-evidence paths before delegating to the base synchronizer, so rebuilding a
point-in-time replay cannot invalidate hashes that belong to historical research.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import sync_point_in_time_universe as base  # noqa: E402


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

    if _option_value(arguments, "--manifests-dir") is None:
        arguments.extend(["--manifests-dir", str(DEFAULT_REALISTIC_MANIFESTS)])

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
