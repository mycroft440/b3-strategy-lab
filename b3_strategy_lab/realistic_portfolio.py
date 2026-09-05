from __future__ import annotations

import copy
import math
import statistics
from bisect import bisect_left, bisect_right

from b3_strategy_lab import realistic_portfolio_core as _core

_original_apply_ticker_transitions = _core._apply_ticker_transitions
_original_apply_split_from_adjustment_factors = _core._apply_split_from_adjustment_factors


def _apply_ticker_transitions(account, transitions) -> None:
    for transition in transitions:
        # A source-reviewed corporate event is relevant to account economics only
        # when the account actually carries the disappearing instrument across it.
        # Unheld terminal/complex events must not poison unrelated portfolios.
        if account.shares(transition.old_ticker) <= 0:
            continue
        if not math.isclose(float(transition.cash_per_old_share), 0.0, abs_tol=1e-12):
            raise ValueError(
                f"{transition.old_ticker}->{transition.new_ticker}: cash component is not "
                "supported without an explicit, source-tested tax-basis rule."
            )
        ratio_is_one = math.isclose(
            float(transition.share_ratio), 1.0, rel_tol=1e-12, abs_tol=1e-12
        )
        if not ratio_is_one:
            if getattr(transition, "certification_status", "unresolved") != "certified":
                raise ValueError(
                    f"{transition.old_ticker}->{transition.new_ticker}: non-1:1 conversion "
                    "requires a certified source-bound instrument transition."
                )
            if getattr(transition, "tax_basis_treatment", "") != "carry_total_basis":
                raise ValueError(
                    f"{transition.old_ticker}->{transition.new_ticker}: non-1:1 conversion "
                    "requires explicit carry_total_basis treatment."
                )
        if not transition.new_ticker:
            if (
                getattr(transition, "certification_status", "unresolved") != "certified"
                or getattr(transition, "event_type", "") != "economic_termination"
                or getattr(transition, "tax_basis_treatment", "") != "terminal_worthless"
            ):
                raise ValueError(
                    f"{transition.old_ticker}: terminal transition requires a certified "
                    "economic_termination with terminal_worthless treatment."
                )
    _original_apply_ticker_transitions(account, transitions)


def _remap_target_weights(targets, transitions) -> dict[str, float]:
    """Carry designated weights through a supported ticker rename."""

    result = dict(targets)
    for transition in transitions:
        weight = result.pop(transition.old_ticker, 0.0)
        if weight > 0 and transition.new_ticker:
            result[transition.new_ticker] = (
                result.get(transition.new_ticker, 0.0) + weight
            )
    return result


def _apply_split_from_adjustment_factors(account, data, current: str) -> None:
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


def _provisional_tax_reserve(account, value_date: str) -> float:
    return max(0.0, float(_core._provisional_ordinary_tax(account, value_date)))


def rebalance_atomic(account, data, pricebook, current: str, targets: dict[str, float]):
    """Atomic rebalance sized from actual 010/020 opens and current tax reserve."""

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
    reserved_tax = _provisional_tax_reserve(trial, current)
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

    if trial.cash < _provisional_tax_reserve(trial, current) - 1e-7:
        raise ValueError(f"{current}: atomic rebalance consumed provisional tax reserve.")
    return trial


def _cash_event_maps(events, dates: list[str]):
    """Map entitlements and the earliest legally usable payment session.

    A distribution right exists only after the close of ``last_date_prior``. Even if
    a source reports a payment date on or before that date, the replay never makes
    the cash spendable before the next simulated B3 session after entitlement.
    """

    by_entitlement = {}
    by_payment_session = {}
    for event in events:
        by_entitlement.setdefault(event.last_date_prior, []).append(event)
        payment_index = bisect_left(dates, event.payment_date)
        post_entitlement_index = bisect_right(dates, event.last_date_prior)
        index = max(payment_index, post_entitlement_index)
        if index >= len(dates):
            continue
        by_payment_session.setdefault(dates[index], []).append(event)
    return by_entitlement, by_payment_session


