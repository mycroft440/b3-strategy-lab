from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence


BLOCKING_REALISTIC_VALIDITY_TAGS = (
    "__RETROSPECTIVE_UNIVERSE",
    "__RETROSPECTIVE_SELECTION",
    "__UNCERTIFIED_CASH_EVENTS",
    "__UNBOUND_TICKER_TRANSITIONS",
    "__BONUS_TAX_BASIS_UNCERTIFIED",
    "__MODELED_FEES",
)


class ValidationError(ValueError):
    """Raised when an ex-ante/PIT contract cannot be certified."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(payload: object) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _iso_day(value: object) -> str:
    text = str(value)[:10]
    return date.fromisoformat(text).isoformat()


def _utc_datetime(value: str | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValidationError("Freeze timestamp must include an explicit timezone.")
    return parsed.astimezone(timezone.utc)


def latest_complete_calendar_year(
    market_dates: Sequence[str],
    *,
    as_of: date | None = None,
    minimum_sessions: int = 200,
) -> int:
    """Return the latest completed calendar year represented by B3 sessions.

    This helper is retrospective diagnostics only. A completed year is not
    automatically an untouched holdout: certification additionally requires a
    wall-clock candidate freeze before the first holdout session.
    """
    if minimum_sessions <= 0:
        raise ValueError("minimum_sessions must be positive")
    today = as_of or date.today()
    by_year: dict[int, list[date]] = defaultdict(list)
    for raw in market_dates:
        value = date.fromisoformat(str(raw)[:10])
        if value.year < today.year:
            by_year[value.year].append(value)
    complete = [
        year
        for year, values in by_year.items()
        if len(values) >= minimum_sessions
        and min(values).month == 1
        and max(values).month == 12
    ]
    if not complete:
        raise ValidationError("No complete historical calendar year is available.")
    return max(complete)


def holdout_bounds(market_dates: Sequence[str], holdout_year: int) -> tuple[str, str]:
    values = sorted(
        {_iso_day(item) for item in market_dates if int(str(item)[:4]) == holdout_year}
    )
    if not values:
        raise ValidationError(f"No market sessions found for holdout year {holdout_year}.")
    if date.fromisoformat(values[0]).month != 1 or date.fromisoformat(values[-1]).month != 12:
        raise ValidationError(f"Holdout year {holdout_year} is not a complete calendar year.")
    return values[0], values[-1]


def point_in_time_contract_issues(
    *,
    universe: Mapping[str, object],
    snapshots: Iterable[Mapping[str, object]],
    data_dir: Path,
    actions_dir: Path,
    manifests_dir: Path,
    split_evidence: Path,
    cash_certification: Mapping[str, object] | None = None,
    require_cash_announcement_timing: bool = True,
) -> list[str]:
    """Validate the information-set contract without using future market outcomes."""
    issues: list[str] = []
    try:
        schema_version = int(universe.get("schema_version", 0))
    except (TypeError, ValueError):
        schema_version = 0
    if schema_version < 8:
        issues.append("universe_schema_lt_8")
    if universe.get("point_in_time") is not True:
        issues.append("universe_not_point_in_time")
    if universe.get("survivorship_safe") is not True:
        issues.append("universe_not_survivorship_safe")

    rules = universe.get("selection_rules")
    if not isinstance(rules, Mapping):
        issues.append("selection_rules_missing")
        rules = {}
    if rules.get("future_continuity_filter") is not False:
        issues.append("future_continuity_filter_not_false")
    if rules.get("future_return_filter") is not False:
        issues.append("future_return_filter_not_false")
    try:
        expected_size = int(rules.get("weekly_candidates", 0))
    except (TypeError, ValueError):
        expected_size = 0
    if expected_size <= 0:
        issues.append("weekly_candidates_not_positive")

    expected_storage = {
        "data_dir": "candles_point_in_time",
        "actions_dir": "actions_point_in_time",
        "manifests_dir": "manifests_point_in_time",
        "split_evidence": "point_in_time_split_evidence.json",
    }
    actual_storage = {
        "data_dir": data_dir.name,
        "actions_dir": actions_dir.name,
        "manifests_dir": manifests_dir.name,
        "split_evidence": split_evidence.name,
    }
    for key, expected in expected_storage.items():
        if actual_storage[key] != expected:
            issues.append(f"legacy_or_unexpected_{key}")

    try:
        selected_as_of = _iso_day(universe.get("selected_as_of"))
        selection_end = _iso_day(universe.get("selection_end"))
        if selected_as_of > selection_end:
            issues.append("invalid_universe_date_window")
    except (TypeError, ValueError):
        selected_as_of = "9999-12-31"
        selection_end = "0001-01-01"
        issues.append("invalid_universe_date_window")

    raw_tickers = universe.get("tickers", [])
    if not isinstance(raw_tickers, (list, tuple, set)):
        raw_tickers = []
        issues.append("invalid_selectable_union")
    selectable = {str(item).strip().upper() for item in raw_tickers if str(item).strip()}
    if not selectable:
        issues.append("empty_selectable_union")

    grouped: dict[str, list[tuple[int, str]]] = defaultdict(list)
    seen_rows: set[tuple[str, str]] = set()
    for raw in snapshots:
        try:
            effective_date = _iso_day(raw.get("effective_date"))
            ticker = str(raw.get("ticker", "")).strip().upper()
            rank = int(raw.get("rank", 0))
        except (TypeError, ValueError):
            issues.append("invalid_snapshot_row")
            continue
        if not ticker or rank <= 0:
            issues.append("invalid_snapshot_row")
            continue
        key = (effective_date, ticker)
        if key in seen_rows:
            issues.append("duplicate_snapshot_ticker")
            continue
        seen_rows.add(key)
        if effective_date < selected_as_of or effective_date > selection_end:
            issues.append("snapshot_outside_declared_window")
        if ticker not in selectable:
            issues.append("snapshot_ticker_outside_union")
        grouped[effective_date].append((rank, ticker))

    if not grouped:
        issues.append("empty_snapshot_history")
    snapshot_union: set[str] = set()
    for effective_date, rows in grouped.items():
        ordered = sorted(rows)
        ranks = [rank for rank, _ticker in ordered]
        tickers = [ticker for _rank, ticker in ordered]
        snapshot_union.update(tickers)
        if ranks != list(range(1, len(rows) + 1)):
            issues.append(f"nonsequential_snapshot_ranks:{effective_date}")
        if expected_size and len(rows) != expected_size:
            issues.append(f"snapshot_size_mismatch:{effective_date}")
    if grouped and snapshot_union != selectable:
        issues.append("snapshot_union_mismatch")

    certification = cash_certification or {}
    if require_cash_announcement_timing and certification.get("announcement_timing_certified") is not True:
        issues.append("cash_announcement_timing_not_certified")
    if certification.get("coverage_certified") is not True:
        issues.append("cash_event_coverage_not_certified")
    return sorted(set(issues))


def _validate_candidate_inputs(
    *,
    candidates: Mapping[str, object],
    matrix_manifest: Mapping[str, object],
    pit_audit: Mapping[str, object],
) -> tuple[dict[str, object], str, str]:
    if pit_audit.get("status") != "PASS":
        raise ValidationError("Point-in-time validation must PASS before candidate freeze.")
    if matrix_manifest.get("catalog_complete") is not True:
        raise ValidationError("Training matrix must cover the complete strategy catalog.")
    universe = matrix_manifest.get("universe")
    if not isinstance(universe, Mapping):
        raise ValidationError("Training matrix lacks a bound universe manifest.")
    if universe.get("point_in_time") is not True or universe.get("survivorship_safe") is not True:
        raise ValidationError("Training matrix universe is not point-in-time/survivorship-safe.")
    candidate_period = candidates.get("period")
    if not isinstance(candidate_period, Mapping):
        raise ValidationError("Candidate file lacks its selection period.")
    candidate_start = _iso_day(candidate_period.get("start"))
    candidate_end = _iso_day(candidate_period.get("end"))
    manifest_start = _iso_day(matrix_manifest.get("start"))
    manifest_end = _iso_day(matrix_manifest.get("end"))
    if (candidate_start, candidate_end) != (manifest_start, manifest_end):
        raise ValidationError("Candidate period differs from training matrix period.")
    raw_top = candidates.get("top_10")
    if not isinstance(raw_top, list) or not raw_top or not isinstance(raw_top[0], Mapping):
        raise ValidationError("Candidate file has no rank-1 result.")
    champion = dict(raw_top[0])
    if int(champion.get("rank", 0)) != 1:
        raise ValidationError("First candidate is not rank 1.")
    if not str(champion.get("trading_strategy", "")).strip() or not str(champion.get("management_strategy", "")).strip():
        raise ValidationError("Frozen candidate identity is incomplete.")
    return champion, candidate_start, candidate_end


def build_prospective_freeze(
    *,
    candidates: Mapping[str, object],
    matrix_manifest: Mapping[str, object],
    pit_audit: Mapping[str, object],
    source_bindings: Mapping[str, str],
    frozen_at_utc: str | None = None,
) -> dict[str, object]:
    """Freeze rank #1 for genuinely future validation after all seen history."""
    champion, candidate_start, candidate_end = _validate_candidate_inputs(
        candidates=candidates,
        matrix_manifest=matrix_manifest,
        pit_audit=pit_audit,
    )
    frozen_at = _utc_datetime(frozen_at_utc)
    if date.fromisoformat(candidate_end) > frozen_at.date():
        raise ValidationError("Training information cutoff cannot be after the freeze date.")
    identity = {
        "trading_strategy": str(champion["trading_strategy"]).strip().lower(),
        "management_strategy": str(champion["management_strategy"]).strip(),
    }
    return {
        "schema_version": 2,
        "status": "PROSPECTIVE_FROZEN_PENDING",
        "frozen_at_utc": frozen_at.isoformat(),
        "information_cutoff": candidate_end,
        "candidate": identity,
        "candidate_identity_sha256": canonical_sha256(identity),
        "training_period": {"start": candidate_start, "end": candidate_end},
        "selection_source_rank": 1,
        "selection_scope": "full_catalog_point_in_time_research_then_prospective_freeze",
        "selection_uses_future_validation_data": False,
        "fallback_candidate_allowed": False,
        "future_result_may_change_candidate": False,
        "prospective_validation_must_start_after": frozen_at.date().isoformat(),
        "historical_holdout_claim_allowed": False,
        "ex_ante_selection_claim_allowed": False,
        "formal_multiple_testing_significance_claim_allowed": False,
        "prospective_evidence_required_for_validated_winner": True,
        "validated_winner_available": False,
        "pit_validation_status": "PASS",
        "pit_validation_sha256": str(pit_audit.get("report_sha256", "")),
        "source_bindings": dict(source_bindings),
    }


