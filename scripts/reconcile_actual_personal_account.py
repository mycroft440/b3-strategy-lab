from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.evidence_coverage import load_and_audit_coverage  # noqa: E402
from b3_strategy_lab.personal_account import (  # noqa: E402
    CashEvent,
    load_actual_fills,
    load_cash_events,
    load_position_events,
    load_snapshot,
    reconcile_actual_account,
)
from b3_strategy_lab.source_evidence import verify_source_documents  # noqa: E402


def _merge_requirement(
    requirements: dict[str, set[str]],
    source_document: str,
    allowed: set[str],
) -> None:
    previous = requirements.get(source_document)
    requirements[source_document] = set(allowed) if previous is None else previous & allowed


def _cash_source_kinds(event: CashEvent) -> set[str]:
    if event.kind in {"B3_FEE", "BROKER_FEE"}:
        return {"trade_note", "account_statement"}
    if event.kind == "TAX":
        return {"tax_document", "account_statement"}
    if event.kind == "OTHER_CERTIFIED":
        return {"other_source", "account_statement"}
    return {"account_statement"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile an actually executed brokerage account from source-backed fills, "
            "cash movements, position adjustments and START_OF_DAY/END_OF_DAY snapshots. "
            "Exact classification requires ledger reconciliation, compatible source types, "
            "source-byte verification, continuous statement coverage, and a reviewed "
            "normalization attestation bound to the exact normalized input files."
        )
    )
    parser.add_argument("--fills", type=Path, required=True)
    parser.add_argument("--cash-events", type=Path, required=True)
    parser.add_argument("--position-events", type=Path)
    parser.add_argument("--opening-snapshot", type=Path, required=True)
    parser.add_argument("--closing-snapshot", type=Path, required=True)
    parser.add_argument("--coverage-manifest", type=Path, required=True)
    parser.add_argument(
        "--evidence-root",
        type=Path,
        required=True,
        help="Private directory containing original files referenced by source_document.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/actual_personal_account_reconciliation.json"),
    )
    args = parser.parse_args(argv)

    fills = load_actual_fills(args.fills)
    cash_events = load_cash_events(args.cash_events)
    position_events = (
        load_position_events(args.position_events) if args.position_events else []
    )
    opening_snapshot = load_snapshot(args.opening_snapshot)
    closing_snapshot = load_snapshot(args.closing_snapshot)

    evidence_records: list[object] = [opening_snapshot, closing_snapshot]
    evidence_records.extend(fills)
    evidence_records.extend(cash_events)
    evidence_records.extend(position_events)
    source_evidence = verify_source_documents(args.evidence_root, evidence_records)

    normalized_inputs: dict[str, Path] = {
        "fills": args.fills,
        "cash_events": args.cash_events,
        "opening_snapshot": args.opening_snapshot,
        "closing_snapshot": args.closing_snapshot,
    }
    if args.position_events:
        normalized_inputs["position_events"] = args.position_events

    source_kind_requirements: dict[str, set[str]] = {}
    _merge_requirement(
        source_kind_requirements,
        opening_snapshot.source_document,
        {"account_statement"},
    )
    _merge_requirement(
        source_kind_requirements,
        closing_snapshot.source_document,
        {"account_statement"},
    )
    for fill in fills:
        _merge_requirement(
            source_kind_requirements,
            fill.source_document,
            {"trade_note", "account_statement"},
        )
    for event in cash_events:
        _merge_requirement(
            source_kind_requirements,
            event.source_document,
            _cash_source_kinds(event),
        )
    for event in position_events:
        _merge_requirement(
            source_kind_requirements,
            event.source_document,
            {"corporate_action_notice", "account_statement"},
        )

    coverage = load_and_audit_coverage(
        args.coverage_manifest,
        evidence_root=args.evidence_root,
        required_start=opening_snapshot.value_date,
        required_end=closing_snapshot.value_date,
        normalized_records=evidence_records,
        normalized_inputs=normalized_inputs,
        source_kind_requirements=source_kind_requirements,
    )

    result = reconcile_actual_account(
        opening_snapshot=opening_snapshot,
        closing_snapshot=closing_snapshot,
        fills=fills,
        cash_events=cash_events,
        position_events=position_events,
    )
    ledger = result.as_dict()
    all_blockers = sorted(
        set(
            [
                *result.blockers,
                *[str(item) for item in source_evidence.get("blockers", [])],
                *[str(item) for item in coverage.get("blockers", [])],
            ]
        )
    )
    exact = (
        result.ledger_reconciles
        and source_evidence.get("verified") is True
        and coverage.get("verified") is True
        and not all_blockers
    )

    payload = {
        **ledger,
        "classification": (
            "ACTUAL_BROKERAGE_ACCOUNT_EXACT_RECONCILIATION"
            if exact
            else "ACTUAL_BROKERAGE_ACCOUNT_RECONCILIATION_REJECTED"
        ),
        "exact": exact,
        "blockers": all_blockers,
        "source_evidence": source_evidence,
        "coverage_audit": coverage,
        "inputs": {
            "fills": str(args.fills),
            "cash_events": str(args.cash_events),
            "position_events": str(args.position_events) if args.position_events else None,
            "opening_snapshot": str(args.opening_snapshot),
            "closing_snapshot": str(args.closing_snapshot),
            "coverage_manifest": str(args.coverage_manifest),
            "evidence_root": str(args.evidence_root),
        },
        "exactness_contract": (
            "The exact label applies to the reconstructed brokerage-account ledger only. "
            "It is emitted only when cash reconciles to the cent, positions reconcile "
            "exactly, each record is backed by a compatible document type, every source "
            "matches its SHA-256, account statements cover the entire period without gaps, "
            "and a reviewed normalization attestation is SHA-256-bound to every normalized "
            "input consumed by this run. It is not a claim about hypothetical fills, "
            "CPF-wide taxes paid outside the brokerage account, or total personal wealth."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if exact else 5


if __name__ == "__main__":
    raise SystemExit(main())
