from __future__ import annotations

import math

from b3_strategy_lab import realistic_portfolio_core as _core

_original_apply_ticker_transitions = _core._apply_ticker_transitions


def _apply_ticker_transitions(account, transitions) -> None:
    for transition in transitions:
        if not math.isclose(float(transition.cash_per_old_share), 0.0, abs_tol=1e-12):
            raise ValueError(
                f"{transition.old_ticker}->{transition.new_ticker}: cash component is not "
                "supported without an explicit, source-tested tax-basis rule."
            )
        if not math.isclose(float(transition.share_ratio), 1.0, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError(
                f"{transition.old_ticker}->{transition.new_ticker}: only 1:1 ticker "
                "transitions are supported without an explicit, source-tested tax-basis rule."
            )
    _original_apply_ticker_transitions(account, transitions)


_core._apply_ticker_transitions = _apply_ticker_transitions


def __getattr__(name: str):
    return getattr(_core, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_core)))
