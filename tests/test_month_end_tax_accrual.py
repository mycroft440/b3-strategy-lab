from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from b3_strategy_lab import realistic
from b3_strategy_lab import realistic_portfolio as portfolio
from scripts import backtest_strategy_management_combinations as combinations
from scripts import research_portfolio_allocation as research


class _Universe:
    def tickers_on(self, _value_date: str) -> set[str]:
        return {"AAA3"}


class MonthEndTaxAccrualTests(unittest.TestCase):
    def test_month_end_curve_is_already_net_of_accrued_ordinary_tax(self) -> None:
        class SeededAccount(realistic.RealCashAccount):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                # Seed a January taxable gain without introducing unrelated trade
                # mechanics into this timing regression.
                self.tax.record_sale("2026-01-30", 25_000.0, 1_000.0)
                self.tax._irrf_incident.clear()  # type: ignore[attr-defined]
                self.tax._irrf_withheld.clear()  # type: ignore[attr-defined]

        candles = [
            SimpleNamespace(date="2026-01-30", close=10.0, raw_close=10.0),
            SimpleNamespace(date="2026-02-02", close=10.0, raw_close=10.0),
        ]
        data = SimpleNamespace(
            dates=["2026-01-30", "2026-02-02"],
            tickers=["AAA3"],
            candles={"AAA3": candles},
            by_date={"AAA3": {candle.date: candle for candle in candles}},
        )
        fee_schedule = realistic.FeeSchedule(
            [realistic.FeeRule("2026-01-01", "2026-12-31", 0.0, quality="official")]
        )
        metrics = {
            "total_return": -0.15,
            "cagr": -0.15,
            "max_drawdown": -0.15,
            "annual_volatility": 0.0,
            "sharpe": 0.0,
        }
        config = SimpleNamespace(name="test_monthly", rebalance="monthly")

        with (
            patch.object(realistic, "RealCashAccount", SeededAccount),
            patch.object(portfolio, "_apply_split_from_adjustment_factors", return_value=None),
            patch.object(
                combinations,
                "_build_eligibility",
                return_value={"dummy": {"AAA3": [0, 0]}},
            ),
            patch.object(research, "_eligible_tickers", return_value=set()),
            patch.object(research, "_target_weights", return_value={}),
            patch.object(research, "_portfolio_metrics", return_value=metrics),
            patch.object(research, "_yearly_returns", return_value={}),
        ):
            summary, curve, account = portfolio.run_realistic(
                data=data,
                universe=_Universe(),
                pricebook=SimpleNamespace(),
                cash_events=[],
                fee_schedule=fee_schedule,
                strategy="dummy",
                config=config,
                start="2026-01-30",
                end="2026-02-02",
                initial_cash=1_000.0,
                base_slippage_bps=0.0,
                participation_bps_at_1pct=0.0,
                max_slippage_bps=0.0,
                transitions={},
                economic_gap_adjustment=False,
                survivorship_safe=True,
            )

        self.assertAlmostEqual(curve[0].cash, 850.0, places=8)
        self.assertAlmostEqual(curve[0].equity, 850.0, places=8)
        self.assertAlmostEqual(curve[1].equity, 850.0, places=8)
        self.assertAlmostEqual(summary.final_equity, 850.0, places=8)
        self.assertAlmostEqual(account.outstanding_tax_liability(), 150.0, places=8)
        self.assertIn("__ACCRUED_TAX_LIABILITY", summary.validity)


if __name__ == "__main__":
    unittest.main()
