from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import asdict, replace
from itertools import product
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from b3_strategy_lab.backtest import Summary
from b3_strategy_lab.candles import DEFAULT_TICKERS, cache_path, load_candles
from b3_strategy_lab.cli import PARAM_FIELDS
from b3_strategy_lab.cotahist import load_verified_candles
from b3_strategy_lab.strategies import build_signals
from scripts.research_aggressive_strategies import (
    _run_price_only,
    _signal_candles,
    _strategy_grids,
    _window_context,
)


REPORTS_DIR = Path("reports")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pesquisa in-sample no historico completo.")
    parser.add_argument("--tickers", nargs="+", default=list(DEFAULT_TICKERS))
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--suffix", default="")
    parser.add_argument("--allow-unverified-data", action="store_true")
    args = parser.parse_args(argv)

    rows = []
    grids = _all_grids()
    for ticker in [item.upper() for item in args.tickers]:
        if args.allow_unverified_data:
            candles = load_candles(cache_path(ticker, args.interval))
        else:
            candles, _manifest = load_verified_candles(ticker, args.interval)
        signal_candles = _signal_candles(candles)
        context = _window_context(candles)

        for strategy, setups in grids.items():
            for label, params in setups:
                signals = build_signals(strategy, signal_candles, **params)
                summary = _run_price_only(ticker, strategy, candles, signals, context)
                row = _row(summary, label, params)
                rows.append(row)
        print(f"{ticker}: {sum(len(items) for items in grids.values())} setups no historico completo", flush=True)

    rows.sort(key=lambda row: float(row["total_return"]), reverse=True)
    output = (
        REPORTS_DIR
        / f"full_history_strategy_research_price_only_raw_{args.interval}{args.suffix}.csv"
    )
    _write(rows, output)
    _print_grouped(rows)
    return 0


def _all_grids() -> dict[str, list[tuple[str, dict]]]:
    grids = {strategy: [(strategy, params) for params in params_grid] for strategy, params_grid in _strategy_grids().items()}
    for strategy, setups in _legacy_grids().items():
        grids.setdefault(strategy, []).extend(setups)
    grids["supertrend_follow"] = [
        (f"supertrend_{atr_period}_{atr_mult:g}", {"atr_period": atr_period, "atr_mult": atr_mult})
        for atr_period, atr_mult in product([7, 10, 14, 20], [1.5, 2.0, 3.0, 4.0, 5.0])
    ]
    grids["keltner_breakout"] = [
        (
            f"keltner_w{window}_atr{atr_period}x{atr_mult:g}_exit{exit_z:g}_tw{trend_window}",
            {
                "window": window,
                "atr_period": atr_period,
                "atr_mult": atr_mult,
                "exit_z": exit_z,
                "trend_window": trend_window,
            },
        )
        for window, atr_period, atr_mult, exit_z, trend_window in product(
            [10, 20, 40, 80],
            [10, 14, 20],
            [1.0, 1.5, 2.0, 3.0],
            [0.0, 0.5, 1.0],
            [0, 50, 200],
        )
    ]
    grids["breakout"] = grids.get("breakout", []) + [
        (f"breakout_{lookback}_{exit_lookback}", {"lookback": lookback, "exit_lookback": exit_lookback})
        for lookback, exit_lookback in product([5, 10, 20, 55, 100, 200], [10, 20, 55, 100])
    ]
    grids["atr_breakout"] = [
        (
            f"atr_breakout_{lookback}_{atr_period}x{atr_mult:g}",
            {"lookback": lookback, "atr_period": atr_period, "atr_mult": atr_mult},
        )
        for lookback, atr_period, atr_mult in product([5, 10, 20, 55, 100], [10, 14, 20], [1.5, 2.0, 3.0, 4.0])
    ]
    grids["sma_cross"] = [
        (f"sma_cross_{fast}_{slow}", {"fast": fast, "slow": slow})
        for fast, slow in product([10, 20, 39, 50], [52, 100, 150, 200])
        if fast < slow
    ]
    grids["ema_cross"] = [
        (f"ema_cross_{fast}_{slow}", {"fast": fast, "slow": slow})
        for fast, slow in product([10, 20, 39, 50], [52, 100, 150, 200])
        if fast < slow
    ]
    return grids


def _legacy_grids() -> dict[str, list[tuple[str, dict]]]:
    return {
        "rsi_reversion_atr": [
            ("legacy_rsi_atr_21_45_75", {"rsi_period": 21, "lower": 45.0, "upper": 75.0, "atr_period": 14, "atr_mult": 2.0}),
            ("legacy_rsi_atr_14_45_80", {"rsi_period": 14, "lower": 45.0, "upper": 80.0, "atr_period": 14, "atr_mult": 3.0}),
        ],
        "rsi_reversion": [
            ("legacy_rsi_21_45_70", {"rsi_period": 21, "lower": 45.0, "upper": 70.0}),
            ("legacy_rsi_14_50_80", {"rsi_period": 14, "lower": 50.0, "upper": 80.0}),
            ("legacy_rsi_14_40_80", {"rsi_period": 14, "lower": 40.0, "upper": 80.0}),
            ("legacy_rsi_7_50_90", {"rsi_period": 7, "lower": 50.0, "upper": 90.0}),
        ],
        "rsi_reversion_hold": [
            ("legacy_rsi_hold_14_50_85_40", {"rsi_period": 14, "lower": 50.0, "upper": 85.0, "max_hold": 40}),
            ("legacy_rsi_hold_7_50_85_40", {"rsi_period": 7, "lower": 50.0, "upper": 85.0, "max_hold": 40}),
        ],
        "breakout": [("legacy_breakout_5_55", {"lookback": 5, "exit_lookback": 55})],
        "chandelier_breakout": [
            ("legacy_chandelier_10_14x3", {"lookback": 10, "atr_period": 14, "atr_mult": 3.0, "volume_window": 0, "volume_mult": 0.0}),
            ("legacy_chandelier_5_10x3", {"lookback": 5, "atr_period": 10, "atr_mult": 3.0, "volume_window": 0, "volume_mult": 0.0}),
        ],
    }


def _row(summary: Summary, label: str, params: dict) -> dict:
    row = asdict(summary)
    row["label"] = label
    row["params"] = ";".join(f"{key}={value:g}" if isinstance(value, float) else f"{key}={value}" for key, value in params.items())
    for field in PARAM_FIELDS:
        row[field] = params.get(field, "")
    return row


def _write(rows: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "ticker",
        "strategy",
        "label",
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
        *PARAM_FIELDS,
    ]
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fields} for row in rows])
    print(f"Salvo: {output} ({len(rows)} linhas)")


def _print_grouped(rows: list[dict]) -> None:
    for ticker in sorted({row["ticker"] for row in rows}):
        print(f"\n{ticker}")
        ticker_rows = [row for row in rows if row["ticker"] == ticker]
        for row in sorted(ticker_rows, key=lambda item: float(item["total_return"]), reverse=True)[:10]:
            print(
                f"  {row['label'][:34]:34} ret={row['total_return'] * 100:10.2f}% "
                f"CAGR={row['cagr'] * 100:7.2f}% MDD={row['max_drawdown'] * 100:7.2f}% trades={row['trades']:3}"
            )


if __name__ == "__main__":
    raise SystemExit(main())
