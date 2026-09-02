from __future__ import annotations

import unittest

from b3_strategy_lab.realistic import (
    ExecutionQuote,
    FeeRule,
    FeeSchedule,
    RealCashAccount,
    SlippageModel,
)
from b3_strategy_lab.realistic_portfolio import _provisional_tax_reserve


class ProvisionalTaxReserveIrrfTests(unittest.TestCase):
    def _account(self, cash: float = 50_000.0) -> RealCashAccount:
        return RealCashAccount(
            cash,
            FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 0.0)]),
            SlippageModel(base_bps=0.0, participation_bps_at_1pct=0.0, max_bps=0.0),
        )

    def _quote(self, day: str, price: float = 10.0) -> ExecutionQuote:
        return ExecutionQuote(day, "AAA3", "010", price, price, 100_000_000.0)

    @staticmethod
    def _seed(account: RealCashAccount, shares: int, average_cost: float) -> None:
        account.positions["AAA3"].shares = shares
        account.positions["AAA3"].average_cost = average_cost

    def test_current_month_irrf_is_not_reserved_twice(self) -> None:
        account = self._account()
        self._seed(account, 2500, 5.0)
        account.sell_leg("2026-01-05", "AAA3", 2500, self._quote("2026-01-05"))

        gross_gain = 2500 * (10.0 - 5.0)
        gross_tax = gross_gain * 0.15
        withheld = account.ordinary_irrf_withheld

        self.assertAlmostEqual(withheld, 1.25, places=8)
        self.assertAlmostEqual(
            _provisional_tax_reserve(account, "2026-01-05"),
            gross_tax - withheld,
            places=8,
        )

    def test_carried_irrf_credit_and_current_withholding_reduce_reserve(self) -> None:
        account = self._account()

        self._seed(account, 2500, 10.04)
        account.sell_leg("2026-01-05", "AAA3", 2500, self._quote("2026-01-05"))
        january, _ = account.finalize_month("2026-01")
        self.assertAlmostEqual(january.tax_due, 0.0)
        self.assertAlmostEqual(account.tax.irrf_credit, 1.25, places=8)

        self._seed(account, 2500, 5.0)
        account.sell_leg("2026-02-05", "AAA3", 2500, self._quote("2026-02-05"))

        gross_gain = 2500 * (10.0 - 5.0)
        taxable_after_loss = gross_gain - 100.0
        gross_tax = taxable_after_loss * 0.15
        total_credit = 1.25 + 1.25
        self.assertAlmostEqual(
            _provisional_tax_reserve(account, "2026-02-05"),
            gross_tax - total_credit,
            places=8,
        )


if __name__ == "__main__":
    unittest.main()
