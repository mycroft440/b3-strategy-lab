from __future__ import annotations

import csv
import math
import statistics
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

from .candles import Candle, CorporateAction


@dataclass(frozen=True)
class CurvePoint:
    date: str
    signal: int
    position: int
    shares: float
    cash: float
    equity: float
    trade: str
    trade_price: float
    dividend_cash: float = 0.0
    split_ratio: float = 1.0


@dataclass(frozen=True)
class Summary:
    ticker: str
    strategy: str
    start: str
    end: str
    candles: int
    trades: int
    exposure: float
    final_equity: float
    total_return: float
    cagr: float
    max_drawdown: float
    annual_volatility: float
    sharpe: float
    benchmark_final_equity: float
    benchmark_total_return: float
    benchmark_cagr: float
    benchmark_max_drawdown: float
    excess_total_return: float


def run_strategy_vs_buy_hold(
    ticker: str,
    strategy_name: str,
    candles: list[Candle],
    signals: list[int],
    *,
    initial_cash: float = 10_000.0,
    cost_bps: float = 0.0,
    slippage_bps: float = 0.0,
    lot_size: int = 0,
    price_mode: str = "adjusted",
    actions: list[CorporateAction] | None = None,
) -> tuple[Summary, list[CurvePoint], list[CurvePoint]]:
    if len(candles) < 2:
        raise ValueError("Sao necessarios pelo menos 2 candles para backtest.")
    if len(candles) != len(signals):
        raise ValueError("Candles e sinais precisam ter o mesmo tamanho.")

    if price_mode == "adjusted":
        benchmark_curve = simulate_buy_and_hold(
            candles,
            initial_cash=initial_cash,
            cost_bps=cost_bps,
            slippage_bps=slippage_bps,
            lot_size=lot_size,
        )
        if strategy_name.strip().lower() == "buy_and_hold":
            strategy_curve = benchmark_curve
        else:
            strategy_curve = simulate_single_asset(
                candles,
                signals,
                initial_cash=initial_cash,
                cost_bps=cost_bps,
                slippage_bps=slippage_bps,
                lot_size=lot_size,
            )
    elif price_mode == "raw_events":
        before_open_actions, after_open_actions = _action_buckets(candles, actions or [])
        benchmark_curve = simulate_buy_and_hold_raw_events(
            candles,
            before_open_actions,
            after_open_actions,
            initial_cash=initial_cash,
            cost_bps=cost_bps,
            slippage_bps=slippage_bps,
            lot_size=lot_size,
        )
        if strategy_name.strip().lower() == "buy_and_hold":
            strategy_curve = benchmark_curve
        else:
            strategy_curve = simulate_single_asset_raw_events(
                candles,
                signals,
                before_open_actions,
                after_open_actions,
                initial_cash=initial_cash,
                cost_bps=cost_bps,
                slippage_bps=slippage_bps,
                lot_size=lot_size,
            )
    else:
        raise ValueError("price_mode precisa ser 'adjusted' ou 'raw_events'.")
    strategy_metrics = metrics(strategy_curve, initial_cash)
    benchmark_metrics = metrics(benchmark_curve, initial_cash)

    summary = Summary(
        ticker=ticker,
        strategy=strategy_name,
        start=candles[0].date,
        end=candles[-1].date,
        candles=len(candles),
        trades=sum(1 for point in strategy_curve if point.trade),
        exposure=sum(1 for point in strategy_curve if point.position == 1) / len(strategy_curve),
        final_equity=strategy_curve[-1].equity,
        total_return=strategy_metrics["total_return"],
        cagr=strategy_metrics["cagr"],
        max_drawdown=strategy_metrics["max_drawdown"],
        annual_volatility=strategy_metrics["annual_volatility"],
        sharpe=strategy_metrics["sharpe"],
        benchmark_final_equity=benchmark_curve[-1].equity,
        benchmark_total_return=benchmark_metrics["total_return"],
        benchmark_cagr=benchmark_metrics["cagr"],
        benchmark_max_drawdown=benchmark_metrics["max_drawdown"],
        excess_total_return=strategy_metrics["total_return"] - benchmark_metrics["total_return"],
    )
    return summary, strategy_curve, benchmark_curve


