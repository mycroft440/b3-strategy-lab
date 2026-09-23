"""Ranking fora da amostra das estrategias no motor estrito (Nivel 1 - pesquisa).

Protocolo:
1. Para cada estrategia, o gerenciamento e escolhido somente no treino.
2. O par estrategia + gerenciamento do protocolo e o melhor do treino entre todas as
   estrategias. Apenas o teste desse par estima o resultado da selecao fora da amostra.
3. A ordem pelo teste e descritiva. Escolher a primeira linha pelo teste e selecao no
   holdout entre varios candidatos, nao validacao.

Cada linha declara seus limites: universo fixo com vies de selecao/sobrevivencia,
precos normalizados por splits sem dividendos/JCP, sem imposto de renda e lote de uma
acao sobre o preco normalizado. Valores de dinheiro real exigem o motor realista
(docs/realistic_backtest_methodology.md).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.benchmarks import benchmark_comparison, load_daily_benchmark  # noqa: E402
from b3_strategy_lab.strategies import STRATEGIES  # noqa: E402
from scripts.backtest_strategy_management_combinations import _build_eligibility  # noqa: E402
from scripts.backtest_strategy_management_strict import _metric, common_dates, run_strict  # noqa: E402
from scripts.research_portfolio_allocation import MarketData, _configs  # noqa: E402

DEFAULT_UNIVERSE = ROOT / "data/universes/fixed_40_2018.json"
DEFAULT_BENCHMARK = ROOT / "data/benchmarks/cdi.csv"
DEFAULT_CSV = ROOT / "reports/ranking_estrategias_realista.csv"
DEFAULT_MD = ROOT / "reports/ranking_estrategias_realista.md"
MARKET_BASELINE_CONFIG = "equal_all_monthly_adjusted"
ECONOMIC_SCOPE = "strict_level1_split_adjusted_no_dividends_no_income_tax"
ALPHA = 0.05

CANONICAL_25_STRATEGIES = [
    # Benchmark
    "buy_and_hold",
    # Tendencia
    "sma_cross",
    "ema_cross",
    "price_sma",
    "macd",
    "sma_stop",
    "donchian_40_20_trend",
    "frama_trend",
    # Momentum
    "momentum",
    "roc_trend",
    "time_series_momentum_3m",
    "time_series_momentum_6m",
    # Reversao a media
    "rsi_reversion",
    "bollinger_reversion",
    "connors_rsi_reversion",
    "ibs_reversion",
    "rsi2_trend_reversion",
    # Rompimento
    "breakout",
    "atr_breakout",
    "keltner_breakout",
    "range_expansion_breakout",
    # Volume e Fluxo
    "chaikin_money_flow",
    "mfi_reversal",
    # Sazonalidade
    "turn_of_month",
    # Gap / Microestrutura
    "gap_momentum",
]


def universe_known_from(universe: dict[str, object]) -> str:
    """First date on which the fixed universe could have been known."""
    rules = universe.get("selection_rules", {})
    liquidity_year = rules.get("liquidity_year") if isinstance(rules, dict) else None
    if isinstance(liquidity_year, int):
        return f"{liquidity_year + 1:04d}-01-01"
    return str(universe.get("selected_as_of", ""))


def one_sided_pvalue(t_stat: float) -> float:
    """Normal approximation of P(T >= t) for iid daily excess returns."""
    return 0.5 * math.erfc(t_stat / math.sqrt(2.0))


def excess_statistics(
    curve: list[tuple[str, float]],
    initial_cash: float,
    benchmark: dict[str, float] | None,
) -> dict[str, float | None]:
    empty = {
        "cdi_total_return": None,
        "excess_total_return_vs_cdi": None,
        "excess_sharpe_vs_cdi": None,
        "excess_t_stat": None,
        "excess_pvalue_one_sided": None,
    }
    if benchmark is None:
        return empty
    dates = [day for day, _ in curve]
    equities = [equity for _, equity in curve]
    comparison = benchmark_comparison(dates, equities, initial_cash, benchmark)
    # benchmark_comparison annualizes with n / years, so t = sharpe * sqrt(years).
    years = ((date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days + 1) / 365.25
    t_stat = comparison["excess_sharpe"] * math.sqrt(years)
    return {
        "cdi_total_return": comparison["benchmark_total_return"],
        "excess_total_return_vs_cdi": comparison["excess_total_return"],
        "excess_sharpe_vs_cdi": comparison["excess_sharpe"],
        "excess_t_stat": t_stat,
        "excess_pvalue_one_sided": one_sided_pvalue(t_stat),
    }


def classify_reading(
    test_total_return: float,
    excess_total_return: float | None,
    pvalue_bonferroni: float | None,
) -> str:
    if test_total_return < 0:
        return "PERDA NO TESTE"
    if excess_total_return is None or pvalue_bonferroni is None:
        return "SEM BENCHMARK"
    if excess_total_return <= 0:
        return "ABAIXO DO CDI"
    if pvalue_bonferroni < ALPHA:
        return "ACIMA DO CDI (SIGNIFICATIVO APOS BONFERRONI)"
    return "ACIMA DO CDI (NAO SIGNIFICATIVO)"


def _cagr(total_return: float, start: str, end: str) -> float:
    years = (date.fromisoformat(end) - date.fromisoformat(start)).days / 365.25
    if years <= 0 or total_return <= -1:
        return -1.0 if total_return <= -1 else 0.0
    return (1 + total_return) ** (1 / years) - 1


def run_ranking(
    strategies: list[str],
    *,
    start: str = "2018-01-02",
    train_end: str = "2022-12-29",
    test_start: str = "2023-01-02",
    end: str | None = None,
    initial_cash: float = 1000.0,
    cost_bps: float = 3.2,
    slippage_bps: float = 10.0,
    lot_size: int = 1,
    config_set: str = "base",
    objective: str = "cagr",
    universe_path: Path = DEFAULT_UNIVERSE,
    benchmark_path: Path | None = DEFAULT_BENCHMARK,
) -> dict[str, object]:
    if not start <= train_end < test_start:
        raise ValueError("Exija start <= train_end < test_start.")
    universe = json.loads(universe_path.read_text(encoding="utf-8"))
    known_from = universe_known_from(universe)
    if known_from and test_start < known_from:
        raise ValueError(
            f"O universo so poderia ser conhecido a partir de {known_from}; "
            f"test_start={test_start} usaria informacao futura."
        )
    tickers = [str(item).upper() for item in universe["tickers"]]
    survivorship_safe = bool(universe.get("survivorship_safe", False))
    validity = "OUT_OF_SAMPLE_SELECTION__BIASED_UNIVERSE" if not survivorship_safe else "OUT_OF_SAMPLE"
    benchmark = (
        load_daily_benchmark(benchmark_path)
        if benchmark_path is not None and Path(benchmark_path).exists()
        else None
    )

    print(f"Carregando base de dados dos {len(tickers)} ativos da B3...", flush=True)
    data = MarketData(
        tickers,
        "1d",
        "adjusted",
        require_verified_splits_from=str(universe["warmup_start"]),
        history_start=str(universe["warmup_start"]),
    )
    dates = common_dates(data, start, end)
    if not dates:
        raise ValueError("Nenhuma sessao comum encontrada no periodo.")
    last_date = end or dates[-1]
    test_dates = common_dates(data, test_start, last_date)
    if len(test_dates) < 2:
        raise ValueError("Periodo de teste insuficiente.")

    configs = _configs("adjusted", config_set)
    valid_strategies = [s for s in strategies if s in STRATEGIES]
    unknown = sorted(set(strategies) - set(valid_strategies))
    if unknown:
        raise ValueError(f"Estrategias desconhecidas: {unknown}")
    baseline_strategies = sorted({*valid_strategies, "buy_and_hold"})
    print(f"Gerando sinais para {len(valid_strategies)} estrategias...", flush=True)
    eligibility = _build_eligibility(
        data, baseline_strategies, "adjusted", signal_start=str(universe["warmup_start"])
    )
    common = {
        "initial_cash": initial_cash,
        "cost_bps": cost_bps,
        "slippage_bps": slippage_bps,
        "lot_size": lot_size,
    }

    rows: list[dict[str, object]] = []
    print(
        f"Treino ({start} a {train_end}) e teste fora da amostra ({test_start} a {last_date})...\n",
        flush=True,
    )
    for idx, strategy in enumerate(valid_strategies, start=1):
        print(f"[{idx:02d}/{len(valid_strategies):02d}] Avaliando {strategy}...", flush=True)
        best = None
        for config in configs:
            train_summary, _ = run_strict(
                data, config, start=start, end=train_end, eligibility=eligibility[strategy], **common
            )
            metric = float(_metric(train_summary, objective))
            if best is None or metric > best[0]:
                best = (metric, config, train_summary)
        if best is None:
            continue
        train_metric, best_config, train_summary = best

        curve: list[tuple[str, float]] = []
        test_summary, _ = run_strict(
            data,
            best_config,
            start=test_start,
            end=last_date,
            eligibility=eligibility[strategy],
            equity_curve=curve,
            **common,
        )
        train_cagr = float(train_summary.cagr)
        test_cagr = float(test_summary.cagr)
        rows.append(
            {
                "strategy": strategy,
                "management": best_config.name,
                "train_objective": objective,
                "train_metric": train_metric,
                "train_cagr": train_cagr,
                "test_start": test_summary.start,
                "test_end": test_summary.end,
                "test_cagr": test_cagr,
                "test_total_return": float(test_summary.total_return),
                "test_final_equity": float(test_summary.final_equity),
                "test_max_drawdown": float(test_summary.max_drawdown),
                "test_calmar": float(test_summary.calmar),
                "test_sharpe": float(test_summary.sharpe),
                "test_sortino": float(test_summary.sortino),
                **excess_statistics(curve, initial_cash, benchmark),
                "retention_ratio": (test_cagr / train_cagr) if train_cagr > 0 else None,
                "trades": test_summary.trades,
                "fees": test_summary.fees,
                "slippage": test_summary.slippage_cost,
                "validity": validity,
                "economic_scope": ECONOMIC_SCOPE,
            }
        )

    candidates = len(rows)
    for row in rows:
        pvalue = row["excess_pvalue_one_sided"]
        row["excess_pvalue_bonferroni"] = (
            min(1.0, float(pvalue) * candidates) if pvalue is not None else None
        )
        row["reading"] = classify_reading(
            float(row["test_total_return"]),
            row["excess_total_return_vs_cdi"],
            row["excess_pvalue_bonferroni"],
        )

    # The protocol order is the training order; the test rank is descriptive only.
    rows.sort(key=lambda r: float(r["train_metric"]), reverse=True)
    for rank, row in enumerate(rows, start=1):
        row["train_rank"] = rank
    for rank, row in enumerate(sorted(rows, key=lambda r: float(r["test_cagr"]), reverse=True), start=1):
        row["test_rank"] = rank

    market_config = next((c for c in _configs("adjusted", "all") if c.name == MARKET_BASELINE_CONFIG), None)
    market = None
    if market_config is not None:
        market_curve: list[tuple[str, float]] = []
        market_summary, _ = run_strict(
            data,
            market_config,
            start=test_start,
            end=last_date,
            eligibility=eligibility["buy_and_hold"],
            equity_curve=market_curve,
            **common,
        )
        market = {
            "strategy": "buy_and_hold",
            "management": MARKET_BASELINE_CONFIG,
            "test_cagr": float(market_summary.cagr),
            "test_total_return": float(market_summary.total_return),
            "test_final_equity": float(market_summary.final_equity),
            "test_max_drawdown": float(market_summary.max_drawdown),
            **excess_statistics(market_curve, initial_cash, benchmark),
        }

    cdi = None
    if rows and rows[0]["cdi_total_return"] is not None:
        cdi_total = float(rows[0]["cdi_total_return"])
        cdi = {
            "total_return": cdi_total,
            "cagr": _cagr(cdi_total, test_dates[0], test_dates[-1]),
            "final_equity": initial_cash * (1 + cdi_total),
        }

    return {
        "rows": rows,
        "protocol_winner": rows[0] if rows else None,
        "market_baseline": market,
        "cdi": cdi,
        "metadata": {
            "start": start,
            "train_end": train_end,
            "test_start": test_dates[0],
            "test_end": test_dates[-1],
            "initial_cash": initial_cash,
            "cost_bps": cost_bps,
            "slippage_bps": slippage_bps,
            "lot_size": lot_size,
            "config_set": config_set,
            "management_candidates_per_strategy": len(configs),
            "objective": objective,
            "universe": str(universe_path.relative_to(ROOT) if universe_path.is_relative_to(ROOT) else universe_path),
            "universe_sha256": hashlib.sha256(universe_path.read_bytes()).hexdigest(),
            "universe_known_from": known_from,
            "survivorship_safe": survivorship_safe,
            "validity": validity,
            "economic_scope": ECONOMIC_SCOPE,
            "benchmark": str(benchmark_path) if benchmark is not None else None,
        },
    }


CSV_FIELDS = [
    "train_rank",
    "test_rank",
    "strategy",
    "management",
    "train_objective",
    "train_metric",
    "train_cagr",
    "test_start",
    "test_end",
    "test_cagr",
    "test_total_return",
    "test_final_equity",
    "test_max_drawdown",
    "test_calmar",
    "test_sharpe",
    "test_sortino",
    "cdi_total_return",
    "excess_total_return_vs_cdi",
    "excess_sharpe_vs_cdi",
    "excess_t_stat",
    "excess_pvalue_one_sided",
    "excess_pvalue_bonferroni",
    "retention_ratio",
    "reading",
    "trades",
    "fees",
    "slippage",
    "validity",
    "economic_scope",
]


def _br(text: str) -> str:
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def _pct(value: object) -> str:
    return "n/d" if value is None else _br(f"{float(value) * 100:,.2f}%")


def _pp(value: object) -> str:
    return "n/d" if value is None else _br(f"{float(value) * 100:+,.2f}") + " p.p."


def _num(value: object, digits: int = 2) -> str:
    return "n/d" if value is None else _br(f"{float(value):.{digits}f}")


def _money(value: object) -> str:
    return "n/d" if value is None else "R$ " + _br(f"{float(value):,.2f}")


def render_markdown(result: dict[str, object]) -> str:
    rows = list(result["rows"])  # type: ignore[arg-type]
    meta = dict(result["metadata"])  # type: ignore[arg-type]
    winner = result["protocol_winner"]
    market = result["market_baseline"]
    cdi = result["cdi"]
    candidates = len(rows)
    initial_cash = float(meta["initial_cash"])

    lines = [
        "# Ranking fora da amostra das estrategias B3 (motor estrito, Nivel 1)",
        "",
        f"Treino: {meta['start']} a {meta['train_end']}. Teste: {meta['test_start']} a "
        f"{meta['test_end']}. Capital inicial: {_money(initial_cash)}. Custos "
        f"{_br(format(float(meta['cost_bps']), 'g'))} bps + slippage "
        f"{_br(format(float(meta['slippage_bps']), 'g'))} bps por "
        f"ordem; lote de {meta['lot_size']} acao. {meta['management_candidates_per_strategy']} "
        f"gerenciamentos por estrategia (`{meta['config_set']}`), escolhidos pelo "
        f"`{meta['objective']}` do treino.",
        "",
        f"`validity={meta['validity']}` · `economic_scope={meta['economic_scope']}`",
        "",
        "Este relatorio e pesquisa (Nivel 1), nao estimativa de dinheiro real:",
        "",
        f"- o universo fixo `{meta['universe']}` foi escolhido com a liquidez de 2018 e exige "
        f"continuidade ate hoje (`survivorship_safe={str(meta['survivorship_safe']).lower()}`), "
        "o que favorece acoes que sobreviveram;",
        "- os precos sao normalizados por splits; dividendos/JCP e imposto de renda nao entram;",
        "- quantidades inteiras sao calculadas sobre o preco normalizado, nao sobre o preco "
        "historico negociado;",
        "- valores de conta real exigem o motor realista "
        "([metodologia](../docs/realistic_backtest_methodology.md)).",
        "",
        "## Resultado do protocolo (escolha somente no treino)",
        "",
    ]
    if winner is not None:
        lines.extend(
            [
                f"O melhor par do treino entre as {candidates} estrategias foi `{winner['strategy']}` + "
                f"`{winner['management']}` ({_pct(winner['train_cagr'])} de CAGR no treino).",
                "",
                f"No teste ele rendeu {_pct(winner['test_cagr'])} ao ano "
                f"({_pct(winner['test_total_return'])} no periodo; {_money(initial_cash)} -> "
                f"{_money(winner['test_final_equity'])}), com drawdown maximo de "
                f"{_pct(winner['test_max_drawdown'])}. Leitura: **{winner['reading']}**.",
                "",
                "Este e o unico numero desta tabela que mede a selecao fora da amostra.",
                "",
            ]
        )

    lines.extend(["## Referencias no mesmo periodo de teste", ""])
    if cdi is not None:
        lines.append(
            f"- CDI (BCB SGS 12): {_pct(cdi['cagr'])} ao ano, {_pct(cdi['total_return'])} no periodo "
            f"({_money(initial_cash)} -> {_money(cdi['final_equity'])}), bruto de impostos."
        )
    else:
        lines.append(
            "- CDI: indisponivel; rode `python scripts/sync_cdi_benchmark.py --end <data>` "
            "para comparar com o benchmark."
        )
    if market is not None:
        lines.append(
            f"- Carteira igual-ponderada dos mesmos ativos (`buy_and_hold` + `{market['management']}`), "
            f"com os mesmos custos: {_pct(market['test_cagr'])} ao ano, "
            f"{_pct(market['test_total_return'])} no periodo, drawdown maximo "
            f"{_pct(market['test_max_drawdown'])}."
        )
    lines.append("")

    lines.extend(
        [
            "## Tabela (ordem do treino)",
            "",
            "`p Bonf.` e o p-valor unilateral do excesso diario sobre o CDI (aproximacao normal), "
            f"multiplicado por {candidates} candidatos. A coluna `Rank teste` e descritiva.",
            "",
            "| Treino | Rank teste | Estrategia | Treino CAGR | Teste CAGR | Retorno teste | "
            "Patrimonio final | Max DD | Sharpe | Retorno - CDI | t | p Bonf. | Leitura |",
            "| ---: | ---: | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row['train_rank']} | {row['test_rank']} | `{row['strategy']}` | {_pct(row['train_cagr'])} | "
            f"{_pct(row['test_cagr'])} | {_pct(row['test_total_return'])} | "
            f"{_money(row['test_final_equity'])} | {_pct(row['test_max_drawdown'])} | "
            f"{_num(row['test_sharpe'])} | {_pp(row['excess_total_return_vs_cdi'])} | "
            f"{_num(row['excess_t_stat'])} | {_num(row['excess_pvalue_bonferroni'], 3)} | {row['reading']} |"
        )
    lines.append("")

    lines.extend(["## Leitura automatica", ""])
    if rows:
        beat_cdi = [r for r in rows if r["excess_total_return_vs_cdi"] is not None and float(r["excess_total_return_vs_cdi"]) > 0]
        significant = [
            r for r in rows
            if r["excess_pvalue_bonferroni"] is not None and float(r["excess_pvalue_bonferroni"]) < ALPHA
            and float(r["excess_total_return_vs_cdi"]) > 0
        ]
        losses = [r for r in rows if float(r["test_total_return"]) < 0]
        best_test = min(rows, key=lambda r: int(r["test_rank"]))
        degradation = statistics.median(float(r["test_cagr"]) - float(r["train_cagr"]) for r in rows)
        if cdi is not None:
            lines.append(f"- {len(beat_cdi)} de {candidates} estrategias superaram o CDI no teste.")
            lines.append(
                f"- {len(significant)} de {candidates} superaram o CDI com p Bonferroni < {_br(format(ALPHA, 'g'))}."
            )
        lines.append(f"- {len(losses)} de {candidates} perderam capital no teste.")
        lines.append(
            f"- Mediana da variacao de CAGR entre treino e teste: {_pp(degradation)}."
        )
        lines.append(
            f"- A melhor linha do teste e `{best_test['strategy']}` ({_pct(best_test['test_cagr'])} ao ano; "
            f"{best_test['train_rank']}a no treino). Escolhe-la agora e selecao no holdout entre "
            f"{candidates} candidatos; o resultado dela precisa de dados posteriores ou do motor "
            "realista antes de qualquer alegacao."
        )
        if significant:
            lines.append(
                "- Mesmo um excesso significativo continua condicionado ao universo com vies de "
                "sobrevivencia e as premissas de custo acima."
            )
    lines.append("")
    return "\n".join(lines)


def write_reports(result: dict[str, object], csv_path: Path, md_path: Path) -> None:
    rows = list(result["rows"])  # type: ignore[arg-type]
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in CSV_FIELDS})
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(result), encoding="utf-8")
    print(f"\nRelatorios gerados:\n- {csv_path}\n- {md_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ranking fora da amostra no motor estrito, com escolha somente no treino."
    )
    parser.add_argument("--strategies", nargs="+", default=CANONICAL_25_STRATEGIES)
    parser.add_argument("--start", default="2018-01-02")
    parser.add_argument("--train-end", default="2022-12-29")
    parser.add_argument("--test-start", default="2023-01-02")
    parser.add_argument("--end")
    parser.add_argument("--initial-cash", type=float, default=1000.0)
    parser.add_argument("--cost-bps", type=float, default=3.2)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--lot-size", type=int, default=1)
    parser.add_argument("--objective", choices=["cagr", "total_return", "sharpe"], default="cagr")
    parser.add_argument("--config-set", default="base", choices=["all", "base", "roc", "roc_hybrid", "roc_filter_short"])
    parser.add_argument("--universe-manifest", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--benchmark-csv", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--md", type=Path, default=DEFAULT_MD)
    args = parser.parse_args(argv)

    try:
        result = run_ranking(
            [item.strip().lower() for item in args.strategies],
            start=args.start,
            train_end=args.train_end,
            test_start=args.test_start,
            end=args.end,
            initial_cash=args.initial_cash,
            cost_bps=args.cost_bps,
            slippage_bps=args.slippage_bps,
            lot_size=args.lot_size,
            config_set=args.config_set,
            objective=args.objective,
            universe_path=args.universe_manifest,
            benchmark_path=args.benchmark_csv,
        )
    except ValueError as exc:
        parser.error(str(exc))
    write_reports(result, args.csv, args.md)
    winner = result["protocol_winner"]
    if winner is not None:
        print("\nPAR ESCOLHIDO SOMENTE NO TREINO")
        print(f"{winner['strategy']} + {winner['management']}")
        print(f"Treino CAGR: {float(winner['train_cagr']):.2%}")
        print(f"Teste CAGR: {float(winner['test_cagr']):.2%} ({winner['reading']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
