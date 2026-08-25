from __future__ import annotations

"""Realistic point-in-time synchronization entry point.

The broad research catalog and the realistic replay deliberately share source
archives, but not generated candles, action ledgers or verification manifests.
This wrapper injects isolated storage roots before delegating to the base
synchronizer, so a short causal replay cannot truncate or invalidate research data.
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.b3_official import B3CorporateActionError  # noqa: E402
from scripts import sync_point_in_time_universe as base  # noqa: E402


DEFAULT_REALISTIC_DATA = Path("data/candles_point_in_time")
DEFAULT_REALISTIC_ACTIONS = Path("data/actions_point_in_time")
DEFAULT_REALISTIC_MANIFESTS = Path("data/manifests_point_in_time")
DEFAULT_REALISTIC_SPLIT_EVIDENCE = Path(
    "data/corporate_actions/point_in_time_split_evidence.json"
)
DEFAULT_ACTION_WORKERS = 1
SYNC_ATTEMPTS = 3
SYNC_RETRY_DELAYS_SECONDS = (20, 60)


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
    # file that is later audited for the replay. One --split-evidence override is
    # sufficient; if a caller explicitly supplies --dataset-split-evidence too, the
    # base synchronizer rejects the invocation unless both paths are identical.
    if _option_value(arguments, "--dataset-split-evidence") is None:
        arguments.extend(["--dataset-split-evidence", split_evidence])

    # The public listed-company endpoint is sensitive to bursts. Realistic mode
    # favors deterministic evidence collection over throughput; callers can still
    # opt into more workers explicitly when they control their own cache/rate limit.
    if _option_value(arguments, "--action-workers") is None:
        arguments.extend(["--action-workers", str(DEFAULT_ACTION_WORKERS)])

    # Successful issuer supplements are written atomically by the base synchronizer.
    # If the B3 endpoint transiently returns an empty/non-JSON response, a retry of
    # the full sync therefore resumes from those cached successes and only fetches
    # the missing issuers. We retry only the explicit B3 transport/data error and
    # preserve fail-closed behavior after the bounded attempts are exhausted.
    for attempt in range(1, SYNC_ATTEMPTS + 1):
        try:
            return base.main(arguments)
        except B3CorporateActionError as error:
            if attempt >= SYNC_ATTEMPTS:
                raise
            delay = SYNC_RETRY_DELAYS_SECONDS[attempt - 1]
            print(
                f"B3 supplement sync transient failure (attempt {attempt}/{SYNC_ATTEMPTS}): "
                f"{error}. Retrying cached resume after {delay}s.",
                flush=True,
            )
            time.sleep(delay)

    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
