from __future__ import annotations

import importlib
import unittest

from b3_strategy_lab import b3_official, b3_payload_hardening
from b3_strategy_lab.b3_official import B3CorporateActionError


class B3PayloadHardeningTests(unittest.TestCase):
    def _extract(self, stock_dividends):
        return b3_official.extract_official_split_events(
            [{"code": "TEST", "stockDividends": stock_dividends}],
            ticker="TEST3",
            issuing_company="TEST",
            quote_dates=["2024-01-02", "2024-01-03"],
            quote_isins=["BRTESTACNOR0"],
            coverage_start="2024-01-01",
        )

    def test_non_list_stock_dividends_fails_closed(self) -> None:
        for malformed in ("", "corrupt", {}, {"event": "x"}, 123, True):
            with self.subTest(value=malformed):
                with self.assertRaisesRegex(
                    B3CorporateActionError,
                    "stockDividends B3 precisa ser uma lista",
                ):
                    self._extract(malformed)

    def test_non_mapping_stock_dividend_row_fails_closed(self) -> None:
        for malformed in (None, "event", 123, ["event"]):
            with self.subTest(value=malformed):
                with self.assertRaisesRegex(
                    B3CorporateActionError,
                    "stockDividends B3 contem registro invalido",
                ):
                    self._extract([malformed])

    def test_missing_or_null_stock_dividends_preserves_zero_event_contract(self) -> None:
        for payload in (
            [{"code": "TEST"}],
            [{"code": "TEST", "stockDividends": None}],
            [{"code": "TEST", "stockDividends": []}],
        ):
            with self.subTest(payload=payload):
                events = b3_official.extract_official_split_events(
                    payload,
                    ticker="TEST3",
                    issuing_company="TEST",
                    quote_dates=["2024-01-02", "2024-01-03"],
                    quote_isins=["BRTESTACNOR0"],
                    coverage_start="2024-01-01",
                )
                self.assertEqual(events, [])

    def test_valid_share_count_event_preserves_canonical_math(self) -> None:
        events = self._extract(
            [
                {
                    "isinCode": "BRTESTACNOR0",
                    "label": "BONIFICACAO",
                    "factor": "10,00000000000",
                    "lastDatePrior": "02/01/2024",
                }
            ]
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].ex_date, "2024-01-03")
        self.assertAlmostEqual(events[0].split_ratio, 1.1)

    def test_patch_reload_does_not_stack_or_recurse(self) -> None:
        canonical = getattr(
            b3_official,
            "_payload_hardening_original_extract_official_split_events",
        )
        for _ in range(3):
            importlib.reload(b3_payload_hardening)
            self.assertIs(
                getattr(
                    b3_official,
                    "_payload_hardening_original_extract_official_split_events",
                ),
                canonical,
            )
        self.assertEqual(self._extract([]), [])


if __name__ == "__main__":
    unittest.main()
