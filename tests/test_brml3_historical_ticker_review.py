from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts import sync_point_in_time_universe_realistic as realistic


ADDENDUM = Path("data/corporate_actions/realistic_split_evidence_addendum.json")


class Brml3HistoricalTickerReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads(ADDENDUM.read_text(encoding="utf-8"))

    def test_brml3_historical_review_has_primary_issuer_binding(self) -> None:
        reviews = realistic._validated_ticker_reviews(self.payload)
        self.assertIn("BRML3", reviews)
        review = reviews["BRML3"]
        self.assertEqual(review["source_authority"], "issuer")
        self.assertTrue(review["source_url"].startswith("https://ri.allos.co/"))
        self.assertIn("BRML3", review["review"])

    def test_brml3_review_preserves_separate_event_and_marker_evidence(self) -> None:
        events = [
            row for row in self.payload.get("events", [])
            if str(row.get("ticker", "")).upper() == "BRML3"
        ]
        markers = [
            row for row in self.payload.get("marker_evidence", [])
            if str(row.get("ticker", "")).upper() == "BRML3"
        ]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["ex_date"], "2017-05-02")
        self.assertEqual(float(events[0]["split_ratio"]), 1.15)
        self.assertEqual(events[0]["source_authority"], "issuer")
        self.assertEqual(len(markers), 1)
        self.assertEqual(markers[0]["marker_date"], "2017-05-02")
        self.assertEqual(markers[0]["source_authority"], "issuer")

    def test_non_primary_review_authority_still_fails_closed(self) -> None:
        broken = {
            "ticker_reviews": [
                {
                    "ticker": "BRML3",
                    "source_authority": "secondary",
                    "source_url": "https://example.com/brml3",
                    "review": "historical BRML3 review",
                }
            ]
        }
        with self.assertRaisesRegex(Exception, "precisa ser issuer ou CVM"):
            realistic._validated_ticker_reviews(broken)


if __name__ == "__main__":
    unittest.main()
