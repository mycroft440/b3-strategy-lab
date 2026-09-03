from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime
from functools import lru_cache
from itertools import product
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from b3_strategy_lab.backtest import (  # noqa: E402
    CurvePoint,
    _slipped_price,
    metrics,
    simulate_buy_and_hold_price_only,
)
from b3_strategy_lab.candles import DEFAULT_TICKERS, Candle, cache_path, load_candles  # noqa: E402
from b3_strategy_lab.cotahist import load_verified_candles  # noqa: E402


INITIAL_CASH = 1_000.0
COST_BPS = 3.2
SLIPPAGE_BPS = 10.0
LOT_SIZE = 1
REPORTS_DIR = Path("reports")


@dataclass(frozen=True)
class PortfolioConfig:
    name: str
    lookback: int = 126
    skip: int = 0
    top_n: int = 1
    trend_window: int = 0
    vol_window: int = 63
    rebalance: str = "monthly"
    score: str = "momentum"
    weighting: str = "equal"
    absolute_momentum: bool = True
    max_weight: float = 1.0
    target_vol: float = 0.0
    signal_mode: str = "adjusted"
    roc_windows: str = ""
    roc_weights: str = ""
    positive_rule: str = "score"
    short_window: int = 0
    short_weight: float = 0.0


@dataclass(frozen=True)
class PortfolioSummary:
    strategy: str
    start: str
    end: str
    candles: int
    trades: int
    exposure: float
    avg_positions: float
    final_equity: float
    total_return: float
    cagr: float
    max_drawdown: float
    annual_volatility: float
    sharpe: float
    turnover: float
    average_annual_return: float


@dataclass(frozen=True)
class PortfolioCurveRow:
    date: str
    equity: float
    cash: float
    invested_weight: float
    positions: int
    selected: str
    trade_count: int
    turnover: float
    dividend_cash: float


class MarketData:
    def __init__(
        self,
        tickers: list[str],
        interval: str,
        signal_mode: str,
        *,
        allow_unverified_data: bool = False,
        require_verified_splits_from: str | None = None,
        history_start: str | None = None,
    ) -> None:
        self.tickers = tickers
        self.interval = interval
        self.signal_mode = signal_mode
        self.candles: dict[str, list[Candle]] = {}
        self.by_date: dict[str, dict[str, Candle]] = {}
        self.index_by_date: dict[str, dict[str, int]] = {}
        self.signal_prices: dict[str, list[float]] = {}
        self.raw_returns: dict[str, list[float]] = {}
        self.manifests: dict[str, object] = {}
        self.candidate_profile_cache: dict[tuple[object, ...], dict | None] = {}
        dates: set[str] = set()

        for ticker in tickers:
            if allow_unverified_data:
                candles = load_candles(cache_path(ticker, interval))
                if history_start is not None:
                    candles = [
                        candle for candle in candles if candle.date >= history_start
                    ]
            else:
                candles, manifest = load_verified_candles(
                    ticker,
                    interval,
                    start=history_start,
                    require_verified_splits_from=require_verified_splits_from,
                )
                self.manifests[ticker] = manifest
            if not candles:
                raise ValueError(
                    f"{ticker}: nenhum candle disponivel desde "
                    f"{history_start or 'o inicio da serie'}."
                )
            self.candles[ticker] = candles
            self.by_date[ticker] = {candle.date: candle for candle in candles}
            self.index_by_date[ticker] = {candle.date: index for index, candle in enumerate(candles)}
            self.signal_prices[ticker] = [
                candle.close if signal_mode == "adjusted" else candle.raw_close
                for candle in candles
            ]
            self.raw_returns[ticker] = _returns(self.signal_prices[ticker])
            dates.update(candle.date for candle in candles)

        self.dates = sorted(dates, key=_point_datetime)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pesquisa de regras de alocacao entre acoes B3.")
    parser.add_argument("--tickers", nargs="+", default=list(DEFAULT_TICKERS))
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--suffix", default="")
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument(
        "--signal-modes",
        nargs="+",
        default=["adjusted"],
        choices=["adjusted", "raw"],
    )
    parser.add_argument("--config-set", default="all", choices=["all", "base", "roc", "roc_hybrid", "roc_filter_short"])
    parser.add_argument("--allow-unverified-data", action="store_true")
    args = parser.parse_args(argv)

    tickers = [ticker.upper() for ticker in args.tickers]
    rows: list[dict] = []
    for signal_mode in args.signal_modes:
        data = MarketData(
            tickers,
            args.interval,
            signal_mode,
            allow_unverified_data=args.allow_unverified_data,
        )
        split_index = max(1, min(len(data.dates) - 2, int(len(data.dates) * args.train_ratio)))
        train_end = data.dates[split_index]
        test_start = data.dates[split_index + 1]
        configs = _configs(signal_mode, args.config_set)

        for index, config in enumerate(configs, start=1):
            full_summary, _ = run_portfolio(data, config)
            train_summary, _ = run_portfolio(data, config, end=train_end)
            test_summary, _ = run_portfolio(data, config, start=test_start)
            rows.append(_row(config, full_summary, train_summary, test_summary, train_end, test_start))
            if index % 100 == 0:
                print(f"{signal_mode}: {index}/{len(configs)} regras...", flush=True)

        print(
            f"{signal_mode}: {len(configs)} regras testadas; treino ate {train_end}, teste desde {test_start}",
            flush=True,
        )

    rows.sort(key=lambda row: (float(row["test_cagr"]), float(row["full_cagr"])), reverse=True)
    output = (
        REPORTS_DIR
        / f"portfolio_allocation_research_price_only_{'_'.join(args.signal_modes)}_"
        f"{args.interval}{args.suffix}.csv"
    )
    _write(rows, output)
    _write_benchmarks(data, output.with_name(output.stem + "_benchmarks.csv"))
    _print_top(rows)
    return 0


