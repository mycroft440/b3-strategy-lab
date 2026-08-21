from __future__ import annotations

import argparse
import csv
import inspect
from dataclasses import asdict, replace
from datetime import date, timedelta
from pathlib import Path

from .backtest import Summary, run_strategy_vs_buy_hold, write_comparison_curve, write_summary_csv
from .candles import (
    DEFAULT_ACTIONS_DIR,
    DEFAULT_DATA_DIR,
    DEFAULT_LEGACY_ACTIONS_DIR,
    DEFAULT_LEGACY_DATA_DIR,
    DEFAULT_TICKERS,
    actions_path,
    cache_path,
    fetch_and_cache,
    load_actions,
    load_candles,
    split_candles_by_year,
    validate_candles,
)
from .cotahist import DEFAULT_MANIFESTS_DIR, DataVerificationError, load_verified_candles
from .strategies import STRATEGIES, available_strategies, build_signals, strategies_by_family, strategy_parameters, sweep_strategies

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
    "long_period",
    "short_period",
    "band_edge",
    "bandwidth",
    "rms_period",
    "period",
    "signal_period",
    "k_period",
    "slowing",
    "d_period",
    "er_period",
    "fast_period",
    "slow_period",
    "entry_level",
    "exit_level",
    "keltner_mult",
    "squeeze_bars",
    "stop_atr",
    "hold_limit",
    "sessions_before",
    "sessions_after",
    "gamma",
    "tenkan_period",
    "kijun_period",
    "span_b_period",
    "displacement",
    "af_step",
    "af_max",
    "strong_level",
    "cycle_period",
    "smoothing",
    "short_roc",
    "long_roc",
    "wma_period",
    "roc1",
    "roc2",
    "roc3",
    "roc4",
    "sma1",
    "sma2",
    "sma3",
    "sma4",
    "high_level",
    "low_level",
    "ema_period",
    "sum_period",
    "bulge_level",
    "trigger_level",
    "exit_window",
    "setup_period",
    "expiry",
    "entry_month",
    "exit_month",
]

