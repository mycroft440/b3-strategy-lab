from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from b3_strategy_lab.realistic import FeeSchedule, PointInTimeUniverse


DEFAULT_UNIVERSE = Path("data/universes/point_in_time_union.json")
DEFAULT_SNAPSHOTS = Path("data/universes/point_in_time_weekly.csv")
DEFAULT_EXECUTION = Path("data/execution/b3_standard_fractional_open.csv")
DEFAULT_CASH_MANIFEST = Path("data/corporate_actions/point_in_time_cash_distributions.manifest.json")
DEFAULT_CASH_CERTIFICATION = Path("data/corporate_actions/cash_distribution_coverage_certification.json")
DEFAULT_SPLITS = Path("data/corporate_actions/point_in_time_split_evidence.json")
DEFAULT_TRANSITIONS = Path("data/corporate_actions/ticker_transitions.manifest.json")
DEFAULT_FEES = Path("data/fees/b3_equity_fee_schedule.json")
DEFAULT_OUTPUT = Path("reports/realistic_input_audit.json")


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit whether realistic-account inputs support a retrospective estimate "
            "and whether they are strong enough for an exact conditional account claim."
        )
    )
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--snapshots", type=Path, default=DEFAULT_SNAPSHOTS)
    parser.add_argument("--execution", type=Path, default=DEFAULT_EXECUTION)
    parser.add_argument("--cash-manifest", type=Path, default=DEFAULT_CASH_MANIFEST)
    parser.add_argument("--cash-certification", type=Path, default=DEFAULT_CASH_CERTIFICATION)
    parser.add_argument("--split-evidence", type=Path, default=DEFAULT_SPLITS)
    parser.add_argument("--transition-manifest", type=Path, default=DEFAULT_TRANSITIONS)
    parser.add_argument("--fee-schedule", type=Path, default=DEFAULT_FEES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    checks: dict[str, bool] = {}
    details: dict[str, object] = {}

    universe_payload = json.loads(args.universe.read_text(encoding="utf-8"))
    universe = PointInTimeUniverse.from_csv(args.snapshots)
    expected_union = {str(item).upper() for item in universe_payload.get("tickers", [])}
    excluded = {
        str(item).strip().upper()
        for item in universe_payload.get("excluded_tickers", [])
        if str(item).strip()
    }

    checks["universe_is_point_in_time"] = universe_payload.get("point_in_time") is True
    checks["universe_declares_survivorship_safe"] = universe_payload.get("survivorship_safe") is True
    checks["snapshot_union_matches_manifest"] = universe.union == expected_union
    checks["no_replacement_policy_declared"] = universe_payload.get("no_replacements") is True
    checks["excluded_tickers_absent"] = not bool(universe.union & excluded)

    allowed_file_value = str(universe_payload.get("allowed_universe_file", "")).strip()
    allowed_tickers: set[str] = set()
    if allowed_file_value:
        allowed_file = Path(allowed_file_value)
        if allowed_file.exists():
            allowed_payload = json.loads(allowed_file.read_text(encoding="utf-8"))
            allowed_tickers = {
                str(item).strip().upper()
                for item in allowed_payload.get("tickers", [])
                if str(item).strip()
            }
    if universe_payload.get("no_replacements") is True:
        checks["snapshot_union_within_allowed_universe"] = bool(allowed_tickers) and universe.union <= allowed_tickers
    else:
        checks["snapshot_union_within_allowed_universe"] = True

    details["snapshot_count"] = len(universe.snapshots)
    details["historical_symbol_union"] = len(universe.union)
    details["minimum_snapshot_size"] = min(len(snapshot.tickers) for snapshot in universe.snapshots)
    details["maximum_snapshot_size"] = max(len(snapshot.tickers) for snapshot in universe.snapshots)
    details["selection_mode"] = universe_payload.get("selection_mode", "")
    details["excluded_tickers"] = sorted(excluded)
    details["selection_bias_disclosure"] = universe_payload.get("bias_disclosure", "")
    details["allowed_universe_file"] = allowed_file_value
    details["allowed_universe_size"] = len(allowed_tickers)

    split_payload = json.loads(args.split_evidence.read_text(encoding="utf-8"))
    checks["split_markers_fully_covered"] = int(split_payload.get("uncovered_count", -1)) == 0

    cash_payload = json.loads(args.cash_manifest.read_text(encoding="utf-8"))
    checks["cash_response_has_no_parse_issues"] = not bool(cash_payload.get("issues"))
    details["cash_event_count"] = int(cash_payload.get("event_count", 0))
    details["cash_source"] = cash_payload.get("source", "")

    cash_certified = False
    certification: dict[str, object] = {}
    if args.cash_certification.exists():
        certification = json.loads(args.cash_certification.read_text(encoding="utf-8"))
        cash_certified = (
            certification.get("schema_version") == 1
            and certification.get("coverage_certified") is True
            and str(certification.get("start", "")) <= str(universe_payload.get("selected_as_of", ""))
            and str(certification.get("end", "")) >= max(snapshot.effective_date for snapshot in universe.snapshots)
            and certification.get("source_authority") in {"B3", "CVM", "B3+CVM+issuer"}
        )
    checks["cash_history_coverage_certified"] = cash_certified
    details["cash_certification"] = certification

    transition_payload: dict[str, object] = {}
    if args.transition_manifest.exists():
        transition_payload = json.loads(args.transition_manifest.read_text(encoding="utf-8"))
    checks["ticker_transitions_have_no_unresolved_disappearances"] = (
        transition_payload.get("complete") is True
    )
    details["unresolved_historical_disappearances"] = int(
        transition_payload.get("unresolved_disappearances", -1)
    ) if transition_payload else -1

    fees = FeeSchedule.from_json(args.fee_schedule)
    fee_qualities = sorted({rule.quality for rule in fees.rules})
    checks["all_fee_periods_are_official"] = fee_qualities == ["official"]
    details["fee_qualities"] = fee_qualities

    execution_rows = _rows(args.execution)
    standard = {
        (row.get("date", ""), row.get("ticker", ""))
        for row in execution_rows
        if row.get("market_type") == "010"
    }
    fractional_base = {
        (
            row.get("date", ""),
            (row.get("ticker", "")[:-1] if row.get("ticker", "").endswith("F") else row.get("ticker", "")),
        )
        for row in execution_rows
        if row.get("market_type") == "020"
    }
    checks["execution_book_has_standard_quotes"] = bool(standard)
    checks["execution_book_has_fractional_quotes"] = bool(fractional_base)
    execution_bases = {
        (row.get("ticker", "")[:-1] if row.get("ticker", "").endswith("F") else row.get("ticker", "")).upper()
        for row in execution_rows
        if row.get("ticker")
    }
    checks["execution_book_excludes_forbidden_tickers"] = not bool(execution_bases & excluded)
    if universe_payload.get("no_replacements") is True:
        checks["execution_book_within_allowed_universe"] = bool(allowed_tickers) and execution_bases <= allowed_tickers
    else:
        checks["execution_book_within_allowed_universe"] = True
    details["standard_execution_rows"] = len(standard)
    details["fractional_execution_rows"] = len(fractional_base)

    # Selection validity and account reconstruction are separate claims. A fixed,
    # hindsight-selected universe can still support a realistic conditional replay
    # of what the account mechanics would have done if that frozen rule had been
    # followed. It cannot support an ex-ante strategy-selection claim.
    structural_account = [
        "universe_is_point_in_time",
        "snapshot_union_matches_manifest",
        "no_replacement_policy_declared",
        "snapshot_union_within_allowed_universe",
        "excluded_tickers_absent",
        "split_markers_fully_covered",
        "cash_response_has_no_parse_issues",
        "execution_book_has_standard_quotes",
        "execution_book_has_fractional_quotes",
        "execution_book_excludes_forbidden_tickers",
        "execution_book_within_allowed_universe",
    ]
    ready_for_estimate = all(checks[name] for name in structural_account)

    exact_requirements = [
        "cash_history_coverage_certified",
        "ticker_transitions_have_no_unresolved_disappearances",
        "all_fee_periods_are_official",
    ]
    ready_for_exact_claim = ready_for_estimate and all(checks[name] for name in exact_requirements)

    selection_validity = (
        "SURVIVORSHIP_SAFE_POINT_IN_TIME"
        if checks["universe_declares_survivorship_safe"]
        else "RETROSPECTIVE_FIXED_UNIVERSE_ONLY"
    )
    estimate_blockers = [name for name in structural_account if not checks[name]]
    exact_claim_blockers = estimate_blockers + [
        name for name in exact_requirements if not checks[name]
    ]
    selection_limitations = []
    if not checks["universe_declares_survivorship_safe"]:
        selection_limitations.append("universe_is_fixed_and_not_survivorship_safe")
    if universe_payload.get("no_replacements") is True:
        selection_limitations.append("candidate_universe_frozen_to_pre_existing_project_list")

    payload = {
        "schema_version": 3,
        "checks": checks,
        "details": details,
        "ready_for_realistic_estimate": ready_for_estimate,
        "ready_for_exact_historical_account_claim": ready_for_exact_claim,
        "selection_validity": selection_validity,
        "ex_ante_selection_claim_allowed": checks["universe_declares_survivorship_safe"],
        "estimate_blockers": estimate_blockers,
        "exact_claim_blockers": exact_claim_blockers,
        "selection_limitations": selection_limitations,
        # Backward-compatible field: blockers now means blockers to running the
        # realistic estimate, not intentional methodological limitations.
        "blockers": estimate_blockers,
        "interpretation": (
            "Account reconstruction and strategy-selection validity are separate. "
            "A realistic conditional account replay may run when structural market-data "
            "checks pass even if the candidate list is a fixed hindsight-selected universe. "
            "The fixed/no-replacement constraint and explicit exclusions are audited as "
            "data-integrity rules. Such a run remains retrospective and cannot be presented "
            "as proof that the same securities would have been selected ex ante."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if ready_for_estimate else 2


if __name__ == "__main__":
    raise SystemExit(main())