def run_portfolio(
    data: MarketData,
    config: PortfolioConfig,
    *,
    start: str | None = None,
    end: str | None = None,
    initial_cash: float = INITIAL_CASH,
    cost_bps: float = COST_BPS,
    slippage_bps: float = SLIPPAGE_BPS,
    lot_size: int = LOT_SIZE,
    eligibility: dict[str, list[int]] | None = None,
    collect_curve: bool = True,
) -> tuple[PortfolioSummary, list[PortfolioCurveRow]]:
    cost_rate = cost_bps / 10_000
    slippage_rate = slippage_bps / 10_000
    dates = _date_window(data.dates, start, end)
    if len(dates) < 2:
        raise ValueError("Sao necessarias pelo menos 2 datas para simular a carteira.")

    cash = float(initial_cash)
    shares = {ticker: 0.0 for ticker in data.tickers}
    last_prices: dict[str, float] = {}
    pending_targets: dict[str, float] | None = None
    designated_targets: dict[str, float] = {}
    active_targets: dict[str, float] = {}
    curve: list[PortfolioCurveRow] = []
    equities: list[float] = []
    total_trades = 0
    total_turnover = 0.0
    exposure_days = 0
    position_days = 0

    prior_dates = [value for value in data.dates if value < dates[0]]
    prior_date = prior_dates[-1] if prior_dates else None
    if (
        prior_date is not None
        and _is_rebalance_date(prior_date, dates[0], config.rebalance)
    ):
        designated_targets = _target_weights(
            data,
            prior_date,
            config,
            eligible_tickers=_eligible_tickers(data, prior_date, eligibility),
        )
        pending_targets = dict(designated_targets)

    for index, current_date in enumerate(dates):
        next_date = dates[index + 1] if index + 1 < len(dates) else None
        today_candles = {
            ticker: data.by_date[ticker][current_date]
            for ticker in data.tickers
            if current_date in data.by_date[ticker]
        }

        dividend_cash = 0.0

        trade_count = 0
        turnover = 0.0
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
            active_targets = dict(pending_targets)
            total_trades += trade_count
            total_turnover += turnover

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
                f"{current_date}: fechamento fresco obrigatorio ausente para "
                + ", ".join(missing_closes)
            )
        invested_value = sum(
            shares[ticker] * today_candles[ticker].close for ticker in selected
        )
        equity = cash + invested_value
        invested_weight = invested_value / equity if equity > 0 else 0.0
        equities.append(equity)
        exposure_days += int(invested_weight > 0.01)
        position_days += len(selected)
        if collect_curve:
            curve.append(
                PortfolioCurveRow(
                    date=current_date,
                    equity=equity,
                    cash=cash,
                    invested_weight=invested_weight,
                    positions=len(selected),
                    selected=";".join(selected),
                    trade_count=trade_count,
                    turnover=turnover,
                    dividend_cash=dividend_cash,
                )
            )

        pending_targets = None
        if next_date is not None and _is_rebalance_date(
            current_date, next_date, config.rebalance
        ):
            designated_targets = _target_weights(
                data,
                current_date,
                config,
                eligible_tickers=_eligible_tickers(data, current_date, eligibility),
            )
            # A scheduled management rebalance must still run when the target
            # names/weights are unchanged, because market moves make the actual
            # portfolio weights drift between decision dates.
            pending_targets = dict(designated_targets)
        elif next_date is not None and eligibility is not None:
            # The management rule fixes the designated basket until its next
            # weekly/monthly decision. Trading-strategy exits and re-entries are
            # nevertheless acted on at the next open, as the binary signal
            # contract promises: 0 means cash and 1 means invested when the asset
            # remains in that designated basket. The ranking is not recomputed
            # between management rebalances.
            eligible_now = _eligible_tickers(data, current_date, eligibility) or set()
            signal_targets = {
                ticker: weight
                for ticker, weight in designated_targets.items()
                if ticker in eligible_now
            }
            if signal_targets != active_targets:
                pending_targets = signal_targets

    result_metrics = _portfolio_metrics(equities, dates, initial_cash)
    yearly = _yearly_returns(equities, dates, initial_cash)
    summary = PortfolioSummary(
        strategy=config.name,
        start=dates[0],
        end=dates[-1],
        candles=len(dates),
        trades=total_trades,
        exposure=exposure_days / len(dates),
        avg_positions=position_days / len(dates),
        final_equity=equities[-1],
        total_return=result_metrics["total_return"],
        cagr=result_metrics["cagr"],
        max_drawdown=result_metrics["max_drawdown"],
        annual_volatility=result_metrics["annual_volatility"],
        sharpe=result_metrics["sharpe"],
        turnover=total_turnover,
        average_annual_return=statistics.mean(yearly.values()) if yearly else 0.0,
    )
    return summary, curve


