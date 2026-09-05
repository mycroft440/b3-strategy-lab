from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from b3_strategy_lab.cli import _signal_candles  # noqa: E402
from b3_strategy_lab.strategies import (  # noqa: E402
    build_signals,
    portfolio_strategies,
    strategy_parameters,
)
from scripts.research_portfolio_allocation import (  # noqa: E402
    MarketData,
    PortfolioConfig,
    PortfolioCurveRow,
    _configs,
    run_portfolio,
)


INITIAL_CASH = 1_000.0
DEFAULT_COST_BPS = 3.2
DEFAULT_SLIPPAGE_BPS = 10.0
DEFAULT_WORKERS = max(1, min(8, os.cpu_count() or 1))
DEFAULT_START = "2018-01-02"
DEFAULT_REPORT = Path(
    "reports/strategy_management_combinations_40_adjusted_no_dividends_1d.csv.gz"
)
DEFAULT_UNIVERSE_MANIFEST = Path("data/universes/point_in_time_union.json")
PIT_DATA_DIR = Path("data/candles_point_in_time")
PIT_ACTIONS_DIR = Path("data/actions_point_in_time")
PIT_MANIFESTS_DIR = Path("data/manifests_point_in_time")
PIT_SPLIT_EVIDENCE = Path("data/corporate_actions/point_in_time_split_evidence.json")
_WORKER_STATE: tuple | None = None


