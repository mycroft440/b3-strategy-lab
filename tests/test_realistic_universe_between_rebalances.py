from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from b3_strategy_lab import realistic
from b3_strategy_lab import realistic_portfolio as portfolio
from b3_strategy_lab.realistic import ExecutionPriceBook, ExecutionQuote
from scripts import backtest_strategy_management_combinations as combinations
from scripts import research_portfolio_allocation as research

DATES = ["2026-01-30", "2026-02-02", "2026-02-03", "2026-02-04"]


class _UniverseDropsAfterDecision:
    """AAA3 is in the weekly universe at the monthly decision and leaves right after."""

    def tickers_on(self, value_date: str) -> set[str]:
        return {"AAA3"} if value_date <= "2026-01-30" else set()


class RealisticUniverseBetweenRebalancesTests(unittest.TestCase):
    def test_holding_is_kept_until_the_next_decision_when_it_leaves_the_universe(self) -> None:
        # Regression: the realistic replay sold a designated holding mid-month when its
        # liquidity rank left the weekly top 40, while the research matrix it replays
        # applies the universe only at management decisions.
        candles = [
            SimpleNamespace(date=day, open=10.0, close=10.0, raw_close=10.0, adjustment_factor=1.0)
            for day in DATES
        ]
        data = SimpleNamespace(
            dates=DATES,
            tickers=["AAA3"],
            candles={"AAA3": candles},
            by_date={"AAA3": {candle.date: candle for candle in candles}},
            index_by_date={"AAA3": {candle.date: index for index, candle in enumerate(candles)}},
        )
        pricebook = ExecutionPriceBook([
            ExecutionQuote(day, "AAA3", market, 10.0, 10.0, 1e9)
            for day in DATES
            for market in ("010", "020")
        ])
        fee_schedule = realistic.FeeSchedule(
            [realistic.FeeRule("2026-01-01", "2026-12-31", 0.0, quality="official")]
        )
        metrics = {"total_return": 0.0, "cagr": 0.0, "max_drawdown": 0.0,
                   "annual_volatility": 0.0, "sharpe": 0.0}
        with (
            patch.object(portfolio, "_apply_split_from_adjustment_factors", return_value=None),
            patch.object(combinations, "_build_eligibility", return_value={"dummy": {"AAA3": [1] * 4}}),
            patch.object(research, "_eligible_tickers", return_value={"AAA3"}),
            patch.object(research, "_target_weights", return_value={"AAA3": 1.0}),
            patch.object(research, "_portfolio_metrics", return_value=metrics),
            patch.object(research, "_yearly_returns", return_value={}),
        ):
            _summary, curve, account = portfolio.run_realistic(
                data=data,
                universe=_UniverseDropsAfterDecision(),
                pricebook=pricebook,
                cash_events=[],
                fee_schedule=fee_schedule,
                strategy="dummy",
                config=SimpleNamespace(name="test_monthly", rebalance="monthly"),
                start="2026-02-02",
                end="2026-02-04",
                initial_cash=1_000.0,
                base_slippage_bps=0.0,
                participation_bps_at_1pct=0.0,
                max_slippage_bps=0.0,
                transitions={},
                economic_gap_adjustment=False,
                survivorship_safe=True,
            )

        self.assertEqual([row.selected for row in curve], ["AAA3", "AAA3", "AAA3"])
        self.assertEqual([row["side"] for row in account.order_ledger], ["BUY"])


if __name__ == "__main__":
    unittest.main()


class RealisticResidualExitTests(unittest.TestCase):
    def test_exit_cut_short_by_odd_lot_capacity_is_retried_next_open(self) -> None:
        # Regression: orders expire each session and the replay compared only target
        # dictionaries, so odd-lot shares left by a capacity-limited exit stayed held
        # until the next monthly decision.
        days = ["2026-01-30", "2026-02-02", "2026-02-03", "2026-02-04", "2026-02-05", "2026-02-06"]
        prices = {"2026-01-30": 10.0, "2026-02-02": 10.0}
        candles = [
            SimpleNamespace(date=day, open=prices.get(day, 25.0), close=prices.get(day, 25.0),
                            raw_close=prices.get(day, 25.0), adjustment_factor=1.0)
            for day in days
        ]
        data = SimpleNamespace(
            dates=days,
            tickers=["AAA3"],
            candles={"AAA3": candles},
            by_date={"AAA3": {candle.date: candle for candle in candles}},
            index_by_date={"AAA3": {candle.date: index for index, candle in enumerate(candles)}},
        )
        # 1% of R$ 5.000 of odd-lot volume: R$ 50 per session, two shares at R$ 25.
        pricebook = ExecutionPriceBook([
            ExecutionQuote(candle.date, "AAA3", market, candle.open, candle.close,
                           1e9 if market == "010" else 5_000.0)
            for candle in candles
            for market in ("010", "020")
        ])
        fee_schedule = realistic.FeeSchedule(
            [realistic.FeeRule("2026-01-01", "2026-12-31", 0.0, quality="official")]
        )
        metrics = {"total_return": 0.0, "cagr": 0.0, "max_drawdown": 0.0,
                   "annual_volatility": 0.0, "sharpe": 0.0}

        def eligible(_data, current, _eligibility):
            return {"AAA3"} if current <= "2026-02-02" else set()

        with (
            patch.object(portfolio, "_apply_split_from_adjustment_factors", return_value=None),
            patch.object(combinations, "_build_eligibility", return_value={"dummy": {"AAA3": [1] * len(days)}}),
            patch.object(research, "_eligible_tickers", side_effect=eligible),
            patch.object(research, "_target_weights", return_value={"AAA3": 1.0}),
            patch.object(research, "_portfolio_metrics", return_value=metrics),
            patch.object(research, "_yearly_returns", return_value={}),
        ):
            _summary, curve, account = portfolio.run_realistic(
                data=data,
                universe=_UniverseDropsAfterDecision(),
                pricebook=pricebook,
                cash_events=[],
                fee_schedule=fee_schedule,
                strategy="dummy",
                config=SimpleNamespace(name="test_monthly", rebalance="monthly"),
                start="2026-02-02",
                end="2026-02-06",
                initial_cash=1_050.0,
                base_slippage_bps=0.0,
                participation_bps_at_1pct=0.0,
                max_slippage_bps=0.0,
                transitions={},
                economic_gap_adjustment=False,
                survivorship_safe=True,
            )

        odd_lot_sales = [
            row["filled_shares"] for row in account.order_ledger
            if row["side"] == "SELL" and row["market_type"] == "020"
        ]
        self.assertEqual(odd_lot_sales, [2, 2, 1])
        self.assertEqual(account.shares("AAA3"), 0)
        self.assertEqual(curve[-1].selected, "")
