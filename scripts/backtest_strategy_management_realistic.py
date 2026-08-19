from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import statistics
import sys
from bisect import bisect_left
from dataclasses import asdict, dataclass, replace
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.realistic import (  # noqa: E402
    CashDistribution,
    ExecutionPriceBook,
    FeeSchedule,
    PointInTimeUniverse,
    RealCashAccount,
    SlippageModel,
    load_cash_distributions,
    write_dataclass_csv,
)
from b3_strategy_lab.strategies import build_signals, strategy_parameters  # noqa: E402
from scripts.backtest_strategy_management_combinations import _build_eligibility  # noqa: E402
from scripts.research_portfolio_allocation import (  # noqa: E402
    MarketData,
    PortfolioConfig,
    _configs,
    _eligible_tickers,
    _portfolio_metrics,
    _target_weights,
    _yearly_returns,
)


DEFAULT_UNIVERSE = Path("data/universes/point_in_time_union.json")
DEFAULT_SNAPSHOTS = Path("data/universes/point_in_time_weekly.csv")
DEFAULT_EXECUTION = Path("data/execution/b3_standard_fractional_open.csv")
DEFAULT_CASH_EVENTS = Path("data/corporate_actions/point_in_time_cash_distributions.csv")
DEFAULT_CASH_MANIFEST = Path("data/corporate_actions/point_in_time_cash_distributions.manifest.json")
DEFAULT_FEES = Path("data/fees/b3_equity_fee_schedule.json")
DEFAULT_OUTPUT = Path("reports/realistic_account_summary.json")
DEFAULT_CURVE = Path("reports/realistic_account_curve.csv")
DEFAULT_TRADES = Path("reports/realistic_account_trades.csv")
DEFAULT_CASH_LEDGER = Path("reports/realistic_account_distributions.csv")
DEFAULT_TAX = Path("reports/realistic_account_tax.csv")
DEFAULT_TRANSITIONS = Path("data/corporate_actions/ticker_transitions.csv")


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


def _load_transitions(path: Path) -> dict[str, list[TickerTransition]]:
    if not path.exists():
        return {}
    result: dict[str, list[TickerTransition]] = {}
    with path.open(newline="", encoding="utf-8") as file:
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


def _config_by_name(name: str, signal_mode: str) -> PortfolioConfig:
    matches = [config for config in _configs(signal_mode, "all") if config.name == name]
    if len(matches) != 1:
        raise ValueError(f"Management config not found or ambiguous: {name}")
    return matches[0]


def _date_window(values: list[str], start: str, end: str) -> list[str]:
    return [value for value in values if start <= value <= end]


def _gap_adjusted_eligibility(
    data: MarketData,
    strategy: str,
    cash_events: list[CashDistribution],
    signal_mode: str,
) -> dict[str, list[int]]:
    if strategy != "gap_momentum":
        return _build_eligibility(
            data,
            [strategy],
            signal_mode,
            signal_start=min(
                candle.date for ticker in data.tickers for candle in data.candles[ticker]
            ),
        )[strategy]

    per_ex: dict[tuple[str, str], float] = {}
    for event in cash_events:
        per_ex[(event.ticker, event.ex_date)] = (
            per_ex.get((event.ticker, event.ex_date), 0.0) + event.gross_per_share
        )
    params = strategy_parameters(strategy)
    result: dict[str, list[int]] = {}
    for ticker in data.tickers:
        candles = data.candles[ticker]
        modified = []
        for candle in candles:
            add = per_ex.get((ticker, candle.date), 0.0)
            if add:
                modified.append(replace(candle, open=candle.open + add))
            else:
                modified.append(candle)
        result[ticker] = build_signals(strategy, modified, **params)
    return result


