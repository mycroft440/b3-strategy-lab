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
    checks["universe_is_point_in_time"] = universe_payload.get("point_in_time") is True
    checks["universe_declares_survivorship_safe"] = universe_payload.get("survivorship_safe") is True
    checks["snapshot_union_matches_manifest"] = universe.union == expected_union
    checks["no_replacement_policy_declared"] = universe_payload.get("no_replacements") is True
    details["snapshot_count"] = len(universe.snapshots)
    details["historical_symbol_union"] = len(universe.union)
    details["selection_mode"] = universe_payload.get("selection_mode", "")
    details["excluded_tickers"] = universe_payload.get("excluded_tickers", [])
    details["selection_bias_disclosure"] = universe_payload.get("bias_disclosure", "")

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
    details["standard_execution_rows"] = len(standard)
    details["fractional_execution_rows"] = len(fractional_base)

    # Selection validity and account reconstruction are separate claims. A fixed,
    # hindsight-selected universe can still support a realistic conditional replay
    # of what the account mechanics would have done if that frozen rule had been
    # followed. It cannot support an ex-ante strategy-selection claim.
    structural_account = [
        "universe_is_point_in_time",
        "snapshot_union_matches_manifest",
        "split_markers_fully_covered",
        "cash_response_has_no_parse_issues",
        "execution_book_has_standard_quotes",
        "execution_book_has_fractional_quotes",
    ]
    ready_for_estimate = all(checks[name] for name in structural_account)
    ready_for_exact_claim = ready_for_estimate and all(
        checks[name]
        for name in [
            "cash_history_coverage_certified",
            "ticker_transitions_have_no_unresolved_disappearances",
            "all_fee_periods_are_official",
        ]
    )

    selection_validity = (
        "SURVIVORSHIP_SAFE_POINT_IN_TIME"
        if checks["universe_declares_survivorship_safe"]
        else "RETROSPECTIVE_FIXED_UNIVERSE_ONLY"
    )
    blockers = [name for name, ok in checks.items() if not ok]
    payload = {
        "schema_version": 2,
        "checks": checks,
        "details": details,
        "ready_for_realistic_estimate": ready_for_estimate,
        "ready_for_exact_historical_account_claim": ready_for_exact_claim,
        "selection_validity": selection_validity,
        "ex_ante_selection_claim_allowed": checks["universe_declares_survivorship_safe"],
        "blockers": blockers,
        "interpretation": (
            "Account reconstruction and strategy-selection validity are separate. "
            "A realistic conditional account replay may run when structural market-data "
            "checks pass even if the candidate list is a fixed hindsight-selected universe. "
            "Such a run must remain labeled retrospective and cannot be presented as proof "
            "that the same securities would have been selected ex ante."
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