def _configs(signal_mode: str, config_set: str = "all") -> list[PortfolioConfig]:
    if config_set == "roc":
        return _roc_configs(signal_mode)
    if config_set == "roc_hybrid":
        return _roc_hybrid_configs(signal_mode)
    if config_set == "roc_filter_short":
        return _roc_filter_short_configs(signal_mode)

    configs = [
        PortfolioConfig(
            name=f"equal_all_{rebalance}_{signal_mode}",
            lookback=1,
            top_n=99,
            trend_window=0,
            rebalance=rebalance,
            score="all",
            weighting="equal",
            absolute_momentum=False,
            signal_mode=signal_mode,
        )
        for rebalance in ["monthly", "weekly"]
    ]
    configs.extend(
        PortfolioConfig(
            name=f"invvol_all_v{vol_window}_{rebalance}_{signal_mode}",
            lookback=1,
            top_n=99,
            trend_window=0,
            vol_window=vol_window,
            rebalance=rebalance,
            score="all",
            weighting="inv_vol",
            absolute_momentum=False,
            signal_mode=signal_mode,
        )
        for vol_window, rebalance in product([21, 63, 126], ["monthly", "weekly"])
    )

    momentum_setups = []
    for lookback in [21, 63, 126, 252]:
        skips = [0]
        if lookback >= 126:
            skips.append(21)
        momentum_setups.extend((lookback, skip) for skip in skips)

    for (lookback, skip), trend_window, vol_window, rebalance, score in product(
        momentum_setups,
        [0, 200],
        [21, 63],
        ["weekly", "monthly"],
        ["momentum", "risk_adjusted"],
    ):
        name = (
            f"top1_{score}_lb{lookback}_skip{skip}_trend{trend_window}"
            f"_vol{vol_window}_equal_{rebalance}_abs_cap1_{signal_mode}"
        )
        configs.append(
            PortfolioConfig(
                name=name,
                lookback=lookback,
                skip=skip,
                top_n=1,
                trend_window=trend_window,
                vol_window=vol_window,
                rebalance=rebalance,
                score=score,
                weighting="equal",
                absolute_momentum=True,
                signal_mode=signal_mode,
            )
        )

    for lookback, top_n, vol_window, rebalance, weighting in product(
        [63, 126, 252],
        [2, 3],
        [21, 63],
        ["weekly", "monthly"],
        ["equal", "inv_vol"],
    ):
        name = (
            f"top{top_n}_momentum_lb{lookback}_skip0_trend200"
            f"_vol{vol_window}_{weighting}_{rebalance}_abs_cap1_{signal_mode}"
        )
        configs.append(
            PortfolioConfig(
                name=name,
                lookback=lookback,
                top_n=top_n,
                trend_window=200,
                vol_window=vol_window,
                rebalance=rebalance,
                score="momentum",
                weighting=weighting,
                absolute_momentum=True,
                signal_mode=signal_mode,
            )
        )

    for lookback, top_n, trend_window, vol_window, target_vol, rebalance in product(
        [126, 252],
        [1, 2],
        [200],
        [63],
        [0.20, 0.30],
        ["monthly"],
    ):
        name = (
            f"top{top_n}_voltarget_lb{lookback}_trend{trend_window}"
            f"_vol{vol_window}_target{target_vol:g}_{rebalance}_{signal_mode}"
        )
        configs.append(
            PortfolioConfig(
                name=name,
                lookback=lookback,
                top_n=top_n,
                trend_window=trend_window,
                vol_window=vol_window,
                rebalance=rebalance,
                score="momentum",
                weighting="inv_vol",
                absolute_momentum=True,
                target_vol=target_vol,
                signal_mode=signal_mode,
            )
        )

    if config_set == "base":
        return configs
    return configs + _roc_configs(signal_mode) + _roc_hybrid_configs(signal_mode) + _roc_filter_short_configs(signal_mode)


