from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import sync_point_in_time_universe_realistic as realistic


class HistoricalReviewCoveragePreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_parse = realistic.base.parse_supplemental_split_events
        self.original_audit = realistic.base.audit_share_count_markers
        self.original_write = realistic.base._write_json_atomic

    def tearDown(self) -> None:
        realistic.base.parse_supplemental_split_events = self.original_parse
        realistic.base.audit_share_count_markers = self.original_audit
        realistic.base._write_json_atomic = self.original_write

    def test_helper_returns_all_unresolved_historical_tickers_sorted(self) -> None:
        rows = [
            {"ticker": "ZZZZ3", "source_authority": "historical_primary_registry", "source_url": None},
            {"ticker": "AAAA3", "source_authority": "historical_primary_registry", "source_url": ""},
            {"ticker": "LIVE3", "source_authority": "B3", "source_url": "https://www.b3.com.br/live3"},
        ]
        self.assertEqual(
            realistic._unresolved_historical_review_tickers(rows),
            ("AAAA3", "ZZZZ3"),
        )

    def test_preflight_lists_every_gap_and_does_not_write_unsigned_evidence(self) -> None:
        addendum = {
            "schema_version": 1,
            "events": [],
            "marker_evidence": [],
            "ticker_reviews": [
                {
                    "ticker": "COVER3",
                    "source_authority": "issuer",
                    "source_url": "https://ri.example.com/cover3",
                    "review": "primary issuer review for COVER3",
                }
            ],
        }
        evidence = {
            "schema_version": 3,
            "ticker_reviews": [
                {"ticker": "MISS4", "source_authority": "historical_primary_registry", "source_url": None, "result": "historical"},
                {"ticker": "COVER3", "source_authority": "historical_primary_registry", "source_url": None, "result": "historical"},
                {"ticker": "MISS3", "source_authority": "historical_primary_registry", "source_url": None, "result": "historical"},
            ],
        }
        with patch.object(realistic, "_BASE_WRITE_JSON_ATOMIC") as writer:
            realistic._install_evidence_addendum(addendum)
            with self.assertRaisesRegex(
                realistic.HistoricalTickerReviewCoverageError,
                r"MISS3, MISS4.*nenhum manifest foi assinado",
            ):
                realistic.base._write_json_atomic(Path("unused.json"), evidence)
            writer.assert_not_called()

    def test_complete_primary_binding_still_writes_schema_three_evidence(self) -> None:
        addendum = {
            "schema_version": 1,
            "events": [],
            "marker_evidence": [],
            "ticker_reviews": [
                {
                    "ticker": "COVER3",
                    "source_authority": "issuer",
                    "source_url": "https://ri.example.com/cover3",
                    "review": "primary issuer review for COVER3",
                }
            ],
        }
        evidence = {
            "schema_version": 3,
            "ticker_reviews": [
                {"ticker": "COVER3", "source_authority": "historical_primary_registry", "source_url": None, "result": "historical"},
            ],
        }
        with patch.object(realistic, "_BASE_WRITE_JSON_ATOMIC") as writer:
            realistic._install_evidence_addendum(addendum)
            realistic.base._write_json_atomic(Path("unused.json"), evidence)
            writer.assert_called_once()
            written = writer.call_args.args[1]
            review = written["ticker_reviews"][0]
            self.assertEqual(review["source_authority"], "issuer")
            self.assertEqual(review["source_url"], "https://ri.example.com/cover3")


if __name__ == "__main__":
    unittest.main()