def simulate_single_asset(
    candles: list[Candle],
    signals: list[int],
    *,
    initial_cash: float = 10_000.0,
    cost_bps: float = 0.0,
    slippage_bps: float = 0.0,
    lot_size: int = 0,
) -> list[CurvePoint]:
    cost_rate = cost_bps / 10_000
    slippage_rate = slippage_bps / 10_000
    cash = float(initial_cash)
    shares = 0.0
    position = 0
    curve: list[CurvePoint] = []

    for index, candle in enumerate(candles):
        desired_position = signals[index - 1] if index > 0 else 0
        trade = ""
        trade_price = 0.0

        if desired_position != position:
            if desired_position == 1:
                execution_price = _slipped_price(candle.open, "BUY", slippage_rate)
                shares, cash = _buy_all(cash, execution_price, cost_rate, lot_size)
                if shares > 0:
                    trade = "BUY"
                    position = 1
                    trade_price = execution_price
            else:
                execution_price = _slipped_price(candle.open, "SELL", slippage_rate)
                if shares > 0:
                    cash += _sell_all(shares, execution_price, cost_rate)
                    shares = 0.0
                    trade = "SELL"
                    trade_price = execution_price
                position = 0

        equity = cash + shares * candle.close
        curve.append(
            CurvePoint(
                date=candle.date,
                signal=desired_position,
                position=position,
                shares=shares,
                cash=cash,
                equity=equity,
                trade=trade,
                trade_price=trade_price,
            )
        )

    return curve


def simulate_single_asset_raw_events(
    candles: list[Candle],
    signals: list[int],
    before_open_actions: dict[str, CorporateAction],
    after_open_actions: dict[str, CorporateAction] | None = None,
    *,
    initial_cash: float = 10_000.0,
    cost_bps: float = 0.0,
    slippage_bps: float = 0.0,
    lot_size: int = 0,
) -> list[CurvePoint]:
    cost_rate = cost_bps / 10_000
    slippage_rate = slippage_bps / 10_000
    cash = float(initial_cash)
    shares = 0.0
    position = 0
    curve: list[CurvePoint] = []
    after_open_actions = after_open_actions or {}

    for index, candle in enumerate(candles):
        dividend_cash = 0.0
        split_ratio = 1.0
        if index > 0:
            shares, cash, dividend_cash, split_ratio = _apply_action(candle.date, shares, cash, before_open_actions)

        desired_position = signals[index - 1] if index > 0 else 0
        trade = ""
        trade_price = 0.0

        if desired_position != position:
            if desired_position == 1:
                execution_price = _slipped_price(candle.raw_open, "BUY", slippage_rate)
                bought_shares, cash = _buy_all(cash, execution_price, cost_rate, lot_size)
                if bought_shares > 0:
                    shares += bought_shares
                    trade = "BUY"
                    position = 1
                    trade_price = execution_price
            else:
                execution_price = _slipped_price(candle.raw_open, "SELL", slippage_rate)
                if shares > 0:
                    cash += _sell_all(shares, execution_price, cost_rate)
                    shares = 0.0
                    trade = "SELL"
                    trade_price = execution_price
                position = 0

        shares, cash, after_dividend_cash, after_split_ratio = _apply_action(candle.date, shares, cash, after_open_actions)
        dividend_cash += after_dividend_cash
        split_ratio *= after_split_ratio

        curve.append(
            CurvePoint(
                date=candle.date,
                signal=desired_position,
                position=position,
                shares=shares,
                cash=cash,
                equity=cash + shares * candle.raw_close,
                trade=trade,
                trade_price=trade_price,
                dividend_cash=dividend_cash,
                split_ratio=split_ratio,
            )
        )

    return curve


def simulate_buy_and_hold(
    candles: list[Candle],
    *,
    initial_cash: float = 10_000.0,
    cost_bps: float = 0.0,
    slippage_bps: float = 0.0,
    lot_size: int = 0,
) -> list[CurvePoint]:
    cost_rate = cost_bps / 10_000
    slippage_rate = slippage_bps / 10_000
    execution_price = _slipped_price(candles[0].open, "BUY", slippage_rate)
    shares, cash = _buy_all(float(initial_cash), execution_price, cost_rate, lot_size)
    curve: list[CurvePoint] = []

    for index, candle in enumerate(candles):
        curve.append(
            CurvePoint(
                date=candle.date,
                signal=1,
                position=1,
                shares=shares,
                cash=cash,
                equity=cash + shares * candle.close,
                trade="BUY" if index == 0 and shares > 0 else "",
                trade_price=execution_price if index == 0 and shares > 0 else 0.0,
            )
        )

    return curve