def _ranking_key(row: dict[str, object]) -> tuple[float, float, str, str]:
    return (
        -float(row["total_return"]),
        -float(row["cagr"]),
        str(row["trading_strategy"]),
        str(row["management_strategy"]),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Cruza todas as estrategias compradas com todos os gerenciamentos de carteira. "
            "Usa sinais no fechamento, execucao na abertura seguinte e ignora dividendos/JCP."
        ),
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        help="Sobrescreve os tickers, que ainda precisam coincidir com --universe-manifest.",
    )
    parser.add_argument(
        "--universe-manifest",
        type=Path,
        default=DEFAULT_UNIVERSE_MANIFEST,
        help="Manifesto survivorship-safe point-in-time com snapshots historicos.",
    )
    parser.add_argument("--data-dir", type=Path, default=PIT_DATA_DIR)
    parser.add_argument("--actions-dir", type=Path, default=PIT_ACTIONS_DIR)
    parser.add_argument("--manifests-dir", type=Path, default=PIT_MANIFESTS_DIR)
    parser.add_argument("--split-evidence", type=Path, default=PIT_SPLIT_EVIDENCE)
    parser.add_argument("--strategies", nargs="+", default=portfolio_strategies())
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end")
    parser.add_argument("--signal-mode", choices=["raw", "adjusted"], default="adjusted")
    parser.add_argument(
        "--config-set",
        choices=["all", "base", "roc", "roc_hybrid", "roc_filter_short"],
        default="all",
    )
    parser.add_argument("--initial-cash", type=float, default=INITIAL_CASH)
    parser.add_argument("--cost-bps", type=float, default=DEFAULT_COST_BPS)
    parser.add_argument("--slippage-bps", type=float, default=DEFAULT_SLIPPAGE_BPS)
    parser.add_argument("--lot-size", type=int, default=1)
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=(
            f"Processos paralelos por estrategia (padrao seguro: {DEFAULT_WORKERS}; "
            "use 1 para execucao serial reproduzivel)."
        ),
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--allow-unverified-data", action="store_true")
    args = parser.parse_args(argv)

    if not math.isfinite(args.initial_cash) or args.initial_cash <= 0:
        parser.error("--initial-cash precisa ser maior que zero.")
    if (
        not math.isfinite(args.cost_bps)
        or not math.isfinite(args.slippage_bps)
        or args.cost_bps < 0
        or args.slippage_bps < 0
    ):
        parser.error("Custos e slippage precisam ser finitos e nao negativos.")
    if args.slippage_bps >= 10_000:
        parser.error("--slippage-bps precisa ser menor que 10000.")
    if args.lot_size < 0:
        parser.error("--lot-size nao pode ser negativo.")
    if args.top <= 0:
        parser.error("--top precisa ser maior que zero.")
    if args.workers <= 0:
        parser.error("--workers precisa ser maior que zero.")
    if args.workers > (os.cpu_count() or 1):
        parser.error("--workers nao pode exceder a quantidade de CPUs disponiveis.")
    try:
        start_date = date.fromisoformat(args.start)
        end_date = date.fromisoformat(args.end) if args.end else None
    except ValueError:
        parser.error("--start e --end precisam usar datas ISO no formato AAAA-MM-DD.")
    if end_date is not None and start_date > end_date:
        parser.error("--start nao pode ser posterior a --end.")

    strategies = [strategy.strip().lower() for strategy in args.strategies]
    if not strategies or any(not strategy for strategy in strategies):
        parser.error("Informe pelo menos uma estrategia valida.")
    duplicates = sorted(
        {strategy for strategy in strategies if strategies.count(strategy) > 1}
    )
    if duplicates:
        parser.error("Estrategias duplicadas: " + ", ".join(duplicates))
    supported_strategies = set(portfolio_strategies())
    unknown = sorted(set(strategies) - supported_strategies)
    if unknown:
        parser.error("Estrategias fora do catalogo: " + ", ".join(unknown))

    universe = _load_universe(args.universe_manifest)
    manifest_tickers = [str(ticker).upper() for ticker in universe["tickers"]]
    tickers = [ticker.upper() for ticker in (args.tickers or manifest_tickers)]
    if tickers != manifest_tickers:
        parser.error(
            "--tickers diverge da uniao historica do --universe-manifest; "
            "o universo PIT nao pode ser sobrescrito silenciosamente."
        )
    selected_as_of = date.fromisoformat(str(universe["selected_as_of"]))
    selection_end = date.fromisoformat(str(universe["selection_end"]))
    if start_date < selected_as_of:
        parser.error(
            f"--start nao pode anteceder selected_as_of={selected_as_of.isoformat()} "
            "do universo point-in-time."
        )
    if end_date is not None and end_date > selection_end:
        parser.error(
            f"--end nao pode exceder selection_end={selection_end.isoformat()} "
            "do universo point-in-time."
        )
    data = MarketData(
        tickers,
        args.interval,
        args.signal_mode,
        allow_unverified_data=args.allow_unverified_data,
        require_verified_splits_from=universe["warmup_start"],
        history_start=str(universe["warmup_start"]),
        data_dir=args.data_dir,
        actions_dir=args.actions_dir,
        manifests_dir=args.manifests_dir,
        split_evidence_path=args.split_evidence,
    )
    requested_end = args.end or selection_end.isoformat()
    dates = [value for value in data.dates if args.start <= value <= requested_end]
    if len(dates) < 3:
        raise ValueError("Periodo de mercado insuficiente para executar o backtest.")
    args.start = dates[0]
    end = dates[-1]
    universe_membership = _load_point_in_time_membership(universe, data.dates)

    signals_by_strategy = _build_eligibility(
        data,
        strategies,
        args.signal_mode,
        signal_start=str(universe["warmup_start"]),
    )
    configs = _configs(args.signal_mode, args.config_set)
    if len({config.name for config in configs}) != len(configs):
        raise ValueError("O catalogo de gerenciamento contem nomes duplicados.")
    total = len(strategies) * len(configs)
    started = time.perf_counter()
    rows: list[dict[str, object]] = []

    if args.workers == 1:
        for strategy_index, strategy in enumerate(strategies, start=1):
            rows.extend(
                _strategy_rows(
                    data,
                    configs,
                    strategy,
                    signals_by_strategy[strategy],
                    strategy_parameters(strategy),
                    universe_membership=universe_membership,
                    start=args.start,
                    end=end,
                    initial_cash=args.initial_cash,
                    cost_bps=args.cost_bps,
                    slippage_bps=args.slippage_bps,
                    lot_size=args.lot_size,
                )
            )
            _print_progress(strategy_index, len(strategies), len(configs), total, started)
    else:
        initargs = (
            data,
            configs,
            universe_membership,
            args.start,
            end,
            args.initial_cash,
            args.cost_bps,
            args.slippage_bps,
            args.lot_size,
        )
        with ProcessPoolExecutor(
            max_workers=args.workers,
            initializer=_initialize_worker,
            initargs=initargs,
        ) as executor:
            futures = {
                executor.submit(
                    _worker_strategy_rows,
                    strategy,
                    signals_by_strategy[strategy],
                    strategy_parameters(strategy),
                ): strategy
                for strategy in strategies
            }
            for strategy_index, future in enumerate(as_completed(futures), start=1):
                rows.extend(future.result())
                _print_progress(strategy_index, len(strategies), len(configs), total, started)

    rows.sort(key=_ranking_key)
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank

    config_by_name = {config.name: config for config in configs}
    annual_sections = _top_annual_sections(
        rows[: args.top],
        data=data,
        configs=config_by_name,
        signals_by_strategy=signals_by_strategy,
        universe_membership=universe_membership,
        start=args.start,
        end=end,
        initial_cash=args.initial_cash,
        cost_bps=args.cost_bps,
        slippage_bps=args.slippage_bps,
        lot_size=args.lot_size,
    )

    _write_results(rows, args.output)
    report_base = _report_base(args.output)
    annual_path = report_base.with_name(f"{report_base.name}_top{args.top}_annual.md")
    _write_annual_report(annual_sections, annual_path)
    _write_manifest(
        report_base.with_suffix(".manifest.json"),
        args=args,
        tickers=tickers,
        strategies=strategies,
        configs=configs,
        start=args.start,
        end=end,
        combinations=total,
        elapsed_seconds=time.perf_counter() - started,
        universe=universe,
        data=data,
    )
    _print_top(rows[: args.top])
    return 0


