from __future__ import annotations

import unittest
from types import SimpleNamespace

from b3_strategy_lab.candles import Candle
from b3_strategy_lab.realistic import (
    ExecutionPriceBook,
    ExecutionQuote,
    FeeRule,
    FeeSchedule,
    PointInTimeUniverse,
    UniverseSnapshot,
)
from b3_strategy_lab.realistic_portfolio import run_realistic
from scripts.research_portfolio_allocation import PortfolioConfig


def candle(day: str, price: float) -> Candle:
    return Candle(
        date=day,
        ticker="AAA3",
        source_symbol="AAA3",
        open=price,
        high=price * 1.02,
        low=price * 0.98,
        close=price,
        adj_close=price,
        volume=1_000_000,
        raw_open=price,
        raw_high=price * 1.02,
        raw_low=price * 0.98,
        raw_close=price,
        adjustment_factor=1.0,
        raw_volume=1_000_000,
        trades=100,
        financial_volume=10_000_000.0,
        market_type="010",
    )


class ContinuousWalkForwardTests(unittest.TestCase):
    def test_schedule_executes_next_open_and_keeps_one_account(self) -> None:
        dates = [
            "2024-01-02",
            "2024-01-03",
            "2024-01-04",
            "2024-01-05",
            "2024-01-08",
            "2024-01-09",
            "2024-01-10",
        ]
        candles = [candle(day, 10.0 + index) for index, day in enumerate(dates)]
        data = SimpleNamespace(
            tickers=["AAA3"],
            dates=dates,
            candles={"AAA3": candles},
            by_date={"AAA3": {item.date: item for item in candles}},
            index_by_date={"AAA3": {item.date: index for index, item in enumerate(candles)}},
            signal_prices={"AAA3": [item.close for item in candles]},
            raw_returns={"AAA3": [0.0] + [
                candles[index].close / candles[index - 1].close - 1.0
                for index in range(1, len(candles))
            ]},
            candidate_profile_cache={},
        )
        quotes = []
        for item in candles:
            for ticker, market in (("AAA3", "010"), ("AAA3F", "020")):
                quotes.append(
                    ExecutionQuote(
                        item.date,
                        ticker,
                        market,
                        item.raw_open,
                        item.raw_close,
                        10_000_000.0,
                        high=item.raw_high,
                        low=item.raw_low,
                        quantity=1_000_000,
                        trades=100,
                        liquidity_reference_financial_volume=10_000_000.0,
                        liquidity_reference_quantity=1_000_000.0,
                        liquidity_reference_sessions=21,
                        liquidity_reference_end="2023-12-29",
                    )
                )
        config = PortfolioConfig(
            name="daily",
            lookback=1,
            top_n=1,
            vol_window=2,
            rebalance="daily",
            score="all",
            weighting="equal",
            absolute_momentum=False,
            signal_mode="adjusted",
        )
        first_decision = "2024-01-05"
        second_decision = "2024-01-09"
        summary, curve, account = run_realistic(
            data=data,
            universe=PointInTimeUniverse(
                [UniverseSnapshot(first_decision, frozenset({"AAA3"}))]
            ),
            pricebook=ExecutionPriceBook(quotes),
            cash_events=[],
            fee_schedule=FeeSchedule(
                [FeeRule("2000-01-01", "2099-12-31", 0.0)]
            ),
            strategy="buy_and_hold",
            config=config,
            start=first_decision,
            end="2024-01-10",
            initial_cash=1_000.0,
            base_slippage_bps=0.0,
            participation_bps_at_1pct=0.0,
            max_slippage_bps=0.0,
            max_participation_rate=0.01,
            transitions={},
            economic_gap_adjustment=False,
            selection_status="walk_forward_out_of_sample",
            survivorship_safe=True,
            cash_events_complete=True,
            model_schedule={
                first_decision: ("buy_and_hold", config),
                second_decision: ("buy_and_hold", config),
            },
            metrics_start="2024-01-10",
        )
        self.assertEqual(account.trade_ledger[0].date, "2024-01-08")
        self.assertGreater(account.shares("AAA3"), 0)
        self.assertEqual(summary.start, "2024-01-10")
        self.assertEqual(summary.strategy, "walk_forward_selector")
        self.assertEqual(curve[0].date, first_decision)
        # OOS return starts from the immediately preceding close, not from the
        # account's original cash before the training-boundary position was opened.
        prior_equity = next(row.equity for row in curve if row.date == "2024-01-09")
        self.assertNotAlmostEqual(prior_equity, 1_000.0, places=2)
        self.assertAlmostEqual(
            summary.total_return,
            summary.final_equity / prior_equity - 1.0,
            places=12,
        )


if __name__ == "__main__":
    unittest.main()
