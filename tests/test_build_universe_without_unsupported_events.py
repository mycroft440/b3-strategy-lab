from __future__ import annotations

import unittest

from scripts.build_universe_without_unsupported_events import unsupported_tickers


class UnsupportedTickersTests(unittest.TestCase):
    def test_lists_only_selectable_tickers_with_first_reason(self) -> None:
        boundaries = [
            ("2024-08-27", "CIEL3", "", "registration_cancelled"),
            ("2025-09-23", "BRFS3", "MBRF3", "incorporation"),
            ("2021-03-01", "PCAR3", "PCAR3", "spin_off"),
        ]
        delistings = [
            {"ticker": "TIMP3", "last_quote_date": "2020-10-09"},
            {"ticker": "CIEL3", "last_quote_date": "2024-08-26"},
        ]

        result = unsupported_tickers(boundaries, delistings, ["ciel3", "BRFS3", "TIMP3", "PETR4"])

        self.assertEqual(sorted(result), ["BRFS3", "CIEL3", "TIMP3"])
        self.assertEqual(result["CIEL3"], "registration_cancelled em 2024-08-27 (sem sucessor)")
        self.assertEqual(result["BRFS3"], "incorporation em 2025-09-23 (BRFS3->MBRF3)")
        self.assertIn("sem sucessor documentado", result["TIMP3"])

    def test_nothing_to_remove(self) -> None:
        self.assertEqual(unsupported_tickers([], [], ["PETR4"]), {})


if __name__ == "__main__":
    unittest.main()
