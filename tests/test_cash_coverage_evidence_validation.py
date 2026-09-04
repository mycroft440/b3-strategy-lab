from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from b3_strategy_lab.realistic import cash_coverage_certification_issues


class CashCoverageEvidenceValidationTests(unittest.TestCase):
    def _fixture(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        events = root / "events.csv"
        manifest = root / "manifest.json"
        events.write_text("ticker,label\nAAAA3,DIVIDENDO\n", encoding="utf-8")
        manifest.write_text("{}\n", encoding="utf-8")
        payload = {
            "schema_version": 1,
            "coverage_certified": True,
            "start": "2024-01-01",
            "end": "2024-12-31",
            "tickers": ["AAAA3"],
            "source_authority": "B3",
            "reviewed_by": "reviewer",
            "reviewed_at_utc": "2025-01-01T00:00:00+00:00",
            "evidence": [
                {
                    "source_authority": "B3",
                    "source_url": "https://example.test/b3",
                    "scope": "AAAA3 2024",
                    "conclusion": "Primary-source cash coverage reviewed.",
                }
            ],
            "cash_events_sha256": hashlib.sha256(events.read_bytes()).hexdigest(),
            "cash_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        }
        return temp, events, manifest, payload

    def _issues(self, events: Path, manifest: Path, payload: dict[str, object]) -> list[str]:
        return cash_coverage_certification_issues(
            payload,
            cash_events_path=events,
            cash_manifest_path=manifest,
            tickers={"AAAA3"},
            start="2024-01-01",
            end="2024-12-31",
        )

    def test_valid_primary_evidence_preserves_existing_certificate_contract(self) -> None:
        temp, events, manifest, payload = self._fixture()
        self.addCleanup(temp.cleanup)
        self.assertEqual(self._issues(events, manifest, payload), [])

    def test_nonempty_but_empty_evidence_object_is_rejected(self) -> None:
        temp, events, manifest, payload = self._fixture()
        self.addCleanup(temp.cleanup)
        payload["evidence"] = [{}]
        issues = self._issues(events, manifest, payload)
        self.assertIn("evidence[0] source authority is not accepted", issues)
        self.assertIn("evidence[0] requires an https source_url", issues)
        self.assertIn("evidence[0] scope is missing", issues)
        self.assertIn("evidence[0] conclusion is missing", issues)
        self.assertIn("summary B3 authority is not backed by B3 evidence", issues)

    def test_non_mapping_evidence_record_is_rejected(self) -> None:
        temp, events, manifest, payload = self._fixture()
        self.addCleanup(temp.cleanup)
        payload["evidence"] = ["not-an-object"]
        self.assertIn(
            "evidence[0] must be an object",
            self._issues(events, manifest, payload),
        )

    def test_summary_authority_must_be_backed_by_matching_evidence(self) -> None:
        temp, events, manifest, payload = self._fixture()
        self.addCleanup(temp.cleanup)
        payload["evidence"] = [
            {
                "source_authority": "issuer",
                "source_url": "https://example.test/issuer",
                "scope": "AAAA3 2024",
                "conclusion": "Issuer evidence reviewed.",
            }
        ]
        self.assertIn(
            "summary B3 authority is not backed by B3 evidence",
            self._issues(events, manifest, payload),
        )

    def test_malformed_optional_source_hash_is_rejected(self) -> None:
        temp, events, manifest, payload = self._fixture()
        self.addCleanup(temp.cleanup)
        evidence = payload["evidence"]
        assert isinstance(evidence, list)
        assert isinstance(evidence[0], dict)
        evidence[0]["source_payload_sha256"] = "not-a-sha256"
        self.assertIn(
            "evidence[0] source_payload_sha256 is invalid",
            self._issues(events, manifest, payload),
        )


if __name__ == "__main__":
    unittest.main()
