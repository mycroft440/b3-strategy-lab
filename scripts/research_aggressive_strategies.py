from __future__ import annotations

import csv
import argparse
import sys
from dataclasses import asdict, replace
from itertools import product
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from b3_strategy_lab.backtest import (
    Summary,
    _action_buckets,
    metrics,
    simulate_buy_and_hold_raw_events,
    simulate_single_asset_raw_events,
)
from b3_strategy_lab.candles import DEFAULT_TICKERS, actions_path, cache_path, load_actions, load_candles
from b3_strategy_lab.cli import PARAM_FIELDS
from b3_strategy_lab.strategies import build_signals


TICKERS = list(DEFAULT_TICKERS)
INTERVAL = "1d"
INITIAL_CASH = 10_000.0
COST_BPS = 20.0
SLIPPAGE_BPS = 5.0
LOT_SIZE = 1
TRAIN_RATIO = 0.7
REPORTS_DIR = Path("reports")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pesquisa estrategias agressivas em backtest single-asset.")
    parser.add_argument("--tickers", nargs="+", default=TICKERS)
    parser.add_argument("--suffix", default="")
    args = parser.parse_args(argv)

    screen_rows = []
    train_test_rows = []

    for ticker in [item.upper() for item in args.tickers]:
        candles = load_candles(cache_path(ticker, INTERVAL))
        actions = load_actions(actions_path(ticker))
        split = max(2, min(len(candles) - 2, int(len(candles) * TRAIN_RATIO)))
        train_candles = candles[:split]
        test_candles = candles[split:]
        full_signal_candles = _signal_candles(candles)
        train_signal_candles = full_signal_candles[:split]
        train_context = _window_context(train_candles, actions)
        test_context = _window_context(test_candles, actions)

        for strategy, params_grid in _strategy_grids().items():
            best_train: tuple[Summary, dict] | None = None
            for params in params_grid:
                full_signals = build_signals(strategy, full_signal_candles, **params)
                test_summary = _run_raw_events(ticker, strategy, test_candles, full_signals[split:], test_context)
                screen_rows.append(_result_row(test_summary, params, family=strategy, train_ratio=TRAIN_RATIO))

                train_signals = build_signals(strategy, train_signal_candles, **params)
                train_summary = _run_raw_events(ticker, strategy, train_candles, train_signals, train_context)
                if best_train is None or train_summary.cagr > best_train[0].cagr:
                    best_train = (train_summary, params)

            if best_train is not None:
                train_summary, best_params = best_train
                full_signals = build_signals(strategy, full_signal_candles, **best_params)
                test_summary = _run_raw_events(ticker, strategy, test_candles, full_signals[split:], test_context)
                row = _result_row(test_summary, best_params, family=strategy, train_ratio=TRAIN_RATIO)
                row["train_cagr"] = train_summary.cagr
                row["train_total_return"] = train_summary.total_return
                row["train_trades"] = train_summary.trades
                row["train_max_drawdown"] = train_summary.max_drawdown
                train_test_rows.append(row)
        print(f"{ticker}: pesquisa concluida", flush=True)

    screen_rows.sort(key=lambda row: float(row["cagr"]), reverse=True)
    train_test_rows.sort(key=lambda row: float(row["cagr"]), reverse=True)
    suffix = args.suffix
    _write_rows(screen_rows, REPORTS_DIR / f"aggressive_strategy_screen_70_30_raw_events_raw_1d{suffix}.csv")
    _write_rows(train_test_rows, REPORTS_DIR / f"aggressive_strategy_train_selected_raw_events_raw_1d{suffix}.csv")
    _print_top("TOP screening 70/30 por CAGR da estrategia", screen_rows, limit=30)
    _print_top("TOP train-selected 70/30 por CAGR da estrategia", train_test_rows, limit=30)
    return 0


