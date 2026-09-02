from __future__ import annotations

import unittest
from types import SimpleNamespace

from b3_strategy_lab.realistic import (
    CashDistribution,
    FeeRule,
    FeeSchedule,
    RealCashAccount,
    SlippageModel,
)
from b3_strategy_lab.realistic_portfolio import (
    _account_close_equity,
    _event_key,
    _restore_distribution_entitlements,
)


class ContinuousOosAccountTests(unittest.TestCase):
    def _account(self) -> RealCashAccount:
        return RealCashAccount(
            1_000.0,
            FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 0.0)]),
            SlippageModel(base_bps=0.0, participation_bps_at_1pct=0.0, max_bps=0.0),
        )

    @staticmethod
    def _event(last_date_prior: str, payment_date: str, amount: float = 1.0) -> CashDistribution:
        return CashDistribution(
            ticker="AAA3",
            label="DIVIDENDO",
            last_date_prior=last_date_prior,
            ex_date="2025-01-02",
            payment_date=payment_date,
            gross_per_share=amount,
        )

    @staticmethod
    def _data(close: float = 10.0):
        return SimpleNamespace(
            by_date={"AAA3": {"2024-12-30": SimpleNamespace(raw_close=close)}}
        )

    def test_new_cum_right_receivable_is_not_double_counted_at_fold_boundary(self) -> None:
        account = self._account()
        account.positions["AAA3"].shares = 10
        account.positions["AAA3"].average_cost = 8.0
        event = self._event("2024-12-30", "2025-01-10")
        account.register_distribution_receivable(
            _event_key(event),
            ticker=event.ticker,
            label=event.label,
            shares_entitled=10,
            gross_per_share=event.gross_per_share,
            payment_date=event.payment_date,
        )

        # The 2024-12-30 closing price is still cum-right. The newly registered
        # R$10 receivable exists only for cross-fold state continuity and therefore
        # must not also be added to that same closing-equity baseline.
        self.assertAlmostEqual(
            _account_close_equity(account, self._data(), "2024-12-30", [event]),
            1_100.0,
        )
        self.assertEqual(
            _restore_distribution_entitlements(account, [event]),
            {_event_key(event): 10},
        )

    def test_older_unpaid_receivable_remains_in_boundary_equity(self) -> None:
        account = self._account()
        account.positions["AAA3"].shares = 10
        account.positions["AAA3"].average_cost = 8.0
        event = self._event("2024-12-20", "2025-01-10", amount=2.0)
        account.register_distribution_receivable(
            _event_key(event),
            ticker=event.ticker,
            label=event.label,
            shares_entitled=10,
            gross_per_share=event.gross_per_share,
            payment_date=event.payment_date,
        )

        self.assertAlmostEqual(
            _account_close_equity(account, self._data(), "2024-12-30", [event]),
            1_120.0,
        )

    def test_carried_tax_state_is_not_reinitialized(self) -> None:
        account = self._account()
        account.tax.loss_carry = 321.0
        account.tax.irrf_credit = 7.5
        account.tax_escrow = 42.0
        account._darf_carry = 8.0
        account._scheduled_darfs["2025-01"] = 34.0

        # These are the exact state fields the continuous OOS runner hands to the
        # next fold. This regression test makes accidental reinitialization visible.
        self.assertEqual(account.tax.loss_carry, 321.0)
        self.assertEqual(account.tax.irrf_credit, 7.5)
        self.assertEqual(account.tax_escrow, 42.0)
        self.assertEqual(account._darf_carry, 8.0)
        self.assertEqual(account._scheduled_darfs["2025-01"], 34.0)

    def test_unknown_carried_receivable_fails_closed(self) -> None:
        account = self._account()
        event = self._event("2024-12-20", "2025-01-10")
        account.register_distribution_receivable(
            _event_key(event),
            ticker=event.ticker,
            label=event.label,
            shares_entitled=1,
            gross_per_share=event.gross_per_share,
            payment_date=event.payment_date,
        )
        with self.assertRaisesRegex(ValueError, "no matching certified event"):
            _restore_distribution_entitlements(account, [])


if __name__ == "__main__":
    unittest.main()
