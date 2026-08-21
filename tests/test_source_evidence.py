from __future__ import annotations

import hashlib
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from b3_strategy_lab.source_evidence import verify_source_documents


@dataclass(frozen=True)
class Ref:
    source_document: str
    source_sha256: str


class SourceEvidenceTests(unittest.TestCase):
    def test_matching_source_bytes_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "nota.pdf"
            source.write_bytes(b"broker-evidence")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            result = verify_source_documents(root, [Ref("nota.pdf", digest)])
            self.assertTrue(result["verified"])
            self.assertEqual(result["verified_documents"], 1)

    def test_hash_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "nota.pdf").write_bytes(b"different")
            result = verify_source_documents(root, [Ref("nota.pdf", "a" * 64)])
            self.assertFalse(result["verified"])
            self.assertIn("source_document_hash_mismatch:nota.pdf", result["blockers"])

    def test_path_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "evidence"
            root.mkdir()
            outside = Path(tmp) / "outside.pdf"
            outside.write_bytes(b"outside")
            digest = hashlib.sha256(outside.read_bytes()).hexdigest()
            result = verify_source_documents(root, [Ref("../outside.pdf", digest)])
            self.assertFalse(result["verified"])
            self.assertIn(
                "source_document_path_escapes_evidence_root:../outside.pdf",
                result["blockers"],
            )

    def test_same_document_cannot_have_conflicting_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "note.csv").write_bytes(b"source")
            result = verify_source_documents(
                root,
                [Ref("note.csv", "a" * 64), Ref("note.csv", "b" * 64)],
            )
            self.assertFalse(result["verified"])
            self.assertIn("conflicting_hash_for_source_document:note.csv", result["blockers"])


if __name__ == "__main__":
    unittest.main()