def build_frozen_candidate(
    *,
    candidates: Mapping[str, object],
    matrix_manifest: Mapping[str, object],
    pit_audit: Mapping[str, object],
    holdout_start: str,
    holdout_end: str,
    source_bindings: Mapping[str, str],
    frozen_at_utc: str | None = None,
) -> dict[str, object]:
    """Freeze rank #1 before a genuine holdout; retroactive freezes are forbidden."""
    champion, candidate_start, candidate_end = _validate_candidate_inputs(
        candidates=candidates,
        matrix_manifest=matrix_manifest,
        pit_audit=pit_audit,
    )
    holdout_start = _iso_day(holdout_start)
    holdout_end = _iso_day(holdout_end)
    if holdout_end < holdout_start:
        raise ValidationError("Holdout end precedes holdout start.")
    if candidate_end >= holdout_start:
        raise ValidationError("Selection period overlaps the final holdout.")
    frozen_at = _utc_datetime(frozen_at_utc)
    if frozen_at.date() >= date.fromisoformat(holdout_start):
        raise ValidationError(
            "Candidate was frozen on/after the holdout began; retroactive ex-ante certification is forbidden."
        )
    identity = {
        "trading_strategy": str(champion["trading_strategy"]).strip().lower(),
        "management_strategy": str(champion["management_strategy"]).strip(),
    }
    return {
        "schema_version": 2,
        "status": "FROZEN_BEFORE_HOLDOUT",
        "frozen_at_utc": frozen_at.isoformat(),
        "candidate": identity,
        "candidate_identity_sha256": canonical_sha256(identity),
        "training_period": {"start": candidate_start, "end": candidate_end},
        "holdout_period": {"start": holdout_start, "end": holdout_end},
        "selection_source_rank": 1,
        "selection_scope": "full_catalog_pre_holdout_training_only",
        "selection_uses_holdout_data": False,
        "fallback_candidate_allowed": False,
        "holdout_result_may_change_candidate": False,
        "formal_multiple_testing_significance_claim_allowed": False,
        "performance_claim_scope_if_validated": "single_genuinely_pre_frozen_holdout",
        "pit_validation_status": "PASS",
        "pit_validation_sha256": str(pit_audit.get("report_sha256", "")),
        "source_bindings": dict(source_bindings),
    }