def simulate_buy_and_hold_raw_events(
    candles: list[Candle],
    before_open_actions: dict[str, CorporateAction],
    after_open_actions: dict[str, CorporateAction] | None = None,
    *,
    initial_cash: float = 10_000.0,
    cost_bps: float = 0.0,
    slippage_bps: float = 0.0,
    lot_size: int = 0,
) -> list[CurvePoint]:
    cost_rate = cost_bps / 10_000
    slippage_rate = slippage_bps / 10_000
    execution_price = _slipped_price(candles[0].raw_open, "BUY", slippage_rate)
    shares, cash = _buy_all(float(initial_cash), execution_price, cost_rate, lot_size)
    curve: list[CurvePoint] = []
    after_open_actions = after_open_actions or {}

    for index, candle in enumerate(candles):
        dividend_cash = 0.0
        split_ratio = 1.0
        if index > 0:
            shares, cash, dividend_cash, split_ratio = _apply_action(candle.date, shares, cash, before_open_actions)
        shares, cash, after_dividend_cash, after_split_ratio = _apply_action(candle.date, shares, cash, after_open_actions)
        dividend_cash += after_dividend_cash
        split_ratio *= after_split_ratio

        curve.append(
            CurvePoint(
                date=candle.date,
                signal=1,
                position=1,
                shares=shares,
                cash=cash,
                equity=cash + shares * candle.raw_close,
                trade="BUY" if index == 0 and shares > 0 else "",
                trade_price=execution_price if index == 0 and shares > 0 else 0.0,
                dividend_cash=dividend_cash,
                split_ratio=split_ratio,
            )
        )

    return curve


def metrics(curve: list[CurvePoint], initial_cash: float) -> dict[str, float]:
    equities = [point.equity for point in curve]
    returns = [
        equities[index] / equities[index - 1] - 1
        for index in range(1, len(equities))
        if equities[index - 1] > 0
    ]
    total_return = equities[-1] / initial_cash - 1
    years = _years_between(curve[0].date, curve[-1].date)
    periods_per_year = (len(curve) - 1) / years if years > 0 else 252.0
    annual_volatility = _annual_volatility(returns, periods_per_year)

    return {
        "total_return": total_return,
        "cagr": _cagr(total_return, years),
        "max_drawdown": _max_drawdown(equities),
        "annual_volatility": annual_volatility,
        "sharpe": _sharpe(returns, periods_per_year),
    }


def write_summary_csv(summaries: list[Summary], path: Path | str) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=[field for field in Summary.__dataclass_fields__])
        writer.writeheader()
        for summary in summaries:
            writer.writerow(asdict(summary))
    return output


def write_comparison_curve(
    strategy_curve: list[CurvePoint],
    benchmark_curve: list[CurvePoint],
    path: Path | str,
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "date",
        "strategy_equity",
        "benchmark_equity",
        "strategy_position",
        "benchmark_position",
        "strategy_trade",
        "benchmark_trade",
        "strategy_trade_price",
        "benchmark_trade_price",
        "strategy_dividend_cash",
        "benchmark_dividend_cash",
        "strategy_split_ratio",
        "benchmark_split_ratio",
    ]

    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for strategy_point, benchmark_point in zip(strategy_curve, benchmark_curve):
            writer.writerow(
                {
                    "date": strategy_point.date,
                    "strategy_equity": strategy_point.equity,
                    "benchmark_equity": benchmark_point.equity,
                    "strategy_position": strategy_point.position,
                    "benchmark_position": benchmark_point.position,
                    "strategy_trade": strategy_point.trade,
                    "benchmark_trade": benchmark_point.trade,
                    "strategy_trade_price": strategy_point.trade_price,
                    "benchmark_trade_price": benchmark_point.trade_price,
                    "strategy_dividend_cash": strategy_point.dividend_cash,
                    "benchmark_dividend_cash": benchmark_point.dividend_cash,
                    "strategy_split_ratio": strategy_point.split_ratio,
                    "benchmark_split_ratio": benchmark_point.split_ratio,
                }
            )
    return output


