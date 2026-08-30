from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.strategies import portfolio_strategies, strategy_parameters  # noqa: E402
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

UNIVERSE = Path("data/universes/fixed_40_2018.json")
OUTPUT = Path("reports/strict_holdout_strategy_management.csv")
LEDGER = Path("reports/strict_holdout_winner_ledger.csv")


@dataclass(frozen=True)
class Summary:
    strategy: str
    start: str
    end: str
    sessions: int
    trades: int
    rebalance_attempts: int
    rebalance_skips: int
    initial_equity: float
    final_equity: float
    total_return: float
    cagr: float
    max_drawdown: float
    annual_volatility: float
    sharpe: float
    average_annual_return: float
    turnover: float
    fees: float
    slippage_cost: float


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value) if "T" in value or " " in value else datetime.combine(date.fromisoformat(value), datetime.min.time())


def common_dates(data: MarketData, start: str | None = None, end: str | None = None) -> list[str]:
    if not data.tickers:
        return []
    values = set(data.by_date[data.tickers[0]])
    for ticker in data.tickers[1:]:
        values.intersection_update(data.by_date[ticker])
    result = sorted(values, key=_dt)
    if start:
        result = [item for item in result if item >= start]
    if end:
        result = [item for item in result if item <= end]
    return result


def _rebalance_close(current: str, following: str, frequency: str) -> bool:
    a, b = _dt(current).date(), _dt(following).date()
    if frequency == "daily":
        return True
    if frequency == "weekly":
        return a.isocalendar()[:2] != b.isocalendar()[:2]
    if frequency == "monthly":
        return (a.year, a.month) != (b.year, b.month)
    raise ValueError(f"Frequencia desconhecida: {frequency}")


def _floor_lot(value: float, lot: int) -> float:
    return value if lot <= 0 else math.floor((value + 1e-12) / lot) * lot


def rebalance_atomic(
    current_date: str,
    tickers: list[str],
    candles: dict[str, object],
    shares: dict[str, float],
    cash: float,
    targets: dict[str, float],
    cost_rate: float,
    slippage_rate: float,
    lot_size: int,
) -> tuple[float, int, float, float, float, bool, str, list[dict[str, object]]]:
    required = {ticker for ticker in tickers if shares[ticker] > 0 or targets.get(ticker, 0) > 0}
    missing = [ticker for ticker in sorted(required) if ticker not in candles]
    invalid = [
        ticker for ticker in sorted(required)
        if ticker in candles and (not math.isfinite(float(getattr(candles[ticker], "open", 0) or 0)) or float(getattr(candles[ticker], "open", 0) or 0) <= 0)
    ]
    if missing or invalid:
        reason = ("missing_open:" + ",".join(missing)) if missing else ("invalid_open:" + ",".join(invalid))
        return cash, 0, 0.0, 0.0, 0.0, False, reason, []

    opens = {ticker: float(getattr(candles[ticker], "open")) for ticker in required}
    equity_open = cash + sum(shares[ticker] * opens[ticker] for ticker in required if shares[ticker] > 0)
    if not math.isfinite(equity_open) or equity_open <= 0:
        return cash, 0, 0.0, 0.0, 0.0, False, "invalid_equity_open", []

    original_cash, original_shares = cash, dict(shares)
    fees = slippage = notional = 0.0
    ledger: list[dict[str, object]] = []
    try:
        for ticker in tickers:
            held = shares[ticker]
            if held <= 0:
                continue
            raw = opens[ticker]
            target_value = equity_open * max(0.0, targets.get(ticker, 0.0))
            excess = held * raw - target_value
            if excess <= 1e-12:
                continue
            qty = held if target_value <= 0 else min(held, _floor_lot(excess / raw, lot_size))
            if qty <= 0:
                continue
            fill = raw * (1 - slippage_rate)
            gross, fee = qty * fill, qty * fill * cost_rate
            slip = qty * (raw - fill)
            cash += gross - fee
            shares[ticker] -= qty
            fees += fee
            slippage += slip
            notional += gross
            ledger.append({"date": current_date, "side": "SELL", "ticker": ticker, "shares": qty, "raw_open": raw, "execution_price": fill, "fee": fee, "slippage_cost": slip})

        for ticker, weight in sorted(targets.items()):
            if weight <= 0:
                continue
            raw = opens[ticker]
            desired = max(0.0, equity_open * weight - shares[ticker] * raw)
            if desired <= 1e-12:
                continue
            fill = raw * (1 + slippage_rate)
            affordable = cash / (fill * (1 + cost_rate)) if fill > 0 else 0.0
            qty = _floor_lot(min(desired / raw, affordable), lot_size)
            if qty <= 0:
                continue
            gross, fee = qty * fill, qty * fill * cost_rate
            slip = qty * (fill - raw)
            if gross + fee > cash + 1e-8:
                raise ArithmeticError("buy_debit_exceeds_cash")
            cash -= gross + fee
            shares[ticker] += qty
            fees += fee
            slippage += slip
            notional += gross
            ledger.append({"date": current_date, "side": "BUY", "ticker": ticker, "shares": qty, "raw_open": raw, "execution_price": fill, "fee": fee, "slippage_cost": slip})

        if cash < -1e-7 or not math.isfinite(cash) or any(value < -1e-9 or not math.isfinite(value) for value in shares.values()):
            raise ArithmeticError("invalid_portfolio_state")
    except Exception as exc:
        shares.clear()
        shares.update(original_shares)
        return original_cash, 0, 0.0, 0.0, 0.0, False, f"rollback:{exc}", []

    return cash, len(ledger), notional / equity_open, fees, slippage, True, "", ledger


