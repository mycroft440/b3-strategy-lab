from __future__ import annotations

import unittest

from b3_strategy_lab.realistic import (
    ExecutionPriceBook,
    ExecutionQuote,
    FeeRule,
    FeeSchedule,
    RealCashAccount,
    SlippageModel,
)


class FixedBrokerageMarketLegTests(unittest.TestCase):
    def test_150_share_order_charges_one_fixed_fee_per_010_and_020_leg(self) -> None:
        value_date = "2026-01-05"
        pricebook = ExecutionPriceBook(
            [
                ExecutionQuote(
                    value_date,
                    "AAA3",
                    "010",
                    10.00,
                    10.00,
                    100_000_000.0,
                ),
                ExecutionQuote(
                    value_date,
                    "AAA3F",
                    "020",
                    10.10,
                    10.10,
                    10_000_000.0,
                ),
            ]
        )
        account = RealCashAccount(
            2_000.0,
            FeeSchedule(
                [
                    FeeRule(
                        "2000-01-01",
                        "2099-12-31",
                        0.0,
                        brokerage_fixed=4.90,
                    )
                ]
            ),
            SlippageModel(
                base_bps=0.0,
                participation_bps_at_1pct=0.0,
                max_bps=0.0,
            ),
        )

        legs = pricebook.legs(value_date, "AAA3", 150)
        self.assertEqual([(qty, quote.market_type) for qty, quote in legs], [(100, "010"), (50, "020")])
        for quantity, quote in legs:
            account.buy_leg(value_date, "AAA3", quantity, quote)

        expected_notional = 100 * 10.00 + 50 * 10.10
        expected_fees = 2 * 4.90
        self.assertEqual(account.shares("AAA3"), 150)
        self.assertAlmostEqual(account.fees_paid, expected_fees, places=8)
        self.assertAlmostEqual(account.cash, 2_000.0 - expected_notional - expected_fees, places=8)
        self.assertEqual([row.market_type for row in account.trade_ledger], ["010", "020"])
        self.assertEqual([row.fee for row in account.trade_ledger], [4.90, 4.90])


if __name__ == "__main__":
    unittest.main()
