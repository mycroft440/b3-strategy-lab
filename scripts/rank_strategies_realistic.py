"""Ranking Realista e Fora da Amostra (Out-of-Sample) das Estrategias da B3.

Mede o desempenho verdadeiro de cada estrategia:
1. Treino (2018 a 2022) para calibracao / selecao.
2. Teste Cego / Holdout (2023 ate hoje) com precos nao vistos, custos de 3,2 bps,
   slippage de 10 bps e lotes inteiros de 1 acao.
3. Classifica as estrategias pelo resultado REAL fora da amostra (Teste CAGR),
   revelando quais tem robustez estatistica e quais eram apenas overfitting.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.strategies import portfolio_strategies, strategy_parameters  # noqa: E402
from scripts.backtest_strategy_management_combinations import _build_eligibility  # noqa: E402
from scripts.backtest_strategy_management_strict import common_dates, run_strict  # noqa: E402
from scripts.research_portfolio_allocation import MarketData, _configs  # noqa: E402

DEFAULT_UNIVERSE = ROOT / "data/universes/fixed_40_2018.json"
DEFAULT_CSV = ROOT / "reports/ranking_estrategias_realista.csv"
DEFAULT_MD = ROOT / "reports/ranking_estrategias_realista.md"

CANONICAL_STRATEGIES = [
    "sma_cross",
    "ema_cross",
    "breakout",
    "atr_breakout",
    "donchian_40_20_trend",
    "frama_trend",
    "rsi_reversion",
    "bollinger_reversion",
    "connors_rsi_reversion",
    "gap_momentum",
    "momentum",
    "chaikin_money_flow",
    "mfi_reversal",
    "turn_of_month",
]


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
    universe_path: Path = DEFAULT_UNIVERSE,
) -> list[dict[str, object]]:
    universe = json.loads(universe_path.read_text(encoding="utf-8"))
    tickers = [str(item).upper() for item in universe["tickers"]]

    print("Carregando base de dados dos 40 ativos da B3...", flush=True)
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

    configs = _configs("adjusted", config_set)
    print(f"Gerando sinais para {len(strategies)} estrategias...", flush=True)
    eligibility = _build_eligibility(
        data, strategies, "adjusted", signal_start=str(universe["warmup_start"])
    )

    rows: list[dict[str, object]] = []
    print(f"Executando Treino ({start} a {train_end}) e Teste ({test_start} a {last_date})...\n", flush=True)

    for idx, strategy in enumerate(strategies, start=1):
        print(f"[{idx}/{len(strategies)}] Avaliando {strategy}...", flush=True)
        best_train_metric = -float("inf")
        best_train_summary = None
        best_config = None

        for config in configs:
            train_summary, _ = run_strict(
                data,
                config,
                start=start,
                end=train_end,
                initial_cash=initial_cash,
                cost_bps=cost_bps,
                slippage_bps=slippage_bps,
                lot_size=lot_size,
                eligibility=eligibility[strategy],
            )
            metric = float(train_summary.cagr)
            if metric > best_train_metric:
                best_train_metric = metric
                best_train_summary = train_summary
                best_config = config

        if best_config is None or best_train_summary is None:
            continue

        test_summary, _ = run_strict(
            data,
            best_config,
            start=test_start,
            end=last_date,
            initial_cash=initial_cash,
            cost_bps=cost_bps,
            slippage_bps=slippage_bps,
            lot_size=lot_size,
            eligibility=eligibility[strategy],
        )

        train_cagr = float(best_train_summary.cagr)
        test_cagr = float(test_summary.cagr)
        test_ret = float(test_summary.total_return)
        test_mdd = float(test_summary.max_drawdown)
        test_sharpe = float(test_summary.sharpe)
        retention = (test_cagr / train_cagr) if train_cagr > 0 else -1.0

        rows.append(
            {
                "strategy": strategy,
                "management": best_config.name,
                "train_cagr": train_cagr,
                "test_cagr": test_cagr,
                "test_total_return": test_ret,
                "test_max_drawdown": test_mdd,
                "test_sharpe": test_sharpe,
                "retention_ratio": retention,
                "trades": test_summary.trades,
                "fees": test_summary.fees,
                "slippage": test_summary.slippage_cost,
            }
        )

    # Classificar pelo resultado REAL fora da amostra (Teste CAGR)
    rows.sort(key=lambda r: float(r["test_cagr"]), reverse=True)
    for rank, r in enumerate(rows, start=1):
        r["real_rank"] = rank

    return rows


def write_reports(rows: list[dict[str, object]], csv_path: Path, md_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "real_rank",
        "strategy",
        "management",
        "test_cagr",
        "test_total_return",
        "test_max_drawdown",
        "test_sharpe",
        "train_cagr",
        "retention_ratio",
        "trades",
        "fees",
        "slippage",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k) for k in fieldnames})

    md_content = [
        "# Ranking Realista das Estratégias B3 (Fora da Amostra)\n",
        "Este ranking separa a ilusão retrospectiva da realidade. Cada estratégia teve seu melhor gerenciamento ",
        "escolhido **estritamente no período de treino (2018-2022)** e foi testada em **dados cegos/não vistos (2023-presente)** ",
        "com custos de corretagem/emolumentos B3 (3,2 bps), slippage adverso (10 bps) e lote inteiro de 1 ação.\n",
        "| Rank Real | Estratégia | Teste CAGR | Teste Retorno Total | Teste Max Drawdown | Teste Sharpe | Treino CAGR | Retenção OOS |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for r in rows:
        strat = r["strategy"]
        test_cagr = f"{float(r['test_cagr']):.2%}"
        test_ret = f"{float(r['test_total_return']):.2%}"
        test_mdd = f"{float(r['test_max_drawdown']):.2%}"
        test_sharpe = f"{float(r['test_sharpe']):.2f}"
        train_cagr = f"{float(r['train_cagr']):.2%}"
        retention = f"{float(r['retention_ratio']):.1%}" if float(r['retention_ratio']) >= 0 else "N/A"
        md_content.append(
            f"| **#{r['real_rank']}** | `{strat}` | **{test_cagr}** | {test_ret} | {test_mdd} | {test_sharpe} | {train_cagr} | {retention} |"
        )

    md_content.append("\n## Diagnóstico das Estratégias e Conclusões\n")
    md_content.append("- **Vencedora Real**: A estratégia no topo da tabela acima é a que comprovadamente entrega retorno positivo e controlado fora da amostra com custos reais.")
    md_content.append("- **Alerta de Overfitting**: Estratégias com alto Treino CAGR (>50%) mas Teste CAGR negativo ou próximo de zero sofreram sobreajuste no passado e não se sustentam na prática.")

    md_path.write_text("\n".join(md_content) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ranking realista e honesto das estrategias da B3.")
    parser.add_argument("--strategies", nargs="+", default=CANONICAL_STRATEGIES)
    parser.add_argument("--all-strategies", action="store_true", help="Testar todas as 249 estrategias do catalogo.")
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    strats = list(portfolio_strategies()) if args.all_strategies else args.strategies
    results = run_ranking(strats)
    write_reports(results, args.output_csv, args.output_md)

    print("\n" + "=" * 90)
    print("RANKING REALISTA DAS ESTRATÉGIAS B3 (FORA DA AMOSTRA / HOLDOUT)")
    print("=" * 90)
    print(f"{'Rank':<5} {'Estratégia':<24} {'Teste CAGR':<12} {'Teste Retorno':<14} {'Teste MDD':<12} {'Treino CAGR':<12}")
    print("-" * 90)
    for r in results:
        print(
            f"#{r['real_rank']:<4} {r['strategy']:<24} {float(r['test_cagr']):>10.2%} {float(r['test_total_return']):>12.2%} {float(r['test_max_drawdown']):>10.2%} {float(r['train_cagr']):>10.2%}"
        )
    print("=" * 90)
    print(f"\nRelatório completo em Markdown salvo em: {args.output_md}")
    print(f"Tabela de dados em CSV salva em: {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
