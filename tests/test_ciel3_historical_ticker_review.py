from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts import sync_point_in_time_universe_realistic as realistic


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
        self.assertEqual(events[0]["ex_date"], "2017-04-18")
        self.assertEqual(events[0]["last_date_prior"], "2017-04-17")
        self.assertEqual(float(events[0]["split_ratio"]), 1.2)
        self.assertEqual(events[0]["source_authority"], "issuer")
        self.assertEqual(len(markers), 1)
        self.assertEqual(markers[0]["marker_date"], "2017-04-13")
        self.assertEqual(markers[0]["specification"], "ON EB NM")

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