def _build_eligibility(
    data: MarketData,
    strategies: list[str],
    signal_mode: str,
    *,
    signal_start: str | None = None,
) -> dict[str, dict[str, list[int]]]:
    result: dict[str, dict[str, list[int]]] = {}
    for strategy in strategies:
        params = strategy_parameters(strategy)
        by_ticker: dict[str, list[int]] = {}
        for ticker in data.tickers:
            candles = data.candles[ticker]
            first_index = next(
                (
                    index
                    for index, candle in enumerate(candles)
                    if signal_start is None or candle.date >= signal_start
                ),
                len(candles),
            )
            verified_window = candles[first_index:]
            window_signals = build_signals(
                strategy,
                _signal_candles(verified_window, signal_mode),
                session_calendar=[
                    value
                    for value in data.dates
                    if signal_start is None or value >= signal_start
                ],
                **params,
            )
            signals = [0] * first_index + window_signals
            if len(signals) != len(candles):
                raise ValueError(f"{strategy}/{ticker}: quantidade de sinais invalida.")
            if any(signal not in (0, 1) for signal in signals):
                raise ValueError(f"{strategy}/{ticker}: sinal fora de 0/1.")
            by_ticker[ticker] = signals
        result[strategy] = by_ticker
    return result


def _initialize_worker(
    data: MarketData,
    configs: list[PortfolioConfig],
    universe_membership: dict[str, set[str]],
    start: str,
    end: str,
    initial_cash: float,
    cost_bps: float,
    slippage_bps: float,
    lot_size: int,
) -> None:
    global _WORKER_STATE
    _WORKER_STATE = (
        data,
        configs,
        universe_membership,
        start,
        end,
        initial_cash,
        cost_bps,
        slippage_bps,
        lot_size,
    )


