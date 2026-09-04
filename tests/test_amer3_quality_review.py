from __future__ import annotations

import json
import unittest
from pathlib import Path


QUALITY_REVIEWS = Path("data/quality_reviews.json")
WARNING_2023 = "AMER3 2023-01-12: variacao de fechamento sem split de -77.33%."
WARNING_2024 = "AMER3 2024-08-15: variacao de fechamento sem split de -57.58%."
COTAHIST_2023_SHA256 = (
    "ad1603788d78aaa1de806498572277f1d9443f88ae116452751b5800cb23523e"
)


class Amer3QualityReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads(QUALITY_REVIEWS.read_text(encoding="utf-8"))

    def test_exact_fail_closed_warnings_have_explicit_reviews(self) -> None:
        reviews = self.payload["warning_reviews"]
        self.assertIn(WARNING_2023, reviews)
        self.assertIn(WARNING_2024, reviews)

    def test_2023_review_is_bound_to_official_cotahist_and_raw_prices(self) -> None:
        evidence = self.payload["warning_reviews"][WARNING_2023]
        self.assertIn("COTAHIST_A2023.ZIP", evidence)
        self.assertIn(COTAHIST_2023_SHA256, evidence)
        self.assertIn("R$ 12.00", evidence)
        self.assertIn("R$ 2.72", evidence)

    def test_2024_review_is_bound_to_official_cotahist_and_raw_prices(self) -> None:
        evidence = self.payload["warning_reviews"][WARNING_2024]
        self.assertIn("COTAHIST_A2024", evidence)
        self.assertIn("R$ 0.33", evidence)
        self.assertIn("R$ 0.14", evidence)
        self.assertIn("57.58%", evidence)

    def test_reviews_do_not_reclassify_market_crashes_as_split_or_synthetic_repair(self) -> None:
        reviews = self.payload["warning_reviews"]
        for warning in (WARNING_2023, WARNING_2024):
            with self.subTest(warning=warning):
                evidence = reviews[warning]
                self.assertIn("sem reparo sintetico", evidence)
                self.assertIn("sem reclassificacao como split", evidence)


if __name__ == "__main__":
    unittest.main()
