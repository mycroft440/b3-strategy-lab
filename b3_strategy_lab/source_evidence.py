from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def verify_source_documents(
    evidence_root: Path | str,
    records: Iterable[object],
) -> dict[str, object]:
    """Verify every normalized ledger reference against the actual source bytes.

    `source_document` must be a relative path below evidence_root and
    `source_sha256` must match the file bytes. The same document cannot appear with
    conflicting hashes. This keeps normalized CSV/JSON rows cryptographically bound
    to broker statements, trade notes or other original evidence without requiring
    those private files to be committed to GitHub.
    """

    root = Path(evidence_root).expanduser().resolve()
    blockers: list[str] = []
    references: dict[str, str] = {}

    if not root.exists() or not root.is_dir():
        return {
            "evidence_root": str(root),
            "verified_documents": 0,
            "blockers": ["evidence_root_missing_or_not_directory"],
            "verified": False,
        }

    for record in records:
        name = str(getattr(record, "source_document", "")).strip()
        digest = str(getattr(record, "source_sha256", "")).strip().lower()
        if not name or not digest:
            blockers.append("normalized_record_missing_source_reference")
            continue
        previous = references.get(name)
        if previous is not None and previous != digest:
            blockers.append(f"conflicting_hash_for_source_document:{name}")
            continue
        references[name] = digest

    verified = 0
    for name, expected in sorted(references.items()):
        relative = Path(name)
        if relative.is_absolute():
            blockers.append(f"absolute_source_document_path_forbidden:{name}")
            continue
        candidate = (root / relative).resolve()
        if not _inside(root, candidate):
            blockers.append(f"source_document_path_escapes_evidence_root:{name}")
            continue
        if not candidate.exists() or not candidate.is_file():
            blockers.append(f"source_document_missing:{name}")
            continue
        actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if actual != expected:
            blockers.append(f"source_document_hash_mismatch:{name}")
            continue
        verified += 1

    return {
        "evidence_root": str(root),
        "referenced_documents": len(references),
        "verified_documents": verified,
        "blockers": sorted(set(blockers)),
        "verified": not blockers and verified == len(references) and bool(references),
    }