def _buy_all(cash: float, price: float, cost_rate: float, lot_size: int = 0) -> tuple[float, float]:
    if cash <= 0 or price <= 0:
        return 0.0, cash
    shares = cash / (price * (1 + cost_rate))
    if lot_size > 0:
        shares = math.floor(shares / lot_size) * lot_size
    if shares <= 0:
        return 0.0, cash
    remaining_cash = cash - shares * price * (1 + cost_rate)
    return shares, remaining_cash


def _sell_all(shares: float, price: float, cost_rate: float) -> float:
    if shares <= 0 or price <= 0:
        return 0.0
    return shares * price * (1 - cost_rate)


def _action_buckets(candles: list[Candle], actions: list[CorporateAction]) -> tuple[dict[str, CorporateAction], dict[str, CorporateAction]]:
    before_open: dict[str, CorporateAction] = {}
    after_open: dict[str, CorporateAction] = {}
    candle_dates = [_point_date(candle.date) for candle in candles]

    for action in actions:
        action_day = date.fromisoformat(action.date)
        index = _action_candle_index(candle_dates, action_day)
        if index is None:
            continue
        bucket = before_open if action_day == candle_dates[index] else after_open
        _merge_action(bucket, candles[index].date, action)

    return before_open, after_open


def _action_candle_index(candle_dates: list[date], action_day: date) -> int | None:
    if not candle_dates:
        return None
    if action_day < candle_dates[0]:
        return None

    candidate = None
    for index, candle_day in enumerate(candle_dates):
        if candle_day == action_day:
            return index
        if candle_day > action_day:
            break
        candidate = index
    return candidate


def _merge_action(bucket: dict[str, CorporateAction], candle_date: str, action: CorporateAction) -> None:
    existing = bucket.get(candle_date)
    if existing is None:
        bucket[candle_date] = action
        return
    bucket[candle_date] = CorporateAction(
        date=candle_date,
        ticker=action.ticker,
        source_symbol=action.source_symbol,
        dividend=existing.dividend + action.dividend,
        split_ratio=existing.split_ratio * action.split_ratio,
    )


def _actions_by_date(actions: list[CorporateAction]) -> dict[str, CorporateAction]:
    by_date: dict[str, CorporateAction] = {}
    for action in actions:
        _merge_action(by_date, action.date, action)
    return by_date


def _apply_action(
    action_date: str,
    shares: float,
    cash: float,
    action_map: dict[str, CorporateAction],
) -> tuple[float, float, float, float]:
    action = action_map.get(action_date)
    if action is None or shares <= 0:
        return shares, cash, 0.0, 1.0

    dividend_cash = shares * action.dividend
    cash += dividend_cash
    # Yahoo OHLC is already split-adjusted; applying split ratios again double-counts old splits.
    return shares, cash, dividend_cash, action.split_ratio


def _slipped_price(price: float, side: str, slippage_rate: float) -> float:
    if side == "BUY":
        return price * (1 + slippage_rate)
    if side == "SELL":
        return price * (1 - slippage_rate)
    raise ValueError(f"Lado invalido para slippage: {side}")


def _years_between(start: str, end: str) -> float:
    seconds = (_point_datetime(end) - _point_datetime(start)).total_seconds()
    return max(seconds / (365.25 * 24 * 60 * 60), 1 / 365.25)


def _point_date(value: str) -> date:
    return _point_datetime(value).date()


def _point_datetime(value: str) -> datetime:
    if "T" in value or " " in value:
        return datetime.fromisoformat(value)
    return datetime.combine(date.fromisoformat(value), datetime.min.time())


def _cagr(total_return: float, years: float) -> float:
    if total_return <= -1:
        return -1.0
    return (1 + total_return) ** (1 / years) - 1


def _max_drawdown(equities: list[float]) -> float:
    peak = equities[0]
    max_drawdown = 0.0
    for equity in equities:
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = min(max_drawdown, equity / peak - 1)
    return max_drawdown


def _annual_volatility(returns: list[float], periods_per_year: float) -> float:
    if len(returns) < 2:
        return 0.0
    return statistics.stdev(returns) * math.sqrt(periods_per_year)


def _sharpe(returns: list[float], periods_per_year: float) -> float:
    if len(returns) < 2:
        return 0.0
    std = statistics.stdev(returns)
    if std == 0:
        return 0.0
    return statistics.mean(returns) / std * math.sqrt(periods_per_year)
