from __future__ import annotations

import math
from unittest.mock import patch

from b3_strategy_lab.candles import Candle
from scripts import research_portfolio_allocation_core as core


def _candle(day: str, *, open_price: float, close_price: float) -> Candle:
    high = max(open_price, close_price)
    low = min(open_price, close_price)
    return Candle(
        date=day,
        ticker="AAA",
        source_symbol="AAA",
        open=open_price,
        high=high,
        low=low,
        close=close_price,
        adj_close=close_price,
        volume=1_000,
        raw_open=open_price,
        raw_high=high,
        raw_low=low,
        raw_close=close_price,
        adjustment_factor=1.0,
    )


def test_final_liquidation_uses_close_slippage_and_costs() -> None:
    candle = _candle("2026-01-05", open_price=100.0, close_price=100.0)
    shares = {"AAA": 10.0}

    trades, turnover, cash = core._liquidate_at_close(
        candle.date,
        ["AAA"],
        {"AAA": candle},
        shares,
        0.0,
        0.001,
        0.01,
    )

    assert trades == 1
    assert shares["AAA"] == 0.0
    assert math.isclose(cash, 10 * 99.0 * 0.999, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(turnover, 990.0 / 1000.0, rel_tol=0, abs_tol=1e-12)


def test_average_year_input_excludes_partial_calendar_years() -> None:
    dates = [
        "2018-01-02",
        "2018-12-28",
        "2019-01-02",
        "2019-12-30",
        "2020-01-02",
        "2020-08-31",
    ]
    equities = [100.0, 110.0, 110.0, 121.0, 121.0, 133.1]

    yearly = core._yearly_returns(equities, dates, 100.0)
    completed = core._full_calendar_year_returns(equities, dates, 100.0)

    assert set(yearly) == {2018, 2019, 2020}
    assert set(completed) == {2018, 2019}
    assert all(math.isclose(value, 0.1, rel_tol=0, abs_tol=1e-12) for value in completed.values())


def test_run_portfolio_finishes_in_cash_after_last_close() -> None:
    candles = [
        _candle("2026-01-05", open_price=100.0, close_price=100.0),
        _candle("2026-01-06", open_price=100.0, close_price=105.0),
        _candle("2026-01-07", open_price=105.0, close_price=110.0),
    ]

    class Data:
        tickers = ["AAA"]
        dates = [candle.date for candle in candles]
        by_date = {"AAA": {candle.date: candle for candle in candles}}
        index_by_date = {"AAA": {candle.date: i for i, candle in enumerate(candles)}}
        signal_prices = {"AAA": [candle.close for candle in candles]}
        raw_returns = {"AAA": [0.0, 0.05, 110.0 / 105.0 - 1.0]}
        candidate_profile_cache = {}

    config = core.PortfolioConfig(name="test", rebalance="daily")
    with patch.object(core, "_target_weights", return_value={"AAA": 1.0}):
        summary, curve = core.run_portfolio(
            Data(),
            config,
            initial_cash=1_000.0,
            cost_bps=0.0,
            slippage_bps=0.0,
            lot_size=1,
            collect_curve=True,
        )

    assert summary.trades == 2
    # selected/positions describe the asset held during the final session;
    # cash/equity already reflect the mandatory close liquidation.
    assert curve[-1].positions == 1
    assert curve[-1].selected == "AAA"
    assert math.isclose(curve[-1].cash, curve[-1].equity, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(summary.final_equity, curve[-1].cash, rel_tol=0, abs_tol=1e-12)
