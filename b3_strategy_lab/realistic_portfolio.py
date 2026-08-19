from __future__ import annotations

import copy
import csv
import math
import statistics
from bisect import bisect_left
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from .realistic import (
    CashDistribution,
    ExecutionPriceBook,
    FeeSchedule,
    PointInTimeUniverse,
    RealCashAccount,
    SlippageModel,
)
from .strategies import build_signals, strategy_parameters


@dataclass(frozen=True)
class TickerTransition:
    effective_date: str
    old_ticker: str
    new_ticker: str
    share_ratio: float = 1.0
    cash_per_old_share: float = 0.0


@dataclass(frozen=True)
class CurveRow:
    date: str
    equity: float
    cash: float
    selected: str
    positions: int
    tax_paid: float
    fees_paid: float
    distributions_net: float


@dataclass(frozen=True)
class RealisticSummary:
    strategy: str
    management: str
    start: str
    end: str
    initial_cash: float
    final_equity: float
    total_return: float
    cagr: float
    max_drawdown: float
    annual_volatility: float
    sharpe: float
    average_annual_return: float
    trades: int
    fees_paid: float
    ordinary_income_tax_paid: float
    distribution_tax_paid: float
    distributions_net: float
    validity: str
    point_in_time_universe: bool
    survivorship_safe: bool
    fractional_execution: bool
    cash_events_complete: bool
    fee_quality: str
    economic_gap_adjustment: bool
    selection_status: str


def load_transitions(path: Path | str) -> dict[str, list[TickerTransition]]:
    source = Path(path)
    if not source.exists():
        return {}
    result: dict[str, list[TickerTransition]] = {}
    with source.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            item = TickerTransition(
                effective_date=str(row["effective_date"])[:10],
                old_ticker=str(row["old_ticker"]).upper(),
                new_ticker=str(row.get("new_ticker", "")).upper(),
                share_ratio=float(row.get("share_ratio", 1.0) or 1.0),
                cash_per_old_share=float(row.get("cash_per_old_share", 0.0) or 0.0),
            )
            result.setdefault(item.effective_date, []).append(item)
    return result


def _gap_adjusted_eligibility(
    data,
    strategy: str,
    cash_events: list[CashDistribution],
    signal_mode: str,
):
    from scripts.backtest_strategy_management_combinations import _build_eligibility

    signal_start = min(
        candle.date for ticker in data.tickers for candle in data.candles[ticker]
    )
    if strategy != "gap_momentum":
        return _build_eligibility(
            data,
            [strategy],
            signal_mode,
            signal_start=signal_start,
        )[strategy]

    per_ex: dict[tuple[str, str], float] = {}
    for event in cash_events:
        key = (event.ticker, event.ex_date)
        per_ex[key] = per_ex.get(key, 0.0) + event.gross_per_share

    params = strategy_parameters(strategy)
    result: dict[str, list[int]] = {}
    for ticker in data.tickers:
        candles = data.candles[ticker]
        modified = []
        for candle in candles:
            raw_distribution = per_ex.get((ticker, candle.date), 0.0)
            if raw_distribution:
                # Signal candles are split-normalized. Cash distributions are quoted
                # per historical raw share, so convert the distribution to the same
                # split-normalized basis before removing its mechanical ex-date gap.
                normalized_distribution = raw_distribution * candle.adjustment_factor
                modified.append(replace(candle, open=candle.open + normalized_distribution))
            else:
                modified.append(candle)
        result[ticker] = build_signals(strategy, modified, **params)
    return result


def _cash_event_maps(
    events: list[CashDistribution],
    dates: list[str],
) -> tuple[dict[str, list[CashDistribution]], dict[str, list[CashDistribution]]]:
    by_entitlement: dict[str, list[CashDistribution]] = {}
    by_payment_session: dict[str, list[CashDistribution]] = {}
    for event in events:
        by_entitlement.setdefault(event.last_date_prior, []).append(event)
        index = bisect_left(dates, event.payment_date)
        if index >= len(dates):
            continue
        by_payment_session.setdefault(dates[index], []).append(event)
    return by_entitlement, by_payment_session