def _strategy_grids() -> dict[str, list[dict]]:
    return {
        "ibs_reversion": [
            {"ibs_lower": ibs_lower, "ibs_upper": ibs_upper, "max_hold": max_hold, "trend_window": trend_window}
            for ibs_lower, ibs_upper, max_hold, trend_window in product(
                [0.1, 0.2, 0.3],
                [0.7, 0.9],
                [1, 3, 5],
                [0, 200],
            )
            if ibs_lower < ibs_upper
        ],
        "rsi2_trend_reversion": [
            {
                "rsi_period": rsi_period,
                "lower": lower,
                "upper": upper,
                "trend_window": trend_window,
                "sma_window": sma_window,
                "max_hold": max_hold,
            }
            for rsi_period, lower, upper, trend_window, sma_window, max_hold in product(
                [2, 3],
                [5.0, 10.0, 20.0],
                [50.0, 70.0],
                [0, 200],
                [3, 5],
                [3, 5, 10],
            )
            if lower < upper
        ],
        "rsi_ibs_reversion": [
            {
                "rsi_period": rsi_period,
                "lower": lower,
                "upper": upper,
                "ibs_lower": ibs_lower,
                "ibs_upper": ibs_upper,
                "trend_window": trend_window,
                "max_hold": max_hold,
            }
            for rsi_period, lower, upper, ibs_lower, ibs_upper, trend_window, max_hold in product(
                [2, 3],
                [5.0, 10.0, 20.0],
                [50.0, 70.0],
                [0.1, 0.2],
                [0.8],
                [0, 200],
                [3, 5, 10],
            )
            if lower < upper and ibs_lower < ibs_upper
        ],
        "down_streak_reversion": [
            {
                "streak_length": streak_length,
                "ibs_lower": ibs_lower,
                "ibs_upper": ibs_upper,
                "trend_window": trend_window,
                "max_hold": max_hold,
            }
            for streak_length, ibs_lower, ibs_upper, trend_window, max_hold in product(
                [2, 3, 4],
                [0.2, 0.3],
                [0.8],
                [0, 200],
                [3, 5],
            )
            if ibs_lower < ibs_upper
        ],
        "range_expansion_breakout": [
            {
                "range_mult": range_mult,
                "atr_period": atr_period,
                "atr_mult": atr_mult,
                "trend_window": trend_window,
                "volume_window": volume_window,
                "volume_mult": volume_mult,
                "max_hold": max_hold,
            }
            for range_mult, atr_period, atr_mult, trend_window, volume_window, volume_mult, max_hold in product(
                [0.25, 0.5, 1.0],
                [10, 14],
                [1.5, 2.0, 3.0],
                [0, 50, 200],
                [0, 20],
                [0.0, 1.0],
                [5, 10, 20],
            )
        ],
        "chandelier_breakout": [
            {
                "lookback": lookback,
                "atr_period": atr_period,
                "atr_mult": atr_mult,
                "volume_window": volume_window,
                "volume_mult": volume_mult,
            }
            for lookback, atr_period, atr_mult, volume_window, volume_mult in product(
                [5, 10, 20, 55],
                [10, 14],
                [1.5, 2.0, 3.0],
                [0, 20],
                [0.0, 1.0],
            )
        ],
    }


def _signal_candles(candles):
    return [
        replace(
            candle,
            open=candle.raw_open,
            high=candle.raw_high,
            low=candle.raw_low,
            close=candle.raw_close,
            adj_close=candle.raw_close,
            adjustment_factor=1.0,
        )
        for candle in candles
    ]


def _window_context(candles, actions):
    before_open_actions, after_open_actions = _action_buckets(candles, actions)
    benchmark_curve = simulate_buy_and_hold_raw_events(
        candles,
        before_open_actions,
        after_open_actions,
        initial_cash=INITIAL_CASH,
        cost_bps=COST_BPS,
        slippage_bps=SLIPPAGE_BPS,
        lot_size=LOT_SIZE,
    )
    benchmark_metrics = metrics(benchmark_curve, INITIAL_CASH)
    return before_open_actions, after_open_actions, benchmark_curve, benchmark_metrics


def _run_raw_events(ticker: str, strategy: str, candles, signals, context) -> Summary:
    before_open_actions, after_open_actions, benchmark_curve, benchmark_metrics = context
    strategy_curve = simulate_single_asset_raw_events(
        candles,
        signals,
        before_open_actions,
        after_open_actions,
        initial_cash=INITIAL_CASH,
        cost_bps=COST_BPS,
        slippage_bps=SLIPPAGE_BPS,
        lot_size=LOT_SIZE,
    )
    strategy_metrics = metrics(strategy_curve, INITIAL_CASH)
    return Summary(
        ticker=ticker,
        strategy=strategy,
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


def _result_row(summary: Summary, params: dict, *, family: str, train_ratio: float) -> dict:
    row = asdict(summary)
    row["family"] = family
    row["params"] = _params_text(params)
    row["train_ratio"] = train_ratio
    for field in PARAM_FIELDS:
        row[field] = params.get(field, "")
    return row


def _params_text(params: dict) -> str:
    return ";".join(f"{key}={_format_value(value)}" for key, value in params.items())


def _format_value(value) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _write_rows(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "ticker",
        "strategy",
        "family",
        "params",
        "start",
        "end",
        "candles",
        "trades",
        "exposure",
        "total_return",
        "cagr",
        "max_drawdown",
        "sharpe",
        "benchmark_total_return",
        "benchmark_cagr",
        "benchmark_max_drawdown",
        "excess_total_return",
        "train_cagr",
        "train_total_return",
        "train_trades",
        "train_max_drawdown",
        "train_ratio",
        *PARAM_FIELDS,
    ]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fields} for row in rows])
    print(f"Salvo: {path} ({len(rows)} linhas)")


def _print_top(title: str, rows: list[dict], *, limit: int) -> None:
    print(f"\n{title}:")
    for row in rows[:limit]:
        print(
            f"{row['ticker']:5} {row['strategy']:26} CAGR={row['cagr'] * 100:8.2f}% "
            f"ret={row['total_return'] * 100:9.2f}% MDD={row['max_drawdown'] * 100:7.2f}% "
            f"trades={row['trades']:3} exp={row['exposure'] * 100:5.1f}% {row['params'][:72]}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
