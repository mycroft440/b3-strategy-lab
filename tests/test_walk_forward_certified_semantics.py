from __future__ import annotations

import unittest
from types import SimpleNamespace

from scripts.research_portfolio_allocation import PortfolioConfig
from scripts.walk_forward_certified import _force_certified_semantics
from scripts.walk_forward_realistic import _metric, _rank_candidates


class CertifiedWalkForwardSemanticsTests(unittest.TestCase):
    def test_certified_semantics_force_gap_adjustment_and_continuous_account(self) -> None:
        argv = _force_certified_semantics(["--all-strategies", "--start", "2018-01-02"])
        self.assertIn("--economic-gap-adjustment", argv)
        self.assertIn("--continuous-oos-account", argv)

    def test_certified_flags_are_not_duplicated(self) -> None:
        argv = _force_certified_semantics(
            [
                "--all-strategies",
                "--economic-gap-adjustment",
                "--continuous-oos-account",
            ]
        )
        self.assertEqual(argv.count("--economic-gap-adjustment"), 1)
        self.assertEqual(argv.count("--continuous-oos-account"), 1)

    def test_exact_metric_ties_do_not_compare_portfolio_config_objects(self) -> None:
        config_z = PortfolioConfig(name="z_config")
        config_a = PortfolioConfig(name="a_config")
        summary = SimpleNamespace(cagr=0.0, total_return=0.0, sharpe=0.0)
        ranked = _rank_candidates(
            [
                (0.0, "same_strategy", config_z, summary),
                (0.0, "same_strategy", config_a, summary),
            ]
        )
        self.assertEqual(ranked[0][2].name, "a_config")
        self.assertEqual(ranked[1][2].name, "z_config")

    def test_training_objective_rejects_nonfinite_values(self) -> None:
        summary = SimpleNamespace(cagr=float("nan"), total_return=0.0, sharpe=0.0)
        with self.assertRaisesRegex(ValueError, "Non-finite training objective"):
            _metric(summary, "cagr")


if __name__ == "__main__":
    unittest.main()
