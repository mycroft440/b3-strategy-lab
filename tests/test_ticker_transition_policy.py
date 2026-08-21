from __future__ import annotations

import unittest
from collections import defaultdict

from b3_strategy_lab.realistic import FeeRule, FeeSchedule, RealCashAccount, SlippageModel
from b3_strategy_lab.realistic_portfolio import TickerTransition, _apply_ticker_transitions


class TickerTransitionPolicyTests(unittest.TestCase):
    def _account(self) -> RealCashAccount:
        account = RealCashAccount(
            1000.0,
            FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 0.0)]),
            SlippageModel(base_bps=0.0, participation_bps_at_1pct=0.0, max_bps=0.0),
        )
        account.positions = defaultdict(type(account.positions["X3"]))
        account.positions["OLD3"].shares = 10
        account.positions["OLD3"].average_cost = 12.0
        return account

    def test_same_isin_style_one_for_one_rename_is_supported(self) -> None:
        account = self._account()
        _apply_ticker_transitions(
            account,
            [TickerTransition("2026-01-02", "OLD3", "NEW3", 1.0, 0.0)],
        )
        self.assertEqual(account.shares("OLD3"), 0)
        self.assertEqual(account.shares("NEW3"), 10)
        self.assertAlmostEqual(account.positions["NEW3"].average_cost, 12.0)

    def test_cash_component_is_rejected_without_explicit_tax_basis_rule(self) -> None:
        account = self._account()
        with self.assertRaisesRegex(ValueError, "cash component"):
            _apply_ticker_transitions(
                account,
                [TickerTransition("2026-01-02", "OLD3", "NEW3", 1.0, 2.0)],
            )

    def test_non_one_for_one_conversion_is_rejected_without_explicit_tax_basis_rule(self) -> None:
        account = self._account()
        with self.assertRaisesRegex(ValueError, "1:1"):
            _apply_ticker_transitions(
                account,
                [TickerTransition("2026-01-02", "OLD3", "NEW3", 0.5, 0.0)],
            )


if __name__ == "__main__":
    unittest.main()
