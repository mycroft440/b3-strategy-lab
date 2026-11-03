"""Backtest do indicador RSI + WMA Heikin Ashi SEM gerenciamento de carteira.

Nao usa nenhum dos 478 gerenciamentos (sem ranking de momentum, sem
rebalanceamento, sem alvo de volatilidade). A carteira apenas segue o sinal:

- Sinal no fechamento, execucao na abertura do pregao seguinte.
- Vendas primeiro: toda posicao cujo sinal virou 0 e zerada.
- Compras depois: ativos com sinal 1 que nao estao na carteira ocupam vagas
  livres (``max_positions``). Cada entrada usa patrimonio/vagas, limitado ao
  caixa, e a posicao fica parada ate o sinal de saida (sem rebalancear).
- Ordem de compra: sinais prioritarios primeiro (fechamento ou SMA20 acima da
  SMA50), depois os demais. Empates seguem a ordem alfabetica do ticker.
  A variante ``sem_prioridade`` usa somente a ordem alfabetica, para medir o
  efeito do filtro de prioridade.

Tambem gera o resultado isolado por ativo (100% do capital em cada ativo, o
backtest classico de um ativo por vez) e as estatisticas de todos os trades do
sinal separados em prioritarios e nao prioritarios.
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
DEFAULT_UNIVERSE = ROOT / "data/universes/fixed_40_2018.json"
DEFAULT_OUTPUT_DIR = ROOT / "reports/rsi_wma_heikin_ashi"


@dataclass
class Position:
    shares: float
    entry_date: str
    entry_price: float
    entry_cost: float
    priority: int


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
) -> PortfolioResult:
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
                                  "priority": pos.priority})
            result.trades.append(_closed_trade(ticker, pos, current, fill, gross - fee))

        # 2) Entradas na abertura (sinal de compra no fechamento anterior).
        candidates = []
        for ticker in data.tickers:
            if ticker in positions:
                continue
            signal, prio = state(ticker, previous)
            if signal == 1:
                candidates.append((-(prio if use_priority else 0), ticker, prio))
        candidates.sort()
        free = max_positions - len(positions)
        if candidates and free > 0:
            equity_open = cash + sum(p.shares * float(candles[t].open) for t, p in positions.items())
            slot_value = equity_open / max_positions
            for _, ticker, prio in candidates[:free]:
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
                positions[ticker] = Position(qty, current, fill, gross + fee, prio)
                result.ledger.append({"date": current, "side": "BUY", "ticker": ticker, "shares": qty,
                                      "raw_open": raw, "execution_price": fill, "fee": fee, "slippage_cost": slip,
                                      "priority": prio})
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


def _closed_trade(ticker: str, pos: Position, exit_date: str, exit_price: float, proceeds: float) -> dict[str, object]:
    return {
        "ticker": ticker,
        "entry_date": pos.entry_date,
        "exit_date": exit_date,
        "entry_price": pos.entry_price,
        "exit_price": exit_price,
        "shares": pos.shares,
        "priority": pos.priority,
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
        if open_trade is None and wanted == 1:
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
        "dias_sinal_sem_vaga": result.missed_entries,
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
        f"e WMA({context['params']['wma_period']}) do fechamento Heikin Ashi subindo (WMA[t] > WMA[t-1]).",
        f"- **Venda**: RSI abaixo de {context['params']['rsi_exit']:g} ou WMA Heikin Ashi caindo (WMA[t] < WMA[t-1]).",
        "- **Prioridade**: sinal de compra com fechamento OU SMA20 acima da SMA50 entra antes dos demais.",
        "- \"RSI acima de 0\" foi lido como RSI centralizado (RSI - 50 > 0), ou seja RSI > 50; a leitura literal (RSI > 0) aparece como variante.",
        "- Sinal no fechamento, execucao na abertura seguinte; "
        f"custos {context['cost_bps']} bps + slippage {context['slippage_bps']} bps por ordem; lote de {context['lot_size']} acao.",
        f"- Universo: {len(context['tickers'])} acoes (`{context['universe_id']}`), candles ajustados por splits, sem dividendos/JCP. "
        "O universo tem vies de sobrevivencia declarado.",
        "- **Sem gerenciamento**: sem ranking, sem rebalanceamento e sem alvo de volatilidade. Cada vaga recebe patrimonio/vagas "
        "na entrada e fica parada ate o sinal de venda.\n",
        "## Carteira seguindo o sinal\n",
        "| Periodo | Variante | Vagas | CAGR | Retorno total | Max DD | Sharpe | Calmar | Exposicao | Trades | Acerto | Fator lucro | Dias-sinal sem vaga |",
        "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in rows:
        lines.append(
            f"| {r['periodo']} | `{r['variante']}` | {r['max_posicoes']} | **{_pct(r['cagr'])}** | {_pct(r['retorno_total'])} | "
            f"{_pct(r['max_drawdown'])} | {_num(r['sharpe'])} | {_num(r['calmar'])} | {_pct(r['exposicao'])} | "
            f"{r['trades_fechados']} | {_pct(r['taxa_acerto'])} | {_num(r['fator_lucro'])} | {r['dias_sinal_sem_vaga']} |"
        )

    lines += [
        "\n## Efeito da prioridade (todos os trades do sinal, sem limite de vagas)\n",
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
        f"\n## Ativo isolado (100% do capital em cada ativo, {context['full_start']} a {context['end']})\n",
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
    parser.add_argument("--priority-fast", type=int, default=20)
    parser.add_argument("--priority-slow", type=int, default=50)
    parser.add_argument("--max-positions", type=int, nargs="+", default=[1, 3, 5, 10])
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
              "rsi_exit": args.rsi_exit, "wma_period": args.wma_period}
    literal = dict(params, rsi_entry=0.0)

    def build(parameters: dict[str, object]) -> dict[str, list[int]]:
        return {t: rsi_wma_heikin_ashi(data.candles[t], **parameters) for t in tickers}

    signals = build(params)
    literal_signals = build(literal)
    always = {t: [1] * len(data.candles[t]) for t in tickers}
    priority = {t: priority_flags(data.candles[t], fast_period=args.priority_fast, slow_period=args.priority_slow)
                for t in tickers}

    common = dict(initial_cash=args.initial_cash, cost_bps=args.cost_bps,
                  slippage_bps=args.slippage_bps, lot_size=args.lot_size)
    portfolio_rows: list[dict[str, object]] = []
    default_result: PortfolioResult | None = None
    default_slots = 5 if 5 in args.max_positions else args.max_positions[0]
    for period, dates in (("2018+", full_dates), ("2023+ (teste)", test_dates)):
        if len(dates) < 2:
            continue
        for slots in args.max_positions:
            for use_priority in (True, False):
                name = "com_prioridade" if use_priority else "sem_prioridade"
                res = simulate_portfolio(data, signals, priority, dates, name=name, max_positions=slots,
                                         use_priority=use_priority, **common)
                portfolio_rows.append(portfolio_row(res, args.initial_cash, period))
                if period == "2018+" and slots == default_slots and use_priority:
                    default_result = res
        res = simulate_portfolio(data, literal_signals, priority, dates, name="rsi_acima_de_0_literal",
                                 max_positions=default_slots, use_priority=True, **common)
        portfolio_rows.append(portfolio_row(res, args.initial_cash, period))
        res = simulate_portfolio(data, always, priority, dates, name="buy_and_hold_peso_igual",
                                 max_positions=len(tickers), use_priority=False, **common)
        portfolio_rows.append(portfolio_row(res, args.initial_cash, period))
        print(f"Periodo {period} concluido.", flush=True)

    # Todos os trades do sinal por ativo (sem limite de vagas) e efeito da prioridade.
    all_trades: list[dict[str, object]] = []
    for t in tickers:
        all_trades += signal_trades(t, data, signals[t], priority[t], args.start, end,
                                    args.cost_bps, args.slippage_bps)
    priority_stats = {
        "Todos": trade_stats(all_trades),
        "Prioritarios (preco ou SMA20 > SMA50)": trade_stats([t for t in all_trades if t["priority"] == 1]),
        "Nao prioritarios": trade_stats([t for t in all_trades if t["priority"] == 0]),
    }

    # Ativo isolado: backtest classico de um ativo por vez.
    per_asset: list[dict[str, object]] = []
    for t in tickers:
        candles = data.candles[t]
        first = next(i for i, c in enumerate(candles) if c.date >= args.start)
        last = max(i for i, c in enumerate(candles) if c.date <= end)
        summary, _, _ = run_strategy_vs_buy_hold(
            t, STRATEGY, candles[first:last + 1], signals[t][first:last + 1],
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
        write_csv(out / f"ledger_carteira_{default_slots}_vagas.csv", default_result.ledger)
        write_csv(out / f"equity_carteira_{default_slots}_vagas.csv",
                  [{"date": d, "equity": e} for d, e in zip(default_result.dates, default_result.equities)])
    context = {
        "params": params, "cost_bps": args.cost_bps, "slippage_bps": args.slippage_bps, "lot_size": args.lot_size,
        "tickers": tickers, "universe_id": universe.get("id", ""), "portfolio_rows": portfolio_rows,
        "priority_stats": priority_stats, "per_asset": per_asset, "full_start": full_dates[0], "end": end,
    }
    write_markdown(out / "RESUMO.md", context)
    (out / "resumo.json").write_text(json.dumps({
        "estrategia": STRATEGY,
        "parametros": params,
        "prioridade": {"sma_rapida": args.priority_fast, "sma_lenta": args.priority_slow},
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