def _worker_strategy_rows(
    strategy: str,
    eligibility: dict[str, list[int]],
    params: dict[str, object],
) -> list[dict[str, object]]:
    if _WORKER_STATE is None:
        raise RuntimeError("Worker da matriz nao foi inicializado.")
    (
        data,
        configs,
        universe_membership,
        start,
        end,
        initial_cash,
        cost_bps,
        slippage_bps,
        lot_size,
    ) = _WORKER_STATE
    return _strategy_rows(
        data,
        configs,
        strategy,
        eligibility,
        params,
        universe_membership=universe_membership,
        start=start,
        end=end,
        initial_cash=initial_cash,
        cost_bps=cost_bps,
        slippage_bps=slippage_bps,
        lot_size=lot_size,
    )


def _strategy_rows(
    data: MarketData,
    configs: list[PortfolioConfig],
    strategy: str,
    eligibility: dict[str, list[int]],
    params: dict[str, object],
    *,
    universe_membership: dict[str, set[str]],
    start: str,
    end: str,
    initial_cash: float,
    cost_bps: float,
    slippage_bps: float,
    lot_size: int,
) -> list[dict[str, object]]:
    rows = []
    params_text = _params_text(params)
    for config in configs:
        summary, _ = run_portfolio(
            data,
            config,
            start=start,
            end=end,
            initial_cash=initial_cash,
            cost_bps=cost_bps,
            slippage_bps=slippage_bps,
            lot_size=lot_size,
            eligibility=eligibility,
            universe_membership=universe_membership,
            collect_curve=False,
        )
        rows.append(
            {
                "trading_strategy": strategy,
                "strategy_params": params_text,
                "management_strategy": config.name,
                "start": summary.start,
                "end": summary.end,
                "candles": summary.candles,
                "trades": summary.trades,
                "exposure": summary.exposure,
                "avg_positions": summary.avg_positions,
                "initial_equity": initial_cash,
                "final_equity": summary.final_equity,
                "total_return": summary.total_return,
                "cagr": summary.cagr,
                "average_annual_return": summary.average_annual_return,
                "max_drawdown": summary.max_drawdown,
                "annual_volatility": summary.annual_volatility,
                "sharpe": summary.sharpe,
                "turnover": summary.turnover,
            }
        )
    return rows


def _print_progress(
    strategy_index: int,
    strategy_count: int,
    config_count: int,
    total: int,
    started: float,
) -> None:
    completed = strategy_index * config_count
    elapsed = time.perf_counter() - started
    print(
        f"{strategy_index}/{strategy_count} estrategias; "
        f"{completed}/{total} combinacoes; {elapsed:.1f}s",
        flush=True,
    )


def _top_annual_sections(
    rows: list[dict[str, object]],
    *,
    data: MarketData,
    configs: dict[str, PortfolioConfig],
    signals_by_strategy: dict[str, dict[str, list[int]]],
    universe_membership: dict[str, set[str]],
    start: str,
    end: str,
    initial_cash: float,
    cost_bps: float,
    slippage_bps: float,
    lot_size: int,
) -> list[dict[str, object]]:
    sections = []
    for row in rows:
        strategy = str(row["trading_strategy"])
        config = configs[str(row["management_strategy"])]
        summary, curve = run_portfolio(
            data,
            config,
            start=start,
            end=end,
            initial_cash=initial_cash,
            cost_bps=cost_bps,
            slippage_bps=slippage_bps,
            lot_size=lot_size,
            eligibility=signals_by_strategy[strategy],
            universe_membership=universe_membership,
            collect_curve=True,
        )
        yearly = _yearly_returns(curve, initial_cash)
        sections.append(
            {
                "rank": row["rank"],
                "trading_strategy": strategy,
                "management_strategy": config.name,
                "yearly": yearly,
                "average": summary.average_annual_return,
            }
        )
    return sections


def _yearly_returns(
    curve: list[PortfolioCurveRow],
    initial_equity: float,
) -> dict[int, float]:
    year_ends: dict[int, float] = {}
    for point in curve:
        year = int(point.date[:4])
        year_ends[year] = point.equity

    result: dict[int, float] = {}
    prior_equity = initial_equity
    for year, end_equity in year_ends.items():
        result[year] = end_equity / prior_equity - 1 if prior_equity > 0 else 0.0
        prior_equity = end_equity
    return result