SWEEP_STRATEGIES = sweep_strategies()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B3 single-asset candle downloader and strategy lab.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser(
        "fetch",
        help="Baixa a fonte legada para uma area isolada; nao certifica os dados.",
    )
    _add_common_data_args(fetch_parser)
    fetch_parser.set_defaults(
        data_dir=str(DEFAULT_LEGACY_DATA_DIR),
        actions_dir=str(DEFAULT_LEGACY_ACTIONS_DIR),
    )
    fetch_parser.add_argument("--range", dest="range_name", default="max", help="Range Yahoo, exemplo: max, 10y, 5y.")

    verify_parser = subparsers.add_parser(
        "verify-data",
        help="Confere hashes, origem, anomalias revisadas e janela dos candles.",
    )
    _add_common_data_args(verify_parser)
    verify_parser.add_argument("--manifests-dir", default=str(DEFAULT_MANIFESTS_DIR))
    verify_parser.add_argument(
        "--require-verified-actions",
        action="store_true",
        help="Exige proventos certificados para diagnosticos de retorno total.",
    )

    list_parser = subparsers.add_parser("list-strategies", help="Lista estrategias disponiveis.")
    list_parser.set_defaults(command="list-strategies")

    backtest_parser = subparsers.add_parser("backtest", help="Roda uma estrategia contra buy and hold por ativo.")
    _add_common_data_args(backtest_parser, include_yearly=True, verified_options=True)
    backtest_parser.add_argument("--strategy", default="sma_cross", choices=available_strategies())
    backtest_parser.add_argument("--initial-cash", type=float, default=1_000.0)
    backtest_parser.add_argument("--cost-bps", type=float, default=3.2, help="Custo por ordem em basis points. 10 bps = 0,10 por cento.")
    backtest_parser.add_argument("--slippage-bps", type=float, default=10.0, help="Slippage adverso por ordem em basis points.")
    backtest_parser.add_argument("--lot-size", type=int, default=1, help="1 permite mercado fracionario; 100 usa lote padrao; 0 permite fracao irreal.")
    backtest_parser.add_argument(
        "--price-mode",
        choices=["price_only", "adjusted", "raw_events"],
        default="price_only",
        help=(
            "price_only usa OHLC oficial normalizado por splits e ignora "
            "dividendos/JCP; raw_events e diagnostico de retorno total."
        ),
    )
    backtest_parser.add_argument("--signal-mode", choices=["adjusted", "raw"], default="adjusted")
    backtest_parser.add_argument("--reports-dir", default="reports")
    backtest_parser.add_argument(
        "--refresh-data",
        action="store_true",
        help="Atualiza pela fonte legada; exige --allow-unverified-data.",
    )
    # None deixa cada motor aplicar seu proprio parametro canonico. Assim uma
    # opcao generica da CLI nao sobrescreve silenciosamente defaults distintos.
    backtest_parser.add_argument("--fast", type=int, default=None, help="Media curta, quando suportada pela estrategia.")
    backtest_parser.add_argument("--slow", type=int, default=None, help="Media longa, quando suportada pela estrategia.")
    backtest_parser.add_argument("--lookback", type=int, default=None, help="Janela retrospectiva, quando suportada.")
    backtest_parser.add_argument("--exit-lookback", type=int, default=None, help="Janela de saida, quando suportada.")
    backtest_parser.add_argument("--signal-window", type=int, default=None, help="Janela da linha de sinal, quando suportada.")
    backtest_parser.add_argument("--rsi-period", type=int, default=None, help="Periodo do RSI, quando suportado.")
    backtest_parser.add_argument("--lower", type=float, default=None, help="Limite inferior, quando suportado.")
    backtest_parser.add_argument("--upper", type=float, default=None, help="Limite superior, quando suportado.")
    backtest_parser.add_argument("--trend-window", type=int, default=None, help="Janela do filtro de tendencia, quando suportada.")
    backtest_parser.add_argument("--sma-window", type=int, default=None, help="Janela da media simples, quando suportada.")
    backtest_parser.add_argument("--stop-pct", type=float, default=None, help="Stop percentual, quando suportado.")
    backtest_parser.add_argument("--window", type=int, default=None, help="Janela principal, quando suportada.")
    backtest_parser.add_argument("--num-std", type=float, default=None, help="Desvios-padrao, quando suportados.")
    backtest_parser.add_argument("--exit-z", type=float, default=None, help="Nivel de saida em desvios, quando suportado.")
    backtest_parser.add_argument("--atr-period", type=int, default=None, help="Periodo do ATR, quando suportado.")
    backtest_parser.add_argument("--atr-mult", type=float, default=None, help="Multiplicador do ATR, quando suportado.")
    backtest_parser.add_argument("--max-hold", type=int, default=None, help="Permanencia maxima, quando suportada.")
    backtest_parser.add_argument("--streak-rsi-period", type=int, default=None, help="Periodo do RSI de sequencia, quando suportado.")
    backtest_parser.add_argument("--rank-period", type=int, default=None, help="Periodo do percent rank, quando suportado.")
    backtest_parser.add_argument("--ibs-lower", type=float, default=None, help="Limite inferior do IBS, quando suportado.")
    backtest_parser.add_argument("--ibs-upper", type=float, default=None, help="Limite superior do IBS, quando suportado.")
    backtest_parser.add_argument("--range-mult", type=float, default=None, help="Multiplicador de range, quando suportado.")
    backtest_parser.add_argument("--volume-window", type=int, default=None, help="Janela de volume, quando suportada.")
    backtest_parser.add_argument("--volume-mult", type=float, default=None, help="Multiplicador de volume, quando suportado.")
    backtest_parser.add_argument("--streak-length", type=int, default=None, help="Tamanho da sequencia, quando suportado.")
    backtest_parser.add_argument(
        "--strategy-param",
        action="append",
        default=[],
        metavar="NOME=VALOR",
        help="Sobrescreve um parametro documentado da estrategia; pode ser repetido.",
    )

    sweep_parser = subparsers.add_parser("sweep", help="Varre parametros por ativo contra buy and hold.")
    _add_common_data_args(sweep_parser, include_yearly=True, verified_options=True)
    sweep_parser.add_argument(
        "--strategy",
        default="sma_cross",
        choices=SWEEP_STRATEGIES,
    )
    sweep_parser.add_argument("--initial-cash", type=float, default=1_000.0)
    sweep_parser.add_argument("--cost-bps", type=float, default=3.2, help="Custo por ordem em basis points.")
    sweep_parser.add_argument("--slippage-bps", type=float, default=10.0, help="Slippage adverso por ordem em basis points.")
    sweep_parser.add_argument("--lot-size", type=int, default=1, help="1 permite mercado fracionario; 100 usa lote padrao; 0 permite fracao irreal.")
    sweep_parser.add_argument(
        "--price-mode",
        choices=["price_only", "adjusted", "raw_events"],
        default="price_only",
    )
    sweep_parser.add_argument("--signal-mode", choices=["adjusted", "raw"], default="adjusted")
    sweep_parser.add_argument("--reports-dir", default="reports")
    sweep_parser.add_argument(
        "--refresh-data",
        action="store_true",
        help="Atualiza pela fonte legada; exige --allow-unverified-data.",
    )
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
    _add_common_data_args(train_test_parser, include_yearly=True, verified_options=True)
    train_test_parser.add_argument("--strategy", default="sma_cross", choices=SWEEP_STRATEGIES)
    train_test_parser.add_argument("--initial-cash", type=float, default=1_000.0)
    train_test_parser.add_argument("--cost-bps", type=float, default=3.2)
    train_test_parser.add_argument("--slippage-bps", type=float, default=10.0)
    train_test_parser.add_argument("--lot-size", type=int, default=1)
    train_test_parser.add_argument(
        "--price-mode",
        choices=["price_only", "adjusted", "raw_events"],
        default="price_only",
    )
    train_test_parser.add_argument("--signal-mode", choices=["adjusted", "raw"], default="adjusted")
    train_test_parser.add_argument("--reports-dir", default="reports")
    train_test_parser.add_argument("--refresh-data", action="store_true")
    train_test_parser.add_argument("--train-ratio", type=float, default=0.7)
    train_test_parser.add_argument("--objective", choices=["excess", "cagr", "sharpe"], default="excess")
    _add_sweep_grid_args(train_test_parser)

    args = parser.parse_args(argv)

    try:
        if args.command == "fetch":
            return _fetch_command(args)
        if args.command == "verify-data":
            return _verify_data_command(args)
        if args.command == "backtest":
            return _backtest_command(args)
        if args.command == "sweep":
            return _sweep_command(args)
        if args.command == "train-test":
            return _train_test_command(args)
        if args.command == "list-strategies":
            _print_strategy_catalog()
            return 0
    except DataVerificationError as error:
        print(f"Dados rejeitados: {error}")
        return 2

    parser.error("Comando invalido.")
    return 2


