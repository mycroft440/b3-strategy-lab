from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts import sync_point_in_time_universe_realistic as realistic


ADDENDUM = Path("data/corporate_actions/realistic_split_evidence_addendum.json")


class Brfs3PrimaryReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads(ADDENDUM.read_text(encoding="utf-8"))

    def test_brfs3_review_has_primary_issuer_binding(self) -> None:
        reviews = realistic._validated_ticker_reviews(self.payload)
        self.assertIn("BRFS3", reviews)
        review = reviews["BRFS3"]
        self.assertEqual(review["source_authority"], "issuer")
        self.assertTrue(
            review["source_url"].startswith(
                "https://ri.brf-global.com/governanca-corporativa/visao-geral/"
            )
        )
        self.assertIn("BRFS3", review["review"])

    def test_brfs3_review_does_not_invent_economic_event_or_marker(self) -> None:
        brfs_events = [
            row
            for row in self.payload.get("events", [])
            if str(row.get("ticker", "")).upper() == "BRFS3"
        ]
        brfs_markers = [
            row
            for row in self.payload.get("marker_evidence", [])
            if str(row.get("ticker", "")).upper() == "BRFS3"
        ]
        self.assertEqual(brfs_events, [])
        self.assertEqual(brfs_markers, [])

    def test_brfs3_non_primary_authority_still_fails_closed(self) -> None:
        broken = {
            "ticker_reviews": [
                {
                    "ticker": "BRFS3",
                    "source_authority": "secondary",
                    "source_url": "https://example.com/brfs3",
                    "review": "secondary review for BRFS3",
                }
            ]
        }
        with self.assertRaisesRegex(Exception, "precisa ser issuer ou CVM"):
            realistic._validated_ticker_reviews(broken)


if __name__ == "__main__":
    unittest.main()
