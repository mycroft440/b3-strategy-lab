from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from b3_strategy_lab.b3_official import B3CorporateActionError
from scripts import sync_point_in_time_universe as base
from scripts import sync_point_in_time_universe_realistic as realistic


class HistoricalTickerReviewAddendumTests(unittest.TestCase):
    def tearDown(self) -> None:
        base.parse_supplemental_split_events = realistic._BASE_PARSE_SUPPLEMENTAL_SPLITS
        base.audit_share_count_markers = realistic._BASE_AUDIT_SHARE_MARKERS
        base._write_json_atomic = realistic._BASE_WRITE_JSON_ATOMIC

    def test_arzz3_has_primary_historical_review_without_invented_split(self) -> None:
        payload = realistic._load_evidence_addendum()
        reviews = realistic._validated_ticker_reviews(payload)
        self.assertIn("ARZZ3", reviews)
        self.assertEqual(reviews["ARZZ3"]["source_authority"], "issuer")
        self.assertTrue(reviews["ARZZ3"]["source_url"].startswith("https://"))
        self.assertFalse(
            any(
                str(event.get("ticker", "")).strip().upper() == "ARZZ3"
                for event in payload.get("events", [])
            )
        )
        self.assertFalse(
            any(
                str(marker.get("ticker", "")).strip().upper() == "ARZZ3"
                for marker in payload.get("marker_evidence", [])
            )
        )

    def test_generated_historical_review_is_bound_before_manifest_verification(self) -> None:
        addendum = {
            "schema_version": 1,
            "coverage_start": "2017-01-01",
            "events": [],
            "marker_evidence": [],
            "ticker_reviews": [
                {
                    "ticker": "ARZZ3",
                    "source_authority": "issuer",
                    "source_url": "https://ri.azzas2154.com.br/informacoes-aos-investidores/perguntas-frequentes/",
                    "review": "Historical ARZZ3 issuer identity review.",
                }
            ],
        }
        realistic._install_evidence_addendum(addendum)
        generated = {
            "schema_version": 3,
            "coverage_start": "2017-01-01",
            "ticker_reviews": [
                {
                    "ticker": "ARZZ3",
                    "issuing_company": "AREZZO",
                    "source_authority": "historical_primary_registry",
                    "source_url": None,
                    "result": "0 evento(s) de quantidade desde 2017-01-01.",
                }
            ],
            "events": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            base._write_json_atomic(path, generated)
            saved = json.loads(path.read_text(encoding="utf-8"))
        review = saved["ticker_reviews"][0]
        self.assertEqual(review["source_authority"], "issuer")
        self.assertEqual(
            review["source_url"],
            "https://ri.azzas2154.com.br/informacoes-aos-investidores/perguntas-frequentes/",
        )
        self.assertIn("Revisao primaria historica", review["result"])
        self.assertEqual(saved["events"], [])

    def test_non_primary_review_authority_remains_fail_closed(self) -> None:
        payload = {
            "ticker_reviews": [
                {
                    "ticker": "ARZZ3",
                    "source_authority": "historical_primary_registry",
                    "source_url": "https://example.com/review",
                    "review": "not an accepted primary authority",
                }
            ]
        }
        with self.assertRaises(B3CorporateActionError):
            realistic._validated_ticker_reviews(payload)


if __name__ == "__main__":
    unittest.main()
