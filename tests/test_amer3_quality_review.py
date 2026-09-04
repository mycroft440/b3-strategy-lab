from __future__ import annotations

import json
import unittest
from pathlib import Path


QUALITY_REVIEWS = Path("data/quality_reviews.json")
WARNING = "AMER3 2023-01-12: variacao de fechamento sem split de -77.33%."
COTAHIST_2023_SHA256 = (
    "ad1603788d78aaa1de806498572277f1d9443f88ae116452751b5800cb23523e"
)


class Amer3QualityReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads(QUALITY_REVIEWS.read_text(encoding="utf-8"))

    def test_exact_fail_closed_warning_has_explicit_review(self) -> None:
        reviews = self.payload["warning_reviews"]
        self.assertIn(WARNING, reviews)

    def test_review_is_bound_to_official_2023_cotahist_and_raw_prices(self) -> None:
        evidence = self.payload["warning_reviews"][WARNING]
        self.assertIn("COTAHIST_A2023.ZIP", evidence)
        self.assertIn(COTAHIST_2023_SHA256, evidence)
        self.assertIn("R$ 12.00", evidence)
        self.assertIn("R$ 2.72", evidence)

    def test_review_does_not_reclassify_market_crash_as_split_or_synthetic_repair(self) -> None:
        evidence = self.payload["warning_reviews"][WARNING]
        self.assertIn("sem reparo sintetico", evidence)
        self.assertIn("sem reclassificacao como split", evidence)


if __name__ == "__main__":
    unittest.main()
