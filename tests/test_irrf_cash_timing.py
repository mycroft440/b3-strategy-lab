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
        self.assertAlmostEqual(account.outstanding_tax_liability(), 0.0)

    def test_crossing_one_real_withholds_then_darf_waits_until_due_session(self) -> None:
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
        # Only source withholding has left the account so far.
        self.assertAlmostEqual(account.tax_paid, 1.05, places=8)
        self.assertAlmostEqual(account.outstanding_tax_liability(), gross_tax - 1.05, places=8)

        sessions = ["2026-02-25", "2026-02-26", "2026-02-27"]
        self.assertAlmostEqual(account.process_due_taxes("2026-02-26", sessions), 0.0)
        paid = account.process_due_taxes("2026-02-27", sessions)
        self.assertAlmostEqual(paid, gross_tax - 1.05, places=8)
        # IRRF + DARF equals the gross monthly tax, without double charging.
        self.assertAlmostEqual(account.tax_paid, gross_tax, places=8)
        self.assertAlmostEqual(account.outstanding_tax_liability(), 0.0)

    def test_accrued_tax_escrow_is_not_reserved_twice_from_next_month_cash(self) -> None:
        account = self._account(50_000.0)
        self._seed(account, 2500, 5.0)
        account.sell_leg("2026-01-05", "AAA3", 2500, self._quote("2026-01-05", 10.0))
        tax, _ = account.finalize_month("2026-01")

        self.assertGreater(tax.tax_due, 0.0)
        self.assertAlmostEqual(account.tax_escrow, tax.tax_due, places=8)
        # January's known liability has already been removed from account.cash into
        # tax_escrow. February must reserve only any new provisional February tax;
        # subtracting tax_escrow here again would reduce purchasing power twice.
        self.assertAlmostEqual(_provisional_tax_reserve(account, "2026-02-02"), 0.0)

    def test_unused_irrf_credit_carries_into_later_taxable_month(self) -> None:
        account = self._account(50_000.0)
        self._seed(account, 2500, 10.04)
        # January: R$25k sales with a R$100 loss. IRRF is withheld, but no tax is due.
        account.sell_leg("2026-01-05", "AAA3", 2500, self._quote("2026-01-05", 10.0))
        january, _ = account.finalize_month("2026-01")
        self.assertAlmostEqual(january.irrf_withheld_month, 1.25, places=8)
        self.assertAlmostEqual(january.tax_due, 0.0)
        self.assertAlmostEqual(account.tax.irrf_credit, 1.25, places=8)

        # February: profitable >R$20k sales. The small prior loss is offset first;
        # then January's credit and February's withholding reduce the DARF.
        self._seed(account, 2500, 5.0)
        account.sell_leg("2026-02-05", "AAA3", 2500, self._quote("2026-02-05", 10.0))
        february, _ = account.finalize_month("2026-02")
        self.assertAlmostEqual(february.loss_carry_in, 100.0, places=6)
        self.assertAlmostEqual(february.irrf_credit_in, 1.25, places=8)
        self.assertAlmostEqual(february.irrf_withheld_month, 1.25, places=8)
        self.assertAlmostEqual(february.irrf_credit_used, 2.50, places=8)
        self.assertAlmostEqual(account.tax.irrf_credit, 0.0, places=8)

    def test_darf_below_ten_reais_accumulates_until_later_month(self) -> None:
        account = self._account(50_000.0)
        for month in ("2026-01", "2026-02"):
            self._seed(account, 2100, 9.98)
            day = month + "-05"
            account.sell_leg(day, "AAA3", 2100, self._quote(day, 10.0))
            tax, _ = account.finalize_month(month)
            self.assertAlmostEqual(tax.gross_tax_before_irrf, 6.30, places=6)
            self.assertAlmostEqual(tax.irrf_withheld_month, 1.05, places=6)
            self.assertAlmostEqual(tax.tax_due, 5.25, places=6)

        self.assertAlmostEqual(account.outstanding_tax_liability(), 10.50, places=6)
        march_sessions = ["2026-03-27", "2026-03-30", "2026-03-31"]
        self.assertAlmostEqual(account.process_due_taxes("2026-03-30", march_sessions), 0.0)
        self.assertAlmostEqual(account.process_due_taxes("2026-03-31", march_sessions), 10.50, places=6)
        self.assertAlmostEqual(account.outstanding_tax_liability(), 0.0)
        self.assertAlmostEqual(account.tax_paid, 12.60, places=6)


if __name__ == "__main__":
    unittest.main()