def _roc_configs(signal_mode: str) -> list[PortfolioConfig]:
    configs: list[PortfolioConfig] = []
    weight_sets = {
        "1_1_1": (1.0, 1.0, 1.0),
        "2_1_1": (2.0, 1.0, 1.0),
        "1_1_2": (1.0, 1.0, 2.0),
    }
    windows = "252,126,63"

    for weight_label, weights in weight_sets.items():
        weights_text = ",".join(f"{weight:g}" for weight in weights)
        for skip, top_n, score, positive_rule in product(
            [0, 21],
            [1, 2, 3],
            ["roc_combo", "roc_combo_risk_adjusted"],
            ["score", "all_windows"],
        ):
            trend_windows = [0, 200] if top_n == 1 else [200]
            weightings = ["equal"] if top_n == 1 else ["equal", "inv_vol", "score_inv_vol"]
            for trend_window, weighting in product(trend_windows, weightings):
                name = (
                    f"top{top_n}_{score}_roc12_6_3_w{weight_label}_skip{skip}"
                    f"_trend{trend_window}_vol63_{weighting}_monthly"
                    f"_pos{positive_rule}_{signal_mode}"
                )
                configs.append(
                    PortfolioConfig(
                        name=name,
                        lookback=252,
                        skip=skip,
                        top_n=top_n,
                        trend_window=trend_window,
                        vol_window=63,
                        rebalance="monthly",
                        score=score,
                        weighting=weighting,
                        absolute_momentum=True,
                        signal_mode=signal_mode,
                        roc_windows=windows,
                        roc_weights=weights_text,
                        positive_rule=positive_rule,
                    )
                )

    for weight_label, weights in weight_sets.items():
        weights_text = ",".join(f"{weight:g}" for weight in weights)
        for top_n, target_vol in product([1, 2, 3], [0.25, 0.35]):
            name = (
                f"top{top_n}_roc_combo_risk_adjusted_roc12_6_3_w{weight_label}_skip0"
                f"_trend200_vol63_inv_vol_monthly_target{target_vol:g}_{signal_mode}"
            )
            configs.append(
                PortfolioConfig(
                    name=name,
                    lookback=252,
                    top_n=top_n,
                    trend_window=200,
                    vol_window=63,
                    rebalance="monthly",
                    score="roc_combo_risk_adjusted",
                    weighting="inv_vol" if top_n > 1 else "equal",
                    absolute_momentum=True,
                    target_vol=target_vol,
                    signal_mode=signal_mode,
                    roc_windows=windows,
                    roc_weights=weights_text,
                    positive_rule="score",
                )
            )

    return configs


def _roc_hybrid_configs(signal_mode: str) -> list[PortfolioConfig]:
    configs: list[PortfolioConfig] = []
    weight_sets = {
        "1_1_1": (1.0, 1.0, 1.0),
        "2_1_1": (2.0, 1.0, 1.0),
        "1_1_2": (1.0, 1.0, 2.0),
    }
    windows = "252,126,63"

    for weight_label, weights in weight_sets.items():
        weights_text = ",".join(f"{weight:g}" for weight in weights)
        for short_weight, top_n, positive_rule in product(
            [1.0, 2.0],
            [1, 2],
            ["score", "all_windows"],
        ):
            trend_windows = [0, 200] if top_n == 1 else [200]
            weightings = ["equal"] if top_n == 1 else ["equal", "inv_vol", "score_inv_vol"]
            for trend_window, weighting in product(trend_windows, weightings):
                name = (
                    f"top{top_n}_roc_short_blend_risk_adjusted_roc12_6_3_w{weight_label}_short21x{short_weight:g}"
                    f"_trend{trend_window}_vol63_{weighting}_monthly_pos{positive_rule}_{signal_mode}"
                )
                configs.append(
                    PortfolioConfig(
                        name=name,
                        lookback=252,
                        top_n=top_n,
                        trend_window=trend_window,
                        vol_window=63,
                        rebalance="monthly",
                        score="roc_short_blend_risk_adjusted",
                        weighting=weighting,
                        absolute_momentum=True,
                        signal_mode=signal_mode,
                        roc_windows=windows,
                        roc_weights=weights_text,
                        positive_rule=positive_rule,
                        short_window=21,
                        short_weight=short_weight,
                    )
                )

    return configs


def _roc_filter_short_configs(signal_mode: str) -> list[PortfolioConfig]:
    configs: list[PortfolioConfig] = []
    weight_sets = {
        "1_1_1": (1.0, 1.0, 1.0),
        "2_1_1": (2.0, 1.0, 1.0),
        "1_1_2": (1.0, 1.0, 2.0),
    }
    windows = "252,126,63"

    for weight_label, weights in weight_sets.items():
        weights_text = ",".join(f"{weight:g}" for weight in weights)
        for top_n, trend_window, vol_window, weighting, positive_rule in product(
            [1, 2],
            [0, 200],
            [21, 63],
            ["equal", "inv_vol"],
            ["score", "all_windows"],
        ):
            if top_n == 1 and weighting != "equal":
                continue
            if top_n > 1 and trend_window == 0:
                continue
            name = (
                f"top{top_n}_short_risk_adjusted_roc_filter_roc12_6_3_w{weight_label}"
                f"_short21_trend{trend_window}_vol{vol_window}_{weighting}"
                f"_monthly_pos{positive_rule}_{signal_mode}"
            )
            configs.append(
                PortfolioConfig(
                    name=name,
                    lookback=252,
                    top_n=top_n,
                    trend_window=trend_window,
                    vol_window=vol_window,
                    rebalance="monthly",
                    score="short_risk_adjusted_roc_filter",
                    weighting=weighting,
                    absolute_momentum=True,
                    signal_mode=signal_mode,
                    roc_windows=windows,
                    roc_weights=weights_text,
                    positive_rule=positive_rule,
                    short_window=21,
                    short_weight=1.0,
                )
            )

    return configs


