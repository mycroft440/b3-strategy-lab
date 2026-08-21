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
    load_actual_fills,
    load_cash_events,
    load_position_events,
    load_snapshot,
    reconcile_actual_account,
)
from b3_strategy_lab.source_evidence import verify_source_documents  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile an actually executed personal account from broker-source fills, "
            "non-trade cash events, position adjustments and documentary opening/closing "
            "broker snapshots. Exact classification requires ledger reconciliation, source "
            "byte verification, continuous statement coverage, and a reviewed normalization "
            "attestation bound to the exact normalized input files."
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

    coverage = load_and_audit_coverage(
        args.coverage_manifest,
        evidence_root=args.evidence_root,
        required_start=opening_snapshot.value_date,
        required_end=closing_snapshot.value_date,
        normalized_records=evidence_records,
        normalized_inputs=normalized_inputs,
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
            "ACTUAL_PERSONAL_ACCOUNT_EXACT_RECONCILIATION"
            if exact
            else "ACTUAL_PERSONAL_ACCOUNT_RECONCILIATION_REJECTED"
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
            "The exact label is emitted only when the normalized broker ledger reconciles "
            "cash to the cent and positions exactly, every referenced source document "
            "matches its SHA-256, account-statement evidence covers the entire period "
            "without date gaps, and a reviewed normalization attestation is bound by "
            "SHA-256 to every normalized input consumed by this run. No market price, fee, "
            "tax or corporate-action quantity is inferred in this path."
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
