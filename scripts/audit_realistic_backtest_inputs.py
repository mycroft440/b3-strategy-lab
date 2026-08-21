from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.realistic import (  # noqa: E402
    FeeSchedule,
    PointInTimeUniverse,
    cash_coverage_certification_issues,
)


DEFAULT_UNIVERSE = Path("data/universes/point_in_time_union.json")
DEFAULT_SNAPSHOTS = Path("data/universes/point_in_time_weekly.csv")
DEFAULT_EXECUTION = Path("data/execution/b3_standard_fractional_open.csv")
DEFAULT_CASH_EVENTS = Path("data/corporate_actions/point_in_time_cash_distributions.csv")
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


def _fee_schedule_contiguous(fees: FeeSchedule, start: str, end: str) -> bool:
    rules = sorted(fees.rules, key=lambda item: item.start)
    if not rules or rules[0].start > start or rules[-1].end < end:
        return False
    cursor = date.fromisoformat(start)
    target = date.fromisoformat(end)
    for rule in rules:
        rule_start = date.fromisoformat(rule.start)
        rule_end = date.fromisoformat(rule.end)
        if rule_end < cursor:
            continue
        if rule_start > cursor:
            return False
        cursor = max(cursor, rule_end + timedelta(days=1))
        if cursor > target:
            return True
    return cursor > target


