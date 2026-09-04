from __future__ import annotations

import unittest

from b3_strategy_lab import b3_official


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

    def test_unrelated_valid_registry_event_is_not_treated_as_current_universe_corruption(self) -> None:
        payload = {
            "schema_version": 1,
            "coverage_start": "2017-01-01",
            "events": [self._valid_event("AAAA3"), self._valid_event("BBBB3")],
        }
        events = b3_official.parse_supplemental_split_events(
            payload,
            tickers=["AAAA3"],
            quote_dates_by_ticker={"AAAA3": ["2017-01-02", "2017-01-03"]},
            coverage_start="2017-01-01",
        )
        self.assertEqual([(event.ticker, event.ex_date) for event in events], [("AAAA3", "2017-01-03")])

    def test_in_scope_invalid_event_still_fails_closed(self) -> None:
        broken = self._valid_event("AAAA3")
        broken["source_authority"] = "secondary"
        payload = {
            "schema_version": 1,
            "coverage_start": "2017-01-01",
            "events": [broken],
        }
        with self.assertRaisesRegex(Exception, "fonte suplementar precisa ser CVM ou issuer"):
            b3_official.parse_supplemental_split_events(
                payload,
                tickers=["AAAA3"],
                quote_dates_by_ticker={"AAAA3": ["2017-01-02", "2017-01-03"]},
                coverage_start="2017-01-01",
            )

    def test_missing_ticker_record_is_preserved_for_canonical_rejection(self) -> None:
        broken = self._valid_event("AAAA3")
        broken.pop("ticker")
        payload = {
            "schema_version": 1,
            "coverage_start": "2017-01-01",
            "events": [broken],
        }
        with self.assertRaisesRegex(Exception, "Ticker suplementar fora do universo: <vazio>"):
            b3_official.parse_supplemental_split_events(
                payload,
                tickers=["AAAA3"],
                quote_dates_by_ticker={"AAAA3": ["2017-01-02", "2017-01-03"]},
                coverage_start="2017-01-01",
            )

    def test_non_mapping_registry_record_is_preserved_for_canonical_rejection(self) -> None:
        payload = {
            "schema_version": 1,
            "coverage_start": "2017-01-01",
            "events": ["corrupt-record"],
        }
        with self.assertRaisesRegex(Exception, "Evento suplementar invalido"):
            b3_official.parse_supplemental_split_events(
                payload,
                tickers=["AAAA3"],
                quote_dates_by_ticker={"AAAA3": ["2017-01-02", "2017-01-03"]},
                coverage_start="2017-01-01",
            )


if __name__ == "__main__":
    unittest.main()
