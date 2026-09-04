from __future__ import annotations

import math
import unittest
from types import SimpleNamespace

from b3_strategy_lab.cash_distributions import build_cash_events


class CashDistributionFailClosedTests(unittest.TestCase):
    def _quotes(self):
        return [
            SimpleNamespace(date="2024-01-02", isin="BRAAAAACNOR0"),
            SimpleNamespace(date="2024-01-03", isin="BRAAAAACNOR0"),
        ]

    def _build(self, cash_dividends):
        return build_cash_events(
            ["AAAA3"],
            {"AAAA3": "AAAA"},
            {"AAAA": [{"code": "AAAA", "cashDividends": cash_dividends}]},
            {"AAAA3": self._quotes()},
        )

    def test_non_list_cash_dividends_is_blocking_issue(self) -> None:
        for malformed in ("corrupt", {}, 123, True):
            with self.subTest(value=malformed):
                rows, issues = self._build(malformed)
                self.assertEqual(rows, [])
                self.assertEqual(issues[0]["issue"], "cash_dividends_invalid_container")

    def test_non_mapping_cash_row_is_blocking_issue(self) -> None:
        rows, issues = self._build([None])
        self.assertEqual(rows, [])
        self.assertEqual(issues[0]["issue"], "cash_dividend_invalid_record")
        self.assertEqual(issues[0]["event_index"], 0)

    def test_invalid_top_level_payload_is_blocking_issue(self) -> None:
        for malformed in ([], [None], "corrupt"):
            with self.subTest(value=malformed):
                rows, issues = build_cash_events(
                    ["AAAA3"],
                    {"AAAA3": "AAAA"},
                    {"AAAA": malformed},
                    {"AAAA3": self._quotes()},
                )
                self.assertEqual(rows, [])
                self.assertEqual(issues[0]["issue"], "issuer_payload_invalid")

    def test_nonfinite_and_nonpositive_rates_are_blocking(self) -> None:
        for value in ("nan", "inf", "-inf", "0", "-1"):
            with self.subTest(rate=value):
                rows, issues = self._build(
                    [
                        {
                            "label": "DIVIDENDO",
                            "isinCode": "BRAAAAACNOR0",
                            "lastDatePrior": "02/01/2024",
                            "paymentDate": "10/01/2024",
                            "rate": value,
                        }
                    ]
                )
                self.assertEqual(rows, [])
                self.assertEqual(issues[0]["issue"], "invalid_rate")

    def test_missing_cash_dividends_keeps_legitimate_empty_ledger(self) -> None:
        for company in ({"code": "AAAA"}, {"code": "AAAA", "cashDividends": None}):
            rows, issues = build_cash_events(
                ["AAAA3"],
                {"AAAA3": "AAAA"},
                {"AAAA": [company]},
                {"AAAA3": self._quotes()},
            )
            self.assertEqual(rows, [])
            self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