def _event_key(event: CashDistribution) -> tuple[str, str, str, str, float]:
    return (
        event.ticker,
        event.last_date_prior,
        event.payment_date,
        event.label,
        event.gross_per_share,
    )


def _apply_split_from_adjustment_factors(account, data, current: str) -> None:
    for ticker, position in list(account.positions.items()):
        if position.shares <= 0:
            continue
        index = data.index_by_date.get(ticker, {}).get(current)
        if index is None or index <= 0:
            continue
        current_candle = data.candles[ticker][index]
        previous_candle = data.candles[ticker][index - 1]
        prior_factor = float(previous_candle.adjustment_factor)
        current_factor = float(current_candle.adjustment_factor)
        if prior_factor <= 0 or current_factor <= 0:
            raise ValueError(f"{ticker}/{current}: invalid adjustment factor.")
        ratio = current_factor / prior_factor
        if math.isclose(ratio, 1.0, rel_tol=1e-10, abs_tol=1e-12):
            continue
        new_shares = position.shares * ratio
        rounded = round(new_shares)
        if not math.isclose(new_shares, rounded, abs_tol=1e-9):
            raise ValueError(
                f"{ticker}/{current}: corporate action creates {new_shares:.8f} shares "
                "from an integer position. Add the official cash-in-lieu event before "
                "claiming a real-money result."
            )
        if rounded <= 0:
            raise ValueError(f"{ticker}/{current}: invalid post-action quantity.")
        position.shares = int(rounded)
        position.average_cost /= ratio


def _apply_ticker_transitions(
    account: RealCashAccount,
    transitions: list[TickerTransition],
) -> None:
    for transition in transitions:
        old = account.positions[transition.old_ticker]
        if old.shares <= 0:
            continue
        old_shares = old.shares
        if transition.cash_per_old_share:
            account.cash += old_shares * transition.cash_per_old_share
        if transition.new_ticker:
            new_qty = old_shares * transition.share_ratio
            rounded = round(new_qty)
            if not math.isclose(new_qty, rounded, abs_tol=1e-9):
                raise ValueError(
                    f"{transition.old_ticker}->{transition.new_ticker}: non-integer "
                    "share conversion requires explicit cash-in-lieu."
                )
            new = account.positions[transition.new_ticker]
            total_cost = old_shares * old.average_cost
            new_total_cost = new.shares * new.average_cost
            new.shares += int(rounded)
            if new.shares > 0:
                new.average_cost = (new_total_cost + total_cost) / new.shares
        old.shares = 0
        old.average_cost = 0.0


def _estimate_buy_cost(
    account: RealCashAccount,
    pricebook: ExecutionPriceBook,
    value_date: str,
    ticker: str,
    quantity: int,
) -> float:
    total = 0.0
    for qty, quote in pricebook.legs(value_date, ticker, quantity):
        raw_notional = qty * quote.open
        fill, _ = account.slippage.price(
            "BUY", quote.open, raw_notional, quote.financial_volume
        )
        notional = qty * fill
        total += notional + account.fee_schedule.cost(value_date, notional)
    return total


def _max_affordable(
    account: RealCashAccount,
    pricebook: ExecutionPriceBook,
    value_date: str,
    ticker: str,
    upper: int,
) -> int:
    low, high = 0, max(0, upper)
    while low < high:
        mid = (low + high + 1) // 2
        cost = _estimate_buy_cost(account, pricebook, value_date, ticker, mid)
        if cost <= account.cash + 1e-9:
            low = mid
        else:
            high = mid - 1
    return low


