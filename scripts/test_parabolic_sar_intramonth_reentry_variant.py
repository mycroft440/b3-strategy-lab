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
from scripts.test_parabolic_sar_immediate_exit_variant import _summary_dict  # noqa: E402

STRATEGY = "parabolic_sar_trend"
MANAGEMENT = "top1_risk_adjusted_lb252_skip0_trend0_vol63_equal_monthly_abs_cap1_adjusted"
START = "2018-01-02"
INITIAL_CASH = 1_000.0
COST_BPS = 3.2
SLIPPAGE_BPS = 10.0
LOT_SIZE = 1
DEFAULT_OUTPUT = Path("reports/parabolic_sar_intramonth_reentry_variant/AUDIT.json")


def run_intramonth_reentry_variant(
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
    """Monthly ranking with daily SAR exit and re-entry into the same monthly target.

    The monthly ranking fixes the designated target until the next monthly decision.
    If that target's Parabolic SAR becomes bearish at a confirmed close, the position
    is sold at the next session open. If the same target becomes bullish again before
    the next monthly rebalance, it is repurchased at the next session open. The
    ranking itself is never recomputed intramonth.
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
    designated_target: dict[str, float] = {}
    equities: list[float] = []
    total_trades = 0
    total_turnover = 0.0
    exposure_days = 0
    position_days = 0
    exit_signal_count = 0
    exit_trade_count = 0
    reentry_signal_count = 0
    reentry_trade_count = 0
    exit_dates: list[str] = []
    reentry_dates: list[str] = []

    for index, current_date in enumerate(dates):
        next_date = dates[index + 1] if index + 1 < len(dates) else None
        today_candles = {
            ticker: data.by_date[ticker][current_date]
            for ticker in data.tickers
            if current_date in data.by_date[ticker]
        }

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
            elif execution_reason == "sar_reentry" and trade_count > 0:
                reentry_trade_count += trade_count
                reentry_dates.append(current_date)

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
            designated_target = _target_weights(
                data,
                current_date,
                config,
                eligible_tickers=_eligible_tickers(data, current_date, eligibility),
            )
            pending_targets = dict(designated_target)
            pending_reason = "monthly_rebalance"
            continue

        if not designated_target:
            continue

        # top1 management should designate at most one ticker, but keep the logic
        # general and fail closed if the contract changes unexpectedly.
        target_tickers = [ticker for ticker, weight in designated_target.items() if weight > 0]
        if len(target_tickers) > 1:
            raise ValueError("Variante espera gerenciamento top1 com no maximo um alvo mensal.")
        if not target_tickers:
            continue
        target = target_tickers[0]
        eligible_today = _eligible_tickers(data, current_date, eligibility) or set()
        is_bull = target in eligible_today
        is_held = shares[target] > 0

        if is_held and not is_bull:
            pending_targets = {}
            pending_reason = "sar_exit"
            exit_signal_count += 1
        elif not is_held and is_bull:
            pending_targets = dict(designated_target)
            pending_reason = "sar_reentry"
            reentry_signal_count += 1

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
        "sar_reentry_signal_count": reentry_signal_count,
        "sar_reentry_trade_count": reentry_trade_count,
        "sar_exit_execution_dates": exit_dates,
        "sar_reentry_execution_dates": reentry_dates,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compara o Parabolic SAR mensal original com saida/reentrada SAR intramensal causal."
    )
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
    variant = run_intramonth_reentry_variant(
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
    delta = {metric: float(variant[metric]) - float(baseline[metric]) for metric in metrics}
    payload = {
        "strategy": STRATEGY,
        "strategy_parameters": {"af_step": 0.02, "af_max": 0.2},
        "management": MANAGEMENT,
        "execution_contract": {
            "selection": "monthly ranking at confirmed close",
            "normal_execution": "next session open",
            "monthly_target_persistence": "monthly selected ticker remains designated until next monthly ranking",
            "variant_exit_signal": "designated held ticker Parabolic SAR eligibility is 0 at any non-rebalance close",
            "variant_exit_execution": "next session open to cash",
            "variant_reentry_signal": "same designated monthly ticker Parabolic SAR eligibility returns to 1 before next monthly ranking",
            "variant_reentry_execution": "next session open into the same designated ticker",
            "intramonth_ranking_reoptimization": False,
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
        "# Parabolic SAR — saida e reentrada intramensal\n\n"
        f"Periodo: **{baseline['start']} a {baseline['end']}**  \n"
        f"Gerenciamento: `{MANAGEMENT}`  \n"
        f"Custos: **{COST_BPS} bps** | Slippage: **{SLIPPAGE_BPS} bps**\n\n"
        "| Metrica | Original mensal | Saida + reentrada SAR | Delta |\n"
        "|---|---:|---:|---:|\n"
        f"| Patrimonio final | R$ {float(baseline['final_equity']):,.2f} | R$ {float(variant['final_equity']):,.2f} | R$ {delta['final_equity']:,.2f} |\n"
        f"| Retorno total | {float(baseline['total_return']):.2%} | {float(variant['total_return']):.2%} | {delta['total_return']:.2%} |\n"
        f"| CAGR | {float(baseline['cagr']):.2%} | {float(variant['cagr']):.2%} | {delta['cagr']:.2%} |\n"
        f"| Drawdown max. | {float(baseline['max_drawdown']):.2%} | {float(variant['max_drawdown']):.2%} | {delta['max_drawdown']:.2%} |\n"
        f"| Sharpe | {float(baseline['sharpe']):.3f} | {float(variant['sharpe']):.3f} | {delta['sharpe']:.3f} |\n"
        f"| Trades | {int(baseline['trades'])} | {int(variant['trades'])} | {int(delta['trades'])} |\n"
        f"| Turnover | {float(baseline['turnover']):.2f}x | {float(variant['turnover']):.2f}x | {delta['turnover']:.2f}x |\n"
        f"| Exposicao | {float(baseline['exposure']):.2%} | {float(variant['exposure']):.2%} | {delta['exposure']:.2%} |\n\n"
        f"Saidas SAR intramensais executadas: **{int(variant['sar_exit_trade_count'])}**.  \n"
        f"Reentradas SAR intramensais executadas: **{int(variant['sar_reentry_trade_count'])}**.\n",
        encoding="utf-8",
    )
    print(md.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
