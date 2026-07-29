from __future__ import annotations

import unittest

from b3_strategy_lab.candles import Candle
from scripts.research_portfolio_allocation import (
    MarketData,
    PortfolioConfig,
    _configs,
    _target_weights,
    run_portfolio,
)


def candle(day: str, ticker: str, price: float) -> Candle:
    return Candle(
        date=day,
        ticker=ticker,
        source_symbol=f"{ticker}.SA",
        open=price,
        high=price,
        low=price,
        close=price,
        adj_close=price,
        volume=1_000,
        raw_open=price,
        raw_high=price,
        raw_low=price,
        raw_close=price,
        adjustment_factor=1.0,
    )


def market_data() -> MarketData:
    data = MarketData.__new__(MarketData)
    data.tickers = ["FAST3", "SLOW3"]
    fast = [
        candle("2024-01-01", "FAST3", 10.0),
        candle("2024-01-02", "FAST3", 11.0),
        candle("2024-01-03", "FAST3", 14.0),
        candle("2024-01-04", "FAST3", 15.0),
    ]
    slow = [
        candle("2024-01-01", "SLOW3", 10.0),
        candle("2024-01-02", "SLOW3", 10.5),
        candle("2024-01-03", "SLOW3", 11.0),
        candle("2024-01-04", "SLOW3", 11.5),
    ]
    data.interval = "1d"
    data.signal_mode = "raw"
    data.candles = {"FAST3": fast, "SLOW3": slow}
    data.by_date = {
        ticker: {item.date: item for item in items}
        for ticker, items in data.candles.items()
    }
    data.index_by_date = {
        ticker: {item.date: index for index, item in enumerate(items)}
        for ticker, items in data.candles.items()
    }
    data.signal_prices = {
        ticker: [item.raw_close for item in items]
        for ticker, items in data.candles.items()
    }
    data.raw_returns = {
        ticker: [
            0.0,
            *[
                items[index].raw_close / items[index - 1].raw_close - 1
                for index in range(1, len(items))
            ],
        ]
        for ticker, items in data.candles.items()
    }
    data.dates = [item.date for item in fast]
    data.candidate_profile_cache = {}
    return data


class PortfolioCombinationTests(unittest.TestCase):
    def test_catalog_has_478_management_strategies(self) -> None:
        configs = _configs("raw", "all")
        self.assertEqual(len(configs), 478)
        self.assertEqual(len({config.name for config in configs}), 478)

    def test_target_weights_rank_only_eligible_tickers(self) -> None:
        data = market_data()
        config = PortfolioConfig(
            name="test",
            lookback=1,
            top_n=1,
            vol_window=2,
            score="momentum",
            weighting="equal",
            absolute_momentum=True,
            signal_mode="raw",
        )

        unrestricted = _target_weights(data, "2024-01-03", config)
        restricted = _target_weights(
            data,
            "2024-01-03",
            config,
            eligible_tickers={"SLOW3"},
        )

        self.assertEqual(unrestricted, {"FAST3": 1.0})
        self.assertEqual(restricted, {"SLOW3": 1.0})

    def test_run_portfolio_uses_trading_strategy_as_eligibility_filter(self) -> None:
        data = market_data()
        config = PortfolioConfig(
            name="equal",
            lookback=1,
            top_n=99,
            vol_window=2,
            rebalance="daily",
            score="all",
            weighting="equal",
            absolute_momentum=False,
            signal_mode="raw",
        )
        eligibility = {
            "FAST3": [0, 0, 0, 0],
            "SLOW3": [1, 1, 1, 1],
        }

        summary, curve = run_portfolio(
            data,
            config,
            initial_cash=100.0,
            cost_bps=0.0,
            slippage_bps=0.0,
            lot_size=0,
            eligibility=eligibility,
        )

        self.assertGreater(summary.exposure, 0)
        self.assertTrue(
            all("FAST3" not in point.selected for point in curve),
        )
        self.assertTrue(any("SLOW3" in point.selected for point in curve))
        self.assertTrue(all(point.dividend_cash == 0.0 for point in curve))


if __name__ == "__main__":
    unittest.main()