def _add_common_data_args(
    parser: argparse.ArgumentParser,
    *,
    include_yearly: bool = False,
    verified_options: bool = False,
) -> None:
    parser.add_argument("--tickers", nargs="+", default=list(DEFAULT_TICKERS), help="Tickers B3 sem .SA.")
    parser.add_argument("--interval", default="1d", choices=["1d", "4h", "1wk", "1mo"], help="Intervalo dos candles.")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Diretorio de cache dos candles.")
    parser.add_argument("--actions-dir", default=str(DEFAULT_ACTIONS_DIR), help="Diretorio de cache de dividendos e splits.")
    if verified_options:
        parser.add_argument(
            "--manifests-dir",
            default=str(DEFAULT_MANIFESTS_DIR),
            help="Diretorio dos manifestos de verificacao dos dados.",
        )
        parser.add_argument(
            "--allow-unverified-actions",
            action="store_true",
            help=(
                "Permite proventos nao certificados somente no modo raw_events. "
                "Nao afeta o modo seguro price_only."
            ),
        )
        parser.add_argument(
            "--allow-unverified-data",
            action="store_true",
            help="Ignora manifestos e permite dados legados. Use apenas para diagnostico.",
        )
    parser.add_argument("--start", default=None, help="Data inicial YYYY-MM-DD.")
    parser.add_argument("--end", default=None, help="Data final YYYY-MM-DD.")
    if include_yearly:
        parser.add_argument("--by-year", action="store_true", help="Executa cada ano como um backtest independente.")
        parser.add_argument("--years", nargs="+", type=int, default=None, help="Filtra anos especificos, exemplo: --years 2024 2025.")


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


