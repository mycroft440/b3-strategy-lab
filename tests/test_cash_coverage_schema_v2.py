from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from b3_strategy_lab.realistic import cash_coverage_certification_issues


class CashCoverageSchemaV2Tests(unittest.TestCase):
    def _fixture(self, root: Path, *, timing: bool = True) -> tuple[dict[str, object], Path, Path]:
        events = root / "cash.csv"
        manifest = root / "cash.manifest.json"
        events.write_text("ticker,ex_date\nAAA3,2025-01-02\n", encoding="utf-8")
        manifest.write_text("{}\n", encoding="utf-8")
        sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        payload: dict[str, object] = {
            "schema_version": 2,
            "coverage_certified": True,
            "announcement_timing_certified": timing,
            "start": "2025-01-01",
            "end": "2025-12-31",
            "tickers": ["AAA3"],
            "source_authority": "B3",
            "reviewed_by": "independent reviewer",
            "reviewed_at_utc": "2026-09-04T12:00:00+00:00",
            "evidence": [
                {
                    "source_authority": "B3",
                    "source_url": "https://www.b3.com.br/example",
                    "scope": "cash distribution coverage",
                    "conclusion": "complete",
                }
            ],
            "announcement_timing_evidence": (
                [
                    {
                        "source_authority": "B3",
                        "source_url": "https://www.b3.com.br/example-timing",
                        "scope": "announcement availability timing",
                        "conclusion": "no future announcement information used",
                    }
                ]
                if timing
                else []
            ),
            "cash_events_sha256": sha(events),
            "cash_manifest_sha256": sha(manifest),
        }
        return payload, events, manifest

    def test_schema2_with_coverage_and_announcement_timing_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload, events, manifest = self._fixture(Path(directory))
            issues = cash_coverage_certification_issues(
                payload,
                cash_events_path=events,
                cash_manifest_path=manifest,
                tickers={"AAA3"},
                start="2025-01-01",
                end="2025-12-31",
            )
        self.assertEqual(issues, [])

    def test_schema2_without_announcement_timing_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload, events, manifest = self._fixture(Path(directory), timing=False)
            issues = cash_coverage_certification_issues(
                payload,
                cash_events_path=events,
                cash_manifest_path=manifest,
                tickers={"AAA3"},
                start="2025-01-01",
                end="2025-12-31",
            )
        self.assertIn("announcement timing is not certified", issues)
        self.assertIn("announcement timing evidence is missing", issues)

    def test_legacy_schema1_cannot_claim_current_certification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload, events, manifest = self._fixture(Path(directory))
            payload["schema_version"] = 1
            issues = cash_coverage_certification_issues(
                payload,
                cash_events_path=events,
                cash_manifest_path=manifest,
                tickers={"AAA3"},
                start="2025-01-01",
                end="2025-12-31",
            )
        self.assertIn("unsupported certification schema", issues)


if __name__ == "__main__":
    unittest.main()