def _credit_event(account, event, entitlements) -> float:
    key = _core._event_key(event)
    settler = getattr(account, "settle_distribution_receivable", None)
    if settler is not None:
        settler(key)
    entitled = entitlements.pop(key, 0)
    row = account.credit_distribution(
        event.payment_date,
        event.ticker,
        event.label,
        entitled,
        event.gross_per_share,
    )
    return row.net


def _register_entitlement_receivable(account, event, entitlements) -> None:
    key = _core._event_key(event)
    entitled = account.shares(event.ticker)
    entitlements[key] = entitled
    registrar = getattr(account, "register_distribution_receivable", None)
    if registrar is not None:
        registrar(
            key,
            ticker=event.ticker,
            label=event.label,
            shares_entitled=entitled,
            gross_per_share=event.gross_per_share,
            payment_date=event.payment_date,
        )


def _receivable_value(account) -> float:
    getter = getattr(account, "distribution_receivable_value", None)
    return max(0.0, float(getter())) if getter is not None else 0.0


def _restore_distribution_entitlements(account, cash_events) -> dict[object, int]:
    """Rebuild pending share entitlements when a live account crosses a fold boundary."""

    pending = getattr(account, "_distribution_receivables", {})
    if not pending:
        return {}
    by_key = {_core._event_key(event): event for event in cash_events}
    result: dict[object, int] = {}
    for key, item in pending.items():
        event = by_key.get(key)
        if event is None:
            raise ValueError(
                "Carried distribution receivable has no matching certified event: "
                + repr(key)
            )
        gross = float(item[1])
        per_share = float(event.gross_per_share)
        if per_share <= 0:
            if gross > 1e-12:
                raise ValueError(f"{event.ticker}: invalid carried distribution per-share value.")
            result[key] = 0
            continue
        shares = int(round(gross / per_share))
        if not math.isclose(shares * per_share, gross, rel_tol=1e-9, abs_tol=1e-7):
            raise ValueError(
                f"{event.ticker}: carried distribution receivable cannot be reconciled to shares."
            )
        result[key] = shares
    return result


def _account_close_equity(account, data, value_date: str, cash_events) -> float:
    """Economic equity at a carried fold boundary without double-counting cum-right value.

    Receivables registered immediately *after* ``value_date`` close are intentionally
    absent from that day's curve because the cum-right closing price still embeds the
    distribution right. They live on the account only so they can survive into the next
    fold. Excluding exactly those newly registered rights reconstructs the same close
    equity used by the preceding fold while preserving older unpaid receivables.
    """

    pending = getattr(account, "_distribution_receivables", {})
    by_key = {_core._event_key(event): event for event in cash_events}
    receivables = 0.0
    for key, item in pending.items():
        event = by_key.get(key)
        if event is None:
            raise ValueError(
                "Carried distribution receivable has no matching certified event: "
                + repr(key)
            )
        if event.last_date_prior == value_date:
            continue
        receivables += max(0.0, float(item[0]))

    equity = float(account.cash) + receivables
    for ticker, position in account.positions.items():
        if position.shares <= 0:
            continue
        candle = data.by_date.get(ticker, {}).get(value_date)
        if candle is None or candle.raw_close <= 0:
            raise ValueError(
                f"{value_date}/{ticker}: carried position lacks a fresh official close."
            )
        equity += position.shares * float(candle.raw_close)
    if equity <= 0 or not math.isfinite(equity):
        raise ValueError(f"{value_date}: invalid carried account equity.")
    return equity