def rebalance_atomic(
    account: RealCashAccount,
    data,
    pricebook: ExecutionPriceBook,
    current: str,
    targets: dict[str, float],
) -> RealCashAccount:
    trial = copy.deepcopy(account)
    held = {ticker for ticker, pos in trial.positions.items() if pos.shares > 0}
    required = held | {ticker for ticker, weight in targets.items() if weight > 0}
    raw_opens: dict[str, float] = {}
    for ticker in required:
        candle = data.by_date.get(ticker, {}).get(current)
        if candle is None or candle.raw_open <= 0:
            raise ValueError(f"{current}/{ticker}: required official open is missing.")
        raw_opens[ticker] = candle.raw_open

    equity_open = trial.cash + sum(
        trial.shares(ticker) * raw_opens[ticker] for ticker in held
    )
    if equity_open <= 0 or not math.isfinite(equity_open):
        raise ValueError(f"{current}: invalid opening equity.")

    desired_shares: dict[str, int] = {}
    for ticker in required:
        weight = max(0.0, targets.get(ticker, 0.0))
        desired_shares[ticker] = (
            int(math.floor(equity_open * weight / raw_opens[ticker]))
            if weight > 0
            else 0
        )

    for ticker in sorted(held):
        excess = trial.shares(ticker) - desired_shares.get(ticker, 0)
        if excess <= 0:
            continue
        for qty, quote in pricebook.legs(current, ticker, excess):
            trial.sell_leg(current, ticker, qty, quote)

    for ticker in sorted(targets):
        wanted = desired_shares.get(ticker, 0) - trial.shares(ticker)
        if wanted <= 0:
            continue
        affordable = _max_affordable(trial, pricebook, current, ticker, wanted)
        if affordable <= 0:
            continue
        for qty, quote in pricebook.legs(current, ticker, affordable):
            trial.buy_leg(current, ticker, qty, quote)

    if trial.cash < -1e-7:
        raise ValueError(f"{current}: atomic rebalance would create negative cash.")
    return trial


def _is_rebalance(current: str, next_date: str, frequency: str) -> bool:
    current_day = date.fromisoformat(current)
    next_day = date.fromisoformat(next_date)
    if frequency == "daily":
        return True
    if frequency == "weekly":
        return current_day.isocalendar()[:2] != next_day.isocalendar()[:2]
    if frequency == "monthly":
        return (current_day.year, current_day.month) != (next_day.year, next_day.month)
    raise ValueError(f"Unknown rebalance frequency: {frequency}")