def _verify_data_command(args: argparse.Namespace) -> int:
    for ticker in args.tickers:
        candles, manifest = load_verified_candles(
            ticker,
            args.interval,
            data_dir=args.data_dir,
            actions_dir=args.actions_dir,
            manifests_dir=args.manifests_dir,
            start=args.start,
            end=args.end,
            require_verified_actions=args.require_verified_actions,
        )
        if not candles:
            raise DataVerificationError(
                f"Nenhum candle de {ticker} {args.interval} no recorte solicitado."
            )
        print(
            f"{ticker.upper()} {args.interval}: {len(candles)} candles, "
            f"{candles[0].date} a {candles[-1].date}, "
            f"precos={manifest.status}, "
            f"price_only=ready_desde_{manifest.split_verified_from or 'indefinido'}, "
            f"splits={manifest.split_action_status}_desde_{manifest.split_verified_from or 'indefinido'}, "
            f"proventos={manifest.corporate_action_status}, "
            f"avisos={len(manifest.warnings)}/{len(manifest.warning_reviews)} revisados"
        )
    return 0


def _backtest_command(args: argparse.Namespace) -> int:
    if args.by_year:
        return _backtest_by_year_command(args)

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
    if args.by_year:
        return _sweep_by_year_command(args)

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
    if args.by_year:
        return _train_test_by_year_command(args)

    rows: list[dict] = []
    reports_dir = Path(args.reports_dir)

    for ticker in args.tickers:
        candles = _load_or_fetch_for_backtest(ticker, args)
        actions = _load_actions_for_backtest(ticker, args)
        split_index = _split_index(candles, args.train_ratio)
        train_candles = candles[:split_index]
        test_candles = candles[split_index:]
        train_actions = _actions_for_candles(actions, train_candles, args.interval)
        test_actions = _actions_for_candles(actions, test_candles, args.interval)
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
                actions=train_actions,
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
            actions=test_actions,
        )
        curve_path = reports_dir / f"{ticker.lower()}_{args.strategy}_{args.objective}_{args.price_mode}_{args.signal_mode}_{args.interval}_train_test_equity.csv"
        write_comparison_curve(strategy_curve, benchmark_curve, curve_path)
        rows.append(_train_test_row(train_summary, test_summary, best_params, args.objective))

    output = reports_dir / f"train_test_{args.strategy}_{args.objective}_{args.price_mode}_{args.signal_mode}_{args.interval}.csv"
    _write_train_test_csv(rows, output)
    _print_train_test_table(rows)
    print(f"\nTreino-teste salvo em: {output}")
    return 0


def _backtest_by_year_command(args: argparse.Namespace) -> int:
    rows: list[dict] = []
    reports_dir = Path(args.reports_dir)

    for ticker in args.tickers:
        full_candles = _load_or_fetch_for_backtest(ticker, args)
        actions = _load_actions_for_backtest(ticker, args)
        for year, candles in _iter_yearly_candle_windows(full_candles, args):
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
                actions=_actions_for_candles(actions, candles, args.interval),
            )
            rows.append({"year": year, **asdict(summary)})
            curve_path = (
                reports_dir
                / "yearly"
                / str(year)
                / f"{ticker.lower()}_{args.strategy}_{args.price_mode}_{args.signal_mode}_{args.interval}_{year}_equity.csv"
            )
            write_comparison_curve(strategy_curve, benchmark_curve, curve_path)

    output = reports_dir / f"summary_{args.strategy}_{args.price_mode}_{args.signal_mode}_{args.interval}_by_year.csv"
    _write_yearly_summary_csv(rows, output)
    _print_yearly_summary_table(rows)
    print(f"\nResumo anual salvo em: {output}")
    print(f"Curvas anuais salvas em: {reports_dir / 'yearly'}")
    return 0