def run_realistic(
    *,
    data,
    universe,
    pricebook,
    cash_events,
    fee_schedule,
    strategy: str,
    config,
    start: str,
    end: str,
    initial_cash: float,
    base_slippage_bps: float,
    participation_bps_at_1pct: float,
    max_slippage_bps: float,
    transitions,
    economic_gap_adjustment: bool,
    selection_status: str = "retrospective_hypothesis_replay",
    survivorship_safe: bool = False,
    cash_events_complete: bool = False,
    progress_callback=None,
    existing_account=None,
    force_initial_decision: bool = False,
):
    """Realistic replay with optional continuous account state across OOS folds.

    When ``existing_account`` is supplied, positions, tax-loss carry, IRRF credit,
    scheduled DARFs and distribution receivables continue unchanged. The summary
    reports fold deltas while the returned account remains cumulative.
    """

    from scripts.backtest_strategy_management_combinations import _build_eligibility
    from scripts.research_portfolio_allocation import (
        _eligible_tickers,
        _portfolio_metrics,
        _target_weights,
        _yearly_returns,
    )
    from b3_strategy_lab.realistic import RealCashAccount, SlippageModel

    dates = [value for value in data.dates if start <= value <= end]
    if len(dates) < 2:
        raise ValueError("Insufficient sessions for realistic backtest.")

    prior_dates = [value for value in data.dates if value < dates[0]]
    prior_date = prior_dates[-1] if prior_dates else None

    if existing_account is None:
        account = RealCashAccount(
            initial_cash,
            fee_schedule,
            SlippageModel(
                base_bps=base_slippage_bps,
                participation_bps_at_1pct=participation_bps_at_1pct,
                max_bps=max_slippage_bps,
            ),
        )
        metric_initial_equity = float(initial_cash)
    else:
        account = copy.deepcopy(existing_account)
        if prior_date is None:
            raise ValueError("A continuous account requires a prior market session.")
        metric_initial_equity = _account_close_equity(
            account, data, prior_date, cash_events
        )

    starting_trades = len(account.trade_ledger)
    starting_fees = float(account.fees_paid)
    starting_ordinary_tax = float(account.tax_paid)
    starting_distribution_tax = float(account.dividend_jcp_tax_paid)

    signal_start = min(
        candle.date for ticker in data.tickers for candle in data.candles[ticker]
    )
    eligibility = (
        _core._gap_adjusted_eligibility(data, strategy, cash_events, "adjusted")
        if economic_gap_adjustment
        else _build_eligibility(
            data,
            [strategy],
            "adjusted",
            signal_start=signal_start,
        )[strategy]
    )
    entitlement_map, payment_map = _cash_event_maps(cash_events, dates)
    entitlements = _restore_distribution_entitlements(account, cash_events)
    pending_targets: dict[str, float] | None = None
    designated_targets: dict[str, float] = {}
    active_targets: dict[str, float] = {}
    curve: list[_core.CurveRow] = []
    equities: list[float] = []
    distributions_net = 0.0
    progress_interval = max(1, len(dates) // 100)
    if progress_callback is not None:
        progress_callback(0, len(dates), dates[0])

    if prior_date is not None and (
        force_initial_decision or _core._is_rebalance(prior_date, dates[0], config.rebalance)
    ):
        try:
            prior_investable = universe.tickers_on(prior_date)
        except ValueError:
            # Never borrow the first future universe snapshot to manufacture an
            # opening portfolio. A replay that starts before universe coverage
            # begins remains in cash until its first causal decision.
            prior_investable = set()
        prior_eligible = _eligible_tickers(data, prior_date, eligibility) or set()
        allowed = prior_eligible.intersection(prior_investable)
        designated_targets = (
            _target_weights(
                data,
                prior_date,
                config,
                eligible_tickers=allowed,
            )
            if allowed
            else {}
        )
        if allowed or force_initial_decision:
            pending_targets = dict(designated_targets)

    for index, current in enumerate(dates):
        next_date = dates[index + 1] if index + 1 < len(dates) else None
        payment_events = payment_map.get(current, [])
        preopen_payments = [event for event in payment_events if event.payment_date < current]
        same_day_payments = [event for event in payment_events if event.payment_date == current]

        _apply_split_from_adjustment_factors(account, data, current)
        if current in transitions:
            _apply_ticker_transitions(account, transitions[current])
            designated_targets = _remap_target_weights(
                designated_targets, transitions[current]
            )
            active_targets = _remap_target_weights(active_targets, transitions[current])
            if pending_targets is not None:
                pending_targets = _remap_target_weights(
                    pending_targets, transitions[current]
                )

        for event in preopen_payments:
            distributions_net += _credit_event(account, event, entitlements)

        if pending_targets is not None:
            account = rebalance_atomic(account, data, pricebook, current, pending_targets)
            active_targets = dict(pending_targets)

        for event in same_day_payments:
            distributions_net += _credit_event(account, event, entitlements)

        # Once the final B3 session of a month has traded, every ordinary sale for
        # that month is known. At a terminal mid-month replay date this is a terminal
        # no-more-sales assumption for the remainder of that month. Accrue before
        # recording the close so economic equity is not temporarily overstated.
        month_ends_here = next_date is None or next_date[:7] != current[:7]
        if month_ends_here:
            account.finalize_month(current[:7])

        equity = account.cash + _receivable_value(account)
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
            _core.CurveRow(
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

        # Register after today's close so the cum-right close and the receivable are
        # never counted at the same instant. It becomes economic equity next session.
        for event in entitlement_map.get(current, []):
            _register_entitlement_receivable(account, event, entitlements)

        pending_targets = None
        if next_date is not None and _core._is_rebalance(
            current, next_date, config.rebalance
        ):
            strategy_eligible = _eligible_tickers(data, current, eligibility) or set()
            investable = universe.tickers_on(current)
            allowed = strategy_eligible.intersection(investable)
            designated_targets = _target_weights(
                data,
                current,
                config,
                eligible_tickers=allowed,
            )
            pending_targets = dict(designated_targets)
        elif next_date is not None:
            strategy_eligible = _eligible_tickers(data, current, eligibility) or set()
            investable = universe.tickers_on(current)
            signal_targets = {
                ticker: weight
                for ticker, weight in designated_targets.items()
                if ticker in strategy_eligible and ticker in investable
            }
            if signal_targets != active_targets:
                pending_targets = signal_targets

        completed = index + 1
        if progress_callback is not None and (
            completed == len(dates) or completed % progress_interval == 0
        ):
            progress_callback(completed, len(dates), current)

    metrics = _portfolio_metrics(equities, dates, metric_initial_equity)
    yearly = _yearly_returns(equities, dates, metric_initial_equity)
    fee_qualities = {fee_schedule.quality_on(value) for value in dates}
    fee_quality = ",".join(sorted(fee_qualities))
    validity = "REALISTIC_POINT_IN_TIME"
    if fee_qualities != {"official"}:
        validity += "__MODELED_FEES"
    if not survivorship_safe:
        validity += "__RETROSPECTIVE_UNIVERSE"
    if selection_status == "retrospective_hypothesis_replay":
        validity += "__RETROSPECTIVE_SELECTION"
    if not cash_events_complete:
        validity += "__UNCERTIFIED_CASH_EVENTS"
    if account.outstanding_tax_liability() > 1e-9:
        validity += "__ACCRUED_TAX_LIABILITY"
    if _receivable_value(account) > 1e-9:
        validity += "__UNPAID_DISTRIBUTION_RECEIVABLE"

    summary = _core.RealisticSummary(
        strategy=strategy,
        management=config.name,
        start=dates[0],
        end=dates[-1],
        initial_cash=metric_initial_equity,
        final_equity=equities[-1],
        total_return=metrics["total_return"],
        cagr=metrics["cagr"],
        max_drawdown=metrics["max_drawdown"],
        annual_volatility=metrics["annual_volatility"],
        sharpe=metrics["sharpe"],
        average_annual_return=statistics.mean(yearly.values()) if yearly else 0.0,
        trades=len(account.trade_ledger) - starting_trades,
        fees_paid=account.fees_paid - starting_fees,
        ordinary_income_tax_paid=account.tax_paid - starting_ordinary_tax,
        distribution_tax_paid=account.dividend_jcp_tax_paid - starting_distribution_tax,
        distributions_net=distributions_net,
        validity=validity,
        point_in_time_universe=True,
        survivorship_safe=survivorship_safe,
        fractional_execution=True,
        cash_events_complete=cash_events_complete,
        fee_quality=fee_quality,
        economic_gap_adjustment=economic_gap_adjustment,
        selection_status=selection_status,
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
