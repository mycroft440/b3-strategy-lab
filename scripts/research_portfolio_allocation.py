from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import research_portfolio_allocation_core as _core
from b3_strategy_lab.portfolio_risk import covariance_target_weights

# Patch the preserved core once at import time. All core functions resolve the
# module-global _target_weights at runtime, so matrix, research and imported
# run_portfolio users share the same covariance-aware target-vol implementation.
_core._target_weights = covariance_target_weights

_target_weights = covariance_target_weights


def __getattr__(name: str):
    return getattr(_core, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_core)))


def main(argv: list[str] | None = None) -> int:
    return _core.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
