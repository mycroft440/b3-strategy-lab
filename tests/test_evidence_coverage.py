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
    def _normalized_inputs(self, root: Path) -> tuple[dict[str, Path], list[dict[str, str]]]:
        supplied: dict[str, Path] = {}
        declared: list[dict[str, str]] = []
        for role in ("fills", "cash_events", "opening_snapshot", "closing_snapshot"):
            path = root / f"{role}.dat"
            path.write_bytes(f"normalized-{role}".encode())
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            supplied[role] = path
            declared.append({"role": role, "sha256": digest})
        return supplied, declared

    def _manifest(
        self,
        path: Path,
        *,
        source_digest: str,
        normalized: list[dict[str, str]],
        complete: bool = True,
        start: str = "2026-01-01",
        end: str = "2026-01-31",
        statement_start: str = "2026-01-01",
        statement_end: str = "2026-01-31",
        reviewed_at: str = "2026-02-01T12:00:00+00:00",
        normalization_reviewed_at: str = "2026-02-01T12:00:00+00:00",
    ) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "coverage_start": start,
                    "coverage_end": end,
                    "coverage_complete": complete,
                    "reviewed_by": "test-reviewer",
                    "reviewed_at_utc": reviewed_at,
                    "normalization_verified": True,
                    "normalization_reviewed_by": "test-normalizer-reviewer",
                    "normalization_reviewed_at_utc": normalization_reviewed_at,
                    "normalization_attestation": "Every normalized value was checked against the referenced source bytes.",
                    "documents": [
                        {
                            "path": "source.bin",
                            "sha256": source_digest,
                            "kind": "account_statement",
                            "coverage_start": statement_start,
                            "coverage_end": statement_end,
                        }
                    ],
                    "normalized_inputs": normalized,
                }
            ),
            encoding="utf-8",
        )

    def test_complete_coverage_with_reviewed_normalized_inputs_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.bin"
            source.write_bytes(b"evidence")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            normalized_inputs, normalized_manifest = self._normalized_inputs(root)
            manifest = root / "coverage.json"
            self._manifest(
                manifest,
                source_digest=digest,
                normalized=normalized_manifest,
            )
            result = load_and_audit_coverage(
                manifest,
                evidence_root=root,
                required_start="2026-01-01",
                required_end="2026-01-31",
                normalized_records=[Ref("source.bin", digest)],
                normalized_inputs=normalized_inputs,
            )
            self.assertTrue(result["verified"])
            self.assertTrue(result["continuous_account_statement_coverage"])
            self.assertEqual(result["blockers"], [])

    def test_incomplete_coverage_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.bin"
            source.write_bytes(b"evidence")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            normalized_inputs, normalized_manifest = self._normalized_inputs(root)
            manifest = root / "coverage.json"
            self._manifest(
                manifest,
                source_digest=digest,
                normalized=normalized_manifest,
                complete=False,
            )
            result = load_and_audit_coverage(
                manifest,
                evidence_root=root,
                required_start="2026-01-01",
                required_end="2026-01-31",
                normalized_records=[Ref("source.bin", digest)],
                normalized_inputs=normalized_inputs,
            )
            self.assertFalse(result["verified"])
            self.assertIn("coverage_manifest_not_certified_complete", result["blockers"])

    def test_short_manifest_period_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.bin"
            source.write_bytes(b"evidence")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            normalized_inputs, normalized_manifest = self._normalized_inputs(root)
            manifest = root / "coverage.json"
            self._manifest(
                manifest,
                source_digest=digest,
                normalized=normalized_manifest,
                start="2026-01-05",
                end="2026-01-20",
            )
            result = load_and_audit_coverage(
                manifest,
                evidence_root=root,
                required_start="2026-01-01",
                required_end="2026-01-31",
                normalized_records=[Ref("source.bin", digest)],
                normalized_inputs=normalized_inputs,
            )
            self.assertFalse(result["verified"])
            self.assertIn("coverage_manifest_period_too_short", result["blockers"])

    def test_statement_gap_is_rejected_even_if_manifest_claims_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.bin"
            source.write_bytes(b"evidence")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            normalized_inputs, normalized_manifest = self._normalized_inputs(root)
            manifest = root / "coverage.json"
            self._manifest(
                manifest,
                source_digest=digest,
                normalized=normalized_manifest,
                statement_start="2026-01-05",
                statement_end="2026-01-31",
            )
            result = load_and_audit_coverage(
                manifest,
                evidence_root=root,
                required_start="2026-01-01",
                required_end="2026-01-31",
                normalized_records=[Ref("source.bin", digest)],
                normalized_inputs=normalized_inputs,
            )
            self.assertFalse(result["verified"])
            self.assertIn("continuous_account_statement_coverage_missing", result["blockers"])

    def test_normalized_source_missing_from_manifest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.bin"
            source.write_bytes(b"evidence")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            normalized_inputs, normalized_manifest = self._normalized_inputs(root)
            manifest = root / "coverage.json"
            self._manifest(
                manifest,
                source_digest=digest,
                normalized=normalized_manifest,
            )
            result = load_and_audit_coverage(
                manifest,
                evidence_root=root,
                required_start="2026-01-01",
                required_end="2026-01-31",
                normalized_records=[Ref("other.bin", "b" * 64)],
                normalized_inputs=normalized_inputs,
            )
            self.assertFalse(result["verified"])
            self.assertIn(
                "normalized_source_not_in_coverage_manifest:other.bin",
                result["blockers"],
            )

    def test_normalized_file_mutation_after_review_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.bin"
            source.write_bytes(b"evidence")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            normalized_inputs, normalized_manifest = self._normalized_inputs(root)
            manifest = root / "coverage.json"
            self._manifest(
                manifest,
                source_digest=digest,
                normalized=normalized_manifest,
            )
            normalized_inputs["fills"].write_bytes(b"changed-after-review")
            result = load_and_audit_coverage(
                manifest,
                evidence_root=root,
                required_start="2026-01-01",
                required_end="2026-01-31",
                normalized_records=[Ref("source.bin", digest)],
                normalized_inputs=normalized_inputs,
            )
            self.assertFalse(result["verified"])
            self.assertIn("normalized_input_hash_mismatch:fills", result["blockers"])

    def test_review_cannot_predate_period_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.bin"
            source.write_bytes(b"evidence")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            normalized_inputs, normalized_manifest = self._normalized_inputs(root)
            manifest = root / "coverage.json"
            self._manifest(
                manifest,
                source_digest=digest,
                normalized=normalized_manifest,
                reviewed_at="2026-01-15T12:00:00+00:00",
                normalization_reviewed_at="2026-01-15T12:00:00+00:00",
            )
            result = load_and_audit_coverage(
                manifest,
                evidence_root=root,
                required_start="2026-01-01",
                required_end="2026-01-31",
                normalized_records=[Ref("source.bin", digest)],
                normalized_inputs=normalized_inputs,
            )
            self.assertFalse(result["verified"])
            self.assertIn("coverage_manifest_review_predates_required_period_end", result["blockers"])
            self.assertIn("normalization_review_predates_required_period_end", result["blockers"])


if __name__ == "__main__":
    unittest.main()
