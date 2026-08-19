from __future__ import annotations

import unittest
from types import SimpleNamespace

from b3_strategy_lab.cash_distributions import build_cash_events


class CashDistributionCollectorTests(unittest.TestCase):
    def _quotes(self):
        return [
            SimpleNamespace(date="2024-01-02", isin="BRAAAAACNOR0"),
            SimpleNamespace(date="2024-01-03", isin="BRAAAAACNOR0"),
            SimpleNamespace(date="2024-02-01", isin="BRAAAAACNOR0"),
        ]

    def test_distinct_payment_installments_are_not_collapsed(self) -> None:
        payloads = {
            "AAAA": [
                {
                    "code": "AAAA",
                    "cashDividends": [
                        {
                            "label": "DIVIDENDO",
                            "isinCode": "BRAAAAACNOR0",
                            "lastDatePrior": "02/01/2024",
                            "paymentDate": "10/01/2024",
                            "rate": "1.25",
                        },
                        {
                            "label": "DIVIDENDO",
                            "isinCode": "BRAAAAACNOR0",
                            "lastDatePrior": "02/01/2024",
                            "paymentDate": "10/02/2024",
                            "rate": "1.25",
                        },
                    ],
                }
            ]
        }
        rows, issues = build_cash_events(
            ["AAAA3"],
            {"AAAA3": "AAAA"},
            payloads,
            {"AAAA3": self._quotes()},
        )
        self.assertEqual(issues, [])
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            [row["payment_date"] for row in rows],
            ["2024-01-10", "2024-02-10"],
        )
        self.assertTrue(all(row["ex_date"] == "2024-01-03" for row in rows))

    def test_exact_duplicate_is_deduplicated(self) -> None:
        event = {
            "label": "JCP",
            "isinCode": "BRAAAAACNOR0",
            "lastDatePrior": "02/01/2024",
            "paymentDate": "10/01/2024",
            "rate": "0.50",
        }
        payloads = {
            "AAAA": [
                {
                    "code": "AAAA",
                    "cashDividends": [dict(event), dict(event)],
                }
            ]
        }
        rows, issues = build_cash_events(
            ["AAAA3"],
            {"AAAA3": "AAAA"},
            payloads,
            {"AAAA3": self._quotes()},
        )
        self.assertEqual(issues, [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["label"], "JCP")


if __name__ == "__main__":
    unittest.main()