def _sweep_by_year_command(args: argparse.Namespace) -> int:
    rows: list[dict] = []
    reports_dir = Path(args.reports_dir)

    for ticker in args.tickers:
        full_candles = _load_or_fetch_for_backtest(ticker, args)
        actions = _load_actions_for_backtest(ticker, args)
        for year, candles in _iter_yearly_candle_windows(full_candles, args):
            signal_candles = _signal_candles(candles, args.signal_mode)
            year_actions = _actions_for_candles(actions, candles, args.interval)
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
                    actions=year_actions,
                )
                rows.append(_summary_row(summary, params, year=year))

    rows.sort(key=lambda row: (row["ticker"], int(row["year"]), -float(row["excess_total_return"])))
    output = reports_dir / f"sweep_{args.strategy}_{args.price_mode}_{args.signal_mode}_{args.interval}_by_year.csv"
    _write_sweep_csv(rows, output)
    _print_sweep_table(rows, args.top)
    print(f"\nVarredura anual salva em: {output}")
    return 0


def _train_test_by_year_command(args: argparse.Namespace) -> int:
    rows: list[dict] = []
    reports_dir = Path(args.reports_dir)

    for ticker in args.tickers:
        full_candles = _load_or_fetch_for_backtest(ticker, args)
        actions = _load_actions_for_backtest(ticker, args)
        for year, candles in _iter_yearly_candle_windows(full_candles, args):
            try:
                split_index = _split_index(candles, args.train_ratio)
            except ValueError as error:
                print(f"Aviso: {ticker.upper()} {year} ignorado no treino-teste: {error}")
                continue

            year_actions = _actions_for_candles(actions, candles, args.interval)
            train_candles = candles[:split_index]
            test_candles = candles[split_index:]
            train_actions = _actions_for_candles(year_actions, train_candles, args.interval)
            test_actions = _actions_for_candles(year_actions, test_candles, args.interval)
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
                    actions=train_actions,
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
                actions=test_actions,
            )
            curve_path = (
                reports_dir
                / "yearly"
                / str(year)
                / f"{ticker.lower()}_{args.strategy}_{args.objective}_{args.price_mode}_{args.signal_mode}_{args.interval}_{year}_train_test_equity.csv"
            )
            write_comparison_curve(strategy_curve, benchmark_curve, curve_path)
            rows.append(_train_test_row(train_summary, test_summary, best_params, args.objective, year=year))

    output = reports_dir / f"train_test_{args.strategy}_{args.objective}_{args.price_mode}_{args.signal_mode}_{args.interval}_by_year.csv"
    _write_train_test_csv(rows, output)
    _print_train_test_table(rows)
    print(f"\nTreino-teste anual salvo em: {output}")
    return 0


def _load_or_fetch_for_backtest(ticker: str, args: argparse.Namespace):
    path = cache_path(ticker, args.interval, args.data_dir)
    if args.allow_unverified_data:
        if args.refresh_data or not path.exists():
            if Path(args.data_dir) == DEFAULT_DATA_DIR or Path(args.actions_dir) == DEFAULT_ACTIONS_DIR:
                raise DataVerificationError(
                    "A atualizacao legada nao pode sobrescrever a base oficial. Use "
                    f"--data-dir {DEFAULT_LEGACY_DATA_DIR} "
                    f"--actions-dir {DEFAULT_LEGACY_ACTIONS_DIR}."
                )
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
            raise DataVerificationError(
                f"Dados legados invalidos para {ticker}: {len(issues)} problemas; primeiro: {issues[0]}"
            )
        return candles

    if args.refresh_data:
        raise DataVerificationError(
            "--refresh-data usa a fonte legada e nao pode ser combinado com o modo seguro. "
            "Atualize com scripts/build_verified_market_data.py."
        )
    if not path.exists():
        raise DataVerificationError(
            f"Dados verificados ausentes para {ticker} {args.interval}: {path}. "
            "Execute scripts/build_verified_market_data.py."
        )
    candles, _manifest = load_verified_candles(
        ticker,
        args.interval,
        data_dir=args.data_dir,
        actions_dir=args.actions_dir,
        manifests_dir=args.manifests_dir,
        start=args.start,
        end=args.end,
        require_verified_actions=(
            args.price_mode == "raw_events" and not args.allow_unverified_actions
        ),
    )
    issues = validate_candles(candles)
    if issues:
        raise DataVerificationError(
            f"Recorte de dados invalido para {ticker}: {len(issues)} problemas; primeiro: {issues[0]}"
        )
    return candles