def _eligible_tickers(
    data: MarketData,
    current_date: str,
    eligibility: dict[str, list[int]] | None,
) -> set[str] | None:
    if eligibility is None:
        return None

    eligible: set[str] = set()
    for ticker in data.tickers:
        index = data.index_by_date[ticker].get(current_date)
        signals = eligibility.get(ticker)
        if index is not None and signals is not None and index < len(signals) and signals[index] == 1:
            eligible.add(ticker)
    return eligible


def _target_weights(
    data: MarketData,
    current_date: str,
    config: PortfolioConfig,
    *,
    eligible_tickers: set[str] | None = None,
) -> dict[str, float]:
    candidates = []
    for ticker in data.tickers:
        if eligible_tickers is not None and ticker not in eligible_tickers:
            continue
        index = data.index_by_date[ticker].get(current_date)
        if index is None:
            continue
        profile = _candidate_profile(data, ticker, index, config)
        if profile is None:
            continue
        candidates.append(profile)

    if not candidates:
        return {}
    if config.score == "all":
        selected = candidates
    else:
        candidates.sort(key=lambda item: item["score"], reverse=True)
        selected = candidates[: config.top_n]

    weights = _weights(selected, config)
    weights = _cap_weights(weights, config.max_weight)

    if config.target_vol > 0 and weights:
        estimated_vol = math.sqrt(
            sum((weights[item["ticker"]] * item["volatility"]) ** 2 for item in selected if item["ticker"] in weights)
        )
        if estimated_vol > 0:
            scale = min(1.0, config.target_vol / estimated_vol)
            weights = {ticker: weight * scale for ticker, weight in weights.items()}

    return weights


def _candidate_profile(data: MarketData, ticker: str, index: int, config: PortfolioConfig) -> dict | None:
    cache = getattr(data, "candidate_profile_cache", None)
    # Portfolio name, rebalance frequency, number of selected assets, weighting,
    # caps and target volatility do not change a per-ticker candidate profile.
    # Excluding them lets semantically shared management configurations reuse the
    # expensive momentum/trend/volatility calculation without changing results.
    cache_key = (
        ticker,
        index,
        config.lookback,
        config.skip,
        config.trend_window,
        config.vol_window,
        config.score,
        config.absolute_momentum,
        config.roc_windows,
        config.roc_weights,
        config.positive_rule,
        config.short_window,
        config.short_weight,
    )
    if cache is not None and cache_key in cache:
        return cache[cache_key]

    profile = _candidate_profile_uncached(data, ticker, index, config)
    if cache is not None:
        cache[cache_key] = profile
    return profile


def _candidate_profile_uncached(
    data: MarketData,
    ticker: str,
    index: int,
    config: PortfolioConfig,
) -> dict | None:
    prices = data.signal_prices[ticker]
    recent_index = index - config.skip
    roc_windows = _parse_ints(config.roc_windows)
    lookback = max(roc_windows) if roc_windows else config.lookback
    past_index = recent_index - lookback
    if past_index < 0 or recent_index <= 0:
        return None
    if config.trend_window > 0 and index + 1 < config.trend_window:
        return None
    if index < config.vol_window:
        return None

    current_price = prices[index]
    recent_price = prices[recent_index]
    past_price = prices[past_index]
    if current_price <= 0 or recent_price <= 0 or past_price <= 0:
        return None

    momentum = recent_price / past_price - 1
    component_rocs = [momentum]
    if roc_windows:
        weights = _parse_floats(config.roc_weights) or [1.0] * len(roc_windows)
        if len(weights) != len(roc_windows):
            raise ValueError("roc_weights precisa ter o mesmo tamanho de roc_windows.")
        component_rocs = []
        weighted_sum = 0.0
        total_weight = 0.0
        for window, weight in zip(roc_windows, weights):
            window_index = recent_index - window
            if window_index < 0 or prices[window_index] <= 0:
                return None
            roc = recent_price / prices[window_index] - 1
            component_rocs.append(roc)
            weighted_sum += roc * weight
            total_weight += abs(weight)
        if total_weight <= 0:
            return None
        momentum = weighted_sum / total_weight
    if config.absolute_momentum and momentum <= 0:
        return None
    if config.positive_rule == "all_windows" and any(roc <= 0 for roc in component_rocs):
        return None
    if config.short_window > 0:
        short_index = recent_index - config.short_window
        if short_index < 0 or prices[short_index] <= 0:
            return None
        short_momentum = recent_price / prices[short_index] - 1
        if config.score.startswith("roc_short_blend"):
            momentum = (momentum + config.short_weight * short_momentum) / (1 + abs(config.short_weight))
            if config.absolute_momentum and momentum <= 0:
                return None
        elif config.score == "short_risk_adjusted_roc_filter":
            momentum = short_momentum
            if config.absolute_momentum and momentum <= 0:
                return None
    if config.trend_window > 0:
        trend_values = prices[index - config.trend_window + 1 : index + 1]
        if current_price <= sum(trend_values) / len(trend_values):
            return None

    vol_slice = data.raw_returns[ticker][max(0, index - config.vol_window + 1) : index + 1]
    volatility = _annualized_volatility(vol_slice)
    if volatility <= 0:
        return None

    if config.score in {
        "risk_adjusted",
        "roc_combo_risk_adjusted",
        "roc_short_blend_risk_adjusted",
        "short_risk_adjusted_roc_filter",
    }:
        score = momentum / volatility
    elif config.score == "all":
        score = 1.0
    elif config.score in {"momentum", "roc_combo", "roc_short_blend"}:
        score = momentum
    else:
        raise ValueError(f"Score desconhecido: {config.score}")

    return {"ticker": ticker, "momentum": momentum, "volatility": volatility, "score": score}


