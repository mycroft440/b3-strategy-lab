from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import sync_point_in_time_universe_realistic as realistic


class RealisticPriceOnlyCashSyncScopeTests(unittest.TestCase):
    def test_wrapper_does_not_model_or_leave_cash_distribution_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cash_output = root / "cash.csv"
            cash_manifest = root / "cash.manifest.json"
            cash_output.write_text("stale\n", encoding="utf-8")
            cash_manifest.write_text("{}\n", encoding="utf-8")
            original_builder = realistic.base.build_cash_events
            original_writer = realistic.base._write_cash

            def delegated(arguments: list[str]) -> int:
                self.assertFalse(cash_output.exists())
                self.assertFalse(cash_manifest.exists())
                self.assertEqual(realistic.base.build_cash_events([], {}, {}, {}), ([], []))
                realistic.base._write_cash(cash_output, [{"ticker": "SHOULD_NOT_EXIST"}])
                realistic.base._write_json_atomic(cash_manifest, {"complete": True})
                self.assertFalse(cash_output.exists())
                self.assertFalse(cash_manifest.exists())
                return 0

            with (
                patch.object(realistic, "_load_evidence_addendum", return_value={}),
                patch.object(realistic, "_install_evidence_addendum", wraps=realistic._install_evidence_addendum),
                patch.object(realistic.base, "main", side_effect=delegated),
            ):
                self.assertEqual(
                    realistic.main([
                        "--cash-output", str(cash_output),
                        "--cash-manifest", str(cash_manifest),
                    ]),
                    0,
                )

            self.assertIs(realistic.base.build_cash_events, original_builder)
            self.assertIs(realistic.base._write_cash, original_writer)
            self.assertFalse(cash_output.exists())
            self.assertFalse(cash_manifest.exists())

    def test_cash_supplement_is_rejected_in_price_only_mode(self) -> None:
        with self.assertRaisesRegex(ValueError, "out of scope"):
            realistic.main(["--cash-supplement", "forbidden.json"])


if __name__ == "__main__":
    unittest.main()