def _write_results(rows: list[dict[str, object]], output: Path) -> None:
    fields = [
        "rank",
        "trading_strategy",
        "strategy_params",
        "management_strategy",
        "start",
        "end",
        "candles",
        "trades",
        "exposure",
        "avg_positions",
        "initial_equity",
        "final_equity",
        "total_return",
        "cagr",
        "average_annual_return",
        "max_drawdown",
        "annual_volatility",
        "sharpe",
        "turnover",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    if output.suffix == ".gz":
        with temporary.open("wb") as raw:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=raw,
                compresslevel=9,
                mtime=0,
            ) as compressed:
                with io.TextIOWrapper(
                    compressed, encoding="utf-8", newline=""
                ) as file:
                    _write_csv_rows(file, fields, rows)
    else:
        with temporary.open("w", newline="", encoding="utf-8") as file:
            _write_csv_rows(file, fields, rows)
    temporary.replace(output)
    print(f"Salvo: {output} ({len(rows)} combinacoes)", flush=True)


def _write_csv_rows(
    file: io.TextIOBase,
    fields: list[str],
    rows: list[dict[str, object]],
) -> None:
    writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows([{field: row.get(field, "") for field in fields} for row in rows])


def _report_base(path: Path) -> Path:
    if path.suffixes[-2:] == [".csv", ".gz"]:
        return path.with_suffix("").with_suffix("")
    return path.with_suffix("")


def _write_annual_report(sections: list[dict[str, object]], output: Path) -> None:
    lines = ["# Resultados anuais das melhores combinacoes", ""]
    for section in sections:
        lines.extend(
            [
                (
                    f"## {section['rank']}. {section['trading_strategy']} + "
                    f"{section['management_strategy']}"
                ),
                "",
                "| Ano | Retorno |",
                "|---:|---:|",
            ]
        )
        for year, value in dict(section["yearly"]).items():
            lines.append(f"| {year} | {value:.2%} |")
        lines.extend(
            [
                "",
                f"Media dos anos-calendario completos: {float(section['average']):.2%}",
                "",
            ]
        )
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text("\n".join(lines), encoding="utf-8")
    temporary.replace(output)
    print(f"Relatorio anual: {output}", flush=True)