def run_strict(
    data: MarketData,
    config: PortfolioConfig,
    *,
    start: str,
    end: str,
    initial_cash: float,
    cost_bps: float,
    slippage_bps: float,
    lot_size: int,
    eligibility: dict[str, list[int]],
    collect_trades: bool = False,
) -> tuple[Summary, list[dict[str, object]]]:
    _validate_economic_assumptions(
        initial_cash=initial_cash,
        cost_bps=cost_bps,
        slippage_bps=slippage_bps,
        lot_size=lot_size,
    )
    dates = common_dates(data, start, end)
    if len(dates) < 2:
        raise ValueError("Periodo comum insuficiente")
    shares = {ticker: 0.0 for ticker in data.tickers}
    cash = float(initial_cash)
    pending: dict[str, float] | None = None
    designated_targets: dict[str, float] = {}
    active_targets: dict[str, float] = {}
    equities: list[float] = []
    ledger: list[dict[str, object]] = []
    trades = attempts = skips = 0
    turnover = fees = slippage = 0.0
    cost_rate, slip_rate = cost_bps / 10_000, slippage_bps / 10_000

    all_dates = common_dates(data)
    prior_dates = [value for value in all_dates if value < dates[0]]
    prior = prior_dates[-1] if prior_dates else None
    if prior is not None and _rebalance_close(prior, dates[0], config.rebalance):
        designated_targets = _target_weights(
            data,
            prior,
            config,
            eligible_tickers=_eligible_tickers(data, prior, eligibility),
        )
        pending = dict(designated_targets)

    for index, current in enumerate(dates):
        candles = {ticker: data.by_date[ticker][current] for ticker in data.tickers}
        if pending is not None:
            attempts += 1
            cash, count, turn, fee, slip, ok, reason, rows = rebalance_atomic(
                current, data.tickers, candles, shares, cash, pending, cost_rate, slip_rate, lot_size
            )
            if ok:
                active_targets = dict(pending)
                trades += count
                turnover += turn
                fees += fee
                slippage += slip
                if collect_trades:
                    ledger.extend(rows)
            else:
                skips += 1
                if reason:
                    print(f"SKIP {current}: {reason}", file=sys.stderr)

        equity = cash
        for ticker in data.tickers:
            if shares[ticker] <= 0:
                continue
            close = float(getattr(candles[ticker], "close", 0) or 0)
            if not math.isfinite(close) or close <= 0:
                raise ValueError(f"{current}/{ticker}: fechamento ausente ou invalido em posicao aberta")
            equity += shares[ticker] * close
        if not math.isfinite(equity) or equity <= 0:
            raise ValueError(f"{current}: patrimonio invalido")
        equities.append(equity)

        next_date = dates[index + 1] if index + 1 < len(dates) else None
        pending = None
        if next_date is not None and _rebalance_close(
            current, next_date, config.rebalance
        ):
            designated_targets = _target_weights(
                data,
                current,
                config,
                eligible_tickers=_eligible_tickers(data, current, eligibility),
            )
            pending = dict(designated_targets)
        elif next_date is not None:
            eligible_now = _eligible_tickers(data, current, eligibility) or set()
            signal_targets = {
                ticker: weight
                for ticker, weight in designated_targets.items()
                if ticker in eligible_now
            }
            if signal_targets != active_targets:
                pending = signal_targets

    metrics = _portfolio_metrics(equities, dates, initial_cash)
    yearly = _yearly_returns(equities, dates, initial_cash)
    return Summary(
        config.name, dates[0], dates[-1], len(dates), trades, attempts, skips, initial_cash, equities[-1],
        metrics["total_return"], metrics["cagr"], metrics["max_drawdown"], metrics["annual_volatility"],
        metrics["sharpe"], statistics.mean(yearly.values()) if yearly else 0.0, turnover, fees, slippage
    ), ledger


