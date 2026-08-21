from __future__ import annotations

import copy
import math
from dataclasses import replace

from b3_strategy_lab import realistic_portfolio_core as _core

_original_apply_ticker_transitions = _core._apply_ticker_transitions
_original_apply_split_from_adjustment_factors = _core._apply_split_from_adjustment_factors
_original_run_realistic = _core.run_realistic


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


def _apply_split_from_adjustment_factors(account, data, current: str) -> None:
    # This hook is called on every simulated market session before trading. It is
    # therefore the deterministic place to settle a DARF exactly on its modeled
    # due session, without requiring a trade to happen that day.
    processor = getattr(account, "process_due_taxes", None)
    if processor is not None:
        processor(current, data.dates)
    _original_apply_split_from_adjustment_factors(account, data, current)


def _raw_execution_value(pricebook, value_date: str, ticker: str, quantity: int) -> float:
    if quantity <= 0:
        return 0.0
    value = 0.0
    for qty, quote in pricebook.legs(value_date, ticker, quantity):
        raw = float(quote.open)
        if raw <= 0 or not math.isfinite(raw):
            raise ValueError(f"{value_date}/{ticker}: invalid executable opening price.")
        value += qty * raw
    return value


def _target_quantity_from_execution_book(
    pricebook,
    value_date: str,
    ticker: str,
    target_value: float,
) -> int:
    """Largest integer quantity whose raw executable opening value fits target_value."""

    if target_value <= 0:
        return 0
    low = 0
    high = 1
    while _raw_execution_value(pricebook, value_date, ticker, high) <= target_value + 1e-12:
        low = high
        high *= 2
        if high > 1_000_000_000:
            raise ValueError(f"{value_date}/{ticker}: unreasonable target quantity.")
    while low + 1 < high:
        middle = (low + high) // 2
        if _raw_execution_value(pricebook, value_date, ticker, middle) <= target_value + 1e-12:
            low = middle
        else:
            high = middle
    return low


def _known_tax_reserve(account, value_date: str) -> float:
    reserve = max(0.0, float(_core._provisional_ordinary_tax(account, value_date)))
    known = getattr(account, "known_darf_reserve", None)
    if known is not None:
        reserve += max(0.0, float(known()))
    return reserve


def rebalance_atomic(account, data, pricebook, current: str, targets: dict[str, float]):
    """Atomic rebalance sized from actual 010/020 opens and known tax reserves."""

    trial = copy.deepcopy(account)
    held = {ticker for ticker, pos in trial.positions.items() if pos.shares > 0}
    required = held | {ticker for ticker, weight in targets.items() if weight > 0}

    equity_open = trial.cash + sum(
        _raw_execution_value(pricebook, current, ticker, trial.shares(ticker))
        for ticker in held
    )
    if equity_open <= 0 or not math.isfinite(equity_open):
        raise ValueError(f"{current}: invalid executable opening equity.")

    desired_shares: dict[str, int] = {}
    for ticker in required:
        weight = max(0.0, float(targets.get(ticker, 0.0)))
        if not math.isfinite(weight):
            raise ValueError(f"{current}/{ticker}: non-finite target weight.")
        desired_shares[ticker] = _target_quantity_from_execution_book(
            pricebook,
            current,
            ticker,
            equity_open * weight,
        )

    for ticker in sorted(held):
        excess = trial.shares(ticker) - desired_shares.get(ticker, 0)
        if excess <= 0:
            continue
        for qty, quote in pricebook.legs(current, ticker, excess):
            trial.sell_leg(current, ticker, qty, quote)

    wanted_by_ticker = {
        ticker: max(0, desired_shares.get(ticker, 0) - trial.shares(ticker))
        for ticker in targets
    }
    wanted_by_ticker = {
        ticker: quantity for ticker, quantity in wanted_by_ticker.items() if quantity > 0
    }
    reserved_tax = _known_tax_reserve(trial, current)
    available_cash = max(0.0, trial.cash - reserved_tax)

    def total_buy_cost(plan: dict[str, int]) -> float:
        return sum(
            _core._estimate_buy_cost(trial, pricebook, current, ticker, quantity)
            for ticker, quantity in plan.items()
            if quantity > 0
        )

    buy_plan = dict(wanted_by_ticker)
    if wanted_by_ticker and total_buy_cost(buy_plan) > available_cash + 1e-9:
        low, high = 0.0, 1.0
        best = {ticker: 0 for ticker in wanted_by_ticker}
        for _ in range(48):
            scale = (low + high) / 2
            candidate = {
                ticker: int(math.floor(quantity * scale))
                for ticker, quantity in wanted_by_ticker.items()
            }
            if total_buy_cost(candidate) <= available_cash + 1e-9:
                best = candidate
                low = scale
            else:
                high = scale
        buy_plan = best

    for ticker in sorted(buy_plan):
        quantity = buy_plan[ticker]
        if quantity <= 0:
            continue
        for qty, quote in pricebook.legs(current, ticker, quantity):
            trial.buy_leg(current, ticker, qty, quote)

    if trial.cash < _known_tax_reserve(trial, current) - 1e-7:
        raise ValueError(f"{current}: atomic rebalance consumed reserved tax cash.")
    return trial


def run_realistic(*args, **kwargs):
    summary, curve, account = _original_run_realistic(*args, **kwargs)
    outstanding = getattr(account, "outstanding_tax_liability", lambda: 0.0)()
    if outstanding > 1e-9 and "__ACCRUED_TAX_LIABILITY" not in summary.validity:
        summary = replace(
            summary,
            validity=summary.validity + "__ACCRUED_TAX_LIABILITY",
        )
    return summary, curve, account


_core._apply_ticker_transitions = _apply_ticker_transitions
_core._apply_split_from_adjustment_factors = _apply_split_from_adjustment_factors
_core.rebalance_atomic = rebalance_atomic
_core.run_realistic = run_realistic


def __getattr__(name: str):
    return getattr(_core, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_core)))