def _portfolio_metrics(
    equities: list[float],
    dates: list[str],
    initial_cash: float,
) -> dict[str, float]:
    if not equities or not dates or len(equities) != len(dates):
        raise ValueError("equities/dates must be non-empty and aligned")
    if initial_cash <= 0 or not math.isfinite(initial_cash):
        raise ValueError("initial_cash must be finite and positive")
    # Include capital-at-risk -> first close. Entry costs/slippage and first-session
    # P&L are economically real and must contribute to Sharpe/volatility.
    returns = [equities[0] / initial_cash - 1.0]
    returns.extend(
        equities[index] / equities[index - 1] - 1.0
        for index in range(1, len(equities))
        if equities[index - 1] > 0
    )
    total_return = equities[-1] / initial_cash - 1
    years = max(
        (_point_datetime(dates[-1]) - _point_datetime(dates[0])).total_seconds()
        / (365.25 * 24 * 60 * 60),
        1 / 365.25,
    )
    # dates[0] is the first close while initial_cash is capital immediately before
    # that first session. Add one calendar day only for risk-period annualization.
    risk_years = years + 1 / 365.25
    periods_per_year = len(returns) / risk_years if risk_years > 0 else 252.0
    peak = initial_cash
    max_drawdown = 0.0
    for equity in equities:
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = min(max_drawdown, equity / peak - 1)
    annual_volatility = (
        statistics.stdev(returns) * math.sqrt(periods_per_year)
        if len(returns) >= 2
        else 0.0
    )
    if len(returns) < 2:
        sharpe = 0.0
    else:
        return_std = statistics.stdev(returns)
        sharpe = (
            statistics.mean(returns) / return_std * math.sqrt(periods_per_year)
            if return_std > 0
            else 0.0
        )
    cagr = (1 + total_return) ** (1 / years) - 1 if total_return > -1 else -1.0
    return {
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": max_drawdown,
        "annual_volatility": annual_volatility,
        "sharpe": sharpe,
    }


def _yearly_returns(
    equities: list[float],
    dates: list[str],
    initial_equity: float,
) -> dict[int, float]:
    year_ends: dict[int, float] = {}
    for current_date, equity in zip(dates, equities):
        year = _point_datetime(current_date).year
        year_ends[year] = equity

    result: dict[int, float] = {}
    prior_equity = initial_equity
    for year, end_equity in year_ends.items():
        result[year] = end_equity / prior_equity - 1 if prior_equity > 0 else 0.0
        prior_equity = end_equity
    return result


def _weights(selected: list[dict], config: PortfolioConfig) -> dict[str, float]:
    if not selected:
        return {}
    if config.weighting == "equal":
        return {item["ticker"]: 1 / len(selected) for item in selected}
    if config.weighting == "inv_vol":
        raw = {item["ticker"]: 1 / item["volatility"] for item in selected if item["volatility"] > 0}
        return _normalize(raw)
    if config.weighting == "score_inv_vol":
        raw = {
            item["ticker"]: max(item["score"], 0.0) / item["volatility"]
            for item in selected
            if item["volatility"] > 0 and item["score"] > 0
        }
        return _normalize(raw)
    raise ValueError(f"Peso desconhecido: {config.weighting}")