def _write_manifest(
    output: Path,
    *,
    args: argparse.Namespace,
    tickers: list[str],
    strategies: list[str],
    configs: list[PortfolioConfig],
    start: str,
    end: str,
    combinations: int,
    elapsed_seconds: float,
    universe: dict[str, object],
    data: MarketData,
) -> None:
    commit, dirty = _git_state()
    catalog_strategies = portfolio_strategies()
    catalog_configs = _configs(args.signal_mode, "all")
    catalog_complete = (
        set(strategies) == set(catalog_strategies)
        and len(strategies) == len(catalog_strategies)
        and {config.name for config in configs}
        == {config.name for config in catalog_configs}
    )
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "git_dirty": dirty,
        "git_dirty_scope": "calculation_sources_and_workflows_excluding_hashed_market_data",
        "source_sha256": {
            "b3_strategy_lab/backtest.py": _sha256_file(
                PROJECT_ROOT / "b3_strategy_lab/backtest.py"
            ),
            "b3_strategy_lab/candles.py": _sha256_file(
                PROJECT_ROOT / "b3_strategy_lab/candles.py"
            ),
            "b3_strategy_lab/cli.py": _sha256_file(
                PROJECT_ROOT / "b3_strategy_lab/cli.py"
            ),
            "b3_strategy_lab/cotahist.py": _sha256_file(
                PROJECT_ROOT / "b3_strategy_lab/cotahist.py"
            ),
            "b3_strategy_lab/point_in_time.py": _sha256_file(
                PROJECT_ROOT / "b3_strategy_lab/point_in_time.py"
            ),
            "scripts/build_survivorship_safe_realistic_universe.py": _sha256_file(
                PROJECT_ROOT / "scripts/build_survivorship_safe_realistic_universe.py"
            ),
            "b3_strategy_lab/strategies.py": _sha256_file(
                PROJECT_ROOT / "b3_strategy_lab/strategies.py"
            ),
            "b3_strategy_lab/extensions.py": _sha256_file(
                PROJECT_ROOT / "b3_strategy_lab/extensions.py"
            ),
            "b3_strategy_lab/portfolio_risk.py": _sha256_file(
                PROJECT_ROOT / "b3_strategy_lab/portfolio_risk.py"
            ),
            "b3_strategy_lab/research_indicators.py": _sha256_file(
                PROJECT_ROOT / "b3_strategy_lab/research_indicators.py"
            ),
            "b3_strategy_lab/indicator_strategies.py": _sha256_file(
                PROJECT_ROOT / "b3_strategy_lab/indicator_strategies.py"
            ),
            "b3_strategy_lab/trend_strategies.py": _sha256_file(
                PROJECT_ROOT / "b3_strategy_lab/trend_strategies.py"
            ),
            "b3_strategy_lab/user_extensions.py": _sha256_file(
                PROJECT_ROOT / "b3_strategy_lab/user_extensions.py"
            ),
            "b3_strategy_lab/additional_strategies.py": _sha256_file(
                PROJECT_ROOT / "b3_strategy_lab/additional_strategies.py"
            ),
            "b3_strategy_lab/researched_strategies.py": _sha256_file(
                PROJECT_ROOT / "b3_strategy_lab/researched_strategies.py"
            ),
            "b3_strategy_lab/extended_strategies.py": _sha256_file(
                PROJECT_ROOT / "b3_strategy_lab/extended_strategies.py"
            ),
            "scripts/backtest_strategy_management_combinations.py": _sha256_file(
                Path(__file__)
            ),
            "scripts/research_portfolio_allocation.py": _sha256_file(
                PROJECT_ROOT / "scripts/research_portfolio_allocation.py"
            ),
            "scripts/research_portfolio_allocation_core.py": _sha256_file(
                PROJECT_ROOT / "scripts/research_portfolio_allocation_core.py"
            ),
        },
        "universe": {
            "manifest": str(args.universe_manifest),
            "sha256": _sha256_file(args.universe_manifest),
            "id": universe["id"],
            "selection_mode": universe["selection_mode"],
            "selected_as_of": universe["selected_as_of"],
            "selection_end": universe["selection_end"],
            "warmup_start": universe["warmup_start"],
            "survivorship_safe": universe["survivorship_safe"],
            "point_in_time": universe["point_in_time"],
            "snapshot_file": universe["snapshot_file"],
            "snapshot_sha256": _sha256_file(_snapshot_path(universe)),
            "bias_disclosure": universe["bias_disclosure"],
        },
        "market_data_paths": {
            "data_dir": str(args.data_dir),
            "actions_dir": str(args.actions_dir),
            "manifests_dir": str(args.manifests_dir),
            "split_evidence": str(args.split_evidence),
        },
        "universe_selection_policy": "latest_snapshot_at_or_before_decision_close_no_future_backfill",
        "datasets": {
            ticker: {
                "status": manifest.status,
                "start": manifest.start,
                "end": manifest.end,
                "candle_sha256": manifest.candle_sha256,
                "split_action_status": manifest.split_action_status,
                "split_verified_from": manifest.split_verified_from,
                "split_evidence_sha256": manifest.split_evidence_sha256,
            }
            for ticker, manifest in sorted(data.manifests.items())
        },
        "tickers": tickers,
        "strategy_count": len(strategies),
        "strategies": strategies,
        "management_count": len(configs),
        "management_configs": [asdict(config) for config in configs],
        "combinations": combinations,
        "combination_identity": (
            "unique strategy-name x management-parameterization pairs; "
            "behavioral uniqueness is not claimed"
        ),
        "behavioral_uniqueness_claimed": False,
        "catalog_complete": catalog_complete,
        "catalog_strategy_count": len(catalog_strategies),
        "catalog_management_count": len(catalog_configs),
        "catalog_combination_count": len(catalog_strategies) * len(catalog_configs),
        "interval": args.interval,
        "start": start,
        "end": end,
        "signal_mode": args.signal_mode,
        "signal_history_start": universe["warmup_start"],
        "management_history_start": universe["warmup_start"],
        "allow_unverified_data": args.allow_unverified_data,
        "execution_price_mode": "split_normalized_open_next_candle",
        "mark_price_mode": "split_normalized_close",
        "dividends_jcp": "excluded",
        "initial_cash": args.initial_cash,
        "cost_bps": args.cost_bps,
        "slippage_bps": args.slippage_bps,
        "lot_size": args.lot_size,
        "ranking": "total_return_desc_then_cagr_desc_then_strategy_management_asc",
        "signal_execution_policy": (
            "designated_basket_binary_signal_changes_execute_next_open_"
            "without_intraperiod_reranking"
        ),
        "signal_calendar_policy": (
            "verified_global_market_sessions_independent_of_ticker_price_path"
        ),
        "initial_entry_policy": (
            "prior_close_decision_executes_at_first_open_when_start_is_"
            "rebalance_boundary"
        ),
        "execution_missing_price_policy": "fail_closed_fresh_open_and_close_required",
        "buy_allocation_policy": "target_shares_at_market_open_then_common_scale_for_costs",
        "evaluation_scope": "full_period",
        "train_ratio_applied": False,
        "result_classification": "RETROSPECTIVE_PRICE_ONLY_RESEARCH",
        "real_money_claim_allowed": False,
        "limitations": [
            "strategy_and_management_selected_on_the_same_full_period",
            "dividends_and_jcp_excluded",
            "taxes_excluded",
            "standard_market_open_used_for_integer_share_research_execution",
        ],
        "final_valuation": "liquidated_at_last_verified_close_with_costs_and_slippage",
        "workers": args.workers,
        "elapsed_seconds": elapsed_seconds,
    }
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(output)
    print(f"Manifesto: {output}", flush=True)


