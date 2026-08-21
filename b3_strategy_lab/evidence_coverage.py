from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path


def load_and_audit_coverage(
    manifest_path: Path | str,
    *,
    evidence_root: Path | str,
    required_start: str,
    required_end: str,
    normalized_records: list[object],
) -> dict[str, object]:
    """Audit a local manifest that asserts complete source-document coverage."""
    payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    blockers: list[str] = []
    if payload.get("schema_version") != 1:
        blockers.append("coverage_manifest_schema_invalid")
    if payload.get("coverage_complete") is not True:
        blockers.append("coverage_manifest_not_certified_complete")

    try:
        manifest_start = date.fromisoformat(str(payload.get("coverage_start", ""))[:10])
        manifest_end = date.fromisoformat(str(payload.get("coverage_end", ""))[:10])
        if manifest_start > date.fromisoformat(required_start) or manifest_end < date.fromisoformat(required_end):
            blockers.append("coverage_manifest_period_too_short")
    except ValueError:
        blockers.append("coverage_manifest_dates_invalid")

    if not str(payload.get("reviewed_by", "")).strip():
        blockers.append("coverage_manifest_reviewer_missing")
    try:
        reviewed = datetime.fromisoformat(str(payload.get("reviewed_at_utc", "")).replace("Z", "+00:00"))
        if reviewed.tzinfo is None:
            raise ValueError
    except ValueError:
        blockers.append("coverage_manifest_review_timestamp_invalid")

    raw_documents = payload.get("documents")
    documents: dict[str, str] = {}
    if not isinstance(raw_documents, list) or not raw_documents:
        blockers.append("coverage_manifest_documents_missing")
        raw_documents = []
    for item in raw_documents:
        name = str(item.get("path", "")).strip()
        digest = str(item.get("sha256", "")).strip().lower()
        if not name or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            blockers.append(f"coverage_manifest_document_invalid:{name or '<missing>'}")
            continue
        if name in documents and documents[name] != digest:
            blockers.append(f"coverage_manifest_document_hash_conflict:{name}")
        documents[name] = digest

    root = Path(evidence_root).expanduser().resolve()
    verified = 0
    if not root.is_dir():
        blockers.append("evidence_root_missing_or_not_directory")
    else:
        for name, expected in documents.items():
            relative = Path(name)
            candidate = (root / relative).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                blockers.append(f"source_document_path_escapes_evidence_root:{name}")
                continue
            if relative.is_absolute() or not candidate.is_file():
                blockers.append(f"source_document_missing_or_invalid:{name}")
                continue
            if hashlib.sha256(candidate.read_bytes()).hexdigest() != expected:
                blockers.append(f"source_document_hash_mismatch:{name}")
                continue
            verified += 1

    for record in normalized_records:
        name = str(getattr(record, "source_document", "")).strip()
        digest = str(getattr(record, "source_sha256", "")).strip().lower()
        expected = documents.get(name)
        if expected is None:
            blockers.append(f"normalized_source_not_in_coverage_manifest:{name}")
        elif expected != digest:
            blockers.append(f"normalized_source_hash_differs_from_coverage_manifest:{name}")

    return {
        "coverage_start": payload.get("coverage_start"),
        "coverage_end": payload.get("coverage_end"),
        "coverage_complete": payload.get("coverage_complete") is True,
        "declared_documents": len(documents),
        "verified_documents": verified,
        "blockers": sorted(set(blockers)),
        "verified": not blockers and bool(documents) and verified == len(documents),
    }
