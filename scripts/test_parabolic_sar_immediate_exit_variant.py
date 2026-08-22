from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.backtest_strategy_management_combinations import (  # noqa: E402
    DEFAULT_UNIVERSE_MANIFEST,
    _build_eligibility,
    _load_universe,
)
from scripts.research_portfolio_allocation import (  # noqa: E402
    MarketData,
    _configs,
    run_portfolio,
)
from scripts.research_portfolio_allocation_core import (  # noqa: E402
    _date_window,
    _eligible_tickers,
    _is_rebalance_date,
    _portfolio_metrics,
    _rebalance,
    _target_weights,
    _yearly_returns,
)

STRATEGY = "parabolic_sar_trend"
MANAGEMENT = "top1_risk_adjusted_lb252_skip0_trend0_vol63_equal_monthly_abs_cap1_adjusted"
START = "2018-01-02"
INITIAL_CASH = 1_000.0
COST_BPS = 3.2
SLIPPAGE_BPS = 10.0
LOT_SIZE = 1
DEFAULT_OUTPUT = Path("reports/parabolic_sar_immediate_exit_variant/AUDIT.json")


def run_immediate_exit_variant(
    data: MarketData,
    config,
    eligibility: dict[str, list[int]],
    *,
    start: str,
    end: str,
    initial_cash: float,
    cost_bps: float,
    slippage_bps: float,
    lot_size: int,
) -> dict[str, object]:
    """Monthly selection, but exit to cash next open when the held SAR signal turns 0.

    Re-entry remains monthly. A signal observed at a session close can only affect the
    next session open, preserving the same close-decision/next-open execution contract
    used by the matrix backtest.
    """

    cost_rate = cost_bps / 10_000
    slippage_rate = slippage_bps / 10_000
    dates = _date_window(data.dates, start, end)
    if len(dates) < 2:
        raise ValueError("Periodo insuficiente para a variante.")

    cash = float(initial_cash)
    shares = {ticker: 0.0 for ticker in data.tickers}
    last_prices: dict[str, float] = {}
    pending_targets: dict[str, float] | None = None
    pending_reason: str | None = None
    equities: list[float] = []
    total_trades = 0
    total_turnover = 0.0
    exposure_days = 0
    position_days = 0
    exit_signal_count = 0
    exit_trade_count = 0
    exit_dates: list[str] = []

    for index, current_date in enumerate(dates):
        next_date = dates[index + 1] if index + 1 < len(dates) else None
        today_candles = {
            ticker: data.by_date[ticker][current_date]
            for ticker in data.tickers
            if current_date in data.by_date[ticker]
        }

        trade_count = 0
        turnover = 0.0
        execution_reason = pending_reason
        if pending_targets is not None:
            trade_count, turnover, cash = _rebalance(
                current_date,
                data.tickers,
                today_candles,
                last_prices,
                shares,
                cash,
                pending_targets,
                cost_rate,
                slippage_rate,
                lot_size,
            )
            total_trades += trade_count
            total_turnover += turnover
            if execution_reason == "sar_exit" and trade_count > 0:
                exit_trade_count += trade_count
                exit_dates.append(current_date)

        for ticker, candle in today_candles.items():
            last_prices[ticker] = candle.close

        selected = [ticker for ticker in data.tickers if shares[ticker] > 0]
        missing_closes = sorted(
            ticker
            for ticker in selected
            if ticker not in today_candles or today_candles[ticker].close <= 0
        )
        if missing_closes:
            raise ValueError(
                f"{current_date}: fechamento fresco ausente para " + ", ".join(missing_closes)
            )

        invested_value = sum(
            shares[ticker] * today_candles[ticker].close for ticker in selected
        )
        equity = cash + invested_value
        invested_weight = invested_value / equity if equity > 0 else 0.0
        equities.append(equity)
        exposure_days += int(invested_weight > 0.01)
        position_days += len(selected)

        pending_targets = None
        pending_reason = None
        if next_date is None:
            continue

        if _is_rebalance_date(current_date, next_date, config.rebalance):
            pending_targets = _target_weights(
                data,
                current_date,
                config,
                eligible_tickers=_eligible_tickers(data, current_date, eligibility),
            )
            pending_reason = "monthly_rebalance"
            continue

        if selected:
            eligible_today = _eligible_tickers(data, current_date, eligibility) or set()
            if any(ticker not in eligible_today for ticker in selected):
                pending_targets = {}
                pending_reason = "sar_exit"
                exit_signal_count += 1

    result_metrics = _portfolio_metrics(equities, dates, initial_cash)
    yearly = _yearly_returns(equities, dates, initial_cash)
    return {
        "start": dates[0],
        "end": dates[-1],
        "candles": len(dates),
        "trades": total_trades,
        "exposure": exposure_days / len(dates),
        "avg_positions": position_days / len(dates),
        "final_equity": equities[-1],
        "total_return": result_metrics["total_return"],
        "cagr": result_metrics["cagr"],
        "max_drawdown": result_metrics["max_drawdown"],
        "annual_volatility": result_metrics["annual_volatility"],
        "sharpe": result_metrics["sharpe"],
        "turnover": total_turnover,
        "average_annual_return": statistics.mean(yearly.values()) if yearly else 0.0,
        "yearly_returns": {str(year): value for year, value in yearly.items()},
        "sar_exit_signal_count": exit_signal_count,
        "sar_exit_trade_count": exit_trade_count,
        "sar_exit_execution_dates": exit_dates,
    }


