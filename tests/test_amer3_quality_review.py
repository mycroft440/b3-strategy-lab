from __future__ import annotations

import json
import unittest
from pathlib import Path


QUALITY_REVIEWS = Path("data/quality_reviews.json")
WARNING_2023 = "AMER3 2023-01-12: variacao de fechamento sem split de -77.33%."
WARNING_2024_CRASH = "AMER3 2024-08-15: variacao de fechamento sem split de -57.58%."
WARNING_2024_GROUPING = (
    "AMER3 2024-08-27: variacao de fechamento apos normalizacao de split de 40.00%."
)
COTAHIST_2023_SHA256 = (
    "ad1603788d78aaa1de806498572277f1d9443f88ae116452751b5800cb23523e"
)


class Amer3QualityReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads(QUALITY_REVIEWS.read_text(encoding="utf-8"))

    def test_exact_fail_closed_warnings_have_explicit_reviews(self) -> None:
        reviews = self.payload["warning_reviews"]
        self.assertIn(WARNING_2023, reviews)
        self.assertIn(WARNING_2024_CRASH, reviews)
        self.assertIn(WARNING_2024_GROUPING, reviews)

    def test_2023_review_is_bound_to_official_cotahist_and_raw_prices(self) -> None:
        evidence = self.payload["warning_reviews"][WARNING_2023]
        self.assertIn("COTAHIST_A2023.ZIP", evidence)
        self.assertIn(COTAHIST_2023_SHA256, evidence)
        self.assertIn("R$ 12.00", evidence)
        self.assertIn("R$ 2.72", evidence)

    def test_2024_crash_review_is_bound_to_official_cotahist_and_raw_prices(self) -> None:
        evidence = self.payload["warning_reviews"][WARNING_2024_CRASH]
        self.assertIn("COTAHIST_A2024", evidence)
        self.assertIn("R$ 0.33", evidence)
        self.assertIn("R$ 0.14", evidence)
        self.assertIn("57.58%", evidence)

    def test_2024_grouping_review_preserves_certified_adjustment_and_residual_move(self) -> None:
        evidence = self.payload["warning_reviews"][WARNING_2024_GROUPING]
        self.assertIn("COTAHIST_A2024", evidence)
        self.assertIn("100:1", evidence)
        self.assertIn("R$ 0.05", evidence)
        self.assertIn("R$ 5.00", evidence)
        self.assertIn("R$ 7.00", evidence)
        self.assertIn("40.00%", evidence)
        self.assertIn("sem alterar a razao de grupamento", evidence)
        self.assertIn("sem suprimir a variacao economica residual", evidence)

    def test_reviews_do_not_replace_official_market_observations_with_synthetic_repairs(self) -> None:
        reviews = self.payload["warning_reviews"]
        for warning in (WARNING_2023, WARNING_2024_CRASH, WARNING_2024_GROUPING):
            with self.subTest(warning=warning):
                self.assertIn("sem reparo sintetico", reviews[warning])

    def test_non_grouping_crashes_are_not_reclassified_as_splits(self) -> None:
        reviews = self.payload["warning_reviews"]
        for warning in (WARNING_2023, WARNING_2024_CRASH):
            with self.subTest(warning=warning):
                self.assertIn("sem reclassificacao como split", reviews[warning])


if __name__ == "__main__":
    unittest.main()
