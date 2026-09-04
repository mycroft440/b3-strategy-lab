from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts import sync_point_in_time_universe_realistic as realistic


FAILED_RUN_33868398460_TICKERS = {
    "BTOW3",
    "BVMF3",
    "CCRO3",
    "CRFB3",
    "ELET3",
    "EMBR3",
    "ESTC3",
    "FIBR3",
    "GNDI3",
    "GOLL4",
    "JBSS3",
    "KROT3",
    "LAME4",
    "MRFG3",
    "NTCO3",
    "PETZ3",
    "RRRP3",
    "SMLS3",
    "VIIA3",
    "VVAR3",
}


class RealisticHistoricalReviewCoverageTests(unittest.TestCase):
    def test_realistic_addendum_covers_historical_tickers_from_failed_rebuild(self) -> None:
        path = Path("data/corporate_actions/realistic_split_evidence_addendum.json")
        payload = json.loads(path.read_text(encoding="utf-8"))

        validated = realistic._validated_ticker_reviews(payload)

        self.assertTrue(FAILED_RUN_33868398460_TICKERS <= validated.keys())
        for ticker in FAILED_RUN_33868398460_TICKERS:
            review = validated[ticker]
            self.assertIn(review["source_authority"], {"issuer", "CVM"})
            self.assertTrue(review["source_url"].startswith("https://"))
            self.assertTrue(review["review"].strip())

    def test_failed_historical_rows_are_bound_before_manifest_write(self) -> None:
        payload = realistic._load_evidence_addendum()
        captured: dict[str, object] = {}
        original_base_writer = realistic.base._write_json_atomic
        original_frozen_writer = realistic._BASE_WRITE_JSON_ATOMIC

        def capture_write(path: Path, value: object) -> None:
            captured["value"] = value

        try:
            realistic._BASE_WRITE_JSON_ATOMIC = capture_write
            realistic._install_evidence_addendum(payload)
            generated = {
                "schema_version": 3,
                "ticker_reviews": [
                    {
                        "ticker": ticker,
                        "source_authority": "historical_primary_registry",
                        "source_url": "",
                        "result": "Revisao gerada fail-closed.",
                    }
                    for ticker in sorted(FAILED_RUN_33868398460_TICKERS)
                ],
            }

            realistic.base._write_json_atomic(Path("ignored-evidence.json"), generated)
        finally:
            realistic.base._write_json_atomic = original_base_writer
            realistic._BASE_WRITE_JSON_ATOMIC = original_frozen_writer

        written = captured["value"]
        self.assertIsInstance(written, dict)
        rows = written["ticker_reviews"]
        self.assertIsInstance(rows, list)
        self.assertEqual({row["ticker"] for row in rows}, FAILED_RUN_33868398460_TICKERS)
        self.assertTrue(all(row["source_authority"] in {"issuer", "CVM"} for row in rows))
        self.assertTrue(all(row["source_url"].startswith("https://") for row in rows))


if __name__ == "__main__":
    unittest.main()