def run_realistic(
    *,
    data,
    universe: PointInTimeUniverse,
    pricebook: ExecutionPriceBook,
    cash_events: list[CashDistribution],
    fee_schedule: FeeSchedule,
    strategy: str,
    config,
    start: str,
    end: str,
    initial_cash: float,
    base_slippage_bps: float,
    participation_bps_at_1pct: float,
    max_slippage_bps: float,
    transitions: dict[str, list[TickerTransition]],
    economic_gap_adjustment: bool,
    selection_status: str = "retrospective_hypothesis_replay",
) -> tuple[RealisticSummary, list[CurveRow], RealCashAccount]:
    from scripts.backtest_strategy_management_combinations import _build_eligibility
    from scripts.research_portfolio_allocation import (
        _eligible_tickers,
        _portfolio_metrics,
        _target_weights,
        _yearly_returns,
    )

    dates = [value for value in data.dates if start <= value <= end]
    if len(dates) < 2:
        raise ValueError("Insufficient sessions for realistic backtest.")

    account = RealCashAccount(
        initial_cash,
        fee_schedule,
        SlippageModel(
            base_bps=base_slippage_bps,
            participation_bps_at_1pct=participation_bps_at_1pct,
            max_bps=max_slippage_bps,
        ),
    )
    signal_start = min(
        candle.date for ticker in data.tickers for candle in data.candles[ticker]
    )
    eligibility = (
        _gap_adjusted_eligibility(data, strategy, cash_events, "adjusted")
        if economic_gap_adjustment
        else _build_eligibility(
            data,
            [strategy],
            "adjusted",
            signal_start=signal_start,
        )[strategy]
    )
    entitlement_map, payment_map = _cash_event_maps(cash_events, dates)
    entitlements: dict[tuple[str, str, str, str, float], int] = {}
    pending_targets: dict[str, float] | None = None
    curve: list[CurveRow] = []
    equities: list[float] = []
    distributions_net = 0.0

    for index, current in enumerate(dates):
        next_date = dates[index + 1] if index + 1 < len(dates) else None

        _apply_split_from_adjustment_factors(account, data, current)
        if current in transitions:
            _apply_ticker_transitions(account, transitions[current])

        if pending_targets is not None:
            account = rebalance_atomic(
                account,
                data,
                pricebook,
                current,
                pending_targets,
            )

        for event in payment_map.get(current, []):
            entitled = entitlements.get(_event_key(event), 0)
            # Cash becomes tradeable on this market session, but the tax ledger
            # retains the event's official payment date/month.
            row = account.credit_distribution(
                event.payment_date,
                event.ticker,
                event.label,
                entitled,
                event.gross_per_share,
            )
            distributions_net += row.net

        if next_date is None or current[:7] != next_date[:7]:
            account.finalize_month(current[:7])

        equity = account.cash
        selected = []
        for ticker, position in account.positions.items():
            if position.shares <= 0:
                continue
            candle = data.by_date.get(ticker, {}).get(current)
            if candle is None or candle.raw_close <= 0:
                raise ValueError(
                    f"{current}/{ticker}: held position lacks a fresh official close. "
                    "Add the delisting/ticker-transition event instead of forward-filling."
                )
            equity += position.shares * candle.raw_close
            selected.append(ticker)
        if equity <= 0 or not math.isfinite(equity):
            raise ValueError(f"{current}: invalid close equity.")
        equities.append(equity)
        curve.append(
            CurveRow(
                date=current,
                equity=equity,
                cash=account.cash,
                selected=";".join(sorted(selected)),
                positions=len(selected),
                tax_paid=account.tax_paid + account.dividend_jcp_tax_paid,
                fees_paid=account.fees_paid,
                distributions_net=distributions_net,
            )
        )

        for event in entitlement_map.get(current, []):
            entitlements[_event_key(event)] = account.shares(event.ticker)

        if next_date is not None and _is_rebalance(current, next_date, config.rebalance):
            strategy_eligible = _eligible_tickers(data, current, eligibility) or set()
            investable = universe.tickers_on(current)
            allowed = strategy_eligible.intersection(investable)
            pending_targets = _target_weights(
                data,
                current,
                config,
                eligible_tickers=allowed,
            )
        else:
            pending_targets = None

    metrics = _portfolio_metrics(equities, dates, initial_cash)
    yearly = _yearly_returns(equities, dates, initial_cash)
    fee_qualities = {fee_schedule.quality_on(value) for value in dates}
    fee_quality = ",".join(sorted(fee_qualities))
    validity = "REALISTIC_POINT_IN_TIME"
    if fee_qualities != {"official"}:
        validity += "__MODELED_FEES"
    if selection_status == "retrospective_hypothesis_replay":
        validity += "__RETROSPECTIVE_SELECTION"

    summary = RealisticSummary(
        strategy=strategy,
        management=config.name,
        start=dates[0],
        end=dates[-1],
        initial_cash=initial_cash,
        final_equity=equities[-1],
        total_return=metrics["total_return"],
        cagr=metrics["cagr"],
        max_drawdown=metrics["max_drawdown"],
        annual_volatility=metrics["annual_volatility"],
        sharpe=metrics["sharpe"],
        average_annual_return=statistics.mean(yearly.values()) if yearly else 0.0,
        trades=len(account.trade_ledger),
        fees_paid=account.fees_paid,
        ordinary_income_tax_paid=account.tax_paid,
        distribution_tax_paid=account.dividend_jcp_tax_paid,
        distributions_net=distributions_net,
        validity=validity,
        point_in_time_universe=True,
        survivorship_safe=True,
        fractional_execution=True,
        cash_events_complete=True,
        fee_quality=fee_quality,
        economic_gap_adjustment=economic_gap_adjustment,
        selection_status=selection_status,
    )
    return summary, curve, account