def holdout_validation_issues(
    *,
    frozen: Mapping[str, object],
    realistic_summary: Mapping[str, object],
    pit_audit: Mapping[str, object],
) -> list[str]:
    issues: list[str] = []
    if frozen.get("status") != "FROZEN_BEFORE_HOLDOUT":
        issues.append("candidate_not_frozen")
    if frozen.get("selection_uses_holdout_data") is not False:
        issues.append("selection_may_use_holdout")
    if frozen.get("fallback_candidate_allowed") is not False:
        issues.append("fallback_candidate_is_allowed")
    if frozen.get("holdout_result_may_change_candidate") is not False:
        issues.append("holdout_can_change_candidate")
    if pit_audit.get("status") != "PASS":
        issues.append("pit_validation_not_passed")
    candidate = frozen.get("candidate")
    holdout = frozen.get("holdout_period")
    training = frozen.get("training_period")
    if not isinstance(candidate, Mapping):
        candidate = {}
        issues.append("frozen_candidate_missing")
    if not isinstance(holdout, Mapping):
        holdout = {}
        issues.append("holdout_period_missing")
    if not isinstance(training, Mapping):
        training = {}
        issues.append("training_period_missing")
    try:
        training_end = _iso_day(training.get("end"))
        holdout_start = _iso_day(holdout.get("start"))
        holdout_end = _iso_day(holdout.get("end"))
        frozen_at = _utc_datetime(str(frozen.get("frozen_at_utc", "")))
        if training_end >= holdout_start:
            issues.append("training_holdout_overlap")
        if frozen_at.date() >= date.fromisoformat(holdout_start):
            issues.append("retroactive_holdout_freeze")
    except (TypeError, ValueError, ValidationError):
        holdout_start = ""
        holdout_end = ""
        issues.append("invalid_freeze_dates")
    if str(realistic_summary.get("strategy", "")).strip().lower() != str(candidate.get("trading_strategy", "")).strip().lower():
        issues.append("holdout_strategy_differs_from_frozen")
    if str(realistic_summary.get("management", "")).strip() != str(candidate.get("management_strategy", "")).strip():
        issues.append("holdout_management_differs_from_frozen")
    if holdout_start and _iso_day(realistic_summary.get("start")) != holdout_start:
        issues.append("holdout_start_mismatch")
    if holdout_end and _iso_day(realistic_summary.get("end")) != holdout_end:
        issues.append("holdout_end_mismatch")
    if realistic_summary.get("selection_status") not in {"ex_ante_holdout", "prospective_frozen"}:
        issues.append("holdout_selection_status_not_frozen")
    if realistic_summary.get("point_in_time_universe") is not True:
        issues.append("holdout_not_point_in_time")
    if realistic_summary.get("survivorship_safe") is not True:
        issues.append("holdout_not_survivorship_safe")
    if realistic_summary.get("cash_events_complete") is not True:
        issues.append("holdout_cash_events_incomplete")
    if realistic_summary.get("fractional_execution") is not True:
        issues.append("holdout_fractional_execution_disabled")
    if str(realistic_summary.get("fee_quality", "")) != "official":
        issues.append("holdout_fee_quality_not_official")
    if realistic_summary.get("economic_gap_adjustment") is True and pit_audit.get("cash_announcement_timing_certified") is not True:
        issues.append("economic_gap_uses_uncertified_announcement_timing")
    validity = str(realistic_summary.get("validity", ""))
    if not validity.startswith("REALISTIC_POINT_IN_TIME"):
        issues.append("holdout_validity_not_realistic_pit")
    for tag in BLOCKING_REALISTIC_VALIDITY_TAGS:
        if tag in validity:
            issues.append(f"blocking_validity_tag:{tag}")
    return sorted(set(issues))


