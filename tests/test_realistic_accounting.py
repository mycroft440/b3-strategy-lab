from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from b3_strategy_lab.candles import Candle
from b3_strategy_lab.realistic import (
    BrazilEquityTaxLedger,
    CashDistribution,
    CashDistributionTaxLedger,
    ExecutionPriceBook,
    ExecutionQuote,
    FeeRule,
    FeeSchedule,
    PointInTimeUniverse,
    RealCashAccount,
    SlippageModel,
    UniverseSnapshot,
    cash_coverage_certification_issues,
)
from b3_strategy_lab.realistic_portfolio import (
    _event_key,
    _gap_adjusted_eligibility,
    _provisional_ordinary_tax,
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


class CashCoverageCertificationTests(unittest.TestCase):
    def test_certificate_is_bound_to_period_tickers_and_input_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            events = root / "events.csv"
            manifest = root / "manifest.json"
            events.write_text("ticker,amount\nAAA3,1.00\n", encoding="utf-8")
            manifest.write_text('{"complete": true}\n', encoding="utf-8")
            certification = {
                "schema_version": 1,
                "coverage_certified": True,
                "start": "2018-01-01",
                "end": "2024-12-31",
                "source_authority": "B3",
                "reviewed_by": "Independent reviewer",
                "reviewed_at_utc": "2025-01-02T12:00:00+00:00",
                "evidence": ["primary-source reconciliation"],
                "tickers": ["AAA3"],
                "cash_events_sha256": hashlib.sha256(events.read_bytes()).hexdigest(),
                "cash_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            }

            self.assertEqual(
                cash_coverage_certification_issues(
                    certification,
                    cash_events_path=events,
                    cash_manifest_path=manifest,
                    tickers={"AAA3"},
                    start="2018-01-02",
                    end="2024-12-30",
                ),
                [],
            )
            events.write_text("ticker,amount\nAAA3,2.00\n", encoding="utf-8")
            self.assertIn(
                "cash_events_sha256 does not match the certified input",
                cash_coverage_certification_issues(
                    certification,
                    cash_events_path=events,
                    cash_manifest_path=manifest,
                    tickers={"AAA3"},
                    start="2018-01-02",
                    end="2024-12-30",
                ),
            )


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
        self.assertEqual(
            [(qty, quote.market_type) for qty, quote in legs],
            [(100, "010"), (14, "020")],
        )

    def test_missing_fractional_open_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "Missing fractional-market open"):
            self._book(False).legs("2024-01-02", "AAA3", 14)


class GapAdjustmentTests(unittest.TestCase):
    def _candle(self, value_date: str, open_price: float, close_price: float, factor: float) -> Candle:
        return Candle(
            date=value_date,
            ticker="AAA3",
            source_symbol="AAA3",
            open=open_price,
            high=max(open_price, close_price),
            low=min(open_price, close_price),
            close=close_price,
            adj_close=close_price,
            volume=1000,
            raw_open=open_price / factor,
            raw_high=max(open_price, close_price) / factor,
            raw_low=min(open_price, close_price) / factor,
            raw_close=close_price / factor,
            adjustment_factor=factor,
            raw_volume=1000,
            trades=10,
            financial_volume=10000.0,
            market_type="010",
        )

    def test_cash_distribution_is_converted_to_split_normalized_signal_basis(self) -> None:
        candles = [
            self._candle("2020-01-02", 10.0, 10.0, 0.5),
            self._candle("2020-01-03", 9.0, 9.5, 0.5),
        ]
        data = SimpleNamespace(tickers=["AAA3"], candles={"AAA3": candles})
        event = CashDistribution(
            ticker="AAA3",
            label="DIVIDENDO",
            last_date_prior="2020-01-02",
            ex_date="2020-01-03",
            payment_date="2020-01-10",
            gross_per_share=2.0,
        )
        captured = {}

        def fake_build(_strategy, modified, **_params):
            captured["open"] = modified[1].open
            return [0, 0]

        with patch("b3_strategy_lab.realistic_portfolio_core.build_signals", side_effect=fake_build):
            _gap_adjusted_eligibility(data, "gap_momentum", [event], "adjusted")

        # Raw R$2/share must become R$1 on an adjustment_factor=0.5 series.
        self.assertAlmostEqual(captured["open"], 10.0)

    def test_distribution_identity_includes_payment_date(self) -> None:
        one = CashDistribution("AAA3", "DIVIDENDO", "2024-01-02", "2024-01-03", "2024-01-10", 1.0)
        two = CashDistribution("AAA3", "DIVIDENDO", "2024-01-02", "2024-01-03", "2024-02-10", 1.0)
        self.assertNotEqual(_event_key(one), _event_key(two))


class TaxTests(unittest.TestCase):
    def test_tax_ledgers_reject_invalid_economic_assumptions(self) -> None:
        for values in (
            {"exemption_sales_limit": -1.0},
            {"exemption_sales_limit": float("nan")},
            {"ordinary_rate": -0.1},
            {"ordinary_rate": float("inf")},
            {"ordinary_rate": 1.1},
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    BrazilEquityTaxLedger(**values)

        ledger = BrazilEquityTaxLedger()
        for gross_sale, gain in (
            (-1.0, 0.0),
            (float("nan"), 0.0),
            (1.0, float("inf")),
        ):
            with self.subTest(gross_sale=gross_sale, gain=gain):
                with self.assertRaises(ValueError):
                    ledger.record_sale("2024-01-02", gross_sale, gain)

        distributions = CashDistributionTaxLedger()
        with self.assertRaises(ValueError):
            distributions.net_jcp("2026-01-02", float("nan"))
        with self.assertRaises(ValueError):
            distributions.record_dividend("2026-01-02", "AAA3", -1.0)

    def _account(self) -> RealCashAccount:
        return RealCashAccount(
            100_000.0,
            FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 0.0)]),
            SlippageModel(base_bps=0, participation_bps_at_1pct=0),
        )

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
        self.assertAlmostEqual(feb.gross_tax_before_irrf, 300.0)
        self.assertAlmostEqual(feb.irrf_credit_used, 3.0)
        self.assertAlmostEqual(feb.tax_due, 297.0)

    def test_provisional_tax_reserves_cash_after_taxable_sales(self) -> None:
        account = self._account()
        account.tax.record_sale("2024-03-05", 30_000.0, 10_000.0)
        self.assertAlmostEqual(_provisional_ordinary_tax(account, "2024-03-05"), 1_500.0)

    def test_later_same_month_loss_reduces_provisional_reserve(self) -> None:
        account = self._account()
        account.tax.record_sale("2024-03-05", 30_000.0, 10_000.0)
        account.tax.record_sale("2024-03-20", 10_000.0, -4_000.0)
        self.assertAlmostEqual(_provisional_ordinary_tax(account, "2024-03-20"), 900.0)

    def test_prior_loss_carry_reduces_provisional_reserve(self) -> None:
        account = self._account()
        account.tax.record_sale("2024-01-10", 30_000.0, -1_000.0)
        account.tax.finalize("2024-01")
        account.tax.record_sale("2024-02-10", 30_000.0, 3_000.0)
        self.assertAlmostEqual(_provisional_ordinary_tax(account, "2024-02-10"), 300.0)

    def test_provisional_tax_is_zero_below_sales_exemption_limit(self) -> None:
        account = self._account()
        account.tax.record_sale("2024-03-05", 19_000.0, 10_000.0)
        self.assertEqual(_provisional_ordinary_tax(account, "2024-03-05"), 0.0)

    def test_jcp_withholding_through_2025_is_15_percent(self) -> None:
        ledger = CashDistributionTaxLedger()
        net, tax = ledger.net_jcp("2025-12-31", 100.0)
        self.assertAlmostEqual(net, 85.0)
        self.assertAlmostEqual(tax, 15.0)

    def test_jcp_withholding_from_2026_is_17_5_percent(self) -> None:
        ledger = CashDistributionTaxLedger()
        net, tax = ledger.net_jcp("2026-01-02", 100.0)
        self.assertAlmostEqual(net, 82.5)
        self.assertAlmostEqual(tax, 17.5)

    def test_2026_dividends_below_monthly_threshold_do_not_withhold(self) -> None:
        ledger = CashDistributionTaxLedger()
        ledger.record_dividend("2026-02-10", "AAA3", 49_999.99)
        self.assertEqual(ledger.settle_dividend_month("2026-02"), 0.0)

    def test_2026_large_dividend_fails_without_transition_classification(self) -> None:
        ledger = CashDistributionTaxLedger()
        ledger.record_dividend("2026-02-10", "AAA3", 60_000.0)
        with self.assertRaisesRegex(ValueError, "transitional/grandfathering"):
            ledger.settle_dividend_month("2026-02")


