from __future__ import annotations

"""Realistic point-in-time sync entry point.

This adapter keeps the original point-in-time sync implementation reproducible
while replacing its cash-distribution collector with the non-lossy ledger builder
from b3_strategy_lab.cash_distributions. The replacement preserves installments
with distinct payment dates instead of collapsing them by entitlement date/rate.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.cash_distributions import build_cash_events  # noqa: E402
from scripts import sync_point_in_time_universe as base  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    base._cash_events = build_cash_events
    return base.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
