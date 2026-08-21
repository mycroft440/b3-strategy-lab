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
                ExecutionQuote(day, "AAA3", "010", 10.0, 10.0, 1_000_000.0),
                ExecutionQuote(day, "AAA3F", "020", 20.0, 20.0, 100_000.0),
                ExecutionQuote(day, "BBB3", "010", 10.0, 10.0, 1_000_000.0),
                ExecutionQuote(day, "BBB3F", "020", 10.0, 10.0, 100_000.0),
            ]
        )

    def test_small_account_weights_use_fractional_not_standard_open(self) -> None:
        account = rebalance_atomic(
            self._account(),
            data=None,
            pricebook=self._pricebook(),
            current="2026-01-02",
            targets={"AAA3": 0.5, "BBB3": 0.5},
        )
        # R$50 target in AAA3 at the fractional open of R$20 fits 2 shares.
        # R$50 target in BBB3 at the fractional open of R$10 fits 5 shares.
        self.assertEqual(account.shares("AAA3"), 2)
        self.assertEqual(account.shares("BBB3"), 5)
        self.assertAlmostEqual(account.cash, 10.0)

    def test_existing_odd_lot_is_valued_at_fractional_open(self) -> None:
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
        # Opening equity is 2 * R$20 + cash, not 2 * the R$10 standard quote.
        self.assertEqual(result.shares("AAA3"), 2)


if __name__ == "__main__":
    unittest.main()
