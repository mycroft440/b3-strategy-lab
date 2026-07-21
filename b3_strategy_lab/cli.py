from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, replace
from pathlib import Path

from .backtest import Summary, run_strategy_vs_buy_hold, write_comparison_curve, write_summary_csv
from .candles import (
    DEFAULT_ACTIONS_DIR,
    DEFAULT_DATA_DIR,
    DEFAULT_TICKERS,
    actions_path,
    cache_path,
    fetch_and_cache,
    load_actions,
    load_candles,
    validate_candles,
)
from .strategies import available_strategies, build_signals

PARAM_FIELDS = [
    "fast",
    "slow",
    "signal_window",
    "lookback",
    "exit_lookback",
    "rsi_period",
    "lower",
    "upper",
    "trend_window",
    "sma_window",
    "stop_pct",
    "window",
    "num_std",
    "exit_z",
    "atr_period",
    "atr_mult",
    "max_hold",
    "streak_rsi_period",
    "rank_period",
    "ibs_lower",
    "ibs_upper",
    "range_mult",
    "volume_window",
    "volume_mult",
    "streak_length",
]

SWEEP_STRATEGIES = [
    "atr_breakout",
    "bollinger_reversion",
    "breakout",
    "chandelier_breakout",
    "connors_rsi_reversion",
    "down_streak_reversion",
    "ema_cross",
    "ibs_reversion",
    "keltner_breakout",
    "macd",
    "momentum",
    "price_sma",
    "range_expansion_breakout",
    "roc_trend",
    "rsi_bollinger",
    "rsi_cross_reversion",
    "rsi_ibs_reversion",
    "rsi2_trend_reversion",
    "rsi_reversion",
    "rsi_reversion_atr",
    "rsi_reversion_hold",
    "rsi_reversion_trend_entry",
    "sma_cross",
    "sma_stop",
    "supertrend_follow",
    "trend_pullback",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B3 single-asset candle downloader and strategy lab.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch", help="Baixa candles e grava CSV ajustado.")
    _add_common_data_args(fetch_parser)
    fetch_parser.add_argument("--range", dest="range_name", default="max", help="Range Yahoo, exemplo: max, 10y, 5y.")

    list_parser = subparsers.add_parser("list-strategies", help="Lista estrategias disponiveis.")
    list_parser.set_defaults(command="list-strategies")

    backtest_parser = subparsers.add_parser("backtest", help="Roda uma estrategia contra buy and hold por ativo.")
    _add_common_data_args(backtest_parser)
    backtest_parser.add_argument("--strategy", default="sma_cross", choices=available_strategies())
    backtest_parser.add_argument("--initial-cash", type=float, default=10_000.0)
    backtest_parser.add_argument("--cost-bps", type=float, default=0.0, help="Custo por ordem em basis points. 10 bps = 0,10 por cento.")
    backtest_parser.add_argument("--slippage-bps", type=float, default=0.0, help="Slippage adverso por ordem em basis points.")
    backtest_parser.add_argument("--lot-size", type=int, default=0, help="0 usa fracao; 1 ou 100 força lote inteiro.")
    backtest_parser.add_argument("--price-mode", choices=["adjusted", "raw_events"], default="adjusted")
    backtest_parser.add_argument("--signal-mode", choices=["adjusted", "raw"], default="adjusted")
    backtest_parser.add_argument("--reports-dir", default="reports")
    backtest_parser.add_argument("--refresh-data", action="store_true", help="Baixa dados novamente antes do backtest.")
    backtest_parser.add_argument("--fast", type=int, default=50, help="Media curta para sma_cross.")
    backtest_parser.add_argument("--slow", type=int, default=200, help="Media longa para sma_cross.")
    backtest_parser.add_argument("--lookback", type=int, default=126, help="Janela para momentum ou entrada do breakout.")
    backtest_parser.add_argument("--exit-lookback", type=int, default=20, help="Janela de saida do breakout.")
    backtest_parser.add_argument("--signal-window", type=int, default=9, help="Media de sinal para MACD.")
    backtest_parser.add_argument("--rsi-period", type=int, default=14, help="Periodo do RSI.")
    backtest_parser.add_argument("--lower", type=float, default=30.0, help="Limite inferior do RSI.")
    backtest_parser.add_argument("--upper", type=float, default=70.0, help="Limite superior do RSI.")
    backtest_parser.add_argument("--trend-window", type=int, default=200, help="Media de tendencia para trend_pullback.")
    backtest_parser.add_argument("--sma-window", type=int, default=200, help="Media para sma_stop.")
    backtest_parser.add_argument("--stop-pct", type=float, default=0.2, help="Stop percentual para sma_stop.")
    backtest_parser.add_argument("--window", type=int, default=20, help="Janela para Bollinger.")
    backtest_parser.add_argument("--num-std", type=float, default=2.0, help="Desvios-padrao da banda de Bollinger.")
    backtest_parser.add_argument("--exit-z", type=float, default=0.0, help="Nivel de saida em desvios-padrao para Bollinger.")
    backtest_parser.add_argument("--atr-period", type=int, default=14, help="Periodo do ATR.")
    backtest_parser.add_argument("--atr-mult", type=float, default=3.0, help="Multiplicador do ATR.")
    backtest_parser.add_argument("--max-hold", type=int, default=20, help="Maximo de candles segurando a posicao.")
    backtest_parser.add_argument("--streak-rsi-period", type=int, default=2, help="Periodo do RSI do streak para Connors RSI.")
    backtest_parser.add_argument("--rank-period", type=int, default=100, help="Periodo do percent rank para Connors RSI.")
    backtest_parser.add_argument("--ibs-lower", type=float, default=0.2, help="Limite inferior de Internal Bar Strength.")
    backtest_parser.add_argument("--ibs-upper", type=float, default=0.8, help="Limite superior de Internal Bar Strength.")
    backtest_parser.add_argument("--range-mult", type=float, default=0.5, help="Multiplicador do range anterior.")
    backtest_parser.add_argument("--volume-window", type=int, default=20, help="Janela da media de volume.")
    backtest_parser.add_argument("--volume-mult", type=float, default=1.0, help="Multiplicador da media de volume.")
    backtest_parser.add_argument("--streak-length", type=int, default=3, help="Sequencia minima de fechamentos negativos.")

    sweep_parser = subparsers.add_parser("sweep", help="Varre parametros por ativo contra buy and hold.")
    _add_common_data_args(sweep_parser)
    sweep_parser.add_argument(
        "--strategy",
        default="sma_cross",
        choices=SWEEP_STRATEGIES,
    )
    sweep_parser.add_argument("--initial-cash", type=float, default=10_000.0)
    sweep_parser.add_argument("--cost-bps", type=float, default=0.0, help="Custo por ordem em basis points.")
    sweep_parser.add_argument("--slippage-bps", type=float, default=0.0, help="Slippage adverso por ordem em basis points.")
    sweep_parser.add_argument("--lot-size", type=int, default=0, help="0 usa fracao; 1 ou 100 força lote inteiro.")
    sweep_parser.add_argument("--price-mode", choices=["adjusted", "raw_events"], default="adjusted")
    sweep_parser.add_argument("--signal-mode", choices=["adjusted", "raw"], default="adjusted")
    sweep_parser.add_argument("--reports-dir", default="reports")
    sweep_parser.add_argument("--refresh-data", action="store_true", help="Baixa dados novamente antes da varredura.")
    sweep_parser.add_argument("--fast-values", nargs="+", type=int, default=[10, 20, 50])
    sweep_parser.add_argument("--slow-values", nargs="+", type=int, default=[100, 150, 200])
    sweep_parser.add_argument("--signal-window-values", nargs="+", type=int, default=[5, 9, 12])
    sweep_parser.add_argument("--lookback-values", nargs="+", type=int, default=[20, 55, 126, 252])
    sweep_parser.add_argument("--exit-lookback-values", nargs="+", type=int, default=[10, 20, 55])
    sweep_parser.add_argument("--rsi-period-values", nargs="+", type=int, default=[2, 5, 14])
    sweep_parser.add_argument("--lower-values", nargs="+", type=float, default=[20.0, 30.0, 40.0])
    sweep_parser.add_argument("--upper-values", nargs="+", type=float, default=[60.0, 70.0, 80.0])
    sweep_parser.add_argument("--trend-window-values", nargs="+", type=int, default=[100, 150, 200, 300])
    sweep_parser.add_argument("--sma-window-values", nargs="+", type=int, default=[50, 100, 200, 300])
    sweep_parser.add_argument("--stop-pct-values", nargs="+", type=float, default=[0.1, 0.15, 0.2, 0.3, 0.4])
    sweep_parser.add_argument("--window-values", nargs="+", type=int, default=[10, 20, 40])
    sweep_parser.add_argument("--num-std-values", nargs="+", type=float, default=[1.5, 2.0, 2.5])
    sweep_parser.add_argument("--exit-z-values", nargs="+", type=float, default=[0.0, 0.5, 1.0])
    sweep_parser.add_argument("--atr-period-values", nargs="+", type=int, default=[10, 14, 20])
    sweep_parser.add_argument("--atr-mult-values", nargs="+", type=float, default=[2.0, 3.0, 4.0])
    sweep_parser.add_argument("--max-hold-values", nargs="+", type=int, default=[5, 10, 20, 40])
    sweep_parser.add_argument("--streak-rsi-period-values", nargs="+", type=int, default=[2, 3])
    sweep_parser.add_argument("--rank-period-values", nargs="+", type=int, default=[50, 100])
    sweep_parser.add_argument("--ibs-lower-values", nargs="+", type=float, default=[0.1, 0.2, 0.3, 0.4])
    sweep_parser.add_argument("--ibs-upper-values", nargs="+", type=float, default=[0.6, 0.7, 0.8, 0.9])
    sweep_parser.add_argument("--range-mult-values", nargs="+", type=float, default=[0.25, 0.5, 0.75, 1.0])
    sweep_parser.add_argument("--volume-window-values", nargs="+", type=int, default=[0, 20, 50])
    sweep_parser.add_argument("--volume-mult-values", nargs="+", type=float, default=[0.0, 1.0, 1.5])
    sweep_parser.add_argument("--streak-length-values", nargs="+", type=int, default=[2, 3, 4, 5])
    sweep_parser.add_argument("--top", type=int, default=5, help="Quantidade de resultados exibidos por ticker.")

    train_test_parser = subparsers.add_parser("train-test", help="Escolhe parametros no treino e avalia no periodo futuro.")
    _add_common_data_args(train_test_parser)
    train_test_parser.add_argument("--strategy", default="sma_cross", choices=SWEEP_STRATEGIES)
    train_test_parser.add_argument("--initial-cash", type=float, default=10_000.0)
    train_test_parser.add_argument("--cost-bps", type=float, default=0.0)
    train_test_parser.add_argument("--slippage-bps", type=float, default=0.0)
    train_test_parser.add_argument("--lot-size", type=int, default=0)
    train_test_parser.add_argument("--price-mode", choices=["adjusted", "raw_events"], default="adjusted")
    train_test_parser.add_argument("--signal-mode", choices=["adjusted", "raw"], default="adjusted")
    train_test_parser.add_argument("--reports-dir", default="reports")
    train_test_parser.add_argument("--refresh-data", action="store_true")
    train_test_parser.add_argument("--train-ratio", type=float, default=0.7)
    train_test_parser.add_argument("--objective", choices=["excess", "cagr", "sharpe"], default="excess")
    _add_sweep_grid_args(train_test_parser)

    args = parser.parse_args(argv)

    if args.command == "fetch":
        return _fetch_command(args)
    if args.command == "backtest":
        return _backtest_command(args)
    if args.command == "sweep":
        return _sweep_command(args)
    if args.command == "train-test":
        return _train_test_command(args)
    if args.command == "list-strategies":
        for strategy in available_strategies():
            print(strategy)
        return 0

    parser.error("Comando invalido.")
    return 2


def _add_common_data_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tickers", nargs="+", default=list(DEFAULT_TICKERS), help="Tickers B3 sem .SA.")
    parser.add_argument("--interval", default="1d", choices=["1d", "4h", "1wk", "1mo"], help="Intervalo dos candles.")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Diretorio de cache dos candles.")
    parser.add_argument("--actions-dir", default=str(DEFAULT_ACTIONS_DIR), help="Diretorio de cache de dividendos e splits.")
    parser.add_argument("--start", default=None, help="Data inicial YYYY-MM-DD.")
    parser.add_argument("--end", default=None, help="Data final YYYY-MM-DD.")


def _add_sweep_grid_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--fast-values", nargs="+", type=int, default=[10, 20, 50])
    parser.add_argument("--slow-values", nargs="+", type=int, default=[100, 150, 200])
    parser.add_argument("--signal-window-values", nargs="+", type=int, default=[5, 9, 12])
    parser.add_argument("--lookback-values", nargs="+", type=int, default=[20, 55, 126, 252])
    parser.add_argument("--exit-lookback-values", nargs="+", type=int, default=[10, 20, 55])
    parser.add_argument("--rsi-period-values", nargs="+", type=int, default=[2, 5, 14])
    parser.add_argument("--lower-values", nargs="+", type=float, default=[20.0, 30.0, 40.0])
    parser.add_argument("--upper-values", nargs="+", type=float, default=[60.0, 70.0, 80.0])
    parser.add_argument("--trend-window-values", nargs="+", type=int, default=[100, 150, 200, 300])
    parser.add_argument("--sma-window-values", nargs="+", type=int, default=[50, 100, 200, 300])
    parser.add_argument("--stop-pct-values", nargs="+", type=float, default=[0.1, 0.15, 0.2, 0.3, 0.4])
    parser.add_argument("--window-values", nargs="+", type=int, default=[10, 20, 40])
    parser.add_argument("--num-std-values", nargs="+", type=float, default=[1.5, 2.0, 2.5])
    parser.add_argument("--exit-z-values", nargs="+", type=float, default=[0.0, 0.5, 1.0])
    parser.add_argument("--atr-period-values", nargs="+", type=int, default=[10, 14, 20])
    parser.add_argument("--atr-mult-values", nargs="+", type=float, default=[2.0, 3.0, 4.0])
    parser.add_argument("--max-hold-values", nargs="+", type=int, default=[5, 10, 20, 40])
    parser.add_argument("--streak-rsi-period-values", nargs="+", type=int, default=[2, 3])
    parser.add_argument("--rank-period-values", nargs="+", type=int, default=[50, 100])
    parser.add_argument("--ibs-lower-values", nargs="+", type=float, default=[0.1, 0.2, 0.3, 0.4])
    parser.add_argument("--ibs-upper-values", nargs="+", type=float, default=[0.6, 0.7, 0.8, 0.9])
    parser.add_argument("--range-mult-values", nargs="+", type=float, default=[0.25, 0.5, 0.75, 1.0])
    parser.add_argument("--volume-window-values", nargs="+", type=int, default=[0, 20, 50])
    parser.add_argument("--volume-mult-values", nargs="+", type=float, default=[0.0, 1.0, 1.5])
    parser.add_argument("--streak-length-values", nargs="+", type=int, default=[2, 3, 4, 5])


def _fetch_command(args: argparse.Namespace) -> int:
    for ticker in args.tickers:
        path, candles, action_path, actions = fetch_and_cache(
            ticker,
            interval=args.interval,
            range_name=args.range_name,
            data_dir=args.data_dir,
            actions_dir=args.actions_dir,
            start=args.start,
            end=args.end,
        )
        _print_fetch_result(ticker, path, candles, action_path, actions)
    return 0


def _backtest_command(args: argparse.Namespace) -> int:
    summaries = []
    reports_dir = Path(args.reports_dir)

    for ticker in args.tickers:
        candles = _load_or_fetch_for_backtest(ticker, args)
        actions = _load_actions_for_backtest(ticker, args)
        signal_candles = _signal_candles(candles, args.signal_mode)
        signals = build_signals(args.strategy, signal_candles, **_strategy_params_from_args(args))
        summary, strategy_curve, benchmark_curve = run_strategy_vs_buy_hold(
            ticker.upper(),
            args.strategy,
            candles,
            signals,
            initial_cash=args.initial_cash,
            cost_bps=args.cost_bps,
            slippage_bps=args.slippage_bps,
            lot_size=args.lot_size,
            price_mode=args.price_mode,
            actions=actions,
        )
        summaries.append(summary)
        curve_path = reports_dir / f"{ticker.lower()}_{args.strategy}_{args.price_mode}_{args.signal_mode}_{args.interval}_equity.csv"
        write_comparison_curve(strategy_curve, benchmark_curve, curve_path)

    summary_path = reports_dir / f"summary_{args.strategy}_{args.price_mode}_{args.signal_mode}_{args.interval}.csv"
    write_summary_csv(summaries, summary_path)
    _print_summary_table(summaries)
    print(f"\nResumo salvo em: {summary_path}")
    print(f"Curvas salvas em: {reports_dir}")
    return 0


def _sweep_command(args: argparse.Namespace) -> int:
    rows: list[dict] = []
    reports_dir = Path(args.reports_dir)

    for ticker in args.tickers:
        candles = _load_or_fetch_for_backtest(ticker, args)
        actions = _load_actions_for_backtest(ticker, args)
        signal_candles = _signal_candles(candles, args.signal_mode)
        for params in _parameter_grid(args):
            signals = build_signals(args.strategy, signal_candles, **params)
            summary, _, _ = run_strategy_vs_buy_hold(
                ticker.upper(),
                args.strategy,
                candles,
                signals,
                initial_cash=args.initial_cash,
                cost_bps=args.cost_bps,
                slippage_bps=args.slippage_bps,
                lot_size=args.lot_size,
                price_mode=args.price_mode,
                actions=actions,
            )
            row = _summary_row(summary, params)
            rows.append(row)

    rows.sort(key=lambda row: (row["ticker"], -float(row["excess_total_return"])))
    output = reports_dir / f"sweep_{args.strategy}_{args.price_mode}_{args.signal_mode}_{args.interval}.csv"
    _write_sweep_csv(rows, output)
    _print_sweep_table(rows, args.top)
    print(f"\nVarredura salva em: {output}")
    return 0


def _train_test_command(args: argparse.Namespace) -> int:
    rows: list[dict] = []
    reports_dir = Path(args.reports_dir)

    for ticker in args.tickers:
        candles = _load_or_fetch_for_backtest(ticker, args)
        actions = _load_actions_for_backtest(ticker, args)
        split_index = _split_index(candles, args.train_ratio)
        train_candles = candles[:split_index]
        test_candles = candles[split_index:]
        train_signal_candles = _signal_candles(train_candles, args.signal_mode)
        full_signal_candles = _signal_candles(candles, args.signal_mode)
        best_train: tuple[Summary, dict] | None = None

        for params in _parameter_grid(args):
            signals = build_signals(args.strategy, train_signal_candles, **params)
            summary, _, _ = run_strategy_vs_buy_hold(
                ticker.upper(),
                args.strategy,
                train_candles,
                signals,
                initial_cash=args.initial_cash,
                cost_bps=args.cost_bps,
                slippage_bps=args.slippage_bps,
                lot_size=args.lot_size,
                price_mode=args.price_mode,
                actions=actions,
            )
            if best_train is None or _objective_value(summary, args.objective) > _objective_value(best_train[0], args.objective):
                best_train = (summary, params)

        if best_train is None:
            continue

        train_summary, best_params = best_train
        full_signals = build_signals(args.strategy, full_signal_candles, **best_params)
        test_signals = full_signals[split_index:]
        test_summary, strategy_curve, benchmark_curve = run_strategy_vs_buy_hold(
            ticker.upper(),
            args.strategy,
            test_candles,
            test_signals,
            initial_cash=args.initial_cash,
            cost_bps=args.cost_bps,
            slippage_bps=args.slippage_bps,
            lot_size=args.lot_size,
            price_mode=args.price_mode,
            actions=actions,
        )
        curve_path = reports_dir / f"{ticker.lower()}_{args.strategy}_{args.objective}_{args.price_mode}_{args.signal_mode}_{args.interval}_train_test_equity.csv"
        write_comparison_curve(strategy_curve, benchmark_curve, curve_path)
        rows.append(_train_test_row(train_summary, test_summary, best_params, args.objective))

    output = reports_dir / f"train_test_{args.strategy}_{args.objective}_{args.price_mode}_{args.signal_mode}_{args.interval}.csv"
    _write_train_test_csv(rows, output)
    _print_train_test_table(rows)
    print(f"\nTreino-teste salvo em: {output}")
    return 0


def _load_or_fetch_for_backtest(ticker: str, args: argparse.Namespace):
    path = cache_path(ticker, args.interval, args.data_dir)
    if args.refresh_data or not path.exists():
        _, candles, _, _ = fetch_and_cache(
            ticker,
            interval=args.interval,
            range_name="max",
            data_dir=args.data_dir,
            actions_dir=args.actions_dir,
            start=args.start,
            end=args.end,
        )
        return candles
    candles = load_candles(path, start=args.start, end=args.end)
    issues = validate_candles(candles)
    if issues:
        print(f"Aviso: {len(issues)} problemas de candles em {ticker}. Primeiro: {issues[0]}")
    return candles


def _load_actions_for_backtest(ticker: str, args: argparse.Namespace):
    path = actions_path(ticker, args.actions_dir)
    if args.refresh_data or not path.exists():
        _, _, _, actions = fetch_and_cache(
            ticker,
            interval=args.interval,
            range_name="max",
            data_dir=args.data_dir,
            actions_dir=args.actions_dir,
            start=args.start,
            end=args.end,
        )
        return actions
    return load_actions(path, start=args.start, end=args.end)


def _signal_candles(candles, signal_mode: str):
    if signal_mode == "adjusted":
        return candles
    if signal_mode == "raw":
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
    raise ValueError("signal_mode precisa ser 'adjusted' ou 'raw'.")


def _strategy_params_from_args(args: argparse.Namespace) -> dict:
    return {
        "fast": getattr(args, "fast", None),
        "slow": getattr(args, "slow", None),
        "signal_window": getattr(args, "signal_window", None),
        "lookback": getattr(args, "lookback", None),
        "exit_lookback": getattr(args, "exit_lookback", None),
        "rsi_period": getattr(args, "rsi_period", None),
        "lower": getattr(args, "lower", None),
        "upper": getattr(args, "upper", None),
        "trend_window": getattr(args, "trend_window", None),
        "sma_window": getattr(args, "sma_window", None),
        "stop_pct": getattr(args, "stop_pct", None),
        "window": getattr(args, "window", None),
        "num_std": getattr(args, "num_std", None),
        "exit_z": getattr(args, "exit_z", None),
        "atr_period": getattr(args, "atr_period", None),
        "atr_mult": getattr(args, "atr_mult", None),
        "max_hold": getattr(args, "max_hold", None),
        "streak_rsi_period": getattr(args, "streak_rsi_period", None),
        "rank_period": getattr(args, "rank_period", None),
        "ibs_lower": getattr(args, "ibs_lower", None),
        "ibs_upper": getattr(args, "ibs_upper", None),
        "range_mult": getattr(args, "range_mult", None),
        "volume_window": getattr(args, "volume_window", None),
        "volume_mult": getattr(args, "volume_mult", None),
        "streak_length": getattr(args, "streak_length", None),
    }


def _parameter_grid(args: argparse.Namespace):
    if args.strategy == "sma_cross":
        for fast in args.fast_values:
            for slow in args.slow_values:
                if fast < slow:
                    yield {"fast": fast, "slow": slow}
    elif args.strategy == "ema_cross":
        for fast in args.fast_values:
            for slow in args.slow_values:
                if fast < slow:
                    yield {"fast": fast, "slow": slow}
    elif args.strategy == "price_sma":
        for sma_window in args.sma_window_values:
            yield {"sma_window": sma_window}
    elif args.strategy == "macd":
        for fast in args.fast_values:
            for slow in args.slow_values:
                for signal_window in args.signal_window_values:
                    if fast < slow:
                        yield {"fast": fast, "slow": slow, "signal_window": signal_window}
    elif args.strategy == "momentum":
        for lookback in args.lookback_values:
            yield {"lookback": lookback}
    elif args.strategy == "roc_trend":
        for lookback in args.lookback_values:
            for sma_window in args.sma_window_values:
                yield {"lookback": lookback, "sma_window": sma_window}
    elif args.strategy == "breakout":
        for lookback in args.lookback_values:
            for exit_lookback in args.exit_lookback_values:
                yield {"lookback": lookback, "exit_lookback": exit_lookback}
    elif args.strategy == "chandelier_breakout":
        for lookback in args.lookback_values:
            for atr_period in args.atr_period_values:
                for atr_mult in args.atr_mult_values:
                    for volume_window in args.volume_window_values:
                        for volume_mult in args.volume_mult_values:
                            yield {
                                "lookback": lookback,
                                "atr_period": atr_period,
                                "atr_mult": atr_mult,
                                "volume_window": volume_window,
                                "volume_mult": volume_mult,
                            }
    elif args.strategy == "atr_breakout":
        for lookback in args.lookback_values:
            for atr_period in args.atr_period_values:
                for atr_mult in args.atr_mult_values:
                    yield {"lookback": lookback, "atr_period": atr_period, "atr_mult": atr_mult}
    elif args.strategy == "range_expansion_breakout":
        for range_mult in args.range_mult_values:
            for atr_period in args.atr_period_values:
                for atr_mult in args.atr_mult_values:
                    for trend_window in args.trend_window_values:
                        for volume_window in args.volume_window_values:
                            for volume_mult in args.volume_mult_values:
                                for max_hold in args.max_hold_values:
                                    yield {
                                        "range_mult": range_mult,
                                        "atr_period": atr_period,
                                        "atr_mult": atr_mult,
                                        "trend_window": trend_window,
                                        "volume_window": volume_window,
                                        "volume_mult": volume_mult,
                                        "max_hold": max_hold,
                                    }
    elif args.strategy == "supertrend_follow":
        for atr_period in args.atr_period_values:
            for atr_mult in args.atr_mult_values:
                yield {"atr_period": atr_period, "atr_mult": atr_mult}
    elif args.strategy == "bollinger_reversion":
        for window in args.window_values:
            for num_std in args.num_std_values:
                for exit_z in args.exit_z_values:
                    yield {"window": window, "num_std": num_std, "exit_z": exit_z}
    elif args.strategy == "keltner_breakout":
        for window in args.window_values:
            for atr_period in args.atr_period_values:
                for atr_mult in args.atr_mult_values:
                    for exit_z in args.exit_z_values:
                        for trend_window in args.trend_window_values:
                            yield {
                                "window": window,
                                "atr_period": atr_period,
                                "atr_mult": atr_mult,
                                "exit_z": exit_z,
                                "trend_window": trend_window,
                            }
    elif args.strategy == "rsi_reversion":
        for rsi_period in args.rsi_period_values:
            for lower in args.lower_values:
                for upper in args.upper_values:
                    if lower < upper:
                        yield {"rsi_period": rsi_period, "lower": lower, "upper": upper}
    elif args.strategy == "ibs_reversion":
        for ibs_lower in args.ibs_lower_values:
            for ibs_upper in args.ibs_upper_values:
                for max_hold in args.max_hold_values:
                    for trend_window in args.trend_window_values:
                        if ibs_lower < ibs_upper:
                            yield {
                                "ibs_lower": ibs_lower,
                                "ibs_upper": ibs_upper,
                                "max_hold": max_hold,
                                "trend_window": trend_window,
                            }
    elif args.strategy == "rsi_ibs_reversion":
        for rsi_period in args.rsi_period_values:
            for lower in args.lower_values:
                for upper in args.upper_values:
                    for ibs_lower in args.ibs_lower_values:
                        for ibs_upper in args.ibs_upper_values:
                            for trend_window in args.trend_window_values:
                                for max_hold in args.max_hold_values:
                                    if lower < upper and ibs_lower < ibs_upper:
                                        yield {
                                            "rsi_period": rsi_period,
                                            "lower": lower,
                                            "upper": upper,
                                            "ibs_lower": ibs_lower,
                                            "ibs_upper": ibs_upper,
                                            "trend_window": trend_window,
                                            "max_hold": max_hold,
                                        }
    elif args.strategy == "rsi2_trend_reversion":
        for rsi_period in args.rsi_period_values:
            for lower in args.lower_values:
                for upper in args.upper_values:
                    for trend_window in args.trend_window_values:
                        for sma_window in args.sma_window_values:
                            for max_hold in args.max_hold_values:
                                if lower < upper:
                                    yield {
                                        "rsi_period": rsi_period,
                                        "lower": lower,
                                        "upper": upper,
                                        "trend_window": trend_window,
                                        "sma_window": sma_window,
                                        "max_hold": max_hold,
                                    }
    elif args.strategy == "down_streak_reversion":
        for streak_length in args.streak_length_values:
            for ibs_lower in args.ibs_lower_values:
                for ibs_upper in args.ibs_upper_values:
                    for trend_window in args.trend_window_values:
                        for max_hold in args.max_hold_values:
                            if ibs_lower < ibs_upper:
                                yield {
                                    "streak_length": streak_length,
                                    "ibs_lower": ibs_lower,
                                    "ibs_upper": ibs_upper,
                                    "trend_window": trend_window,
                                    "max_hold": max_hold,
                                }
    elif args.strategy == "rsi_reversion_hold":
        for rsi_period in args.rsi_period_values:
            for lower in args.lower_values:
                for upper in args.upper_values:
                    for max_hold in args.max_hold_values:
                        if lower < upper:
                            yield {"rsi_period": rsi_period, "lower": lower, "upper": upper, "max_hold": max_hold}
    elif args.strategy == "rsi_reversion_atr":
        for rsi_period in args.rsi_period_values:
            for lower in args.lower_values:
                for upper in args.upper_values:
                    for atr_period in args.atr_period_values:
                        for atr_mult in args.atr_mult_values:
                            if lower < upper:
                                yield {
                                    "rsi_period": rsi_period,
                                    "lower": lower,
                                    "upper": upper,
                                    "atr_period": atr_period,
                                    "atr_mult": atr_mult,
                                }
    elif args.strategy == "rsi_reversion_trend_entry":
        for trend_window in args.trend_window_values:
            for rsi_period in args.rsi_period_values:
                for lower in args.lower_values:
                    for upper in args.upper_values:
                        if lower < upper:
                            yield {
                                "trend_window": trend_window,
                                "rsi_period": rsi_period,
                                "lower": lower,
                                "upper": upper,
                            }
    elif args.strategy == "rsi_cross_reversion":
        for rsi_period in args.rsi_period_values:
            for lower in args.lower_values:
                for upper in args.upper_values:
                    if lower < upper:
                        yield {"rsi_period": rsi_period, "lower": lower, "upper": upper}
    elif args.strategy == "rsi_bollinger":
        for rsi_period in args.rsi_period_values:
            for lower in args.lower_values:
                for upper in args.upper_values:
                    for window in args.window_values:
                        for num_std in args.num_std_values:
                            for exit_z in args.exit_z_values:
                                if lower < upper:
                                    yield {
                                        "rsi_period": rsi_period,
                                        "lower": lower,
                                        "upper": upper,
                                        "window": window,
                                        "num_std": num_std,
                                        "exit_z": exit_z,
                                    }
    elif args.strategy == "connors_rsi_reversion":
        for rsi_period in args.rsi_period_values:
            for streak_rsi_period in args.streak_rsi_period_values:
                for rank_period in args.rank_period_values:
                    for lower in args.lower_values:
                        for upper in args.upper_values:
                            if lower < upper:
                                yield {
                                    "rsi_period": rsi_period,
                                    "streak_rsi_period": streak_rsi_period,
                                    "rank_period": rank_period,
                                    "lower": lower,
                                    "upper": upper,
                                }
    elif args.strategy == "trend_pullback":
        for trend_window in args.trend_window_values:
            for rsi_period in args.rsi_period_values:
                for lower in args.lower_values:
                    for upper in args.upper_values:
                        if lower < upper:
                            yield {
                                "trend_window": trend_window,
                                "rsi_period": rsi_period,
                                "lower": lower,
                                "upper": upper,
                            }
    elif args.strategy == "sma_stop":
        for sma_window in args.sma_window_values:
            for stop_pct in args.stop_pct_values:
                yield {"sma_window": sma_window, "stop_pct": stop_pct}
    else:
        raise ValueError(f"Estrategia sem varredura configurada: {args.strategy}")


def _summary_row(summary: Summary, params: dict) -> dict:
    row = asdict(summary)
    for field in PARAM_FIELDS:
        row[field] = params.get(field, "")
    return row


def _train_test_row(train_summary: Summary, test_summary: Summary, params: dict, objective: str) -> dict:
    row = {
        "ticker": test_summary.ticker,
        "strategy": test_summary.strategy,
        "objective": objective,
        "train_start": train_summary.start,
        "train_end": train_summary.end,
        "test_start": test_summary.start,
        "test_end": test_summary.end,
        "train_total_return": train_summary.total_return,
        "train_benchmark_total_return": train_summary.benchmark_total_return,
        "train_excess_total_return": train_summary.excess_total_return,
        "train_cagr": train_summary.cagr,
        "train_sharpe": train_summary.sharpe,
        "test_total_return": test_summary.total_return,
        "test_benchmark_total_return": test_summary.benchmark_total_return,
        "test_excess_total_return": test_summary.excess_total_return,
        "test_cagr": test_summary.cagr,
        "test_sharpe": test_summary.sharpe,
        "test_max_drawdown": test_summary.max_drawdown,
        "test_trades": test_summary.trades,
        "test_exposure": test_summary.exposure,
    }
    for field in PARAM_FIELDS:
        row[field] = params.get(field, "")
    return row


def _write_sweep_csv(rows: list[dict], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary_fields = [field for field in Summary.__dataclass_fields__ if field not in {"ticker", "strategy"}]
    fields = ["ticker", "strategy", *PARAM_FIELDS, *summary_fields]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def _write_train_test_csv(rows: list[dict], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "ticker",
        "strategy",
        "objective",
        *PARAM_FIELDS,
        "train_start",
        "train_end",
        "test_start",
        "test_end",
        "train_total_return",
        "train_benchmark_total_return",
        "train_excess_total_return",
        "train_cagr",
        "train_sharpe",
        "test_total_return",
        "test_benchmark_total_return",
        "test_excess_total_return",
        "test_cagr",
        "test_sharpe",
        "test_max_drawdown",
        "test_trades",
        "test_exposure",
    ]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def _print_fetch_result(ticker: str, path: Path, candles, action_path: Path, actions) -> None:
    if candles:
        repaired = sum(candle.ohlc_repaired for candle in candles)
        print(
            f"{ticker.upper():<7} {len(candles):>5} candles {candles[0].date} -> {candles[-1].date}  "
            f"{len(actions):>3} eventos  reparos_ohlc={repaired:<2}  {path}  {action_path}"
        )
    else:
        print(f"{ticker.upper():<7} nenhum candle salvo em {path}")


def _print_train_test_table(rows: list[dict]) -> None:
    if not rows:
        print("Nenhum resultado gerado.")
        return

    headers = ["Ticker", "Params", "Treino", "Treino B&H", "Teste", "Teste B&H", "Excesso", "MDD", "Trades"]
    table_rows = []
    for row in rows:
        table_rows.append(
            [
                row["ticker"],
                _params_label(row),
                _pct(float(row["train_total_return"])),
                _pct(float(row["train_benchmark_total_return"])),
                _pct(float(row["test_total_return"])),
                _pct(float(row["test_benchmark_total_return"])),
                _pct(float(row["test_excess_total_return"])),
                _pct(float(row["test_max_drawdown"])),
                str(row["test_trades"]),
            ]
        )
    _print_table(headers, table_rows)


def _print_sweep_table(rows: list[dict], top: int) -> None:
    if not rows:
        print("Nenhum resultado gerado.")
        return

    headers = ["Ticker", "Params", "Ret", "B&H", "Excesso", "MDD", "Trades", "Expos."]
    table_rows = []
    for ticker in sorted({row["ticker"] for row in rows}):
        ticker_rows = [row for row in rows if row["ticker"] == ticker]
        for row in ticker_rows[:top]:
            table_rows.append(
                [
                    row["ticker"],
                    _params_label(row),
                    _pct(float(row["total_return"])),
                    _pct(float(row["benchmark_total_return"])),
                    _pct(float(row["excess_total_return"])),
                    _pct(float(row["max_drawdown"])),
                    str(row["trades"]),
                    _pct(float(row["exposure"])),
                ]
            )

    _print_table(headers, table_rows)


def _print_summary_table(summaries) -> None:
    headers = ["Ticker", "Ret", "B&H", "Excesso", "CAGR", "MDD", "Trades", "Expos."]
    rows = []
    for summary in summaries:
        rows.append(
            [
                summary.ticker,
                _pct(summary.total_return),
                _pct(summary.benchmark_total_return),
                _pct(summary.excess_total_return),
                _pct(summary.cagr),
                _pct(summary.max_drawdown),
                str(summary.trades),
                _pct(summary.exposure),
            ]
        )

    _print_table(headers, rows)


def _print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [len(header) for header in headers]
    for row in rows:
        widths = [max(width, len(value)) for width, value in zip(widths, row)]

    print("  ".join(header.ljust(width) for header, width in zip(headers, widths)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(width) for value, width in zip(row, widths)))


def _params_label(row: dict) -> str:
    parts = []
    for key in PARAM_FIELDS:
        value = row.get(key)
        if value not in ("", None):
            parts.append(f"{key}={value}")
    return ",".join(parts) if parts else "-"


def _split_index(candles, train_ratio: float) -> int:
    if train_ratio <= 0 or train_ratio >= 1:
        raise ValueError("train_ratio precisa estar entre 0 e 1.")
    split_index = int(len(candles) * train_ratio)
    if split_index < 2 or len(candles) - split_index < 2:
        raise ValueError("Historico insuficiente para o split treino-teste.")
    return split_index


def _objective_value(summary: Summary, objective: str) -> float:
    if objective == "excess":
        return summary.excess_total_return
    if objective == "cagr":
        return summary.cagr
    if objective == "sharpe":
        return summary.sharpe
    raise ValueError(f"Objetivo desconhecido: {objective}")


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"
