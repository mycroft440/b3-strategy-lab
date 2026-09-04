from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from b3_strategy_lab.realistic import cash_coverage_certification_issues


class CashAnnouncementTimingCertificationTests(unittest.TestCase):
    def _paths(self, root: Path) -> tuple[Path, Path]:
        events = root / "events.csv"
        manifest = root / "manifest.json"
        events.write_text("ticker,amount\nAAA3,1.00\n", encoding="utf-8")
        manifest.write_text('{"complete": true}\n', encoding="utf-8")
        return events, manifest

    def _base(self, events: Path, manifest: Path) -> dict[str, object]:
        return {
            "schema_version": 1,
            "coverage_certified": True,
            "start": "2018-01-01",
            "end": "2024-12-31",
            "source_authority": "B3",
            "reviewed_by": "Independent reviewer",
            "reviewed_at_utc": "2025-01-02T12:00:00+00:00",
            "evidence": [
                {
                    "source_authority": "B3",
                    "source_url": "https://example.test/b3",
                    "scope": "AAA3 2018-2024",
                    "conclusion": "Cash-event coverage reconciled.",
                }
            ],
            "tickers": ["AAA3"],
            "cash_events_sha256": hashlib.sha256(events.read_bytes()).hexdigest(),
            "cash_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        }

    def test_schema_one_remains_readable_but_cannot_certify_causal_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            events, manifest = self._paths(Path(directory))
            certification = self._base(events, manifest)
            common = dict(
                cash_events_path=events,
                cash_manifest_path=manifest,
                tickers={"AAA3"},
                start="2018-01-02",
                end="2024-12-30",
            )
            self.assertEqual(cash_coverage_certification_issues(certification, **common), [])
            issues = cash_coverage_certification_issues(
                certification,
                require_announcement_timing=True,
                **common,
            )
            self.assertIn(
                "certified causal replay requires cash certification schema 2",
                issues,
            )
            self.assertIn("announcement timing is not certified", issues)
            self.assertIn("announcement timing evidence is missing", issues)

    def test_schema_two_with_primary_timing_evidence_passes_causal_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            events, manifest = self._paths(Path(directory))
            certification = self._base(events, manifest)
            certification.update(
                {
                    "schema_version": 2,
                    "announcement_timing_certified": True,
                    "announcement_timing_evidence": [
                        {
                            "source_authority": "B3",
                            "source_url": "https://example.test/b3/announcement",
                            "scope": "AAA3 event announcement timing",
                            "conclusion": "Publication timestamp precedes the decision session.",
                        }
                    ],
                }
            )
            self.assertEqual(
                cash_coverage_certification_issues(
                    certification,
                    cash_events_path=events,
                    cash_manifest_path=manifest,
                    tickers={"AAA3"},
                    start="2018-01-02",
                    end="2024-12-30",
                    require_announcement_timing=True,
                ),
                [],
            )


class PointInTimeAuditModeContractTests(unittest.TestCase):
    def test_audit_mode_is_explicit_and_production_audit_requires_timing(self) -> None:
        sync_source = Path("scripts/sync_point_in_time_universe.py").read_text(encoding="utf-8")
        input_audit = Path("scripts/audit_realistic_backtest_inputs.py").read_text(encoding="utf-8")
        generator = Path("scripts/build_cash_distribution_coverage_certification.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"--audit-all-errors"', sync_source)
        self.assertIn("if not args.audit_all_errors:\n                    raise", sync_source)
        self.assertIn('"mode": "audit_only_no_publication"', sync_source)
        self.assertIn("require_announcement_timing=True", input_audit)
        self.assertIn('"schema_version": 2', generator)
        self.assertIn('"--confirm-announcement-timing"', generator)


if __name__ == "__main__":
    unittest.main()
