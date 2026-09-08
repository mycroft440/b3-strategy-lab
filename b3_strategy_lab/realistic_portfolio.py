from __future__ import annotations

import copy
import math
import statistics
from bisect import bisect_left, bisect_right

from b3_strategy_lab import realistic_portfolio_core as _core
from b3_strategy_lab.corporate_settlements import (
    apply_cash_transition, apply_fractional_split, mark_and_pay_corporate_receivables,
)

_original_apply_ticker_transitions = _core._apply_ticker_transitions
_original_apply_split_from_adjustment_factors = _core._apply_split_from_adjustment_factors


def _apply_ticker_transitions(account, transitions) -> None:
    transitions = [event for event in transitions if not apply_cash_transition(account, event)]
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
    apply_fractional_split(account, data, current, _original_apply_split_from_adjustment_factors)


def _provisional_tax_reserve(account, value_date: str) -> float:
    return max(0.0, float(_core._provisional_ordinary_tax(account, value_date)))


def _freeze_target_quantities(account, data, pricebook, decision_date, targets, execution_date=None):
    """Fix target quantities using only the decision session's closing marks."""

    held = {ticker for ticker, pos in account.positions.items() if pos.shares > 0}
    required = held | {ticker for ticker, weight in targets.items() if weight > 0}
    closes = {}
    for ticker in required:
        candle = getattr(data, "by_date", {}).get(ticker, {}).get(decision_date)
        quote = pricebook._quotes.get((decision_date, ticker, "010"))
        close = float(candle.raw_close if candle is not None else quote.close if quote else 0.0)
        if close <= 0 or not math.isfinite(close):
            raise ValueError(f"{decision_date}/{ticker}: prior official close required for order sizing.")
        closes[ticker] = close
    equity = account.cash + sum(account.shares(ticker) * closes[ticker] for ticker in held)
    equity = max(0.0, equity - _provisional_tax_reserve(account, decision_date))
    quantities = {}
    for ticker in required:
        weight = float(targets.get(ticker, 0.0))
        if not math.isfinite(weight) or weight < 0:
            raise ValueError(f"{decision_date}/{ticker}: invalid target weight.")
        quantity = int(math.floor(equity * weight / closes[ticker]))
        held_quantity = account.shares(ticker)
        if quantity > held_quantity:
            fee = account.fee_schedule.rule_on(execution_date or decision_date)
            legs = 2 if quantity - held_quantity > pricebook.standard_lot else 1
            budget = equity * weight - held_quantity * closes[ticker] - legs * fee.brokerage_fixed
            unit_cost = closes[ticker] * (1 + account.slippage.max_bps / 10_000) * (1 + fee.b3_bps / 10_000)
            quantity = held_quantity + min(quantity - held_quantity, max(0, math.floor(budget / unit_cost)))
        quantities[ticker] = quantity
    return quantities


def _adjust_pending_quantities(quantities, data, current, transitions):
    result = dict(quantities)
    for ticker, quantity in result.items():
        index = getattr(data, "index_by_date", {}).get(ticker, {}).get(current)
        if index is not None and index > 0:
            candles = data.candles[ticker]
            ratio = float(candles[index].adjustment_factor) / float(candles[index - 1].adjustment_factor)
            if ratio <= 0 or not math.isfinite(ratio):
                raise ValueError(f"{current}/{ticker}: invalid pending-order split ratio.")
            result[ticker] = int(math.floor(quantity * ratio + 1e-9))
    for event in transitions:
        quantity = result.pop(event.old_ticker, 0)
        if event.new_ticker:
            result[event.new_ticker] = result.get(event.new_ticker, 0) + int(
                math.floor(quantity * event.share_ratio + 1e-9)
            )
    return result