def _rebalance(
    current_date: str,
    tickers: list[str],
    today_candles: dict[str, Candle],
    last_prices: dict[str, float],
    shares: dict[str, float],
    cash: float,
    target_weights: dict[str, float],
    cost_rate: float,
    slippage_rate: float,
    lot_size: int,
) -> tuple[int, float, float]:
    required_tickers = {
        ticker
        for ticker in tickers
        if shares[ticker] > 0 or target_weights.get(ticker, 0.0) > 0
    }
    missing_opens = sorted(
        ticker
        for ticker in required_tickers
        if ticker not in today_candles or today_candles[ticker].open <= 0
    )
    if missing_opens:
        raise ValueError(
            f"{current_date}: abertura fresca obrigatoria ausente para "
            + ", ".join(missing_opens)
        )
    prices = {ticker: today_candles[ticker].open for ticker in required_tickers}
    equity = cash + sum(
        shares[ticker] * prices[ticker]
        for ticker in tickers
        if shares[ticker] > 0
    )
    if equity <= 0:
        return 0, 0.0, cash

    trade_count = 0
    traded_notional = 0.0
    for ticker in tickers:
        price = prices.get(ticker)
        if price is None or shares[ticker] <= 0:
            continue
        target_value = equity * target_weights.get(ticker, 0.0)
        current_value = shares[ticker] * price
        if current_value <= target_value:
            continue
        execution_price = _slipped_price(price, "SELL", slippage_rate)
        shares_to_sell = min(shares[ticker], (current_value - target_value) / price)
        shares_to_sell = _floor_lot(shares_to_sell, lot_size)
        if shares_to_sell <= 0:
            continue
        cash += shares_to_sell * execution_price * (1 - cost_rate)
        shares[ticker] -= shares_to_sell
        traded_notional += shares_to_sell * execution_price
        trade_count += 1

    buy_plan: dict[str, float] = {}
    execution_prices: dict[str, float] = {}
    for ticker, weight in target_weights.items():
        price = prices.get(ticker)
        if price is None or weight <= 0:
            continue
        execution_price = _slipped_price(price, "BUY", slippage_rate)
        current_value = shares[ticker] * price
        target_value = equity * weight
        desired_shares = max(0.0, target_value - current_value) / price
        planned_shares = _floor_lot(desired_shares, lot_size)
        if planned_shares <= 0:
            continue
        buy_plan[ticker] = planned_shares
        execution_prices[ticker] = execution_price

    planned_cost = sum(
        quantity * execution_prices[ticker] * (1 + cost_rate)
        for ticker, quantity in buy_plan.items()
    )
    if planned_cost > cash + 1e-9 and planned_cost > 0:
        scale = max(0.0, min(1.0, cash / planned_cost))
        buy_plan = {
            ticker: _floor_lot(quantity * scale, lot_size)
            for ticker, quantity in buy_plan.items()
        }

    for ticker in sorted(buy_plan):
        shares_to_buy = buy_plan[ticker]
        if shares_to_buy <= 0:
            continue
        execution_price = execution_prices[ticker]
        debit = shares_to_buy * execution_price * (1 + cost_rate)
        if debit > cash + 1e-9:
            raise ValueError(
                f"{current_date}/{ticker}: plano proporcional excedeu o caixa disponivel."
            )
        cash -= debit
        shares[ticker] += shares_to_buy
        traded_notional += shares_to_buy * execution_price
        trade_count += 1

    return trade_count, traded_notional / equity, cash


def _write(rows: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "strategy",
        "signal_mode",
        "lookback",
        "skip",
        "top_n",
        "trend_window",
        "vol_window",
        "rebalance",
        "score",
        "weighting",
        "absolute_momentum",
        "max_weight",
        "target_vol",
        "roc_windows",
        "roc_weights",
        "positive_rule",
        "short_window",
        "short_weight",
        "full_start",
        "full_end",
        "full_candles",
        "full_trades",
        "full_exposure",
        "full_avg_positions",
        "full_total_return",
        "full_cagr",
        "full_max_drawdown",
        "full_volatility",
        "full_sharpe",
        "full_turnover",
        "train_end",
        "train_total_return",
        "train_cagr",
        "train_max_drawdown",
        "train_sharpe",
        "test_start",
        "test_total_return",
        "test_cagr",
        "test_max_drawdown",
        "test_sharpe",
        "test_trades",
        "test_exposure",
    ]
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fields} for row in rows])
    print(f"Salvo: {output} ({len(rows)} linhas)")