def _snapshot_path(universe: dict[str, object]) -> Path:
    path = Path(str(universe["snapshot_file"]))
    return path if path.is_absolute() else PROJECT_ROOT / path


def _load_point_in_time_membership(
    universe: dict[str, object],
    market_dates: list[str],
) -> dict[str, set[str]]:
    path = _snapshot_path(universe)
    if not path.exists():
        raise FileNotFoundError(f"Snapshot point-in-time ausente: {path}")
    selectable = {str(ticker).strip().upper() for ticker in universe["tickers"]}
    rules = universe.get("selection_rules")
    expected_size = int(rules.get("weekly_candidates", 0)) if isinstance(rules, dict) else 0
    snapshots: dict[str, list[tuple[int, str]]] = {}
    with path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        required = {"effective_date", "ticker", "rank"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"Snapshot PIT sem colunas obrigatorias {sorted(required)}: {path}")
        for row in reader:
            effective_date = date.fromisoformat(str(row["effective_date"])).isoformat()
            ticker = str(row["ticker"]).strip().upper()
            rank = int(row["rank"])
            if ticker not in selectable:
                raise ValueError(f"Snapshot PIT contem ticker fora da uniao historica: {ticker}")
            snapshots.setdefault(effective_date, []).append((rank, ticker))
    if not snapshots:
        raise ValueError("Snapshot point-in-time vazio.")
    selection_end = str(universe["selection_end"])
    selected_as_of = str(universe["selected_as_of"])
    normalized: list[tuple[str, set[str]]] = []
    for effective_date in sorted(snapshots):
        if effective_date < selected_as_of or effective_date > selection_end:
            raise ValueError(
                f"Snapshot PIT fora da janela declarada: {effective_date} not in "
                f"{selected_as_of}..{selection_end}"
            )
        rows = sorted(snapshots[effective_date])
        ranks = [rank for rank, _ in rows]
        tickers = [ticker for _, ticker in rows]
        if len(set(tickers)) != len(tickers):
            raise ValueError(f"Snapshot PIT possui ticker duplicado em {effective_date}.")
        if ranks != list(range(1, len(rows) + 1)):
            raise ValueError(f"Snapshot PIT possui ranking nao sequencial em {effective_date}.")
        if expected_size and len(rows) != expected_size:
            raise ValueError(
                f"Snapshot PIT {effective_date} tem {len(rows)} ativos; esperado {expected_size}."
            )
        normalized.append((effective_date, set(tickers)))

    membership: dict[str, set[str]] = {}
    snapshot_index = 0
    active: set[str] = set()
    for market_date in sorted(market_dates):
        while (
            snapshot_index < len(normalized)
            and normalized[snapshot_index][0] <= market_date
        ):
            active = set(normalized[snapshot_index][1])
            snapshot_index += 1
        # Deliberately empty before the first historical snapshot: a future
        # composition must never be backfilled into earlier decisions.
        membership[market_date] = set(active)
    return membership


