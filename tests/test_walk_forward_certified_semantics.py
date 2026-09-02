from __future__ import annotations

import unittest

from scripts.walk_forward_certified import _force_certified_semantics


class CertifiedWalkForwardSemanticsTests(unittest.TestCase):
    def test_economic_gap_adjustment_is_forced(self) -> None:
        argv = _force_certified_semantics(["--all-strategies", "--start", "2018-01-02"])
        self.assertIn("--economic-gap-adjustment", argv)

    def test_economic_gap_adjustment_is_not_duplicated(self) -> None:
        argv = _force_certified_semantics(
            ["--all-strategies", "--economic-gap-adjustment"]
        )
        self.assertEqual(argv.count("--economic-gap-adjustment"), 1)


if __name__ == "__main__":
    unittest.main()