def build_holdout_validation_report(
    *,
    frozen: Mapping[str, object],
    realistic_summary: Mapping[str, object],
    pit_audit: Mapping[str, object],
    source_bindings: Mapping[str, str],
) -> dict[str, object]:
    issues = holdout_validation_issues(
        frozen=frozen,
        realistic_summary=realistic_summary,
        pit_audit=pit_audit,
    )
    passed = not issues
    return {
        "schema_version": 2,
        "status": "PASS" if passed else "BLOCKED",
        "selection_classification": "EX_ANTE_FROZEN_SINGLE_HOLDOUT_VALIDATED" if passed else "EX_ANTE_HOLDOUT_VALIDATION_BLOCKED",
        "candidate": frozen.get("candidate"),
        "training_period": frozen.get("training_period"),
        "holdout_period": frozen.get("holdout_period"),
        "selection_uses_holdout_data": False if passed else None,
        "candidate_changed_after_holdout": False if passed else None,
        "data_snooping_control": "wall_clock_pre_freeze_plus_single_frozen_holdout",
        "point_in_time_validation_complete": passed and pit_audit.get("status") == "PASS",
        "formal_multiple_testing_significance_claim_allowed": False,
        "real_money_claim_allowed": False,
        "counterfactual_execution_only": True,
        "issues": issues,
        "holdout_metrics": {
            key: realistic_summary.get(key)
            for key in (
                "initial_cash", "final_equity", "total_return", "cagr",
                "max_drawdown", "annual_volatility", "sharpe",
                "average_annual_return", "trades", "fees_paid",
                "ordinary_income_tax_paid", "distribution_tax_paid", "distributions_net",
            )
        },
        "source_bindings": dict(source_bindings),
    }
