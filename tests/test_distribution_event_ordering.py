from __future__ import annotations

import unittest

from b3_strategy_lab.realistic import (
    CashDistribution,
    FeeRule,
    FeeSchedule,
    RealCashAccount,
    SlippageModel,
)
from b3_strategy_lab.realistic_portfolio import _cash_event_maps, _credit_event


class DistributionEventOrderingTests(unittest.TestCase):
    def _account(self) -> RealCashAccount:
        return RealCashAccount(
            100.0,
            FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 0.0)]),
            SlippageModel(base_bps=0.0, participation_bps_at_1pct=0.0, max_bps=0.0),
        )

    def test_same_day_entitlement_and_payment_is_deferred_to_next_session(self) -> None:
        event = CashDistribution(
            ticker="AAA3",
            label="DIVIDENDO",
            last_date_prior="2026-01-05",
            ex_date="2026-01-06",
            payment_date="2026-01-05",
            gross_per_share=1.0,
        )
        entitlement, payment = _cash_event_maps(
            [event],
            ["2026-01-05", "2026-01-06", "2026-01-07"],
        )
        self.assertEqual(entitlement["2026-01-05"], [event])
        self.assertNotIn("2026-01-05", payment)
        self.assertEqual(payment["2026-01-06"], [event])

    def test_credit_consumes_entitlement_and_cannot_double_pay(self) -> None:
        event = CashDistribution(
            ticker="AAA3",
            label="DIVIDENDO",
            last_date_prior="2026-01-05",
            ex_date="2026-01-06",
            payment_date="2026-01-07",
            gross_per_share=1.0,
        )
        key = ("AAA3", "2026-01-05", "2026-01-07", "DIVIDENDO", 1.0)
        account = self._account()
        entitlements = {key: 10}
        account.register_distribution_receivable(
            key,
            ticker="AAA3",
            label="DIVIDENDO",
            shares_entitled=10,
            gross_per_share=1.0,
            payment_date="2026-01-07",
        )

        self.assertAlmostEqual(_credit_event(account, event, entitlements), 10.0)
        self.assertAlmostEqual(account.cash, 110.0)
        self.assertAlmostEqual(account.distribution_receivable_value(), 0.0)
        self.assertNotIn(key, entitlements)

        self.assertAlmostEqual(_credit_event(account, event, entitlements), 0.0)
        self.assertAlmostEqual(account.cash, 110.0)


if __name__ == "__main__":
    unittest.main()