class CashAccountTests(unittest.TestCase):
    def test_fee_rules_and_costs_reject_invalid_economic_values(self) -> None:
        invalid_rules = (
            ("2024-12-31", "2024-01-01", 1.0, 0.0),
            ("2024-01-01", "2024-12-31", -1.0, 0.0),
            ("2024-01-01", "2024-12-31", float("nan"), 0.0),
            ("2024-01-01", "2024-12-31", 1.0, -1.0),
        )
        for start, end, b3_bps, brokerage in invalid_rules:
            with self.subTest(values=(start, end, b3_bps, brokerage)):
                with self.assertRaises(ValueError):
                    FeeRule(start, end, b3_bps, brokerage)

        schedule = FeeSchedule([FeeRule("2024-01-01", "2024-12-31", 0.0)])
        for invalid_notional in (-1.0, float("nan"), float("inf")):
            with self.subTest(notional=invalid_notional):
                with self.assertRaises(ValueError):
                    schedule.cost("2024-06-01", invalid_notional)

    def test_slippage_model_rejects_invalid_parameters_and_notionals(self) -> None:
        invalid_models = (
            {"base_bps": -1.0},
            {"participation_bps_at_1pct": float("nan")},
            {"max_bps": float("inf")},
            {"base_bps": 10.0, "max_bps": 9.0},
            {"max_bps": 10_000.0},
        )
        for values in invalid_models:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    SlippageModel(**values)

        model = SlippageModel(base_bps=0.0, participation_bps_at_1pct=0.0)
        for invalid_notional in (-1.0, float("nan"), float("inf")):
            with self.subTest(notional=invalid_notional):
                with self.assertRaises(ValueError):
                    model.bps(invalid_notional, 1_000.0)

    def test_cash_account_rejects_nonfinite_initial_cash(self) -> None:
        fees = FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 0.0)])
        slippage = SlippageModel(base_bps=0.0, participation_bps_at_1pct=0.0)
        for initial_cash in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(initial_cash=initial_cash):
                with self.assertRaises(ValueError):
                    RealCashAccount(initial_cash, fees, slippage)

    def test_buy_and_sell_preserve_nonnegative_cash_and_realized_gain(self) -> None:
        fees = FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 3.0)])
        account = RealCashAccount(
            1_000.0,
            fees,
            SlippageModel(base_bps=0, participation_bps_at_1pct=0),
        )
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