def _load_actions_for_backtest(ticker: str, args: argparse.Namespace):
    if args.price_mode != "raw_events":
        return []
    path = actions_path(ticker, args.actions_dir)
    if args.allow_unverified_data and not path.exists():
        fetch_and_cache(
            ticker,
            interval=args.interval,
            range_name="max",
            data_dir=args.data_dir,
            actions_dir=args.actions_dir,
            start=args.start,
            end=args.end,
        )
        return load_actions(path, start=args.start, end=args.end)
    if not path.exists():
        raise DataVerificationError(f"Eventos corporativos ausentes para {ticker}: {path}.")
    return load_actions(path, start=args.start, end=args.end)


def _iter_yearly_candle_windows(candles, args: argparse.Namespace):
    selected_years = set(args.years or [])
    grouped = split_candles_by_year(candles)
    missing_years = sorted(selected_years.difference(grouped))
    for year in missing_years:
        print(f"Aviso: ano {year} nao encontrado nos candles carregados.")

    for year, year_candles in grouped.items():
        if selected_years and year not in selected_years:
            continue
        if len(year_candles) < 2:
            ticker = year_candles[0].ticker if year_candles else "ticker"
            print(f"Aviso: {ticker} {year} ignorado: menos de 2 candles para backtest.")
            continue
        yield year, year_candles


def _actions_for_candles(actions, candles, interval: str):
    if not candles:
        return []
    start = date.fromisoformat(_date_part(candles[0].date))
    end = _action_window_end(candles[-1].date, interval)
    return [action for action in actions if start <= date.fromisoformat(action.date) <= end]


def _action_window_end(candle_date: str, interval: str) -> date:
    end = date.fromisoformat(_date_part(candle_date))
    if interval == "1wk":
        return end + timedelta(days=6)
    return end


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
                volume=candle.raw_volume,
                adjustment_factor=1.0,
            )
            for candle in candles
        ]
    raise ValueError("signal_mode precisa ser 'adjusted' ou 'raw'.")


