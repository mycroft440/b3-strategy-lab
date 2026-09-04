from __future__ import annotations

import unittest
from collections import defaultdict
from pathlib import Path

from b3_strategy_lab.instrument_transitions import InstrumentTransition, load_transition_reviews
from b3_strategy_lab.realistic import FeeRule, FeeSchedule, RealCashAccount, SlippageModel
from b3_strategy_lab.realistic_portfolio import _apply_ticker_transitions


SOURCE = "https://www.b3.com.br/example.pdf"


class InstrumentTransitionLayerTests(unittest.TestCase):
    def _account(self, shares: int = 10, average_cost: float = 10.0) -> RealCashAccount:
        account = RealCashAccount(
            1000.0,
            FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 0.0)]),
            SlippageModel(base_bps=0.0, participation_bps_at_1pct=0.0, max_bps=0.0),
        )
        account.positions = defaultdict(type(account.positions["X3"]))
        account.positions["OLD4"].shares = shares
        account.positions["OLD4"].average_cost = average_cost
        return account

    def _certified(self, **overrides) -> InstrumentTransition:
        values = {
            "effective_date": "2025-06-12",
            "old_ticker": "OLD4",
            "new_ticker": "NEW54",
            "share_ratio": 1.0,
            "old_isin": "BROLDXACNPR4",
            "new_isin": "BRNEWXA01PR5",
            "old_quotation_factor": 1,
            "new_quotation_factor": 1000,
            "cutoff_date": "2025-06-11",
            "first_successor_trade_date": "2025-06-12",
            "event_type": "reorganization",
            "fractional_treatment": "preserve_units",
            "tax_basis_treatment": "carry_total_basis",
            "source_authority": "B3",
            "source_url": SOURCE,
            "source_reference": "official event",
            "certification_status": "certified",
        }
        values.update(overrides)
        return InstrumentTransition(**values)

    def test_goll4_review_preserves_quantity_and_separates_quotation_factor(self) -> None:
        registry = Path("data/corporate_actions/instrument_transition_reviews.json")
        reviews = load_transition_reviews(registry)
        goll = next(item for item in reviews if item.old_ticker == "GOLL4")
        self.assertEqual(goll.new_ticker, "GOLL54")
        self.assertEqual(goll.old_isin, "BRGOLLACNPR4")
        self.assertEqual(goll.new_isin, "BRGOLLA01PR5")
        self.assertTrue(goll.changes_isin)
        self.assertEqual(goll.share_ratio, 1.0)
        self.assertEqual(goll.old_quotation_factor, 1)
        self.assertEqual(goll.new_quotation_factor, 1000)
        self.assertEqual(goll.quotation_factor_ratio, 1000.0)
        self.assertEqual(goll.first_successor_trade_date, "2025-06-12")

    def test_one_for_one_isin_change_preserves_position_and_total_basis(self) -> None:
        account = self._account(shares=100, average_cost=1.10)
        transition = self._certified()
        cash_before = account.cash
        _apply_ticker_transitions(account, [transition])
        self.assertEqual(account.shares("OLD4"), 0)
        self.assertEqual(account.shares("NEW54"), 100)
        self.assertAlmostEqual(account.positions["NEW54"].average_cost, 1.10)
        self.assertAlmostEqual(account.cash, cash_before)
        self.assertAlmostEqual(
            account.positions["NEW54"].shares * account.positions["NEW54"].average_cost,
            110.0,
        )

    def test_certified_non_one_for_one_conversion_carries_total_basis(self) -> None:
        account = self._account(shares=10, average_cost=10.0)
        transition = self._certified(
            share_ratio=0.5,
            old_quotation_factor=1,
            new_quotation_factor=1,
            fractional_treatment="require_integer",
        )
        _apply_ticker_transitions(account, [transition])
        self.assertEqual(account.shares("NEW54"), 5)
        self.assertAlmostEqual(account.positions["NEW54"].average_cost, 20.0)
        self.assertAlmostEqual(
            account.positions["NEW54"].shares * account.positions["NEW54"].average_cost,
            100.0,
        )

    def test_non_integer_conversion_still_fails_without_cash_in_lieu_implementation(self) -> None:
        account = self._account(shares=3, average_cost=10.0)
        transition = self._certified(share_ratio=0.5, fractional_treatment="cash_in_lieu")
        with self.assertRaisesRegex(ValueError, "cash-in-lieu"):
            _apply_ticker_transitions(account, [transition])

    def test_certified_terminal_worthless_event_can_close_position_without_successor(self) -> None:
        account = self._account(shares=10, average_cost=10.0)
        cash_before = account.cash
        transition = self._certified(
            new_ticker="",
            new_isin="",
            event_type="economic_termination",
            fractional_treatment="not_applicable",
            tax_basis_treatment="terminal_worthless",
            first_successor_trade_date="",
            new_quotation_factor=1,
        )
        _apply_ticker_transitions(account, [transition])
        self.assertEqual(account.shares("OLD4"), 0)
        self.assertAlmostEqual(account.cash, cash_before)

    def test_cash_component_remains_fail_closed_without_source_specific_tax_engine(self) -> None:
        account = self._account()
        transition = self._certified(cash_per_old_share=2.0)
        with self.assertRaisesRegex(ValueError, "cash component"):
            _apply_ticker_transitions(account, [transition])


if __name__ == "__main__":
    unittest.main()
