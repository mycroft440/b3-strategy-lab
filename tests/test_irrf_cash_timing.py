from __future__ import annotations

import unittest

from b3_strategy_lab.realistic import (
    ExecutionQuote,
    FeeRule,
    FeeSchedule,
    RealCashAccount,
    SlippageModel,
)


class OrdinaryIrrfCashTimingTests(unittest.TestCase):
    def _account(self, cash: float = 1000.0) -> RealCashAccount:
        return RealCashAccount(
            cash,
            FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 0.0)]),
            SlippageModel(base_bps=0.0, participation_bps_at_1pct=0.0, max_bps=0.0),
        )

    def _quote(self, day: str, price: float = 10.0) -> ExecutionQuote:
        return ExecutionQuote(day, "AAA3", "010", price, price, 100_000_000.0)

    def _seed(self, account: RealCashAccount, shares: int, average_cost: float) -> None:
        account.positions["AAA3"].shares = shares
        account.positions["AAA3"].average_cost = average_cost

    def test_monthly_irrf_at_or_below_one_real_is_not_withheld(self) -> None:
        account = self._account()
        self._seed(account, 1000, 5.0)
        cash_before = account.cash
        account.sell_leg("2026-01-05", "AAA3", 1000, self._quote("2026-01-05"))
        self.assertAlmostEqual(account.ordinary_irrf_withheld, 0.0)
        self.assertAlmostEqual(account.cash, cash_before + 10_000.0)
        tax, _ = account.finalize_month("2026-01")
        self.assertAlmostEqual(tax.tax_due, 0.0)
        self.assertAlmostEqual(account.tax.irrf_credit, 0.0)

    def test_crossing_one_real_withholds_full_monthly_cumulative_amount(self) -> None:
        account = self._account()
        self._seed(account, 2100, 5.0)
        account.sell_leg("2026-01-05", "AAA3", 1500, self._quote("2026-01-05"))
        self.assertAlmostEqual(account.ordinary_irrf_withheld, 0.0)
        account.sell_leg("2026-01-06", "AAA3", 600, self._quote("2026-01-06"))
        self.assertAlmostEqual(account.ordinary_irrf_withheld, 1.05, places=8)

        tax, _ = account.finalize_month("2026-01")
        gross_gain = 2100 * (10.0 - 5.0)
        gross_tax = gross_gain * 0.15
        self.assertAlmostEqual(tax.gross_tax_before_irrf, gross_tax)
        self.assertAlmostEqual(tax.irrf_withheld_month, 1.05, places=8)
        self.assertAlmostEqual(tax.irrf_credit_used, 1.05, places=8)
        self.assertAlmostEqual(tax.tax_due, gross_tax - 1.05, places=8)
        # Cash tax = withholding + DARF, never double-counted.
        self.assertAlmostEqual(account.tax_paid, gross_tax, places=8)

    def test_unused_irrf_credit_carries_into_later_taxable_month(self) -> None:
        account = self._account(50_000.0)
        self._seed(account, 2500, 20.0)
        # January: R$25k sales at a loss. IRRF is withheld, but there is no tax due.
        account.sell_leg("2026-01-05", "AAA3", 2500, self._quote("2026-01-05", 10.0))
        january, _ = account.finalize_month("2026-01")
        self.assertAlmostEqual(january.irrf_withheld_month, 1.25, places=8)
        self.assertAlmostEqual(january.tax_due, 0.0)
        self.assertAlmostEqual(account.tax.irrf_credit, 1.25, places=8)

        # February: new profitable position with >R$20k in sales. Both January's
        # credit and February's withholding reduce the DARF.
        self._seed(account, 2500, 5.0)
        account.sell_leg("2026-02-05", "AAA3", 2500, self._quote("2026-02-05", 10.0))
        february, _ = account.finalize_month("2026-02")
        self.assertAlmostEqual(february.irrf_credit_in, 1.25, places=8)
        self.assertAlmostEqual(february.irrf_withheld_month, 1.25, places=8)
        self.assertAlmostEqual(february.irrf_credit_used, 2.50, places=8)
        self.assertAlmostEqual(account.tax.irrf_credit, 0.0, places=8)


if __name__ == "__main__":
    unittest.main()
