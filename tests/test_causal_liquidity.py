from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from b3_strategy_lab.realistic import ExecutionPriceBook, SlippageModel


class CausalLiquidityTests(unittest.TestCase):
    def _book(self, rows: list[dict[str, object]]) -> ExecutionPriceBook:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "execution.csv"
            with path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=[
                        "date",
                        "ticker",
                        "market_type",
                        "open",
                        "close",
                        "financial_volume",
                    ],
                )
                writer.writeheader()
                writer.writerows(rows)
            return ExecutionPriceBook.from_csv(path)

    def test_from_csv_enables_causal_liquidity_automatically(self) -> None:
        book = self._book(
            [
                {
                    "date": "2024-01-02",
                    "ticker": "AAA3",
                    "market_type": "010",
                    "open": 10,
                    "close": 10,
                    "financial_volume": 1000,
                },
                {
                    "date": "2024-01-03",
                    "ticker": "AAA3",
                    "market_type": "010",
                    "open": 10,
                    "close": 10,
                    "financial_volume": 999999999,
                },
            ]
        )
        self.assertTrue(getattr(book, "_causal_liquidity_enabled", False))
        [(qty, quote)] = book.legs("2024-01-03", "AAA3", 100)
        self.assertEqual(qty, 100)
        self.assertEqual(quote.financial_volume, 1000.0)

    def test_same_day_and_future_volume_cannot_change_opening_slippage(self) -> None:
        common_prior = [
            {
                "date": "2024-01-02",
                "ticker": "AAA3",
                "market_type": "010",
                "open": 10,
                "close": 10,
                "financial_volume": 1_000_000,
            },
            {
                "date": "2024-01-03",
                "ticker": "AAA3",
                "market_type": "010",
                "open": 10,
                "close": 10,
                "financial_volume": 3_000_000,
            },
        ]
        low_future = self._book(
            common_prior
            + [
                {
                    "date": "2024-01-04",
                    "ticker": "AAA3",
                    "market_type": "010",
                    "open": 10,
                    "close": 10,
                    "financial_volume": 1,
                },
                {
                    "date": "2024-01-05",
                    "ticker": "AAA3",
                    "market_type": "010",
                    "open": 10,
                    "close": 10,
                    "financial_volume": 1,
                },
            ]
        )
        high_future = self._book(
            common_prior
            + [
                {
                    "date": "2024-01-04",
                    "ticker": "AAA3",
                    "market_type": "010",
                    "open": 10,
                    "close": 10,
                    "financial_volume": 9_000_000_000,
                },
                {
                    "date": "2024-01-05",
                    "ticker": "AAA3",
                    "market_type": "010",
                    "open": 10,
                    "close": 10,
                    "financial_volume": 9_000_000_000,
                },
            ]
        )
        [(_, low_quote)] = low_future.legs("2024-01-04", "AAA3", 100)
        [(_, high_quote)] = high_future.legs("2024-01-04", "AAA3", 100)
        self.assertEqual(low_quote.financial_volume, 2_000_000.0)
        self.assertEqual(high_quote.financial_volume, 2_000_000.0)

        model = SlippageModel(
            base_bps=10.0,
            participation_bps_at_1pct=5.0,
            max_bps=100.0,
        )
        low_fill, low_bps = model.price(
            "BUY",
            low_quote.open,
            100 * low_quote.open,
            low_quote.financial_volume,
        )
        high_fill, high_bps = model.price(
            "BUY",
            high_quote.open,
            100 * high_quote.open,
            high_quote.financial_volume,
        )
        self.assertEqual(low_bps, high_bps)
        self.assertEqual(low_fill, high_fill)

    def test_missing_fractional_or_standard_sessions_count_as_zero_liquidity(self) -> None:
        book = self._book(
            [
                {
                    "date": "2024-01-02",
                    "ticker": "AAA3",
                    "market_type": "010",
                    "open": 10,
                    "close": 10,
                    "financial_volume": 3000,
                },
                {
                    "date": "2024-01-03",
                    "ticker": "BBB3",
                    "market_type": "010",
                    "open": 20,
                    "close": 20,
                    "financial_volume": 5000,
                },
                {
                    "date": "2024-01-04",
                    "ticker": "BBB3",
                    "market_type": "010",
                    "open": 20,
                    "close": 20,
                    "financial_volume": 5000,
                },
                {
                    "date": "2024-01-05",
                    "ticker": "AAA3",
                    "market_type": "010",
                    "open": 10,
                    "close": 10,
                    "financial_volume": 999999,
                },
            ]
        )
        [(_, quote)] = book.legs("2024-01-05", "AAA3", 100)
        self.assertEqual(quote.financial_volume, 1000.0)

    def test_no_prior_session_fails_closed_instead_of_using_same_day_volume(self) -> None:
        book = self._book(
            [
                {
                    "date": "2024-01-02",
                    "ticker": "AAA3",
                    "market_type": "010",
                    "open": 10,
                    "close": 10,
                    "financial_volume": 999999999,
                }
            ]
        )
        with self.assertRaisesRegex(ValueError, "no prior market session"):
            book.legs("2024-01-02", "AAA3", 100)


if __name__ == "__main__":
    unittest.main()
