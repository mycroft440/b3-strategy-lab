from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from b3_strategy_lab.realistic import (
    BrazilEquityTaxLedger,
    CashDistributionTaxLedger,
    ExecutionPriceBook,
    ExecutionQuote,
    FeeRule,
    FeeSchedule,
    PointInTimeUniverse,
    RealCashAccount,
    SlippageModel,
    UniverseSnapshot,
)


class PointInTimeUniverseTests(unittest.TestCase):
    def test_never_uses_future_snapshot(self) -> None:
        universe = PointInTimeUniverse(
            [
                UniverseSnapshot("2018-01-05", frozenset({"AAA3"})),
                UniverseSnapshot("2018-01-12", frozenset({"BBB3"})),
            ]
        )
        self.assertEqual(universe.tickers_on("2018-01-10"), {"AAA3"})
        self.assertEqual(universe.tickers_on("2018-01-12"), {"BBB3"})
        with self.assertRaises(ValueError):
            universe.tickers_on("2018-01-04")


class FractionalExecutionTests(unittest.TestCase):
    def _book(self, include_fractional: bool = True) -> ExecutionPriceBook:
        rows = [
            ExecutionQuote("2024-01-02", "AAA3", "010", 10.00, 10.20, 1_000_000.0),
        ]
        if include_fractional:
            rows.append(
                ExecutionQuote("2024-01-02", "AAA3F", "020", 10.10, 10.25, 100_000.0)
            )
        return ExecutionPriceBook(rows)

    def test_114_shares_use_round_and_fractional_markets(self) -> None:
        legs = self._book().legs("2024-01-02", "AAA3", 114)
        self.assertEqual([(qty, quote.market_type) for qty, quote in legs], [(100, "010"), (14, "020")])

    def test_missing_fractional_open_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "Missing fractional-market open"):
            self._book(False).legs("2024-01-02", "AAA3", 14)


class TaxTests(unittest.TestCase):
    def test_small_month_positive_gain_is_exempt(self) -> None:
        ledger = BrazilEquityTaxLedger()
        ledger.record_sale("2024-01-10", 19_000.0, 2_000.0)
        month = ledger.finalize("2024-01")
        self.assertEqual(month.tax_due, 0.0)
        self.assertEqual(month.exempt_gain, 2_000.0)

    def test_losses_carry_to_taxable_month(self) -> None:
        ledger = BrazilEquityTaxLedger()
        ledger.record_sale("2024-01-10", 30_000.0, -1_000.0)
        self.assertEqual(ledger.finalize("2024-01").loss_carry_out, 1_000.0)
        ledger.record_sale("2024-02-10", 30_000.0, 3_000.0)
        feb = ledger.finalize("2024-02")
        self.assertAlmostEqual(feb.taxable_gain, 2_000.0)
        self.assertAlmostEqual(feb.tax_due, 300.0)

    def test_jcp_withholding(self) -> None:
        ledger = CashDistributionTaxLedger()
        net, tax = ledger.net_jcp(100.0)
        self.assertAlmostEqual(net, 85.0)
        self.assertAlmostEqual(tax, 15.0)

    def test_2026_large_same_payer_dividend_month(self) -> None:
        ledger = CashDistributionTaxLedger()
        ledger.record_dividend("2026-02-10", "AAA3", 60_000.0)
        self.assertAlmostEqual(ledger.settle_dividend_month("2026-02"), 6_000.0)


class CashAccountTests(unittest.TestCase):
    def test_buy_and_sell_preserve_nonnegative_cash_and_realized_gain(self) -> None:
        fees = FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 3.0)])
        account = RealCashAccount(1_000.0, fees, SlippageModel(base_bps=0, participation_bps_at_1pct=0))
        buy = ExecutionQuote("2024-01-02", "AAA3", "020", 10.0, 10.0, 100_000.0)
        account.buy_leg("2024-01-02", "AAA3", 50, buy)
        self.assertGreaterEqual(account.cash, 0.0)
        sell = ExecutionQuote("2024-01-10", "AAA3", "020", 12.0, 12.0, 100_000.0)
        account.sell_leg("2024-01-10", "AAA3", 50, sell)
        self.assertGreater(account.trade_ledger[-1].realized_gain, 0.0)
        self.assertEqual(account.shares("AAA3"), 0)

    def test_fee_schedule_requires_exactly_one_date_rule(self) -> None:
        schedule = FeeSchedule(
            [
                FeeRule("2024-01-01", "2024-12-31", 3.0),
                FeeRule("2024-06-01", "2024-12-31", 4.0),
            ]
        )
        with self.assertRaises(ValueError):
            schedule.rule_on("2024-07-01")


if __name__ == "__main__":
    unittest.main()