def _cash_event_maps(
    events: list[CashDistribution],
    dates: list[str],
) -> tuple[dict[str, list[CashDistribution]], dict[str, list[CashDistribution]]]:
    by_entitlement: dict[str, list[CashDistribution]] = {}
    by_payment: dict[str, list[CashDistribution]] = {}
    for event in events:
        by_entitlement.setdefault(event.last_date_prior, []).append(event)
        index = bisect_left(dates, event.payment_date)
        if index >= len(dates):
            continue
        pay_session = dates[index]
        by_payment.setdefault(pay_session, []).append(event)
    return by_entitlement, by_payment


def _apply_split_from_adjustment_factors(
    account: RealCashAccount,
    data: MarketData,
    current: str,
    previous: str | None,
) -> None:
    if previous is None:
        return
    for ticker, position in list(account.positions.items()):
        if position.shares <= 0:
            continue
        current_candle = data.by_date.get(ticker, {}).get(current)
        previous_candle = data.by_date.get(ticker, {}).get(previous)
        if current_candle is None or previous_candle is None:
            continue
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


def _rebalance_atomic(
    account: RealCashAccount,
    data: MarketData,
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


def run_realistic(
    *,
    data: MarketData,
    universe: PointInTimeUniverse,
    pricebook: ExecutionPriceBook,
    cash_events: list[CashDistribution],
    fee_schedule: FeeSchedule,
    strategy: str,
    config: PortfolioConfig,
    start: str,
    end: str,
    initial_cash: float,
    base_slippage_bps: float,
    participation_bps_at_1pct: float,
    max_slippage_bps: float,
    transitions: dict[str, list[TickerTransition]],
    economic_gap_adjustment: bool,
) -> tuple[RealisticSummary, list[CurveRow], RealCashAccount]:
    dates = _date_window(data.dates, start, end)
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
    eligibility = (
        _gap_adjusted_eligibility(data, strategy, cash_events, "adjusted")
        if economic_gap_adjustment
        else _build_eligibility(
            data,
            [strategy],
            "adjusted",
            signal_start=min(
                candle.date for ticker in data.tickers for candle in data.candles[ticker]
            ),
        )[strategy]
    )
    entitlement_map, payment_map = _cash_event_maps(cash_events, dates)
    entitlements: dict[tuple[str, str, str, float], int] = {}
    pending_targets: dict[str, float] | None = None
    curve: list[CurveRow] = []
    equities: list[float] = []
    distributions_net = 0.0

    for index, current in enumerate(dates):
        previous = dates[index - 1] if index else None
        next_date = dates[index + 1] if index + 1 < len(dates) else None

        _apply_split_from_adjustment_factors(account, data, current, previous)
        if current in transitions:
            _apply_ticker_transitions(account, transitions[current])

        if pending_targets is not None:
            account = _rebalance_atomic(
                account,
                data,
                pricebook,
                current,
                pending_targets,
            )

        for event in payment_map.get(current, []):
            key = (
                event.ticker,
                event.last_date_prior,
                event.label,
                event.gross_per_share,
            )
            entitled = entitlements.get(key, 0)
            row = account.credit_distribution(
                current,
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
            key = (
                event.ticker,
                event.last_date_prior,
                event.label,
                event.gross_per_share,
            )
            entitlements[key] = account.shares(event.ticker)

        if next_date is not None:
            current_day = date.fromisoformat(current)
            next_day = date.fromisoformat(next_date)
            rebalance = (
                current_day.isocalendar()[:2] != next_day.isocalendar()[:2]
                if config.rebalance == "weekly"
                else (
                    (current_day.year, current_day.month)
                    != (next_day.year, next_day.month)
                    if config.rebalance == "monthly"
                    else config.rebalance == "daily"
                )
            )
            if rebalance:
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
    )
    return summary, curve, account


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Real-money-oriented B3 backtest: point-in-time universe, official "
            "standard/fractional openings, cash distributions, monthly Brazilian "
            "tax accounting, liquidity-aware slippage and no stale-price fallback."
        )
    )
    parser.add_argument("--universe-manifest", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--snapshots", type=Path, default=DEFAULT_SNAPSHOTS)
    parser.add_argument("--execution-prices", type=Path, default=DEFAULT_EXECUTION)
    parser.add_argument("--cash-events", type=Path, default=DEFAULT_CASH_EVENTS)
    parser.add_argument("--cash-manifest", type=Path, default=DEFAULT_CASH_MANIFEST)
    parser.add_argument("--fee-schedule", type=Path, default=DEFAULT_FEES)
    parser.add_argument("--ticker-transitions", type=Path, default=DEFAULT_TRANSITIONS)
    parser.add_argument("--strategy", default="gap_momentum")
    parser.add_argument(
        "--management",
        default="top1_momentum_lb63_skip0_trend0_vol21_equal_weekly_abs_cap1_adjusted",
    )
    parser.add_argument("--start", default="2018-01-02")
    parser.add_argument("--end")
    parser.add_argument("--initial-cash", type=float, default=1_000.0)
    parser.add_argument("--base-slippage-bps", type=float, default=10.0)
    parser.add_argument("--participation-bps-at-1pct", type=float, default=5.0)
    parser.add_argument("--max-slippage-bps", type=float, default=100.0)
    parser.add_argument("--economic-gap-adjustment", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--curve-output", type=Path, default=DEFAULT_CURVE)
    parser.add_argument("--trades-output", type=Path, default=DEFAULT_TRADES)
    parser.add_argument("--cash-ledger-output", type=Path, default=DEFAULT_CASH_LEDGER)
    parser.add_argument("--tax-output", type=Path, default=DEFAULT_TAX)
    args = parser.parse_args(argv)

    manifest = json.loads(args.universe_manifest.read_text(encoding="utf-8"))
    if manifest.get("point_in_time") is not True or manifest.get("survivorship_safe") is not True:
        parser.error("Refusing realistic mode: universe must be point-in-time and survivorship-safe.")
    cash_manifest = json.loads(args.cash_manifest.read_text(encoding="utf-8"))
    if cash_manifest.get("complete") is not True:
        parser.error("Refusing realistic mode: official cash-distribution ledger is incomplete.")

    universe = PointInTimeUniverse.from_csv(args.snapshots)
    if universe.union != {str(item).upper() for item in manifest["tickers"]}:
        parser.error("Snapshot union differs from universe manifest.")
    data = MarketData(
        sorted(universe.union),
        "1d",
        "adjusted",
        require_verified_splits_from=str(manifest["warmup_start"]),
        history_start=str(manifest["warmup_start"]),
    )
    end = args.end or max(data.dates)
    end = min(end, max(value for value in data.dates if value <= end))

    summary, curve, account = run_realistic(
        data=data,
        universe=universe,
        pricebook=ExecutionPriceBook.from_csv(args.execution_prices),
        cash_events=load_cash_distributions(args.cash_events),
        fee_schedule=FeeSchedule.from_json(args.fee_schedule),
        strategy=args.strategy.strip().lower(),
        config=_config_by_name(args.management, "adjusted"),
        start=args.start,
        end=end,
        initial_cash=args.initial_cash,
        base_slippage_bps=args.base_slippage_bps,
        participation_bps_at_1pct=args.participation_bps_at_1pct,
        max_slippage_bps=args.max_slippage_bps,
        transitions=_load_transitions(args.ticker_transitions),
        economic_gap_adjustment=args.economic_gap_adjustment,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(asdict(summary), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_dataclass_csv(args.curve_output, curve)
    write_dataclass_csv(args.trades_output, account.trade_ledger)
    write_dataclass_csv(args.cash_ledger_output, account.cash_ledger)
    write_dataclass_csv(args.tax_output, account.tax.finalized())

    print(json.dumps(asdict(summary), indent=2, ensure_ascii=False))
    print(f"Curve: {args.curve_output}")
    print(f"Trades: {args.trades_output}")
    print(f"Tax: {args.tax_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
