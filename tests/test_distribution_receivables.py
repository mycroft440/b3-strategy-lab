from __future__ import annotations

import unittest
from types import SimpleNamespace

from b3_strategy_lab.candles import Candle
from b3_strategy_lab.realistic import (
    CashDistribution,
    ExecutionPriceBook,
    ExecutionQuote,
    FeeRule,
    FeeSchedule,
    PointInTimeUniverse,
    RealCashAccount,
    SlippageModel,
    UniverseSnapshot,
)
from b3_strategy_lab.realistic_portfolio import run_realistic
from scripts.research_portfolio_allocation import PortfolioConfig


def _candle(day: str, price: float) -> Candle:
    return Candle(
        date=day,
        ticker="AAA3",
        source_symbol="AAA3",
        open=price,
        high=price,
        low=price,
        close=price,
        adj_close=price,
        volume=1_000_000,
        raw_open=price,
        raw_high=price,
        raw_low=price,
        raw_close=price,
        adjustment_factor=1.0,
        raw_volume=1_000_000,
        trades=100,
        financial_volume=10_000_000.0,
        market_type="010",
    )


class DistributionReceivableTests(unittest.TestCase):
    def _account(self, cash: float = 1000.0) -> RealCashAccount:
        return RealCashAccount(
            cash,
            FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 0.0)]),
            SlippageModel(base_bps=0.0, participation_bps_at_1pct=0.0, max_bps=0.0),
        )

    def test_dividend_receivable_is_not_spendable_cash_and_settles_without_equity_jump(self) -> None:
        account = self._account(100.0)
        key = ("AAA3", "2026-01-05", "2026-01-20", "DIVIDENDO", 1.0)
        account.register_distribution_receivable(
            key,
            ticker="AAA3",
            label="DIVIDENDO",
            shares_entitled=10,
            gross_per_share=1.0,
            payment_date="2026-01-20",
        )
        self.assertAlmostEqual(account.cash, 100.0)
        self.assertAlmostEqual(account.distribution_receivable_value(), 10.0)
        economic_before = account.cash + account.distribution_receivable_value()

        account.settle_distribution_receivable(key)
        account.credit_distribution("2026-01-20", "AAA3", "DIVIDENDO", 10, 1.0)
        economic_after = account.cash + account.distribution_receivable_value()
        self.assertAlmostEqual(economic_before, economic_after)
        self.assertAlmostEqual(account.cash, 110.0)

    def test_jcp_receivable_is_recognized_net_of_known_withholding(self) -> None:
        account = self._account()
        key = ("AAA3", "2026-01-05", "2026-02-10", "JCP", 10.0)
        value = account.register_distribution_receivable(
            key,
            ticker="AAA3",
            label="JCP",
            shares_entitled=10,
            gross_per_share=10.0,
            payment_date="2026-02-10",
        )
        self.assertAlmostEqual(value, 82.5)
        self.assertAlmostEqual(account.distribution_receivable_value(), 82.5)

    def test_uncertain_2026_large_dividend_receivable_fails_closed(self) -> None:
        account = self._account(100_000.0)
        with self.assertRaisesRegex(ValueError, "R\\$50,000"):
            account.register_distribution_receivable(
                ("AAA3", "2026-01-05", "2026-02-10", "DIVIDENDO", 600.0),
                ticker="AAA3",
                label="DIVIDENDO",
                shares_entitled=100,
                gross_per_share=600.0,
                payment_date="2026-02-10",
            )

    def test_2026_threshold_keeps_paid_and_unpaid_installments_in_monthly_total(self) -> None:
        account = self._account(100_000.0)
        first = ("AAA3", "2026-01-05", "2026-02-05", "DIVIDENDO", 300.0)
        account.register_distribution_receivable(
            first,
            ticker="AAA3",
            label="DIVIDENDO",
            shares_entitled=100,
            gross_per_share=300.0,
            payment_date="2026-02-05",
        )
        account.settle_distribution_receivable(first)
        account.credit_distribution("2026-02-05", "AAA3", "DIVIDENDO", 100, 300.0)

        # The R$30k already paid remains part of February's known payer total.
        # A second R$30k installment in the same month must therefore cross R$50k
        # even though the first receivable is no longer outstanding.
        with self.assertRaisesRegex(ValueError, "R\\$50,000"):
            account.register_distribution_receivable(
                ("AAA3", "2026-01-20", "2026-02-20", "DIVIDENDO", 300.0),
                ticker="AAA3",
                label="DIVIDENDO",
                shares_entitled=100,
                gross_per_share=300.0,
                payment_date="2026-02-20",
            )

    def test_end_before_payment_keeps_earned_dividend_in_economic_equity(self) -> None:
        dates = [
            "2025-12-29",
            "2025-12-30",
            "2025-12-31",
            "2026-01-02",
            "2026-01-05",
            "2026-01-06",
        ]
        prices = [9.5, 9.7, 9.8, 10.0, 10.0, 9.0]
        candles = [_candle(day, price) for day, price in zip(dates, prices)]
        returns = [0.0]
        for previous, current in zip(prices, prices[1:]):
            returns.append(current / previous - 1.0)
        data = SimpleNamespace(
            tickers=["AAA3"],
            dates=dates,
            candles={"AAA3": candles},
            by_date={"AAA3": {item.date: item for item in candles}},
            index_by_date={"AAA3": {item.date: i for i, item in enumerate(candles)}},
            signal_prices={"AAA3": prices},
            raw_returns={"AAA3": returns},
            candidate_profile_cache={},
        )
        quotes = []
        for day, price in (("2026-01-05", 10.0), ("2026-01-06", 9.0)):
            quotes.append(ExecutionQuote(day, "AAA3", "010", price, price, 10_000_000.0))
            quotes.append(ExecutionQuote(day, "AAA3F", "020", price, price, 1_000_000.0))
        event = CashDistribution(
            ticker="AAA3",
            label="DIVIDENDO",
            last_date_prior="2026-01-05",
            ex_date="2026-01-06",
            payment_date="2026-01-20",
            gross_per_share=1.0,
        )
        summary, curve, account = run_realistic(
            data=data,
            universe=PointInTimeUniverse(
                [UniverseSnapshot("2026-01-02", frozenset({"AAA3"}))]
            ),
            pricebook=ExecutionPriceBook(quotes),
            cash_events=[event],
            fee_schedule=FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 0.0)]),
            strategy="buy_and_hold",
            config=PortfolioConfig(
                name="daily_one",
                lookback=1,
                top_n=1,
                vol_window=2,
                rebalance="daily",
                score="momentum",
                weighting="equal",
                absolute_momentum=False,
                signal_mode="adjusted",
            ),
            start="2026-01-02",
            end="2026-01-06",
            initial_cash=100.0,
            base_slippage_bps=0.0,
            participation_bps_at_1pct=0.0,
            max_slippage_bps=0.0,
            transitions={},
            economic_gap_adjustment=False,
            survivorship_safe=True,
            cash_events_complete=True,
        )
        self.assertEqual(account.shares("AAA3"), 10)
        self.assertAlmostEqual(account.cash, 0.0)
        self.assertAlmostEqual(account.distribution_receivable_value(), 10.0)
        self.assertAlmostEqual(curve[-1].equity, 100.0)
        self.assertAlmostEqual(summary.final_equity, 100.0)
        self.assertIn("UNPAID_DISTRIBUTION_RECEIVABLE", summary.validity)


if __name__ == "__main__":
    unittest.main()
