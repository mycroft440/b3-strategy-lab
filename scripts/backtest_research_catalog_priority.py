from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from pathlib import Path

from b3_strategy_lab.candles import DEFAULT_TICKERS
from scripts.backtest_strategy_management_combinations import _build_eligibility
from scripts.research_portfolio_allocation import MarketData, PortfolioConfig, run_portfolio


@dataclass(frozen=True)
class Experiment:
    name: str
    signal_strategy: str
    management: PortfolioConfig
    rationale: str


def _equal_eligible(name: str, *, rebalance: str = "weekly") -> PortfolioConfig:
    return PortfolioConfig(
        name=name,
        lookback=1,
        top_n=99,
        trend_window=0,
        vol_window=63,
        rebalance=rebalance,
        score="all",
        weighting="equal",
        absolute_momentum=False,
        max_weight=1.0,
        target_vol=0.0,
        signal_mode="adjusted",
    )


def experiments() -> tuple[Experiment, ...]:
    return (
        Experiment(
            "gap_momentum_equal_weekly",
            "gap_momentum",
            _equal_eligible("catalog_gap_momentum_equal_weekly"),
            "Replica o motor Gap Momentum sem adicionar um segundo ranking oculto.",
        ),
        Experiment(
            "donchian_55_20_equal_weekly",
            "donchian_breakout_55_20",
            _equal_eligible("catalog_donchian_55_20_equal_weekly"),
            "Donchian 55/20 causal, com maxima/minima anteriores e execucao no proximo open.",
        ),
        Experiment(
            "time_series_momentum_12m_equal_monthly",
            "time_series_momentum_12m",
            _equal_eligible("catalog_tsmom_12m_equal_monthly", rebalance="monthly"),
            "Momentum temporal por ativo, separado do ranking cross-sectional.",
        ),
        Experiment(
            "rsi2_sma200_equal_weekly",
            "rsi2_trend_reversion",
            _equal_eligible("catalog_rsi2_sma200_equal_weekly"),
            "Reversao curta RSI2 dentro de tendencia, sensivel a custos e slippage.",
        ),
        Experiment(
            "squeeze_breakout_equal_weekly",
            "squeeze_breakout",
            _equal_eligible("catalog_squeeze_breakout_equal_weekly"),
            "Expansao de volatilidade apos compressao Bollinger/Keltner.",
        ),
        Experiment(
            "turn_of_month_equal",
            "turn_of_month",
            _equal_eligible("catalog_turn_of_month_equal", rebalance="daily"),
            "Sazonalidade de baixa dimensionalidade sem otimizar datas.",
        ),
        Experiment(
            "cross_sectional_momentum_12_1_top5",
            "buy_and_hold",
            PortfolioConfig(
                name="catalog_cross_sectional_momentum_12_1_top5",
                lookback=252,
                skip=21,
                top_n=5,
                trend_window=0,
                vol_window=63,
                rebalance="monthly",
                score="momentum",
                weighting="equal",
                absolute_momentum=False,
                max_weight=0.25,
                target_vol=0.0,
                signal_mode="adjusted",
            ),
            "Ranking 12-1 mensal; buy_and_hold aqui significa somente elegibilidade permanente.",
        ),
        Experiment(
            "dual_momentum_top3_invvol",
            "buy_and_hold",
            PortfolioConfig(
                name="catalog_dual_momentum_top3_invvol",
                lookback=252,
                skip=21,
                top_n=3,
                trend_window=200,
                vol_window=63,
                rebalance="monthly",
                score="momentum",
                weighting="inv_vol",
                absolute_momentum=True,
                max_weight=0.50,
                target_vol=0.20,
                signal_mode="adjusted",
            ),
            "Momentum relativo + absoluto, inverse-vol e limite de exposicao por ativo.",
        ),
    )


BLOCKED_WITH_CURRENT_DATA = {
    "value_profitability_fundamental_momentum": (
        "Requer demonstracoes CVM point-in-time com first_public_date/restatements."
    ),
    "pairs_long_short_and_market_neutral": (
        "Requer aluguel/borrow, lado short, margem e custos de financiamento modelados."
    ),
    "options": (
        "Requer cadeia historica por strike/vencimento, bid/ask, exercicio, dividendos e taxas."
    ),
    "machine_learning": (
        "Requer protocolo nested walk-forward/holdout antes de entrar na matriz competitiva."
    ),
    "hft_market_making": (
        "Incompativel com candles diarios; requer livro de ofertas, fila e latencia."
    ),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Executa o primeiro lote causal do catalogo de pesquisa sem inventar dados ausentes."
    )
    parser.add_argument("--tickers", nargs="+", default=list(DEFAULT_TICKERS))
    parser.add_argument("--start", default="2018-01-02")
    parser.add_argument("--end")
    parser.add_argument("--initial-cash", type=float, default=1000.0)
    parser.add_argument("--cost-bps", type=float, default=3.2)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--lot-size", type=int, default=1)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/research_catalog_priority.csv"),
    )
    args = parser.parse_args(argv)

    if args.initial_cash <= 0:
        parser.error("--initial-cash precisa ser maior que zero.")
    if args.cost_bps < 0 or args.slippage_bps < 0:
        parser.error("custos e slippage nao podem ser negativos.")
    if args.lot_size < 0:
        parser.error("--lot-size nao pode ser negativo.")

    data = MarketData(
        [ticker.upper() for ticker in args.tickers],
        "1d",
        "adjusted",
        history_start="2017-01-01",
        require_verified_splits_from="2017-01-01",
    )
    end = args.end or min(data.candles[ticker][-1].date for ticker in data.tickers)
    selected = experiments()
    strategies = sorted({item.signal_strategy for item in selected})
    eligibility = _build_eligibility(
        data,
        strategies,
        "adjusted",
        signal_start="2017-01-01",
    )

    rows: list[dict[str, object]] = []
    for experiment in selected:
        summary, _ = run_portfolio(
            data,
            experiment.management,
            start=args.start,
            end=end,
            initial_cash=args.initial_cash,
            cost_bps=args.cost_bps,
            slippage_bps=args.slippage_bps,
            lot_size=args.lot_size,
            eligibility=eligibility[experiment.signal_strategy],
            collect_curve=False,
        )
        row = asdict(summary)
        row.update(
            experiment=experiment.name,
            signal_strategy=experiment.signal_strategy,
            management_strategy=experiment.management.name,
            rationale=experiment.rationale,
        )
        rows.append(row)

    rows.sort(key=lambda row: (float(row["cagr"]), float(row["total_return"])), reverse=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else []
    with args.output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    for rank, row in enumerate(rows, start=1):
        print(
            f"{rank}. {row['experiment']}: CAGR={float(row['cagr']):.2%} "
            f"retorno={float(row['total_return']):.2%} DD={float(row['max_drawdown']):.2%}"
        )
    print("\nBloqueados ate existir dado/modelagem adequada:")
    for family, reason in BLOCKED_WITH_CURRENT_DATA.items():
        print(f"- {family}: {reason}")
    print(f"\nCSV: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