def _load_universe(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "id",
        "selection_mode",
        "selected_as_of",
        "selection_end",
        "warmup_start",
        "survivorship_safe",
        "point_in_time",
        "snapshot_file",
        "bias_disclosure",
        "selection_rules",
        "tickers",
    }
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"Manifesto de universo PIT incompleto: {missing}.")
    if int(payload["schema_version"]) < 8:
        raise ValueError("A matriz exige schema PIT >= 8; universo fixo legado foi desativado.")
    if payload["survivorship_safe"] is not True or payload["point_in_time"] is not True:
        raise ValueError(
            "A matriz de pesquisa exige survivorship_safe=true e point_in_time=true; "
            "universos fixos retrospectivos nao sao mais aceitos."
        )
    selected_as_of = date.fromisoformat(str(payload["selected_as_of"]))
    selection_end = date.fromisoformat(str(payload["selection_end"]))
    warmup_start = date.fromisoformat(str(payload["warmup_start"])[:10])
    if warmup_start >= selected_as_of or selected_as_of > selection_end:
        raise ValueError("Janela temporal invalida no manifesto PIT.")
    tickers = [str(ticker).strip().upper() for ticker in payload["tickers"]]
    if not tickers or len(tickers) != len(set(tickers)):
        raise ValueError("Uniao historica de tickers invalida no manifesto PIT.")
    payload["tickers"] = tickers
    rules = payload["selection_rules"]
    if not isinstance(rules, dict):
        raise ValueError("selection_rules invalido no manifesto PIT.")
    if rules.get("future_continuity_filter") is not False:
        raise ValueError("O universo PIT nao pode exigir sobrevivencia/continuidade futura.")
    if rules.get("future_return_filter") is not False:
        raise ValueError("O universo PIT nao pode usar retornos futuros na selecao.")
    if int(rules.get("weekly_candidates", 0)) <= 0:
        raise ValueError("weekly_candidates precisa ser positivo no manifesto PIT.")
    snapshot = _snapshot_path(payload)
    if not snapshot.exists():
        raise FileNotFoundError(f"Snapshot PIT declarado nao existe: {snapshot}")
    return payload


def _git_state() -> tuple[str, bool]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        status = subprocess.check_output(
            [
                "git",
                "status",
                "--porcelain",
                "--untracked-files=all",
                "--",
                "b3_strategy_lab",
                "scripts",
                ".github/workflows",
            ],
            cwd=PROJECT_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return commit, bool(status.strip())
    except (OSError, subprocess.CalledProcessError):
        return "", True


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _params_text(params: dict[str, object]) -> str:
    return ";".join(f"{key}={value}" for key, value in params.items())


def _print_top(rows: list[dict[str, object]]) -> None:
    print("\nTop combinacoes por retorno total composto")
    for row in rows:
        print(
            f"{int(row['rank']):02d}. {row['trading_strategy']} + "
            f"{row['management_strategy']} | "
            f"ret={float(row['total_return']):.2%} "
            f"media anual={float(row['average_annual_return']):.2%} "
            f"CAGR={float(row['cagr']):.2%}",
            flush=True,
        )


if __name__ == "__main__":
    raise SystemExit(main())