def rebalance_atomic(
    account, data, pricebook, current: str, targets: dict[str, float],
    *, frozen_quantities=None, decision_date=None,
):
    """Execute frozen orders; gaps, capacity and cash can only reduce their fills.

    Daily prices support a conservative partial-fill scenario, not a claim about
    auction queue priority. Unfilled quantities expire after this session.
    """
    from b3_strategy_lab.audit_hardening import remaining_causal_capacity

    trial = copy.deepcopy(account)
    if frozen_quantities == {} and not any(pos.shares > 0 for pos in trial.positions.values()):
        return trial
    pricebook.enable_causal_liquidity()
    if frozen_quantities is None:
        dates = set(getattr(data, "dates", [])) | {key[0] for key in pricebook._quotes}
        prior_dates = sorted(day for day in dates if day < current)
        decision_date = decision_date or (prior_dates[-1] if prior_dates else None)
        if decision_date is None or decision_date >= current:
            raise ValueError(f"{current}: a prior decision session is required for order sizing.")
        frozen_quantities = _freeze_target_quantities(trial, data, pricebook, decision_date, targets, current)
        frozen_quantities = _adjust_pending_quantities(frozen_quantities, data, current, [])
    desired_shares = dict(frozen_quantities)
    held = {ticker for ticker, pos in trial.positions.items() if pos.shares > 0}
    orders = []
    for ticker in sorted(held | set(desired_shares)):
        delta = desired_shares.get(ticker, 0) - trial.shares(ticker)
        side = "BUY" if delta > 0 else "SELL"
        quantity = abs(delta)
        lot = pricebook.standard_lot
        for requested, unit, market in ((quantity // lot * lot, lot, "010"), (quantity % lot, 1, "020")):
            if requested <= 0:
                continue
            row = dict(date=current, decision_date=decision_date, ticker=ticker, side=side,
                       market_type=market, requested_shares=requested, filled_shares=0,
                       status="CANCELLED", reason="unavailable_execution_reference")
            trial.order_ledger.append(row)
            try:
                _, quote = pricebook.legs(current, ticker, requested)[0]
            except ValueError as exc:
                if any(reason in str(exc) for reason in (
                    "Missing ", "trailing causal financial volume is zero", "no prior market session"
                )):
                    continue
                raise
            maximum = remaining_causal_capacity(trial, current, ticker, quote)
            fill = min(requested, int(math.floor((maximum + 1e-9) / quote.open / unit)) * unit)
            row["reason"] = "capacity" if fill < requested else ""
            orders.append([ticker, side, fill, unit, quote, row])

    for ticker, side, quantity, _unit, quote, row in orders:
        if side == "SELL" and quantity:
            trial.sell_leg(current, ticker, quantity, quote)
            row["filled_shares"] = quantity

    buys = [order for order in orders if order[1] == "BUY"]
    available_cash = max(0.0, trial.cash - _provisional_tax_reserve(trial, current))

    def costs(plan):
        total = 0.0
        for quantity, order in zip(plan, buys):
            if not quantity:
                continue
            quote = order[4]
            fill, _ = trial.slippage.price("BUY", quote.open, quantity * quote.open, quote.financial_volume)
            notional = quantity * fill
            total += notional + trial.fee_schedule.cost(current, notional)
        return total

    buy_plan = [order[2] for order in buys]
    if costs(buy_plan) > available_cash + 1e-9:
        low, high = 0.0, 1.0
        best = [0] * len(buys)
        for _ in range(48):
            scale = (low + high) / 2
            candidate = [int(math.floor(order[2] * scale / order[3])) * order[3] for order in buys]
            if costs(candidate) <= available_cash + 1e-9:
                best, low = candidate, scale
            else:
                high = scale
        buy_plan = best
    for quantity, order in zip(buy_plan, buys):
        ticker, _side, capacity_quantity, _unit, quote, row = order
        if quantity < capacity_quantity:
            row["reason"] = ";".join(filter(None, [row["reason"], "cash"]))
        if quantity:
            trial.buy_leg(current, ticker, quantity, quote)
            row["filled_shares"] = quantity
    for *_order, row in orders:
        filled = row["filled_shares"]
        row["status"] = "FILLED" if filled == row["requested_shares"] else "PARTIAL" if filled else "CANCELLED"
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
    dividends = max(0.0, float(getter())) if getter is not None else 0.0
    return dividends + float(getattr(account, "_corporate_receivable_value", 0.0))


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

    equity = float(account.cash) + receivables + float(getattr(account, "_corporate_receivable_value", 0.0))
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
    max_causal_adv_participation: float | None = None,
    corporate_settlement_rules=None,
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

    if corporate_settlement_rules is not None:
        previous_rules = getattr(account, "_corporate_settlement_rules", {})
        for key in getattr(account, "_corporate_receivables", {}):
            if previous_rules.get(key) != corporate_settlement_rules.get(key):
                raise ValueError("Cannot change the source rule of an outstanding corporate receivable.")
        account._corporate_settlement_rules = corporate_settlement_rules
    if max_causal_adv_participation is not None:
        if not math.isfinite(max_causal_adv_participation) or not 0 < max_causal_adv_participation <= 1:
            raise ValueError("Causal ADV participation must be in (0, 1].")
        account._max_causal_adv_participation = max_causal_adv_participation
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
    pending_quantities = None
    pending_decision_date = None
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
            pending_decision_date = prior_date
            pending_quantities = _freeze_target_quantities(
                account, data, pricebook, prior_date, pending_targets, dates[0]
            )

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
            adjusted_quantities = _adjust_pending_quantities(
                pending_quantities, data, current, transitions.get(current, [])
            )
            account = rebalance_atomic(
                account, data, pricebook, current, pending_targets,
                frozen_quantities=adjusted_quantities, decision_date=pending_decision_date,
            )
            active_targets = dict(pending_targets)

        for event in same_day_payments:
            distributions_net += _credit_event(account, event, entitlements)
        mark_and_pay_corporate_receivables(account, data, current)

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
        pending_quantities = None
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

        if pending_targets is not None:
            pending_decision_date = current
            pending_quantities = _freeze_target_quantities(
                account, data, pricebook, current, pending_targets, next_date
            )

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