def _strategy_params_from_args(args: argparse.Namespace) -> dict:
    strategy_name = args.strategy.strip().lower()
    if strategy_name == "sma":
        strategy_name = "sma_cross"
    documented = strategy_parameters(strategy_name)
    supported = inspect.signature(STRATEGIES[strategy_name]).parameters
    generic_values = {
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
    params = dict(documented)
    for name, value in generic_values.items():
        if value is not None and name in supported:
            params[name] = value

    overrides = getattr(args, "strategy_param", [])
    if not overrides:
        return params

    for item in overrides:
        if "=" not in item:
            raise ValueError(f"Parametro invalido: {item}. Use NOME=VALOR.")
        name, raw_value = (part.strip() for part in item.split("=", 1))
        if not name or name not in documented:
            available = ", ".join(documented) or "nenhum"
            raise ValueError(f"Parametro desconhecido para {strategy_name}: {name}. Disponiveis: {available}.")
        if name not in supported:
            raise ValueError(f"{strategy_name} e um preset fixo; o parametro {name} nao pode ser sobrescrito.")
        params[name] = _coerce_strategy_param(raw_value, documented[name], name)
    return params


def _coerce_strategy_param(raw_value: str, default: object, name: str) -> object:
    try:
        if isinstance(default, bool):
            normalized = raw_value.lower()
            if normalized in {"1", "true", "sim", "yes"}:
                return True
            if normalized in {"0", "false", "nao", "não", "no"}:
                return False
            raise ValueError
        if isinstance(default, int):
            return int(raw_value)
        if isinstance(default, float):
            return float(raw_value)
        return raw_value
    except ValueError as error:
        expected = type(default).__name__
        raise ValueError(f"Valor invalido para {name}: {raw_value} (esperado {expected}).") from error


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
        # Presets e estrategias pesquisadas entram na matriz com seus parametros
        # canonicos quando nao existe uma grade dedicada de otimizacao.
        yield strategy_parameters(args.strategy)


def _summary_row(summary: Summary, params: dict, *, year: int | None = None) -> dict:
    row = asdict(summary)
    if year is not None:
        row["year"] = year
    for field in PARAM_FIELDS:
        row[field] = params.get(field, "")
    return row


def _train_test_row(
    train_summary: Summary,
    test_summary: Summary,
    params: dict,
    objective: str,
    *,
    year: int | None = None,
) -> dict:
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
    if year is not None:
        row["year"] = year
    for field in PARAM_FIELDS:
        row[field] = params.get(field, "")
    return row


def _write_sweep_csv(rows: list[dict], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary_fields = [field for field in Summary.__dataclass_fields__ if field not in {"ticker", "strategy"}]
    prefix_fields = ["year"] if any("year" in row for row in rows) else []
    fields = [*prefix_fields, "ticker", "strategy", *PARAM_FIELDS, *summary_fields]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def _write_yearly_summary_csv(rows: list[dict], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["year", *Summary.__dataclass_fields__]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    return path


def _write_train_test_csv(rows: list[dict], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix_fields = ["year"] if any("year" in row for row in rows) else []
    fields = [
        *prefix_fields,
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
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
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


def _print_strategy_catalog() -> None:
    for family, strategies in strategies_by_family().items():
        print(f"\n{family}")
        rows = []
        for info in strategies:
            params = strategy_parameters(info.name)
            defaults = ", ".join(f"{key}={value}" for key, value in params.items()) if params else "-"
            rows.append([info.name, "sim" if info.sweepable else "nao", defaults, info.description])
        _print_table(["Estrategia", "Sweep", "Parametros padrao", "Descricao"], rows)


def _print_train_test_table(rows: list[dict]) -> None:
    if not rows:
        print("Nenhum resultado gerado.")
        return

    has_year = any("year" in row for row in rows)
    headers = [*(["Ano"] if has_year else []), "Ticker", "Params", "Treino", "Treino B&H", "Teste", "Teste B&H", "Excesso", "MDD", "Trades"]
    table_rows = []
    for row in rows:
        table_rows.append(
            [
                *([str(row["year"])] if has_year else []),
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

    has_year = any("year" in row for row in rows)
    headers = [*(["Ano"] if has_year else []), "Ticker", "Params", "Ret", "B&H", "Excesso", "MDD", "Trades", "Expos."]
    table_rows = []
    groups = sorted({(row.get("year", ""), row["ticker"]) for row in rows})
    for year, ticker in groups:
        ticker_rows = [row for row in rows if row["ticker"] == ticker and row.get("year", "") == year]
        for row in sorted(ticker_rows, key=lambda item: -float(item["excess_total_return"]))[:top]:
            table_rows.append(
                [
                    *([str(row["year"])] if has_year else []),
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


def _print_yearly_summary_table(rows: list[dict]) -> None:
    if not rows:
        print("Nenhum resultado gerado.")
        return

    headers = ["Ano", "Ticker", "Ret", "B&H", "Excesso", "CAGR", "MDD", "Trades", "Expos."]
    table_rows = []
    for row in sorted(rows, key=lambda item: (int(item["year"]), item["ticker"])):
        table_rows.append(
            [
                str(row["year"]),
                row["ticker"],
                _pct(float(row["total_return"])),
                _pct(float(row["benchmark_total_return"])),
                _pct(float(row["excess_total_return"])),
                _pct(float(row["cagr"])),
                _pct(float(row["max_drawdown"])),
                str(row["trades"]),
                _pct(float(row["exposure"])),
            ]
        )

    _print_table(headers, table_rows)


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


def _date_part(value: str) -> str:
    return value.split("T", 1)[0].split(" ", 1)[0]


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