def _write_benchmarks(data: MarketData, output: Path) -> None:
    rows = []
    for ticker in data.tickers:
        candles = data.candles[ticker]
        curve = simulate_buy_and_hold_price_only(
            candles,
            initial_cash=INITIAL_CASH,
            cost_bps=COST_BPS,
            slippage_bps=SLIPPAGE_BPS,
            lot_size=LOT_SIZE,
        )
        result_metrics = metrics(curve, INITIAL_CASH)
        rows.append(
            {
                "ticker": ticker,
                "start": candles[0].date,
                "end": candles[-1].date,
                "candles": len(candles),
                "trades": sum(1 for point in curve if point.trade),
                "total_return": result_metrics["total_return"],
                "cagr": result_metrics["cagr"],
                "max_drawdown": result_metrics["max_drawdown"],
                "annual_volatility": result_metrics["annual_volatility"],
                "sharpe": result_metrics["sharpe"],
            }
        )
    rows.sort(key=lambda row: float(row["cagr"]), reverse=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as file:
        fields = ["ticker", "start", "end", "candles", "trades", "total_return", "cagr", "max_drawdown", "annual_volatility", "sharpe"]
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Salvo: {output} ({len(rows)} linhas)")


def _row(
    config: PortfolioConfig,
    full: PortfolioSummary,
    train: PortfolioSummary,
    test: PortfolioSummary,
    train_end: str,
    test_start: str,
) -> dict:
    row = asdict(config)
    row.update(
        {
            "strategy": config.name,
            "full_start": full.start,
            "full_end": full.end,
            "full_candles": full.candles,
            "full_trades": full.trades,
            "full_exposure": full.exposure,
            "full_avg_positions": full.avg_positions,
            "full_total_return": full.total_return,
            "full_cagr": full.cagr,
            "full_max_drawdown": full.max_drawdown,
            "full_volatility": full.annual_volatility,
            "full_sharpe": full.sharpe,
            "full_turnover": full.turnover,
            "train_end": train_end,
            "train_total_return": train.total_return,
            "train_cagr": train.cagr,
            "train_max_drawdown": train.max_drawdown,
            "train_sharpe": train.sharpe,
            "test_start": test_start,
            "test_total_return": test.total_return,
            "test_cagr": test.cagr,
            "test_max_drawdown": test.max_drawdown,
            "test_sharpe": test.sharpe,
            "test_trades": test.trades,
            "test_exposure": test.exposure,
        }
    )
    return row


def _print_top(rows: list[dict]) -> None:
    print("\nTop 20 por CAGR no teste 30% final")
    for index, row in enumerate(rows[:20], start=1):
        print(
            f"{index:02d}. {row['strategy']} | "
            f"teste CAGR {float(row['test_cagr']):.2%}, ret {float(row['test_total_return']):.2%}, "
            f"MDD {float(row['test_max_drawdown']):.2%}; "
            f"full CAGR {float(row['full_cagr']):.2%}, ret {float(row['full_total_return']):.2%}",
            flush=True,
        )


def _normalize(values: dict[str, float]) -> dict[str, float]:
    total = sum(value for value in values.values() if value > 0)
    if total <= 0:
        return {}
    return {key: value / total for key, value in values.items() if value > 0}


def _cap_weights(weights: dict[str, float], max_weight: float) -> dict[str, float]:
    if not weights or max_weight >= 1:
        return weights
    capped: dict[str, float] = {}
    remaining = dict(weights)
    while remaining:
        total = sum(remaining.values())
        if total <= 0:
            break
        remaining_budget = max(0.0, 1.0 - sum(capped.values()))
        changed = False
        next_remaining: dict[str, float] = {}
        for ticker, weight in remaining.items():
            redistributed = weight / total * remaining_budget
            if redistributed > max_weight:
                capped[ticker] = max_weight
                changed = True
            else:
                next_remaining[ticker] = weight
        remaining = next_remaining
        if not changed:
            total = sum(remaining.values())
            if total > 0:
                remaining_budget = max(0.0, 1.0 - sum(capped.values()))
                capped.update({ticker: weight / total * remaining_budget for ticker, weight in remaining.items()})
            break
    return {ticker: weight for ticker, weight in capped.items() if weight > 0}


def _returns(prices: list[float]) -> list[float]:
    values = [0.0]
    for index in range(1, len(prices)):
        previous = prices[index - 1]
        current = prices[index]
        values.append(current / previous - 1 if previous > 0 else 0.0)
    return values


def _parse_ints(value: str) -> list[int]:
    if not value:
        return []
    return [int(item) for item in value.split(",") if item]


def _parse_floats(value: str) -> list[float]:
    if not value:
        return []
    return [float(item) for item in value.split(",") if item]


def _annualized_volatility(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    return statistics.stdev(returns) * math.sqrt(252)


def _date_window(values: list[str], start: str | None, end: str | None) -> list[str]:
    start_dt = _point_datetime(start) if start else None
    end_dt = _point_datetime(end) if end else None
    result = []
    for value in values:
        value_dt = _point_datetime(value)
        if start_dt and value_dt < start_dt:
            continue
        if end_dt and value_dt > end_dt:
            continue
        result.append(value)
    return result


def _is_rebalance_date(current_date: str, next_date: str, frequency: str) -> bool:
    if frequency == "daily":
        return True
    current = _point_datetime(current_date).date()
    next_day = _point_datetime(next_date).date()
    if frequency == "weekly":
        return current.isocalendar()[:2] != next_day.isocalendar()[:2]
    if frequency == "monthly":
        return (current.year, current.month) != (next_day.year, next_day.month)
    raise ValueError(f"Frequencia desconhecida: {frequency}")


def _floor_lot(shares: float, lot_size: int) -> float:
    if lot_size <= 0:
        return shares
    return math.floor(shares / lot_size) * lot_size


@lru_cache(maxsize=None)
def _point_datetime(value: str) -> datetime:
    if "T" in value or " " in value:
        return datetime.fromisoformat(value)
    return datetime.combine(date.fromisoformat(value), datetime.min.time())


if __name__ == "__main__":
    raise SystemExit(main())
