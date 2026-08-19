from __future__ import annotations

"""Realistic point-in-time synchronization entry point.

The base point-in-time synchronizer now uses the non-lossy B3 cash-distribution
collector directly. This named entry point remains as the stable command used by
the real-money pipeline and delegates without monkey-patching behavior.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import sync_point_in_time_universe as base  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    return base.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