def _next_execution_date(all_dates: list[str], decision: str) -> str | None:
    for value in all_dates:
        if value > decision:
            return value
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit realistic B3 inputs. Market-input certification, counterfactual "
            "execution, strategy-selection validity and brokerage-account exactness are "
            "intentionally separate claims."
        )
    )
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--snapshots", type=Path, default=DEFAULT_SNAPSHOTS)
    parser.add_argument("--execution", type=Path, default=DEFAULT_EXECUTION)
    parser.add_argument("--cash-events", type=Path, default=DEFAULT_CASH_EVENTS)
    parser.add_argument("--cash-manifest", type=Path, default=DEFAULT_CASH_MANIFEST)
    parser.add_argument("--cash-certification", type=Path, default=DEFAULT_CASH_CERTIFICATION)
    parser.add_argument("--split-evidence", type=Path, default=DEFAULT_SPLITS)
    parser.add_argument("--transition-manifest", type=Path, default=DEFAULT_TRANSITIONS)
    parser.add_argument("--fee-schedule", type=Path, default=DEFAULT_FEES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    required_inputs = {
        "universe": args.universe,
        "snapshots": args.snapshots,
        "execution": args.execution,
        "cash_events": args.cash_events,
        "cash_manifest": args.cash_manifest,
        "split_evidence": args.split_evidence,
        "fee_schedule": args.fee_schedule,
    }
    missing_inputs = [f"{name}={path}" for name, path in required_inputs.items() if not path.exists()]
    if missing_inputs:
        parser.error(
            "Entradas realistas ausentes. Execute o pipeline de dados antes da auditoria: "
            + ", ".join(missing_inputs)
        )

    checks: dict[str, bool] = {}
    details: dict[str, object] = {}

    universe_payload = json.loads(args.universe.read_text(encoding="utf-8"))
    universe = PointInTimeUniverse.from_csv(args.snapshots)
    expected_union = {str(item).upper() for item in universe_payload.get("tickers", [])}
    market_data = {
        str(item).strip().upper()
        for item in universe_payload.get("market_data_tickers", universe_payload.get("tickers", []))
        if str(item).strip()
    }
    excluded = {
        str(item).strip().upper()
        for item in universe_payload.get("excluded_tickers", [])
        if str(item).strip()
    }
    survivorship_safe = universe_payload.get("survivorship_safe") is True
    no_replacements = universe_payload.get("no_replacements") is True
    tax_instrument_scope = str(universe_payload.get("tax_instrument_scope", "")).strip().upper()

    checks["universe_is_point_in_time"] = universe_payload.get("point_in_time") is True
    checks["universe_declares_survivorship_safe"] = survivorship_safe
    checks["snapshot_union_matches_manifest"] = universe.union == expected_union
    checks["market_data_contains_selectable_universe"] = bool(market_data) and expected_union <= market_data
    checks["excluded_tickers_absent"] = not bool(universe.union & excluded)
    checks["universe_policy_consistent"] = survivorship_safe or no_replacements
    checks["certified_tax_instrument_scope_is_on_pn_shares"] = (
        tax_instrument_scope == "ON_PN_SHARES_ONLY"
    )

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
    if no_replacements:
        checks["snapshot_union_within_allowed_universe"] = bool(allowed_tickers) and universe.union <= allowed_tickers
    else:
        checks["snapshot_union_within_allowed_universe"] = True

    start = str(universe_payload.get("selected_as_of", universe.snapshots[0].effective_date))[:10]
    end = max(snapshot.effective_date for snapshot in universe.snapshots)
    details["audit_start"] = start
    details["audit_end"] = end
    details["snapshot_count"] = len(universe.snapshots)
    details["historical_symbol_union"] = len(universe.union)
    details["market_data_ticker_count"] = len(market_data)
    details["continuity_only_ticker_count"] = len(market_data - expected_union)
    details["minimum_snapshot_size"] = min(len(snapshot.tickers) for snapshot in universe.snapshots)
    details["maximum_snapshot_size"] = max(len(snapshot.tickers) for snapshot in universe.snapshots)
    details["selection_mode"] = universe_payload.get("selection_mode", "")
    details["tax_instrument_scope"] = tax_instrument_scope
    details["excluded_tickers"] = sorted(excluded)
    details["selection_bias_disclosure"] = universe_payload.get("bias_disclosure", "")
    details["allowed_universe_file"] = allowed_file_value
    details["allowed_universe_size"] = len(allowed_tickers)

    split_payload = json.loads(args.split_evidence.read_text(encoding="utf-8"))
    checks["split_markers_fully_covered"] = int(split_payload.get("uncovered_count", -1)) == 0

    cash_payload = json.loads(args.cash_manifest.read_text(encoding="utf-8"))
    checks["cash_response_has_no_parse_issues"] = not bool(cash_payload.get("issues"))
    checks["cash_manifest_matches_market_data_scope"] = (
        int(cash_payload.get("market_data_ticker_count", -1)) == len(market_data)
    )
    details["cash_event_count"] = int(cash_payload.get("event_count", 0))
    details["cash_source"] = cash_payload.get("source", "")
    details["cash_manifest_market_data_ticker_count"] = int(
        cash_payload.get("market_data_ticker_count", -1)
    )

    cash_certified = False
    certification_issues = ["cash coverage certification file is missing"]
    certification: dict[str, object] = {}
    if args.cash_certification.exists():
        certification = json.loads(args.cash_certification.read_text(encoding="utf-8"))
        certification_issues = cash_coverage_certification_issues(
            certification,
            cash_events_path=args.cash_events,
            cash_manifest_path=args.cash_manifest,
            tickers=market_data,
            start=start,
            end=end,
        )
        cash_certified = not certification_issues
    checks["cash_history_coverage_certified"] = cash_certified
    details["cash_certification"] = certification
    details["cash_certification_issues"] = certification_issues

    transition_payload: dict[str, object] = {}
    if args.transition_manifest.exists():
        transition_payload = json.loads(args.transition_manifest.read_text(encoding="utf-8"))
    checks["ticker_transitions_have_no_unresolved_disappearances"] = transition_payload.get("complete") is True
    details["unresolved_historical_disappearances"] = (
        int(transition_payload.get("unresolved_disappearances", -1)) if transition_payload else -1
    )

    fees = FeeSchedule.from_json(args.fee_schedule)
    fee_qualities = sorted({rule.quality for rule in fees.rules})
    checks["all_b3_fee_periods_are_official"] = fee_qualities == ["official"]
    checks["b3_fee_schedule_covers_period"] = _fee_schedule_contiguous(fees, start, end)
    details["fee_qualities"] = fee_qualities

    execution_rows = _rows(args.execution)
    keys: list[tuple[str, str, str]] = []
    standard: set[tuple[str, str]] = set()
    fractional_base: set[tuple[str, str]] = set()
    invalid_execution_rows: list[dict[str, str]] = []
    execution_dates: set[str] = set()
    execution_bases: set[str] = set()
    for row in execution_rows:
        value_date = row.get("date", "")
        ticker = row.get("ticker", "").upper()
        market = row.get("market_type", "")
        keys.append((value_date, ticker, market))
        execution_dates.add(value_date)
        base = ticker[:-1] if ticker.endswith("F") else ticker
        execution_bases.add(base)
        try:
            values_ok = (
                float(row.get("open", 0) or 0) > 0
                and float(row.get("close", 0) or 0) > 0
                and float(row.get("financial_volume", 0) or 0) > 0
            )
        except ValueError:
            values_ok = False
        if not values_ok:
            invalid_execution_rows.append(row)
        if market == "010":
            standard.add((value_date, ticker))
        elif market == "020":
            fractional_base.add((value_date, base))

    checks["execution_book_has_standard_quotes"] = bool(standard)
    checks["execution_book_has_fractional_quotes"] = bool(fractional_base)
    checks["execution_book_has_no_duplicate_keys"] = len(keys) == len(set(keys))
    checks["execution_book_has_positive_prices_and_volume"] = not invalid_execution_rows
    checks["execution_book_excludes_forbidden_tickers"] = not bool(execution_bases & excluded)
    if no_replacements:
        checks["execution_book_within_allowed_universe"] = bool(allowed_tickers) and execution_bases <= allowed_tickers
    else:
        checks["execution_book_within_allowed_universe"] = bool(market_data) and execution_bases <= market_data

    all_execution_dates = sorted(value for value in execution_dates if value)
    missing_next_open: list[str] = []
    for snapshot in universe.snapshots:
        next_date = _next_execution_date(all_execution_dates, snapshot.effective_date)
        if next_date is None:
            continue
        for ticker in snapshot.tickers:
            if (next_date, ticker) not in standard:
                missing_next_open.append(f"{snapshot.effective_date}->{next_date}:{ticker}:010")
            if (next_date, ticker) not in fractional_base:
                missing_next_open.append(f"{snapshot.effective_date}->{next_date}:{ticker}:020")
    checks["snapshot_next_open_execution_coverage_complete"] = not missing_next_open
    details["execution_rows"] = len(execution_rows)
    details["standard_execution_rows"] = len(standard)
    details["fractional_execution_rows"] = len(fractional_base)
    details["invalid_execution_row_count"] = len(invalid_execution_rows)
    details["missing_snapshot_next_open_count"] = len(missing_next_open)
    details["missing_snapshot_next_open_examples"] = missing_next_open[:50]

    structural_account = [
        "universe_is_point_in_time",
        "snapshot_union_matches_manifest",
        "market_data_contains_selectable_universe",
        "universe_policy_consistent",
        "snapshot_union_within_allowed_universe",
        "excluded_tickers_absent",
        "split_markers_fully_covered",
        "cash_response_has_no_parse_issues",
        "cash_manifest_matches_market_data_scope",
        "execution_book_has_standard_quotes",
        "execution_book_has_fractional_quotes",
        "execution_book_has_no_duplicate_keys",
        "execution_book_has_positive_prices_and_volume",
        "execution_book_excludes_forbidden_tickers",
        "execution_book_within_allowed_universe",
    ]
    ready_for_estimate = all(checks[name] for name in structural_account)

    certified_market_requirements = [
        *structural_account,
        "universe_declares_survivorship_safe",
        "certified_tax_instrument_scope_is_on_pn_shares",
        "snapshot_next_open_execution_coverage_complete",
        "cash_history_coverage_certified",
        "ticker_transitions_have_no_unresolved_disappearances",
        "all_b3_fee_periods_are_official",
        "b3_fee_schedule_covers_period",
    ]
    ready_for_certified_market_inputs = all(checks[name] for name in certified_market_requirements)

    selection_validity = (
        "SURVIVORSHIP_SAFE_POINT_IN_TIME"
        if survivorship_safe
        else "RETROSPECTIVE_FIXED_UNIVERSE_ONLY"
    )
    estimate_blockers = [name for name in structural_account if not checks[name]]
    certified_market_blockers = [
        name for name in certified_market_requirements if not checks[name]
    ]

    brokerage_account_requirements = [
        "documentary_opening_snapshot_not_audited_here",
        "documentary_closing_snapshot_not_audited_here",
        "actual_broker_fills_not_audited_here",
        "complete_broker_cash_ledger_not_audited_here",
        "source_hashes_for_brokerage_account_evidence_not_audited_here",
    ]

    selection_limitations = []
    if not survivorship_safe:
        selection_limitations.append("universe_is_fixed_and_not_survivorship_safe")
    if no_replacements:
        selection_limitations.append("candidate_universe_frozen_to_pre_existing_project_list")

    payload = {
        "schema_version": 7,
        "checks": checks,
        "details": details,
        "ready_for_realistic_estimate": ready_for_estimate,
        "ready_for_certified_market_inputs": ready_for_certified_market_inputs,
        "ready_for_exact_historical_account_claim": False,
        "counterfactual_execution_exact": False,
        "selection_validity": selection_validity,
        "ex_ante_selection_claim_allowed": survivorship_safe,
        "estimate_blockers": estimate_blockers,
        "certified_market_input_blockers": certified_market_blockers,
        "exact_brokerage_account_requirements": brokerage_account_requirements,
        # Deprecated compatibility key retained to avoid breaking old readers.
        "exact_personal_account_requirements": brokerage_account_requirements,
        "selection_limitations": selection_limitations,
        "blockers": estimate_blockers,
        "interpretation": (
            "Certified public market inputs make a counterfactual replay reproducible, not "
            "execution-exact. Certified small-account tax scope is restricted to ON/PN "
            "shares. Cash-distribution certification covers the full market_data_tickers "
            "set, including continuity-only historical symbols. Daily COTAHIST does not "
            "prove the fill of a hypothetical order. The exact brokerage-account label is "
            "reserved for reconciliation of actual broker fills, complete cash events and "
            "source-hashed opening/closing broker snapshots."
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
