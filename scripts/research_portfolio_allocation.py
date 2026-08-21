from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import research_portfolio_allocation_core as _core
from b3_strategy_lab.portfolio_risk import covariance_target_weights

# Keep this symbol local so unittest.mock.patch and external instrumentation on
# the public module still intercept candidate-profile computation.
_candidate_profile_uncached = _core._candidate_profile_uncached


def _candidate_profile(data, ticker: str, index: int, config):
    cache = getattr(data, "candidate_profile_cache", None)
    cache_key = (
        ticker,
        index,
        config.lookback,
        config.skip,
        config.trend_window,
        config.vol_window,
        config.score,
        config.absolute_momentum,
        config.roc_windows,
        config.roc_weights,
        config.positive_rule,
        config.short_window,
        config.short_weight,
    )
    if cache is not None and cache_key in cache:
        return cache[cache_key]
    profile = _candidate_profile_uncached(data, ticker, index, config)
    if cache is not None:
        cache[cache_key] = profile
    return profile


# Patch the preserved core once at import time. Its run_portfolio resolves these
# module globals at execution time, so matrix, research, strict and realistic
# users all share the same cache-compatible candidate function and the corrected
# covariance-aware target-vol implementation.
_core._candidate_profile = _candidate_profile
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
