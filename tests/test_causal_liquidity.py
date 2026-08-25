from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from b3_strategy_lab.point_in_time import execution_rows
from b3_strategy_lab.realistic import (
    ExecutionPriceBook,
    ExecutionQuote,
    FeeRule,
    FeeSchedule,
    RealCashAccount,
    SlippageModel,
)


def quote(day: str, *, financial: float, quantity: int) -> SimpleNamespace:
    return SimpleNamespace(
        date=day,
        ticker="AAA3F",
        isin="BRAAAACNOR00",
        open=10.0,
        high=10.5,
        low=9.5,
        close=10.1,
        volume=quantity,
        trades=100,
        financial_volume=financial,
    )


class CausalLiquidityTests(unittest.TestCase):
    def test_execution_reference_ends_before_execution_session(self) -> None:
        rows = execution_rows(
            [],
            [
                quote("2023-12-29", financial=100_000.0, quantity=10_000),
                quote("2024-01-02", financial=200_000.0, quantity=20_000),
            ],
            union={"AAA3"},
            start="2024-01-02",
            end="2024-01-02",
            liquidity_lookback_sessions=21,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["liquidity_reference_end"], "2023-12-29")
        self.assertEqual(rows[0]["liquidity_reference_financial_volume"], 100_000.0)
        self.assertEqual(rows[0]["liquidity_reference_quantity"], 10_000.0)

    def test_csv_loader_rejects_same_day_liquidity_reference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "execution.csv"
            path.write_text(
                "date,ticker,market_type,open,high,low,close,quantity,trades,"
                "financial_volume,liquidity_reference_financial_volume,"
                "liquidity_reference_quantity,liquidity_reference_sessions,"
                "liquidity_reference_end\n"
                "2024-01-02,AAA3F,020,10,11,9,10,10000,100,100000,"
                "100000,10000,21,2024-01-02\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "strictly pre-trade"):
                ExecutionPriceBook.from_csv(path)

    def test_hard_capacity_cap_rejects_full_fill(self) -> None:
        account = RealCashAccount(
            10_000.0,
            FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 0.0)]),
            SlippageModel(
                base_bps=0.0,
                participation_bps_at_1pct=0.0,
                max_bps=0.0,
                max_participation_rate=0.01,
            ),
        )
        execution = ExecutionQuote(
            "2024-01-02",
            "AAA3F",
            "020",
            10.0,
            10.0,
            1_000_000.0,
            high=11.0,
            low=9.0,
            quantity=100_000,
            liquidity_reference_financial_volume=100_000.0,
            liquidity_reference_quantity=10_000.0,
            liquidity_reference_sessions=21,
            liquidity_reference_end="2023-12-29",
        )
        with self.assertRaisesRegex(ValueError, "hard pre-trade liquidity-capacity"):
            account.buy_leg("2024-01-02", "AAA3", 200, execution)

    def test_fill_uses_prior_reference_and_ohlc_is_diagnostic_only(self) -> None:
        account = RealCashAccount(
            1_000.0,
            FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 0.0)]),
            SlippageModel(
                base_bps=100.0,
                participation_bps_at_1pct=0.0,
                max_bps=100.0,
                max_participation_rate=0.01,
            ),
        )
        execution = ExecutionQuote(
            "2024-01-02",
            "AAA3F",
            "020",
            10.0,
            10.0,
            1.0,  # Full-day volume is intentionally unusable at the opening.
            high=10.05,
            low=9.5,
            quantity=1,
            liquidity_reference_financial_volume=1_000_000.0,
            liquidity_reference_quantity=100_000.0,
            liquidity_reference_sessions=21,
            liquidity_reference_end="2023-12-29",
        )
        account.buy_leg("2024-01-02", "AAA3", 50, execution)
        trade = account.trade_ledger[-1]
        self.assertAlmostEqual(trade.financial_participation, 0.0005)
        self.assertAlmostEqual(trade.execution_price, 10.10)
        self.assertGreater(trade.execution_price, execution.high)
        self.assertTrue(trade.fill_outside_daily_range)


if __name__ == "__main__":
    unittest.main()