def _summary_dict(summary, curve) -> dict[str, object]:
    yearly = {}
    prior = INITIAL_CASH
    year_ends: dict[int, float] = {}
    for point in curve:
        year_ends[int(point.date[:4])] = point.equity
    for year, end_equity in year_ends.items():
        yearly[str(year)] = end_equity / prior - 1 if prior > 0 else 0.0
        prior = end_equity
    return {
        "start": summary.start,
        "end": summary.end,
        "candles": summary.candles,
        "trades": summary.trades,
        "exposure": summary.exposure,
        "avg_positions": summary.avg_positions,
        "final_equity": summary.final_equity,
        "total_return": summary.total_return,
        "cagr": summary.cagr,
        "max_drawdown": summary.max_drawdown,
        "annual_volatility": summary.annual_volatility,
        "sharpe": summary.sharpe,
        "turnover": summary.turnover,
        "average_annual_return": summary.average_annual_return,
        "yearly_returns": yearly,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compara o Parabolic SAR mensal original com saida diaria causal para caixa.")
    parser.add_argument("--universe-manifest", type=Path, default=DEFAULT_UNIVERSE_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    universe = _load_universe(args.universe_manifest)
    tickers = [ticker.upper() for ticker in universe["tickers"]]
    data = MarketData(
        tickers,
        "1d",
        "adjusted",
        require_verified_splits_from=universe["warmup_start"],
        history_start=str(universe["warmup_start"]),
    )
    end = min(data.candles[ticker][-1].date for ticker in tickers)
    eligibility = _build_eligibility(
        data,
        [STRATEGY],
        "adjusted",
        signal_start=str(universe["warmup_start"]),
    )[STRATEGY]

    configs = {config.name: config for config in _configs("adjusted", "all")}
    if MANAGEMENT not in configs:
        raise ValueError(f"Gerenciamento vencedor nao encontrado: {MANAGEMENT}")
    config = configs[MANAGEMENT]

    baseline_summary, baseline_curve = run_portfolio(
        data,
        config,
        start=START,
        end=end,
        initial_cash=INITIAL_CASH,
        cost_bps=COST_BPS,
        slippage_bps=SLIPPAGE_BPS,
        lot_size=LOT_SIZE,
        eligibility=eligibility,
        collect_curve=True,
    )
    baseline = _summary_dict(baseline_summary, baseline_curve)
    variant = run_immediate_exit_variant(
        data,
        config,
        eligibility,
        start=START,
        end=end,
        initial_cash=INITIAL_CASH,
        cost_bps=COST_BPS,
        slippage_bps=SLIPPAGE_BPS,
        lot_size=LOT_SIZE,
    )

    if abs(float(baseline["final_equity"]) - 24062.52) > 1.0:
        raise SystemExit(
            "Baseline divergiu do Top 1 publicado; abortando comparacao para evitar conclusao com premissas diferentes. "
            f"Obtido R$ {float(baseline['final_equity']):.2f}."
        )

    metrics = [
        "final_equity",
        "total_return",
        "cagr",
        "max_drawdown",
        "annual_volatility",
        "sharpe",
        "turnover",
        "trades",
        "exposure",
        "average_annual_return",
    ]
    delta = {
        metric: float(variant[metric]) - float(baseline[metric])
        for metric in metrics
    }
    payload = {
        "strategy": STRATEGY,
        "strategy_parameters": {"af_step": 0.02, "af_max": 0.2},
        "management": MANAGEMENT,
        "execution_contract": {
            "selection": "monthly at confirmed close",
            "normal_execution": "next session open",
            "variant_exit_signal": "held parabolic_sar_trend eligibility changes to 0 at a non-rebalance close",
            "variant_exit_execution": "next session open to cash",
            "variant_reentry": "only at the next normal monthly rebalance",
            "cost_bps_per_order": COST_BPS,
            "slippage_bps_per_order": SLIPPAGE_BPS,
            "lot_size": LOT_SIZE,
        },
        "baseline": baseline,
        "variant": variant,
        "delta_variant_minus_baseline": delta,
        "variant_improves_final_equity": float(variant["final_equity"]) > float(baseline["final_equity"]),
        "variant_improves_max_drawdown": float(variant["max_drawdown"]) > float(baseline["max_drawdown"]),
        "variant_improves_sharpe": float(variant["sharpe"]) > float(baseline["sharpe"]),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md = args.output.with_suffix(".md")
    md.write_text(
        "# Parabolic SAR — variante de saida imediata\n\n"
        f"Periodo: **{baseline['start']} a {baseline['end']}**  \n"
        f"Gerenciamento: `{MANAGEMENT}`  \n"
        f"Custos: **{COST_BPS} bps** | Slippage: **{SLIPPAGE_BPS} bps**\n\n"
        "| Metrica | Original mensal | Variante | Delta |\n"
        "|---|---:|---:|---:|\n"
        f"| Patrimonio final | R$ {float(baseline['final_equity']):,.2f} | R$ {float(variant['final_equity']):,.2f} | R$ {delta['final_equity']:,.2f} |\n"
        f"| Retorno total | {float(baseline['total_return']):.2%} | {float(variant['total_return']):.2%} | {delta['total_return']:.2%} |\n"
        f"| CAGR | {float(baseline['cagr']):.2%} | {float(variant['cagr']):.2%} | {delta['cagr']:.2%} |\n"
        f"| Drawdown max. | {float(baseline['max_drawdown']):.2%} | {float(variant['max_drawdown']):.2%} | {delta['max_drawdown']:.2%} |\n"
        f"| Sharpe | {float(baseline['sharpe']):.3f} | {float(variant['sharpe']):.3f} | {delta['sharpe']:.3f} |\n"
        f"| Trades | {int(baseline['trades'])} | {int(variant['trades'])} | {int(delta['trades'])} |\n"
        f"| Turnover | {float(baseline['turnover']):.2f}x | {float(variant['turnover']):.2f}x | {delta['turnover']:.2f}x |\n"
        f"| Exposicao | {float(baseline['exposure']):.2%} | {float(variant['exposure']):.2%} | {delta['exposure']:.2%} |\n\n"
        f"Sinais de saida SAR intramensais: **{int(variant['sar_exit_signal_count'])}**.  \n"
        f"Ordens executadas por essas saidas: **{int(variant['sar_exit_trade_count'])}**.\n",
        encoding="utf-8",
    )
    print(md.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
