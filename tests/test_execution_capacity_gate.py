from __future__ import annotations

import unittest

from b3_strategy_lab.realistic import (
    ExecutionQuote,
    FeeRule,
    FeeSchedule,
    RealCashAccount,
    SlippageModel,
)


class ExecutionCapacityGateTests(unittest.TestCase):
    def _account(self) -> RealCashAccount:
        return RealCashAccount(
            100_000.0,
            FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 0.0)]),
            SlippageModel(base_bps=0.0, participation_bps_at_1pct=0.0, max_bps=0.0),
        )

    @staticmethod
    def _quote(volume: float = 100_000.0) -> ExecutionQuote:
        return ExecutionQuote("2026-01-05", "AAA3", "010", 10.0, 10.0, volume)

    def test_generic_research_keeps_capacity_gate_disabled(self) -> None:
        account = self._account()
        account.buy_leg("2026-01-05", "AAA3", 200, self._quote())
        self.assertEqual(account.shares("AAA3"), 200)

    def test_certified_capacity_gate_accepts_order_at_limit(self) -> None:
        account = self._account()
        account._max_causal_adv_participation = 0.01
        # R$1,000 / R$100,000 = 1%.
        account.buy_leg("2026-01-05", "AAA3", 100, self._quote())
        self.assertEqual(account.shares("AAA3"), 100)

    def test_certified_capacity_gate_rejects_oversized_buy(self) -> None:
        account = self._account()
        account._max_causal_adv_participation = 0.01
        with self.assertRaisesRegex(ValueError, "Refusing a full-fill assumption"):
            account.buy_leg("2026-01-05", "AAA3", 101, self._quote())
        self.assertEqual(account.shares("AAA3"), 0)

    def test_certified_capacity_gate_rejects_oversized_sell_before_mutation(self) -> None:
        account = self._account()
        account.buy_leg("2026-01-05", "AAA3", 200, self._quote())
        account._max_causal_adv_participation = 0.01
        with self.assertRaisesRegex(ValueError, "Refusing a full-fill assumption"):
            account.sell_leg("2026-01-05", "AAA3", 101, self._quote())
        self.assertEqual(account.shares("AAA3"), 200)

    def test_invalid_capacity_configuration_fails_closed(self) -> None:
        account = self._account()
        account._max_causal_adv_participation = 0.0
        with self.assertRaisesRegex(ValueError, "must be finite and in"):
            account.buy_leg("2026-01-05", "AAA3", 1, self._quote())


if __name__ == "__main__":
    unittest.main()
