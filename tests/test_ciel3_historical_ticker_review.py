from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts import sync_point_in_time_universe_realistic as realistic
from scripts.sync_official_universe import _event_continuity_audit


ADDENDUM = Path("data/corporate_actions/realistic_split_evidence_addendum.json")


class Ciel3HistoricalTickerReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads(ADDENDUM.read_text(encoding="utf-8"))

    def test_ciel3_review_has_primary_issuer_binding(self) -> None:
        reviews = realistic._validated_ticker_reviews(self.payload)
        self.assertIn("CIEL3", reviews)
        review = reviews["CIEL3"]
        self.assertEqual(review["source_authority"], "issuer")
        self.assertEqual(
            review["source_url"],
            "https://ri.cielo.com.br/mercado-de-capitais/bonificacao/",
        )
        self.assertIn("CIEL3", review["review"])

    def test_ciel3_review_preserves_exact_documented_event_and_marker(self) -> None:
        events = [
            row for row in self.payload.get("events", [])
            if str(row.get("ticker", "")).upper() == "CIEL3"
        ]
        markers = [
            row for row in self.payload.get("marker_evidence", [])
            if str(row.get("ticker", "")).upper() == "CIEL3"
        ]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["ex_date"], "2017-04-13")
        self.assertEqual(events[0]["last_date_prior"], "2017-04-12")
        self.assertEqual(float(events[0]["split_ratio"]), 1.2)
        self.assertEqual(events[0]["source_authority"], "issuer")
        self.assertEqual(len(markers), 1)
        self.assertEqual(markers[0]["marker_date"], "2017-04-13")
        self.assertEqual(markers[0]["specification"], "ON EB NM")

    def test_ciel3_bonus_boundary_neutralizes_the_observed_nominal_price_drop(self) -> None:
        event_payload = next(
            row for row in self.payload["events"]
            if str(row.get("ticker", "")).upper() == "CIEL3"
        )
        event = SimpleNamespace(
            ticker="CIEL3",
            ex_date=str(event_payload["ex_date"]),
            split_ratio=float(event_payload["split_ratio"]),
        )
        quotes = [
            SimpleNamespace(date="2017-04-12", open=29.16, close=29.16),
            SimpleNamespace(date="2017-04-13", open=24.33, close=24.33),
            SimpleNamespace(date="2017-04-17", open=24.51, close=24.51),
            SimpleNamespace(date="2017-04-18", open=24.75, close=24.75),
        ]

        rows = _event_continuity_audit(quotes, [event])

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ex_date"], "2017-04-13")
        self.assertLess(abs(float(rows[0]["split_neutral_raw_close_return"])), 0.01)
        self.assertLess(abs(float(rows[0]["split_neutral_raw_open_gap"])), 0.01)

    def test_ciel3_non_primary_review_still_fails_closed(self) -> None:
        broken = {
            "ticker_reviews": [
                {
                    "ticker": "CIEL3",
                    "source_authority": "secondary",
                    "source_url": "https://example.com/ciel3",
                    "review": "secondary review for CIEL3",
                }
            ]
        }
        with self.assertRaisesRegex(Exception, "precisa ser issuer ou CVM"):
            realistic._validated_ticker_reviews(broken)


if __name__ == "__main__":
    unittest.main()
