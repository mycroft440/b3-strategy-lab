"""Backtest do indicador RSI + WMA Heikin Ashi SEM gerenciamento de carteira.

Nao usa nenhum dos 478 gerenciamentos (sem rebalanceamento periodico, sem alvo
de volatilidade). A carteira apenas segue o sinal:

- Sinal no fechamento, execucao na abertura do pregao seguinte.
- Somente 1 acao por vez (padrao). Todo o patrimonio entra nela e ela fica
  parada ate o sinal de venda; so entao outra acao pode ser escolhida.
- Entrada somente no PRIMEIRO candle do sinal (RSI > 50, WMA Heikin Ashi
  subindo e fechamento acima da SMA200): a compra ocorre na abertura
  seguinte a esse candle. Se a vaga estiver ocupada nesse momento, o sinal e
  descartado (nunca ha entrada tardia).
- Escolha (variante principal ``roc3m_positivo_primeiro_candle``): entre as
  acoes cujo sinal nasceu no ultimo fechamento e cujo ROC de 3 meses (63
  pregoes) e positivo, compra-se a de maior ROC. Sem candidato, fica em caixa.
- Variantes de comparacao (todas com a mesma regra de primeiro candle): ROC sem
  exigir positivo, ordem alfabetica entre ROCs positivos, filtro SMA50, sem filtro
  e buy and hold de peso igual.

Tambem gera o resultado isolado por ativo (100% do capital em cada ativo, o
backtest classico de um ativo por vez) e as estatisticas de todos os trades do
sinal.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.backtest import run_strategy_vs_buy_hold  # noqa: E402
from b3_strategy_lab.rsi_wma_heikin_ashi import priority_flags, rsi_wma_heikin_ashi  # noqa: E402
from scripts.backtest_strategy_management_strict import common_dates  # noqa: E402
from scripts.research_portfolio_allocation import (  # noqa: E402
    MarketData,
    _portfolio_metrics,
    _yearly_returns,
)

STRATEGY = "rsi_wma_heikin_ashi"
MAIN_VARIANT = "roc3m_positivo_primeiro_candle"
DEFAULT_UNIVERSE = ROOT / "data/universes/fixed_40_2018.json"
DEFAULT_OUTPUT_DIR = ROOT / "reports/rsi_wma_heikin_ashi"


@dataclass
class Position:
    shares: float
    entry_date: str
    entry_price: float
    entry_cost: float
    priority: int
    roc: float | None = None
    signal_age: int | None = None


@dataclass
class PortfolioResult:
    name: str
    max_positions: int
    use_priority: bool
    dates: list[str]
    equities: list[float]
    ledger: list[dict[str, object]] = field(default_factory=list)
    trades: list[dict[str, object]] = field(default_factory=list)
    fees: float = 0.0
    slippage: float = 0.0
    missed_entries: int = 0
    exposure: float = 0.0


def _floor_lot(value: float, lot: int) -> float:
    return value if lot <= 0 else math.floor((value + 1e-12) / lot) * lot


def simulate_portfolio(
    data: MarketData,
    signals: dict[str, list[int]],
    priority: dict[str, list[int]],
    dates: list[str],
    *,
    name: str,
    max_positions: int,
    use_priority: bool,
    initial_cash: float,
    cost_bps: float,
    slippage_bps: float,
    lot_size: int,
    roc: dict[str, list[float | None]] | None = None,
    signal_age: dict[str, list[int]] | None = None,
    recent_window: int | None = None,
    min_roc: float | None = None,
    rank_by_roc: bool = True,
) -> PortfolioResult:
    """Simula a carteira que segue o sinal.

    ``roc`` ativa a escolha pelo maior ROC (desc). ``recent_window`` limita os
    candidatos a sinais iniciados ha menos de N pregoes (usa ``signal_age``).
    ``use_priority`` coloca os sinais prioritarios antes dos demais. Empates
    finais seguem a ordem alfabetica do ticker.
    """
    cost_rate, slip_rate = cost_bps / 10_000, slippage_bps / 10_000
    all_dates = common_dates(data)
    prior_dates = [value for value in all_dates if value < dates[0]]
    previous = prior_dates[-1] if prior_dates else None

    cash = float(initial_cash)
    positions: dict[str, Position] = {}
    result = PortfolioResult(name, max_positions, use_priority, dates, [])
    invested_sessions = 0

    def state(ticker: str, day: str | None) -> tuple[int, int]:
        if day is None:
            return 0, 0
        index = data.index_by_date[ticker][day]
        return signals[ticker][index], priority[ticker][index]

    for current in dates:
        candles = {ticker: data.by_date[ticker][current] for ticker in data.tickers}

        # 1) Saidas na abertura (sinal de venda no fechamento anterior).
        for ticker in sorted(positions):
            signal, _ = state(ticker, previous)
            if signal == 1:
                continue
            pos = positions.pop(ticker)
            raw = float(candles[ticker].open)
            fill = raw * (1 - slip_rate)
            gross = pos.shares * fill
            fee = gross * cost_rate
            slip = pos.shares * (raw - fill)
            cash += gross - fee
            result.fees += fee
            result.slippage += slip
            result.ledger.append({"date": current, "side": "SELL", "ticker": ticker, "shares": pos.shares,
                                  "raw_open": raw, "execution_price": fill, "fee": fee, "slippage_cost": slip,
                                  "priority": pos.priority, "roc_3m": pos.roc, "idade_sinal": pos.signal_age})
            result.trades.append(_closed_trade(ticker, pos, current, fill, gross - fee))

        # 2) Entradas na abertura (sinal de compra no fechamento anterior).
        candidates = []
        for ticker in data.tickers:
            if ticker in positions or previous is None:
                continue
            signal, prio = state(ticker, previous)
            if signal != 1:
                continue
            index = data.index_by_date[ticker][previous]
            age = signal_age[ticker][index] if signal_age is not None else None
            if recent_window is not None and (age is None or age >= recent_window):
                continue
            momentum = roc[ticker][index] if roc is not None else None
            if roc is not None and momentum is None:
                continue
            if min_roc is not None and (momentum is None or momentum <= min_roc):
                continue
            rank = momentum if (rank_by_roc and momentum is not None) else 0.0
            key = (-(prio if use_priority else 0), -rank, ticker)
            candidates.append((key, ticker, prio, momentum, age))
        candidates.sort()
        free = max_positions - len(positions)
        if candidates and free > 0:
            equity_open = cash + sum(p.shares * float(candles[t].open) for t, p in positions.items())
            slot_value = equity_open / max_positions
            for _, ticker, prio, momentum, age in candidates[:free]:
                raw = float(candles[ticker].open)
                fill = raw * (1 + slip_rate)
                budget = min(slot_value, cash)
                qty = _floor_lot(budget / (fill * (1 + cost_rate)), lot_size)
                if qty <= 0:
                    result.missed_entries += 1
                    continue
                gross = qty * fill
                fee = gross * cost_rate
                slip = qty * (fill - raw)
                cash -= gross + fee
                result.fees += fee
                result.slippage += slip
                positions[ticker] = Position(qty, current, fill, gross + fee, prio, momentum, age)
                result.ledger.append({"date": current, "side": "BUY", "ticker": ticker, "shares": qty,
                                      "raw_open": raw, "execution_price": fill, "fee": fee, "slippage_cost": slip,
                                      "priority": prio, "roc_3m": momentum, "idade_sinal": age})
            result.missed_entries += max(0, len(candidates) - free)
        else:
            result.missed_entries += len(candidates)

        equity = cash + sum(p.shares * float(candles[t].close) for t, p in positions.items())
        if not math.isfinite(equity) or equity <= 0 or cash < -1e-6:
            raise ValueError(f"{current}: patrimonio/caixa invalido")
        result.equities.append(equity)
        invested_sessions += bool(positions)
        previous = current

    # Posicoes ainda abertas: marcadas no ultimo fechamento (sem custo de saida).
    last = dates[-1]
    for ticker, pos in positions.items():
        close = float(data.by_date[ticker][last].close)
        trade = _closed_trade(ticker, pos, last, close, pos.shares * close)
        trade["status"] = "ABERTA"
        result.trades.append(trade)
    result.exposure = invested_sessions / len(dates)
    return result


def rate_of_change(candles, period: int) -> list[float | None]:
    """ROC causal: fechamento[t] / fechamento[t - period] - 1."""
    closes = [float(c.close) for c in candles]
    return [None if i < period or closes[i - period] <= 0 else closes[i] / closes[i - period] - 1
            for i in range(len(closes))]


def signal_ages(signals: list[int]) -> list[int | None]:
    """Pregoes desde o inicio do sinal de compra atual (0 no pregao da virada)."""
    ages: list[int | None] = []
    for index, value in enumerate(signals):
        if value != 1:
            ages.append(None)
        elif index > 0 and signals[index - 1] == 1 and ages[-1] is not None:
            ages.append(ages[-1] + 1)
        else:
            ages.append(0)
    return ages


def filter_signal_runs(
    signals: list[int],
    roc: list[float | None],
    min_roc: float | None,
) -> list[int]:
    """Mantem apenas os sinais cujo PRIMEIRO candle tem ROC acima de ``min_roc``.

    Usado no backtest por ativo e nas estatisticas de trades para aplicar a
    mesma regra de entrada da carteira (o filtro vale so no candle de entrada;
    a saida continua sendo o sinal de venda).
    """
    if min_roc is None:
        return list(signals)
    result = [0] * len(signals)
    keep = False
    for index, value in enumerate(signals):
        if value != 1:
            keep = False
            continue
        if index == 0 or signals[index - 1] != 1:
            momentum = roc[index]
            keep = momentum is not None and momentum > min_roc
        result[index] = 1 if keep else 0
    return result


def _closed_trade(ticker: str, pos: Position, exit_date: str, exit_price: float, proceeds: float) -> dict[str, object]:
    return {
        "ticker": ticker,
        "entry_date": pos.entry_date,
        "exit_date": exit_date,
        "entry_price": pos.entry_price,
        "exit_price": exit_price,
        "shares": pos.shares,
        "priority": pos.priority,
        "roc_3m_entrada": pos.roc,
        "idade_sinal_entrada": pos.signal_age,
        "return": proceeds / pos.entry_cost - 1,
        "pnl": proceeds - pos.entry_cost,
        "sessions": None,
        "status": "FECHADA",
    }


def signal_trades(
    ticker: str,
    data: MarketData,
    signals: list[int],
    priority: list[int],
    start: str,
    end: str,
    cost_bps: float,
    slippage_bps: float,
) -> list[dict[str, object]]:
    """Todos os trades do sinal de um ativo (sem limite de vagas)."""
    cost_rate, slip_rate = cost_bps / 10_000, slippage_bps / 10_000
    candles = data.candles[ticker]
    trades: list[dict[str, object]] = []
    open_trade: dict[str, object] | None = None
    for index in range(1, len(candles)):
        day = candles[index].date
        if day < start or day > end:
            continue
        wanted = signals[index - 1]
        fresh = index < 2 or signals[index - 2] == 0
        # Entrada apenas no primeiro candle do sinal; sinais ja ativos no inicio do
        # periodo sao ignorados (nunca ha entrada tardia).
        if open_trade is None and wanted == 1 and fresh:
            fill = candles[index].open * (1 + slip_rate)
            open_trade = {"ticker": ticker, "entry_date": day, "entry_index": index,
                          "entry_price": fill, "priority": priority[index - 1]}
        elif open_trade is not None and wanted == 0:
            fill = candles[index].open * (1 - slip_rate)
            trades.append(_finish(open_trade, day, index, fill, cost_rate, "FECHADA"))
            open_trade = None
    if open_trade is not None:
        last = max(i for i, c in enumerate(candles) if c.date <= end)
        trades.append(_finish(open_trade, candles[last].date, last, candles[last].close, cost_rate, "ABERTA"))
    return trades


def _finish(trade: dict[str, object], day: str, index: int, price: float, cost_rate: float, status: str) -> dict[str, object]:
    entry = float(trade["entry_price"]) * (1 + cost_rate)
    exit_value = price * (1 - cost_rate) if status == "FECHADA" else price
    return {
        "ticker": trade["ticker"],
        "entry_date": trade["entry_date"],
        "exit_date": day,
        "entry_price": trade["entry_price"],
        "exit_price": price,
        "priority": trade["priority"],
        "return": exit_value / entry - 1,
        "sessions": index - int(trade["entry_index"]),
        "status": status,
    }


def trade_stats(trades: list[dict[str, object]]) -> dict[str, object]:
    closed = [t for t in trades if t["status"] == "FECHADA"]
    if not closed:
        return {"trades": 0}
    returns = [float(t["return"]) for t in closed]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    gross_win, gross_loss = sum(wins), -sum(losses)
    sessions = [int(t["sessions"]) for t in closed if t.get("sessions") is not None]
    return {
        "trades": len(closed),
        "taxa_acerto": len(wins) / len(closed),
        "retorno_medio": statistics.mean(returns),
        "retorno_mediano": statistics.median(returns),
        "ganho_medio": statistics.mean(wins) if wins else 0.0,
        "perda_media": statistics.mean(losses) if losses else 0.0,
        "fator_lucro": gross_win / gross_loss if gross_loss > 0 else None,
        "pregoes_medios": statistics.mean(sessions) if sessions else None,
    }


def portfolio_row(result: PortfolioResult, initial_cash: float, period: str) -> dict[str, object]:
    metrics = _portfolio_metrics(result.equities, result.dates, initial_cash)
    yearly = _yearly_returns(result.equities, result.dates, initial_cash)
    stats = trade_stats(result.trades)
    prio = trade_stats([t for t in result.trades if t["priority"] == 1])
    return {
        "periodo": period,
        "variante": result.name,
        "max_posicoes": result.max_positions,
        "usa_prioridade": result.use_priority,
        "inicio": result.dates[0],
        "fim": result.dates[-1],
        "patrimonio_final": result.equities[-1],
        "retorno_total": metrics["total_return"],
        "cagr": metrics["cagr"],
        "max_drawdown": metrics["max_drawdown"],
        "volatilidade_anual": metrics["annual_volatility"],
        "sharpe": metrics["sharpe"],
        "calmar": metrics.get("calmar", 0.0),
        "sortino": metrics.get("sortino", 0.0),
        "exposicao": result.exposure,
        "trades_fechados": stats.get("trades", 0),
        "taxa_acerto": stats.get("taxa_acerto"),
        "retorno_medio_trade": stats.get("retorno_medio"),
        "fator_lucro": stats.get("fator_lucro"),
        "trades_prioritarios": prio.get("trades", 0),
        "sinais_descartados": result.missed_entries,
        "taxas_brl": result.fees,
        "slippage_brl": result.slippage,
        "retornos_anuais": json.dumps({str(k): round(v, 4) for k, v in yearly.items()}),
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _pct(value: object) -> str:
    return "-" if value is None else f"{float(value):.2%}"


def _num(value: object) -> str:
    if value is None:
        return "-"
    value = float(value)
    return "inf" if math.isinf(value) else f"{value:.2f}"


def write_markdown(path: Path, context: dict[str, object]) -> None:
    rows = context["portfolio_rows"]
    lines = [
        "# RSI + WMA Heikin Ashi - backtest sem gerenciamento de carteira\n",
        "## Regras testadas\n",
        f"- **Compra**: RSI({context['params']['rsi_period']}) do fechamento acima de {context['params']['rsi_entry']:g} "
        f"e WMA({context['params']['wma_period']}) do fechamento Heikin Ashi subindo (WMA[t] > WMA[t-1]), "
        f"com o fechamento ACIMA da SMA{context['params']['entry_sma']} (fechamento > SMA).",
        f"- **Venda**: basta um dos dois: RSI abaixo de {context['params']['rsi_exit']:g} ou WMA Heikin Ashi caindo "
        "(WMA[t] < WMA[t-1]). A SMA so filtra a compra; o preco cair abaixo dela nao vende.",
        f"- **Selecao**: somente {context['max_positions']} acao por vez. A entrada so ocorre na abertura seguinte ao "
        "PRIMEIRO candle do sinal; se a vaga estiver ocupada, o sinal e descartado (nunca ha entrada tardia). "
        f"So entram sinais novos com ROC de 3 meses ({context['roc_period']} pregoes) acima de {context['min_roc']:g}; "
        "entre eles, compra-se o de maior ROC. Sem candidato, a carteira fica em caixa. "
        "A posicao fica ate o sinal de venda (o ROC so e exigido na entrada).",
        "- **Prioridade** (fechamento OU SMA20 acima da SMA50): nao entra na escolha da regra principal; "
        "aparece apenas nas estatisticas de trades.",
        "- \"RSI acima de 0\" foi lido como RSI centralizado (RSI - 50 > 0), ou seja RSI > 50.",
        "- Sinal no fechamento, execucao na abertura seguinte; "
        f"custos {context['cost_bps']} bps + slippage {context['slippage_bps']} bps por ordem; lote de {context['lot_size']} acao.",
        f"- Universo: {len(context['tickers'])} acoes (`{context['universe_id']}`), candles ajustados por splits, sem dividendos/JCP. "
        "O universo tem vies de sobrevivencia declarado.",
        "- **Sem gerenciamento**: sem rebalanceamento periodico e sem alvo de volatilidade. Todo o patrimonio vai para a "
        "acao escolhida e fica parado ate o sinal de venda.\n",
        "## Variantes\n",
        *[f"- `{name}`: {text}" for name, text in context["variant_descriptions"].items()],
        "",
        "## Carteira seguindo o sinal\n",
        "| Periodo | Variante | Vagas | CAGR | Retorno total | Max DD | Sharpe | Calmar | Exposicao | Trades | Acerto | Fator lucro | Sinais descartados |",
        "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in rows:
        lines.append(
            f"| {r['periodo']} | `{r['variante']}` | {r['max_posicoes']} | **{_pct(r['cagr'])}** | {_pct(r['retorno_total'])} | "
            f"{_pct(r['max_drawdown'])} | {_num(r['sharpe'])} | {_num(r['calmar'])} | {_pct(r['exposicao'])} | "
            f"{r['trades_fechados']} | {_pct(r['taxa_acerto'])} | {_num(r['fator_lucro'])} | {r['sinais_descartados']} |"
        )

    main = [r for r in rows if r["variante"] == MAIN_VARIANT and r["periodo"] == "2018+"]
    bench = [r for r in rows if r["variante"] == "buy_and_hold_peso_igual" and r["periodo"] == "2018+"]
    if main and bench:
        years_main = json.loads(str(main[0]["retornos_anuais"]))
        years_bench = json.loads(str(bench[0]["retornos_anuais"]))
        lines += [
            f"\n## Retorno anual da variante principal (`{MAIN_VARIANT}`)\n",
            "| Ano | Estrategia | Buy and hold peso igual |",
            "| :--- | ---: | ---: |",
            *[f"| {year} | {_pct(value)} | {_pct(years_bench.get(year))} |" for year, value in years_main.items()],
        ]
    lines += [
        "\n## Todos os trades do sinal (mesma regra de entrada, sem limite de vagas)\n",

        "| Grupo | Trades | Acerto | Retorno medio | Mediana | Ganho medio | Perda media | Fator lucro | Pregoes medios |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, stats in context["priority_stats"].items():
        lines.append(
            f"| {label} | {stats.get('trades', 0)} | {_pct(stats.get('taxa_acerto'))} | {_pct(stats.get('retorno_medio'))} | "
            f"{_pct(stats.get('retorno_mediano'))} | {_pct(stats.get('ganho_medio'))} | {_pct(stats.get('perda_media'))} | "
            f"{_num(stats.get('fator_lucro'))} | {_num(stats.get('pregoes_medios'))} |"
        )

    per_asset = context["per_asset"]
    beat = sum(1 for r in per_asset if float(r["excesso_vs_buy_hold"]) > 0)
    lines += [
        f"\n## Ativo isolado (100% do capital em cada ativo, entrada so com ROC 3m positivo, "
        f"{context['full_start']} a {context['end']})\n",
        f"Estrategia superou o buy and hold do proprio ativo em **{beat} de {len(per_asset)}** ativos. "
        f"CAGR mediano da estrategia: **{_pct(statistics.median(float(r['cagr']) for r in per_asset))}**; "
        f"buy and hold mediano: **{_pct(statistics.median(float(r['buy_hold_cagr']) for r in per_asset))}**.\n",
        "| Ativo | CAGR | Retorno total | Max DD | Sharpe | Exposicao | Ordens | B&H CAGR | B&H Max DD | Excesso (retorno total) |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in per_asset:
        lines.append(
            f"| {r['ticker']} | {_pct(r['cagr'])} | {_pct(r['retorno_total'])} | {_pct(r['max_drawdown'])} | {_num(r['sharpe'])} | "
            f"{_pct(r['exposicao'])} | {r['ordens']} | {_pct(r['buy_hold_cagr'])} | {_pct(r['buy_hold_max_drawdown'])} | "
            f"{_pct(r['excesso_vs_buy_hold'])} |"
        )
    lines.append(
        "\nResultados retrospectivos: sem otimizacao de parametros, mas com universo fixo (vies de sobrevivencia), "
        "sem impostos e sem proventos. Nao representam expectativa de dinheiro real."
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RSI + WMA Heikin Ashi sem gerenciamento de carteira")
    parser.add_argument("--universe-manifest", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--start", default="2018-01-02")
    parser.add_argument("--test-start", default="2023-01-02")
    parser.add_argument("--end")
    parser.add_argument("--initial-cash", type=float, default=10_000.0)
    parser.add_argument("--cost-bps", type=float, default=3.2)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--lot-size", type=int, default=1)
    parser.add_argument("--rsi-period", type=int, default=14)
    parser.add_argument("--rsi-entry", type=float, default=50.0)
    parser.add_argument("--rsi-exit", type=float, default=50.0)
    parser.add_argument("--wma-period", type=int, default=20)
    parser.add_argument("--entry-sma", type=int, default=200,
                        help="so compra com fechamento acima desta SMA (0 desliga o filtro)")
    parser.add_argument("--priority-fast", type=int, default=20)
    parser.add_argument("--priority-slow", type=int, default=50)
    parser.add_argument("--max-positions", type=int, default=1, help="acoes simultaneas (padrao: 1 por vez)")
    parser.add_argument("--roc-period", type=int, default=63, help="ROC de 3 meses = 63 pregoes")
    parser.add_argument("--min-roc", type=float, default=0.0,
                        help="ROC minimo (exclusivo) no candle de entrada da regra principal")

    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    universe = json.loads(args.universe_manifest.read_text(encoding="utf-8"))
    tickers = [str(item).upper() for item in universe["tickers"]]
    warmup = str(universe["warmup_start"])
    print(f"Carregando {len(tickers)} ativos...", flush=True)
    data = MarketData(tickers, "1d", "adjusted", require_verified_splits_from=warmup, history_start=warmup)
    full_dates = common_dates(data, args.start, args.end)
    if len(full_dates) < 2:
        raise ValueError("Periodo comum insuficiente")
    end = full_dates[-1]
    test_dates = [d for d in full_dates if d >= args.test_start]

    params = {"rsi_period": args.rsi_period, "rsi_entry": args.rsi_entry,
              "rsi_exit": args.rsi_exit, "wma_period": args.wma_period, "entry_sma": args.entry_sma}

    def build(parameters: dict[str, object]) -> dict[str, list[int]]:
        return {t: rsi_wma_heikin_ashi(data.candles[t], **parameters) for t in tickers}

    signals = build(params)
    always = {t: [1] * len(data.candles[t]) for t in tickers}
    priority = {t: priority_flags(data.candles[t], fast_period=args.priority_fast, slow_period=args.priority_slow)
                for t in tickers}
    roc = {t: rate_of_change(data.candles[t], args.roc_period) for t in tickers}
    ages = {t: signal_ages(signals[t]) for t in tickers}
    # Comparacao: mesmo sinal sem o filtro da SMA na entrada.
    # Comparacoes de filtro de tendencia na compra (mesma regra principal).
    filter_tests = []
    for period_sma in (50, 0):
        if period_sma == args.entry_sma:
            continue
        alt = build(dict(params, entry_sma=period_sma))
        label = f"filtro_sma{period_sma}" if period_sma else "sem_filtro_sma"
        text = (f"Comparacao: regra principal com fechamento acima da SMA{period_sma} no lugar da SMA{args.entry_sma}."
                if period_sma else f"Comparacao: regra principal sem filtro de media na compra.")
        filter_tests.append((label, text, alt, {t: signal_ages(alt[t]) for t in tickers}))

    common = dict(initial_cash=args.initial_cash, cost_bps=args.cost_bps,
                  slippage_bps=args.slippage_bps, lot_size=args.lot_size)
    slots = args.max_positions
    main_name = MAIN_VARIANT
    fresh = dict(signal_age=ages, recent_window=1)
    variants: list[tuple[str, str, dict[str, object]]] = [
        (main_name,
         f"PRINCIPAL. Somente sinais no primeiro candle com ROC de {args.roc_period} pregoes acima de "
         f"{args.min_roc:g}; entre eles, o maior ROC.",
         dict(roc=roc, min_roc=args.min_roc, use_priority=False, **fresh)),
        ("roc3m_primeiro_candle",
         "Igual a principal, sem exigir ROC positivo (maior ROC mesmo se negativo).",
         dict(roc=roc, use_priority=False, **fresh)),
        ("alfabetica_roc3m_positivo_primeiro_candle",
         "Igual a principal, mas sem ordenar pelo ROC: empate pela ordem alfabetica (mede o efeito do ranking).",
         dict(roc=roc, min_roc=args.min_roc, use_priority=False, rank_by_roc=False, **fresh)),
    ]

    portfolio_rows: list[dict[str, object]] = []
    default_result: PortfolioResult | None = None
    for period, dates in (("2018+", full_dates), ("2023+ (teste)", test_dates)):
        if len(dates) < 2:
            continue
        for name, _, options in variants:
            res = simulate_portfolio(data, signals, priority, dates, name=name, max_positions=slots,
                                     **options, **common)
            portfolio_rows.append(portfolio_row(res, args.initial_cash, period))
            if period == "2018+" and name == main_name:
                default_result = res
        main_options = variants[0][2]
        for label, _, alt_signals, alt_ages in filter_tests:
            res = simulate_portfolio(data, alt_signals, priority, dates, name=f"{main_name}_{label}",
                                     max_positions=slots,
                                     **dict(main_options, signal_age=alt_ages), **common)
            portfolio_rows.append(portfolio_row(res, args.initial_cash, period))
        # Diagnostico: mesma regra principal sem custos/slippage, para medir o peso dos custos.
        res = simulate_portfolio(data, signals, priority, dates, name=f"{main_name}_sem_custos",
                                 max_positions=slots, **main_options,
                                 **dict(common, cost_bps=0.0, slippage_bps=0.0))
        portfolio_rows.append(portfolio_row(res, args.initial_cash, period))
        # Referencia com fracoes de acao (lot_size=0): com lote inteiro, acoes de preco
        # ajustado alto (ex.: IRBR3 acima de R$ 250 por vaga) ficariam fora do peso igual.
        res = simulate_portfolio(data, always, priority, dates, name="buy_and_hold_peso_igual",
                                 max_positions=len(tickers), use_priority=False,
                                 **dict(common, lot_size=0))
        portfolio_rows.append(portfolio_row(res, args.initial_cash, period))
        print(f"Periodo {period} concluido.", flush=True)
    variant_descriptions = {name: text for name, text, _ in variants}
    for label, text, _, _ in filter_tests:
        variant_descriptions[f"{main_name}_{label}"] = text
    variant_descriptions[f"{main_name}_sem_custos"] = (
        "Diagnostico: regra principal com custos e slippage zerados (mostra quanto os custos pesam).")
    variant_descriptions["buy_and_hold_peso_igual"] = (
        "Referencia: as 40 acoes compradas em peso igual (com fracoes de acao), sem rebalancear.")

    # Mesma regra de entrada da carteira (ROC positivo no primeiro candle) aplicada
    # ao backtest por ativo e as estatisticas de trades.
    entry_signals = {t: filter_signal_runs(signals[t], roc[t], args.min_roc) for t in tickers}

    # Todos os trades do sinal por ativo (sem limite de vagas) e efeito da prioridade.
    all_trades: list[dict[str, object]] = []
    for t in tickers:
        all_trades += signal_trades(t, data, entry_signals[t], priority[t], args.start, end,
                                    args.cost_bps, args.slippage_bps)
    priority_stats = {"Todos": trade_stats(all_trades)}
    non_priority = [t for t in all_trades if t["priority"] == 0]
    # A separacao por prioridade so aparece se houver sinais nao prioritarios.
    if non_priority:
        priority_stats["Prioritarios (preco ou SMA20 > SMA50)"] = trade_stats(
            [t for t in all_trades if t["priority"] == 1])
        priority_stats["Nao prioritarios"] = trade_stats(non_priority)

    # Ativo isolado: backtest classico de um ativo por vez.
    per_asset: list[dict[str, object]] = []
    for t in tickers:
        candles = data.candles[t]
        first = next(i for i, c in enumerate(candles) if c.date >= args.start)
        last = max(i for i, c in enumerate(candles) if c.date <= end)
        window_signals = list(entry_signals[t][first:last + 1])
        # Se o sinal ja estava ativo antes do inicio, espera ele terminar: a entrada
        # so pode ocorrer no primeiro candle de um sinal novo.
        index = 0
        while index < len(window_signals) and window_signals[index] == 1:
            window_signals[index] = 0
            index += 1
        summary, _, _ = run_strategy_vs_buy_hold(
            t, STRATEGY, candles[first:last + 1], window_signals,
            price_mode="adjusted", **common,
        )
        per_asset.append({
            "ticker": t, "cagr": summary.cagr, "retorno_total": summary.total_return,
            "max_drawdown": summary.max_drawdown, "sharpe": summary.sharpe, "exposicao": summary.exposure,
            "ordens": summary.trades, "buy_hold_cagr": summary.benchmark_cagr,
            "buy_hold_retorno_total": summary.benchmark_total_return,
            "buy_hold_max_drawdown": summary.benchmark_max_drawdown,
            "excesso_vs_buy_hold": summary.excess_total_return,
        })
    per_asset.sort(key=lambda r: float(r["cagr"]), reverse=True)

    out = args.output_dir
    write_csv(out / "carteira_variantes.csv", portfolio_rows)
    write_csv(out / "ativo_isolado.csv", per_asset)
    write_csv(out / "trades_do_sinal.csv", all_trades)
    if default_result is not None:
        write_csv(out / "ledger_regra_principal.csv", default_result.ledger)
        write_csv(out / "trades_regra_principal.csv", default_result.trades)
        write_csv(out / "equity_regra_principal.csv",
                  [{"date": d, "equity": e} for d, e in zip(default_result.dates, default_result.equities)])
    context = {
        "params": params, "cost_bps": args.cost_bps, "slippage_bps": args.slippage_bps, "lot_size": args.lot_size,
        "tickers": tickers, "universe_id": universe.get("id", ""), "portfolio_rows": portfolio_rows,
        "priority_stats": priority_stats, "per_asset": per_asset, "full_start": full_dates[0], "end": end,
        "max_positions": slots, "roc_period": args.roc_period, "min_roc": args.min_roc,
        "variant_descriptions": variant_descriptions,
    }
    write_markdown(out / "RESUMO.md", context)
    (out / "resumo.json").write_text(json.dumps({
        "estrategia": STRATEGY,
        "parametros": params,
        "prioridade": {"sma_rapida": args.priority_fast, "sma_lenta": args.priority_slow},
        "selecao": {"acoes_por_vez": slots, "entrada": "somente no primeiro candle do sinal",
                    "criterio": "maior ROC entre sinais novos com ROC positivo",
                    "roc_pregoes": args.roc_period, "roc_minimo": args.min_roc},
        "inicio": full_dates[0], "fim": end, "teste_inicio": test_dates[0] if test_dates else None,
        "capital_inicial_brl": args.initial_cash, "cost_bps": args.cost_bps,
        "slippage_bps": args.slippage_bps, "lot_size": args.lot_size,
        "gerado_em": date.today().isoformat(),
        "efeito_prioridade": priority_stats,
        "carteira": portfolio_rows,
    }, indent=2, ensure_ascii=False, default=lambda v: None), encoding="utf-8")
    print(f"Relatorios em {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
