from __future__ import annotations

import unittest

from b3_strategy_lab.statistical_validation import (
    exact_positive_fold_sign_pvalue,
    oos_evidence_summary,
)


class StatisticalValidationTests(unittest.TestCase):
    def test_exact_sign_test_all_five_positive(self) -> None:
        self.assertAlmostEqual(exact_positive_fold_sign_pvalue(5, 5), 1.0 / 32.0)

    def test_exact_sign_test_four_of_five_positive(self) -> None:
        self.assertAlmostEqual(exact_positive_fold_sign_pvalue(4, 5), 6.0 / 32.0)

    def test_zero_folds_has_no_evidence(self) -> None:
        self.assertEqual(exact_positive_fold_sign_pvalue(0, 0), 1.0)

    def test_invalid_counts_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            exact_positive_fold_sign_pvalue(6, 5)
        with self.assertRaises(ValueError):
            exact_positive_fold_sign_pvalue(-1, 5)
        with self.assertRaises(ValueError):
            exact_positive_fold_sign_pvalue(0, -1)

    def test_oos_summary_passes_only_with_sample_and_alpha(self) -> None:
        strong = oos_evidence_summary(positive_folds=5, folds=5)
        self.assertTrue(strong["oos_sign_test_sufficient_sample"])
        self.assertTrue(strong["oos_sign_test_passed"])
        self.assertAlmostEqual(float(strong["oos_sign_test_p_value"]), 1.0 / 32.0)

        too_short = oos_evidence_summary(positive_folds=4, folds=4)
        self.assertFalse(too_short["oos_sign_test_sufficient_sample"])
        self.assertFalse(too_short["oos_sign_test_passed"])

    def test_invalid_summary_configuration_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            oos_evidence_summary(positive_folds=1, folds=1, alpha=0.0)
        with self.assertRaises(ValueError):
            oos_evidence_summary(positive_folds=1, folds=1, minimum_folds=0)


if __name__ == "__main__":
    unittest.main()
