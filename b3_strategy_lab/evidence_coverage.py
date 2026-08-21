from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


ALLOWED_DOCUMENT_KINDS = {
    "account_statement",
    "trade_note",
    "corporate_action_notice",
    "tax_document",
    "other_source",
}
MANDATORY_NORMALIZED_ROLES = {
    "fills",
    "cash_events",
    "opening_snapshot",
    "closing_snapshot",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_review_timestamp(value: object, blocker: str, blockers: list[str]) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.astimezone(timezone.utc)
    except ValueError:
        blockers.append(blocker)
        return None


def _continuous_statement_coverage(
    intervals: list[tuple[date, date]],
    required_start: date,
    required_end: date,
) -> bool:
    if not intervals:
        return False
    cursor = required_start
    for start, end in sorted(intervals):
        if end < cursor:
            continue
        if start > cursor:
            return False
        cursor = max(cursor, end + timedelta(days=1))
        if cursor > required_end:
            return True
    return cursor > required_end


def load_and_audit_coverage(
    manifest_path: Path | str,
    *,
    evidence_root: Path | str,
    required_start: str,
    required_end: str,
    normalized_records: list[object],
    normalized_inputs: dict[str, Path | str],
    source_kind_requirements: dict[str, set[str]] | None = None,
) -> dict[str, object]:
    """Audit documentary completeness and reviewed normalized-account inputs.

    Exact-account classification requires continuous account-statement coverage,
    byte-verified sources, source types compatible with the records they support,
    and a human-reviewed normalization attestation bound to every normalized input.
    """

    payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    blockers: list[str] = []
    if payload.get("schema_version") != 2:
        blockers.append("coverage_manifest_schema_v2_required")
    if payload.get("coverage_complete") is not True:
        blockers.append("coverage_manifest_not_certified_complete")

    try:
        required_start_date = date.fromisoformat(required_start)
        required_end_date = date.fromisoformat(required_end)
        if required_start_date > required_end_date:
            raise ValueError
    except ValueError:
        raise ValueError("required_start/required_end must be a valid ordered ISO date range")

    try:
        manifest_start = date.fromisoformat(str(payload.get("coverage_start", ""))[:10])
        manifest_end = date.fromisoformat(str(payload.get("coverage_end", ""))[:10])
        if manifest_start > manifest_end:
            raise ValueError
        if manifest_start > required_start_date or manifest_end < required_end_date:
            blockers.append("coverage_manifest_period_too_short")
    except ValueError:
        blockers.append("coverage_manifest_dates_invalid")

    if not str(payload.get("reviewed_by", "")).strip():
        blockers.append("coverage_manifest_reviewer_missing")
    reviewed_at = _parse_review_timestamp(
        payload.get("reviewed_at_utc"),
        "coverage_manifest_review_timestamp_invalid",
        blockers,
    )
    if reviewed_at is not None and reviewed_at.date() < required_end_date:
        blockers.append("coverage_manifest_review_predates_required_period_end")
    if reviewed_at is not None and reviewed_at > datetime.now(timezone.utc) + timedelta(minutes=5):
        blockers.append("coverage_manifest_review_timestamp_in_future")

    if payload.get("normalization_verified") is not True:
        blockers.append("normalization_review_not_certified")
    if not str(payload.get("normalization_reviewed_by", "")).strip():
        blockers.append("normalization_reviewer_missing")
    normalization_reviewed_at = _parse_review_timestamp(
        payload.get("normalization_reviewed_at_utc"),
        "normalization_review_timestamp_invalid",
        blockers,
    )
    if normalization_reviewed_at is not None and normalization_reviewed_at.date() < required_end_date:
        blockers.append("normalization_review_predates_required_period_end")
    if normalization_reviewed_at is not None and normalization_reviewed_at > datetime.now(timezone.utc) + timedelta(minutes=5):
        blockers.append("normalization_review_timestamp_in_future")
    if not str(payload.get("normalization_attestation", "")).strip():
        blockers.append("normalization_attestation_missing")

    raw_documents = payload.get("documents")
    documents: dict[str, str] = {}
    document_kinds: dict[str, str] = {}
    statement_intervals: list[tuple[date, date]] = []
    if not isinstance(raw_documents, list) or not raw_documents:
        blockers.append("coverage_manifest_documents_missing")
        raw_documents = []
    for raw in raw_documents:
        if not isinstance(raw, dict):
            blockers.append("coverage_manifest_document_invalid:<non-object>")
            continue
        name = str(raw.get("path", "")).strip()
        digest = str(raw.get("sha256", "")).strip().lower()
        kind = str(raw.get("kind", "")).strip().lower()
        if not name or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            blockers.append(f"coverage_manifest_document_invalid:{name or '<missing>'}")
            continue
        if kind not in ALLOWED_DOCUMENT_KINDS:
            blockers.append(f"coverage_manifest_document_kind_invalid:{name}")
            continue
        if name in documents and documents[name] != digest:
            blockers.append(f"coverage_manifest_document_hash_conflict:{name}")
            continue
        if name in document_kinds and document_kinds[name] != kind:
            blockers.append(f"coverage_manifest_document_kind_conflict:{name}")
            continue
        documents[name] = digest
        document_kinds[name] = kind

        if kind == "account_statement":
            try:
                interval_start = date.fromisoformat(str(raw.get("coverage_start", ""))[:10])
                interval_end = date.fromisoformat(str(raw.get("coverage_end", ""))[:10])
                if interval_start > interval_end:
                    raise ValueError
                statement_intervals.append((interval_start, interval_end))
            except ValueError:
                blockers.append(f"account_statement_coverage_dates_invalid:{name}")

    if not _continuous_statement_coverage(
        statement_intervals,
        required_start_date,
        required_end_date,
    ):
        blockers.append("continuous_account_statement_coverage_missing")

    for name, allowed in (source_kind_requirements or {}).items():
        actual = document_kinds.get(name)
        if actual is None:
            blockers.append(f"source_kind_requirement_document_missing:{name}")
        elif actual not in allowed:
            blockers.append(f"source_document_kind_not_allowed:{name}:{actual}")

    root = Path(evidence_root).expanduser().resolve()
    verified_documents = 0
    if not root.is_dir():
        blockers.append("evidence_root_missing_or_not_directory")
    else:
        for name, expected in documents.items():
            relative = Path(name)
            if relative.is_absolute():
                blockers.append(f"absolute_source_document_path_forbidden:{name}")
                continue
            candidate = (root / relative).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                blockers.append(f"source_document_path_escapes_evidence_root:{name}")
                continue
            if not candidate.is_file():
                blockers.append(f"source_document_missing_or_invalid:{name}")
                continue
            if _sha256(candidate) != expected:
                blockers.append(f"source_document_hash_mismatch:{name}")
                continue
            verified_documents += 1

    for record in normalized_records:
        name = str(getattr(record, "source_document", "")).strip()
        digest = str(getattr(record, "source_sha256", "")).strip().lower()
        expected = documents.get(name)
        if expected is None:
            blockers.append(f"normalized_source_not_in_coverage_manifest:{name}")
        elif expected != digest:
            blockers.append(f"normalized_source_hash_differs_from_coverage_manifest:{name}")

    supplied_normalized = {str(role): Path(path) for role, path in normalized_inputs.items()}
    if not MANDATORY_NORMALIZED_ROLES <= set(supplied_normalized):
        missing = sorted(MANDATORY_NORMALIZED_ROLES - set(supplied_normalized))
        blockers.extend(f"normalized_input_role_missing:{role}" for role in missing)

    raw_normalized = payload.get("normalized_inputs")
    declared_normalized: dict[str, str] = {}
    if not isinstance(raw_normalized, list) or not raw_normalized:
        blockers.append("coverage_manifest_normalized_inputs_missing")
        raw_normalized = []
    for raw in raw_normalized:
        if not isinstance(raw, dict):
            blockers.append("coverage_manifest_normalized_input_invalid:<non-object>")
            continue
        role = str(raw.get("role", "")).strip()
        digest = str(raw.get("sha256", "")).strip().lower()
        if not role or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            blockers.append(f"coverage_manifest_normalized_input_invalid:{role or '<missing>'}")
            continue
        if role in declared_normalized and declared_normalized[role] != digest:
            blockers.append(f"coverage_manifest_normalized_input_hash_conflict:{role}")
            continue
        declared_normalized[role] = digest

    supplied_roles = set(supplied_normalized)
    declared_roles = set(declared_normalized)
    for role in sorted(supplied_roles - declared_roles):
        blockers.append(f"normalized_input_not_attested:{role}")
    for role in sorted(declared_roles - supplied_roles):
        blockers.append(f"attested_normalized_input_not_supplied:{role}")

    verified_normalized = 0
    for role in sorted(supplied_roles & declared_roles):
        path = supplied_normalized[role]
        if not path.is_file():
            blockers.append(f"normalized_input_missing:{role}")
            continue
        if _sha256(path) != declared_normalized[role]:
            blockers.append(f"normalized_input_hash_mismatch:{role}")
            continue
        verified_normalized += 1

    continuous_statements = _continuous_statement_coverage(
        statement_intervals,
        required_start_date,
        required_end_date,
    )
    return {
        "coverage_start": payload.get("coverage_start"),
        "coverage_end": payload.get("coverage_end"),
        "coverage_complete": payload.get("coverage_complete") is True,
        "continuous_account_statement_coverage": continuous_statements,
        "declared_documents": len(documents),
        "verified_documents": verified_documents,
        "declared_normalized_inputs": len(declared_normalized),
        "verified_normalized_inputs": verified_normalized,
        "normalization_verified": payload.get("normalization_verified") is True,
        "source_kind_requirements_checked": len(source_kind_requirements or {}),
        "blockers": sorted(set(blockers)),
        "verified": (
            not blockers
            and bool(documents)
            and continuous_statements
            and verified_documents == len(documents)
            and supplied_roles == declared_roles
            and verified_normalized == len(supplied_roles)
        ),
    }
