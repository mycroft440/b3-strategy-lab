from __future__ import annotations

import unittest

from scripts.walk_forward_certified import _force_certified_semantics


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


if __name__ == "__main__":
    unittest.main()
