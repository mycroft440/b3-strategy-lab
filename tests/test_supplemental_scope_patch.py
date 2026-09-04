from __future__ import annotations

import importlib
import unittest

from b3_strategy_lab import b3_official, supplemental_scope_patch


class SupplementalScopePatchTests(unittest.TestCase):
    def _valid_event(self, ticker: str) -> dict[str, object]:
        return {
            "ticker": ticker,
            "ex_date": "2017-01-03",
            "last_date_prior": "2017-01-02",
            "split_ratio": 2.0,
            "event": "DESDOBRAMENTO 1 PARA 2",
            "source_authority": "issuer",
            "source_url": "https://ri.example.com/evento",
        }

    def _parse(self, payload: dict) -> list:
        return b3_official.parse_supplemental_split_events(
            payload,
            tickers=["AAAA3"],
            quote_dates_by_ticker={"AAAA3": ["2017-01-02", "2017-01-03"]},
            coverage_start="2017-01-01",
        )

    def test_unrelated_valid_registry_event_is_not_treated_as_current_universe_corruption(self) -> None:
        payload = {
            "schema_version": 1,
            "coverage_start": "2017-01-01",
            "events": [self._valid_event("AAAA3"), self._valid_event("BBBB3")],
        }
        events = self._parse(payload)
        self.assertEqual(
            [(event.ticker, event.ex_date) for event in events],
            [("AAAA3", "2017-01-03")],
        )

    def test_in_scope_invalid_event_still_fails_closed(self) -> None:
        broken = self._valid_event("AAAA3")
        broken["source_authority"] = "secondary"
        payload = {
            "schema_version": 1,
            "coverage_start": "2017-01-01",
            "events": [broken],
        }
        with self.assertRaisesRegex(Exception, "fonte suplementar precisa ser CVM ou issuer"):
            self._parse(payload)

    def test_missing_ticker_record_is_preserved_for_canonical_rejection(self) -> None:
        broken = self._valid_event("AAAA3")
        broken.pop("ticker")
        payload = {
            "schema_version": 1,
            "coverage_start": "2017-01-01",
            "events": [broken],
        }
        with self.assertRaisesRegex(Exception, "Ticker suplementar fora do universo: <vazio>"):
            self._parse(payload)

    def test_non_string_ticker_is_preserved_for_canonical_rejection(self) -> None:
        for malformed_ticker in (None, 123):
            with self.subTest(ticker=malformed_ticker):
                broken = self._valid_event("AAAA3")
                broken["ticker"] = malformed_ticker
                payload = {
                    "schema_version": 1,
                    "coverage_start": "2017-01-01",
                    "events": [broken],
                }
                with self.assertRaisesRegex(Exception, "Ticker suplementar fora do universo"):
                    self._parse(payload)

    def test_non_mapping_registry_record_is_preserved_for_canonical_rejection(self) -> None:
        payload = {
            "schema_version": 1,
            "coverage_start": "2017-01-01",
            "events": ["corrupt-record"],
        }
        with self.assertRaisesRegex(Exception, "Evento suplementar invalido"):
            self._parse(payload)

    def test_reloading_scope_patch_does_not_stack_or_recurse(self) -> None:
        payload = {
            "schema_version": 1,
            "coverage_start": "2017-01-01",
            "events": [self._valid_event("AAAA3"), self._valid_event("BBBB3")],
        }
        canonical = getattr(
            b3_official,
            "_supplemental_scope_patch_original_parse",
        )
        for _ in range(3):
            importlib.reload(supplemental_scope_patch)
            self.assertIs(
                getattr(b3_official, "_supplemental_scope_patch_original_parse"),
                canonical,
            )
            events = self._parse(payload)
            self.assertEqual(
                [(event.ticker, event.ex_date) for event in events],
                [("AAAA3", "2017-01-03")],
            )


if __name__ == "__main__":
    unittest.main()