def _metric(summary: Summary, objective: str) -> float:
    return {"cagr": summary.cagr, "total_return": summary.total_return, "sharpe": summary.sharpe}[objective]


def _validate_economic_assumptions(
    *,
    initial_cash: float,
    cost_bps: float,
    slippage_bps: float,
    lot_size: int,
) -> None:
    if not math.isfinite(initial_cash) or initial_cash <= 0:
        raise ValueError("initial_cash precisa ser finito e positivo")
    if not math.isfinite(cost_bps) or cost_bps < 0:
        raise ValueError("cost_bps precisa ser finito e nao negativo")
    if not math.isfinite(slippage_bps) or slippage_bps < 0:
        raise ValueError("slippage_bps precisa ser finito e nao negativo")
    if slippage_bps >= 10_000:
        raise ValueError("slippage_bps precisa ser menor que 10000")
    if not isinstance(lot_size, int) or isinstance(lot_size, bool) or lot_size < 0:
        raise ValueError("lot_size precisa ser inteiro e nao negativo")


def _summary(prefix: str, value: Summary) -> dict[str, object]:
    return {f"{prefix}_{field}": getattr(value, field) for field in Summary.__dataclass_fields__ if field != "strategy"}


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backtest estrito: escolhe no treino e mede somente depois no holdout.")
    parser.add_argument("--universe-manifest", type=Path, default=UNIVERSE)
    parser.add_argument("--strategies", nargs="+", default=portfolio_strategies())
    parser.add_argument("--config-set", choices=["all", "base", "roc", "roc_hybrid", "roc_filter_short"], default="all")
    parser.add_argument("--signal-mode", choices=["adjusted", "raw"], default="adjusted")
    parser.add_argument("--start", default="2018-01-02")
    parser.add_argument("--train-end", default="2022-12-29")
    parser.add_argument("--test-start", default="2023-01-02")
    parser.add_argument("--end")
    parser.add_argument("--initial-cash", type=float, default=1_000.0)
    parser.add_argument("--cost-bps", type=float, default=3.2)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--lot-size", type=int, default=1)
    parser.add_argument("--objective", choices=["cagr", "total_return", "sharpe"], default="cagr")
    parser.add_argument("--top-train", type=int, default=20)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--ledger-output", type=Path, default=LEDGER)
    parser.add_argument("--allow-unverified-data", action="store_true")
    args = parser.parse_args(argv)

    if args.start > args.train_end or args.train_end >= args.test_start:
        parser.error("Exija start <= train-end < test-start")
    try:
        _validate_economic_assumptions(
            initial_cash=args.initial_cash,
            cost_bps=args.cost_bps,
            slippage_bps=args.slippage_bps,
            lot_size=args.lot_size,
        )
    except ValueError as exc:
        parser.error(str(exc))

    universe = json.loads(args.universe_manifest.read_text(encoding="utf-8"))
    tickers = [str(item).upper() for item in universe["tickers"]]
    rules = universe.get("selection_rules", {})
    liquidity_year = rules.get("liquidity_year") if isinstance(rules, dict) else None
    known_from = f"{liquidity_year + 1:04d}-01-01" if isinstance(liquidity_year, int) else str(universe.get("selected_as_of", ""))
    if known_from and args.test_start < known_from:
        parser.error(f"O universo so poderia ser conhecido a partir de {known_from}; test-start={args.test_start} e invalido")

    data = MarketData(
        tickers, "1d", args.signal_mode,
        allow_unverified_data=args.allow_unverified_data,
        require_verified_splits_from=str(universe["warmup_start"]),
        history_start=str(universe["warmup_start"]),
    )
    dates = common_dates(data, args.start, args.end)
    if not dates:
        raise ValueError("Sem sessoes comuns")
    end = args.end or dates[-1]
    strategies = [item.strip().lower() for item in args.strategies]
    configs = _configs(args.signal_mode, args.config_set)
    eligibility = _build_eligibility(data, strategies, args.signal_mode, signal_start=str(universe["warmup_start"]))

    training: list[tuple[float, str, PortfolioConfig, Summary]] = []
    for strategy in strategies:
        for config in configs:
            summary, _ = run_strict(
                data, config, start=args.start, end=args.train_end, initial_cash=args.initial_cash,
                cost_bps=args.cost_bps, slippage_bps=args.slippage_bps, lot_size=args.lot_size,
                eligibility=eligibility[strategy],
            )
            training.append((_metric(summary, args.objective), strategy, config, summary))
        print(f"Treino concluido: {strategy}", flush=True)
    training.sort(key=lambda item: item[0], reverse=True)

    results: list[dict[str, object]] = []
    winner_ledger: list[dict[str, object]] = []
    survivorship_safe = bool(universe.get("survivorship_safe", False))
    for rank, (_, strategy, config, train) in enumerate(training[: args.top_train], start=1):
        test, ledger = run_strict(
            data, config, start=args.test_start, end=end, initial_cash=args.initial_cash,
            cost_bps=args.cost_bps, slippage_bps=args.slippage_bps, lot_size=args.lot_size,
            eligibility=eligibility[strategy], collect_trades=rank == 1,
        )
        row = {
            "train_rank": rank,
            "trading_strategy": strategy,
            "strategy_params": ";".join(f"{k}={v}" for k, v in sorted(strategy_parameters(strategy).items())),
            "management_strategy": config.name,
            "objective": args.objective,
            "cost_bps": args.cost_bps,
            "slippage_bps": args.slippage_bps,
            "lot_size": args.lot_size,
            "universe_id": universe.get("id", ""),
            "universe_survivorship_safe": survivorship_safe,
            "validity": "OUT_OF_SAMPLE_SELECTION__BIASED_UNIVERSE" if not survivorship_safe else "OUT_OF_SAMPLE",
            "bias_disclosure": universe.get("bias_disclosure", ""),
            **_summary("train", train), **_summary("test", test),
        }
        results.append(row)
        if rank == 1:
            winner_ledger = ledger

    _write_csv(args.output, results)
    _write_csv(args.ledger_output, winner_ledger)
    winner = results[0]
    print("\nVENCEDOR ESCOLHIDO SOMENTE NO TREINO")
    print(f"{winner['trading_strategy']} + {winner['management_strategy']}")
    print(f"Treino CAGR: {float(winner['train_cagr']):.2%}")
    print(f"Teste CAGR: {float(winner['test_cagr']):.2%}")
    print(f"Teste retorno: {float(winner['test_total_return']):.2%}")
    print(f"Teste MDD: {float(winner['test_max_drawdown']):.2%}")
    if not survivorship_safe:
        print("AVISO: permanece vies de sobrevivencia do universo, explicitamente rotulado no resultado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
