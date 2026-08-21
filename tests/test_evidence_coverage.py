from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from b3_strategy_lab.evidence_coverage import load_and_audit_coverage


@dataclass(frozen=True)
class Ref:
    source_document: str
    source_sha256: str


class EvidenceCoverageTests(unittest.TestCase):
    def _manifest(
        self,
        path: Path,
        *,
        digest: str,
        complete: bool = True,
        start: str = "2026-01-01",
        end: str = "2026-01-31",
    ) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "coverage_start": start,
                    "coverage_end": end,
                    "coverage_complete": complete,
                    "reviewed_by": "test-reviewer",
                    "reviewed_at_utc": "2026-02-01T12:00:00+00:00",
                    "documents": [
                        {"path": "source.bin", "sha256": digest, "kind": "source"}
                    ],
                }
            ),
            encoding="utf-8",
        )

    def test_complete_coverage_with_matching_document_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.bin"
            source.write_bytes(b"evidence")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            manifest = root / "coverage.json"
            self._manifest(manifest, digest=digest)
            result = load_and_audit_coverage(
                manifest,
                evidence_root=root,
                required_start="2026-01-01",
                required_end="2026-01-31",
                normalized_records=[Ref("source.bin", digest)],
            )
            self.assertTrue(result["verified"])
            self.assertEqual(result["blockers"], [])

    def test_incomplete_coverage_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.bin"
            source.write_bytes(b"evidence")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            manifest = root / "coverage.json"
            self._manifest(manifest, digest=digest, complete=False)
            result = load_and_audit_coverage(
                manifest,
                evidence_root=root,
                required_start="2026-01-01",
                required_end="2026-01-31",
                normalized_records=[Ref("source.bin", digest)],
            )
            self.assertFalse(result["verified"])
            self.assertIn("coverage_manifest_not_certified_complete", result["blockers"])

    def test_short_manifest_period_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.bin"
            source.write_bytes(b"evidence")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            manifest = root / "coverage.json"
            self._manifest(manifest, digest=digest, start="2026-01-05", end="2026-01-20")
            result = load_and_audit_coverage(
                manifest,
                evidence_root=root,
                required_start="2026-01-01",
                required_end="2026-01-31",
                normalized_records=[Ref("source.bin", digest)],
            )
            self.assertFalse(result["verified"])
            self.assertIn("coverage_manifest_period_too_short", result["blockers"])

    def test_normalized_source_missing_from_manifest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.bin"
            source.write_bytes(b"evidence")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            manifest = root / "coverage.json"
            self._manifest(manifest, digest=digest)
            result = load_and_audit_coverage(
                manifest,
                evidence_root=root,
                required_start="2026-01-01",
                required_end="2026-01-31",
                normalized_records=[Ref("other.bin", "b" * 64)],
            )
            self.assertFalse(result["verified"])
            self.assertIn(
                "normalized_source_not_in_coverage_manifest:other.bin",
                result["blockers"],
            )


if __name__ == "__main__":
    unittest.main()
