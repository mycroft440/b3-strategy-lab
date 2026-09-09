from dataclasses import replace

import pytest

from b3_strategy_lab.backtest import (
    metrics,
    run_strategy_vs_buy_hold,
    simulate_buy_and_hold,
    simulate_buy_and_hold_price_only,
    simulate_single_asset,
    simulate_single_asset_price_only,
)
from b3_strategy_lab.candles import Candle


def candle(day, opening, closing, factor):
    return Candle(
        date=day, ticker="AAA3", source_symbol="AAA3",
        open=opening * factor, high=max(opening, closing) * factor,
        low=min(opening, closing) * factor, close=closing * factor,
        adj_close=closing * factor, volume=1000,
        raw_open=opening, raw_high=max(opening, closing),
        raw_low=min(opening, closing), raw_close=closing,
        adjustment_factor=factor,
    )


@pytest.mark.parametrize("factor", [1.0, 0.1, 0.001])
def test_future_normalization_cannot_make_an_unaffordable_share_affordable(factor):
    bars = [candle("2020-01-02", 150, 150, factor),
            candle("2020-01-03", 150, 180, factor)]
    curves = [
        simulate_buy_and_hold_price_only(bars, initial_cash=100, lot_size=1),
        simulate_single_asset_price_only(bars, [1, 1], initial_cash=100, lot_size=1),
    ]
    for curve in curves:
        assert curve[-1].equity == 100
        assert all(point.shares == 0 for point in curve)


def test_actual_split_changes_shares_without_creating_profit():
    bars = [candle("2020-01-02", 150, 150, 0.5),
            candle("2020-01-03", 75, 75, 1.0)]
    curve = simulate_buy_and_hold_price_only(bars, initial_cash=200, lot_size=1)
    assert [point.shares for point in curve] == [1, 2]
    assert [point.equity for point in curve] == [200, 200]
    assert curve[0].trade_price == 150
    assert curve[1].split_ratio == 2


@pytest.mark.parametrize("strategy", ["buy_and_hold", "test_signal"])
@pytest.mark.parametrize("lot_size", [1, 100])
def test_adjusted_mode_cannot_bypass_historical_share_sizing(strategy, lot_size):
    bars = [candle("2020-01-02", 150, 150, 0.1),
            candle("2020-01-03", 150, 180, 0.1)]
    with pytest.raises(ValueError, match="adjusted prices cannot size integer share lots"):
        run_strategy_vs_buy_hold(
            "AAA3", strategy, bars, [1, 1], initial_cash=100,
            lot_size=lot_size, price_mode="adjusted",
        )


@pytest.mark.parametrize("simulate,args", [
    (simulate_buy_and_hold, ()),
    (simulate_single_asset, ([1, 1],)),
])
def test_direct_adjusted_simulators_reject_discrete_synthetic_shares(simulate, args):
    bars = [candle("2020-01-02", 150, 150, 0.1),
            candle("2020-01-03", 150, 180, 0.1)]
    with pytest.raises(ValueError, match="price_only"):
        simulate(bars, *args, initial_cash=100, lot_size=1)
    # Explicit synthetic fractional-share research keeps its original semantics.
    diagnostic = simulate(bars, *args, initial_cash=100, lot_size=0)
    assert diagnostic[-1].equity == pytest.approx(120)


def test_adjusted_lot_guard_checks_marking_prices_too():
    bars = [candle("2020-01-02", 150, 150, 1),
            replace(candle("2020-01-03", 150, 180, 1), close=18)]
    with pytest.raises(ValueError, match="2020-01-03"):
        simulate_buy_and_hold(bars, initial_cash=150, lot_size=1)


def test_fractional_corporate_entitlement_cannot_be_sold_as_an_ordinary_share():
    bars = [candle("2020-01-02", 10, 10, 1.0),
            candle("2020-01-03", 20, 20, 0.5)]
    with pytest.raises(ValueError, match="cash-in-lieu"):
        simulate_buy_and_hold_price_only(bars, initial_cash=10, lot_size=1)


def test_first_session_cost_is_included_in_risk_metrics():
    bars = [candle("2020-01-02", 10, 10, 1), candle("2020-01-03", 10, 10, 1)]
    curve = simulate_buy_and_hold_price_only(bars, initial_cash=101, cost_bps=100, lot_size=1)
    result = metrics(curve, 101)
    assert result["max_drawdown"] == pytest.approx(100 / 101 - 1)
    assert result["annual_volatility"] > 0
