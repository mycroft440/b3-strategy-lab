from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts import sync_point_in_time_universe_realistic as realistic


ADDENDUM = Path("data/corporate_actions/realistic_split_evidence_addendum.json")


class Brdt3HistoricalTickerReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads(ADDENDUM.read_text(encoding="utf-8"))

    def test_brdt3_historical_review_has_primary_issuer_binding(self) -> None:
        reviews = realistic._validated_ticker_reviews(self.payload)
        self.assertIn("BRDT3", reviews)
        review = reviews["BRDT3"]
        self.assertEqual(review["source_authority"], "issuer")
        self.assertTrue(review["source_url"].startswith("https://ri.vibraenergia.com.br/"))
        self.assertIn("BRDT3", review["review"])
        self.assertIn("VBBR3", review["review"])

    def test_brdt3_review_does_not_invent_economic_split_or_marker(self) -> None:
        brdt_events = [
            row for row in self.payload.get("events", [])
            if str(row.get("ticker", "")).upper() == "BRDT3"
        ]
        brdt_markers = [
            row for row in self.payload.get("marker_evidence", [])
            if str(row.get("ticker", "")).upper() == "BRDT3"
        ]
        self.assertEqual(brdt_events, [])
        self.assertEqual(brdt_markers, [])

    def test_non_primary_authority_still_fails_closed(self) -> None:
        broken = {
            "ticker_reviews": [
                {
                    "ticker": "BRDT3",
                    "source_authority": "secondary",
                    "source_url": "https://example.com/brdt3",
                    "review": "historical ticker BRDT3 to VBBR3",
                }
            ]
        }
        with self.assertRaisesRegex(Exception, "precisa ser issuer ou CVM"):
            realistic._validated_ticker_reviews(broken)


if __name__ == "__main__":
    unittest.main()
