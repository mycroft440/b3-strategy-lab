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
from b3_strategy_lab.realistic_portfolio import rebalance_atomic


class FractionalTargetSizingTests(unittest.TestCase):
    def _account(self, cash: float = 100.0) -> RealCashAccount:
        return RealCashAccount(
            cash,
            FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 0.0)]),
            SlippageModel(base_bps=0.0, participation_bps_at_1pct=0.0, max_bps=0.0),
        )

    def _pricebook(self) -> ExecutionPriceBook:
        day = "2026-01-02"
        return ExecutionPriceBook(
            [
                ExecutionQuote("2025-12-30", "AAA3", "010", 10.0, 10.0, 1_000_000.0),
                ExecutionQuote("2025-12-30", "BBB3", "010", 10.0, 10.0, 1_000_000.0),
                ExecutionQuote("2025-12-30", "AAA3F", "020", 10.0, 10.0, 1_000_000.0),
                ExecutionQuote("2025-12-30", "BBB3F", "020", 10.0, 10.0, 1_000_000.0),
                ExecutionQuote(day, "AAA3", "010", 10.0, 10.0, 1_000_000.0),
                ExecutionQuote(day, "AAA3F", "020", 20.0, 20.0, 100_000.0),
                ExecutionQuote(day, "BBB3", "010", 10.0, 10.0, 1_000_000.0),
                ExecutionQuote(day, "BBB3F", "020", 10.0, 10.0, 100_000.0),
            ]
        )

    def test_fractional_gap_reduces_fills_without_resizing_frozen_orders(self) -> None:
        account = rebalance_atomic(
            self._account(),
            data=None,
            pricebook=self._pricebook(),
            current="2026-01-02",
            targets={"AAA3": 0.5, "BBB3": 0.5},
        )
        # Both orders were 5 shares at the prior R$10 close. A gap in AAA3
        # makes that basket unaffordable; proportional partial fills are 3 each.
        self.assertEqual([row["requested_shares"] for row in account.order_ledger], [5, 5])
        self.assertEqual(account.shares("AAA3"), 3)
        self.assertEqual(account.shares("BBB3"), 3)
        self.assertAlmostEqual(account.cash, 10.0)

    def test_existing_odd_lot_is_not_resized_from_its_fractional_open(self) -> None:
        account = self._account(0.01)
        account.positions["AAA3"].shares = 2
        account.positions["AAA3"].average_cost = 10.0
        result = rebalance_atomic(
            account,
            data=None,
            pricebook=self._pricebook(),
            current="2026-01-02",
            targets={"AAA3": 1.0},
        )
        self.assertEqual(result.shares("AAA3"), 2)
        self.assertFalse(result.order_ledger)


if __name__ == "__main__":
    unittest.main()
