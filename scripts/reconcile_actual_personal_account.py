from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
            "broker snapshots. Every referenced source file is SHA-256 verified. This is "
            "the only path allowed to emit an exact personal-account reconciliation label."
        )
    )
    parser.add_argument("--fills", type=Path, required=True)
    parser.add_argument("--cash-events", type=Path, required=True)
    parser.add_argument("--position-events", type=Path)
    parser.add_argument("--opening-snapshot", type=Path, required=True)
    parser.add_argument("--closing-snapshot", type=Path, required=True)
    parser.add_argument(
        "--evidence-root",
        type=Path,
        required=True,
        help="Private directory containing the original broker files referenced by source_document.",
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
    evidence = verify_source_documents(args.evidence_root, evidence_records)

    result = reconcile_actual_account(
        opening_snapshot=opening_snapshot,
        closing_snapshot=closing_snapshot,
        fills=fills,
        cash_events=cash_events,
        position_events=position_events,
    )
    ledger = result.as_dict()
    evidence_blockers = [str(item) for item in evidence.get("blockers", [])]
    all_blockers = sorted(set([*result.blockers, *evidence_blockers]))
    exact = result.exact and evidence.get("verified") is True and not all_blockers

    payload = {
        **ledger,
        "classification": (
            "ACTUAL_PERSONAL_ACCOUNT_EXACT_RECONCILIATION"
            if exact
            else "ACTUAL_PERSONAL_ACCOUNT_RECONCILIATION_REJECTED"
        ),
        "exact": exact,
        "blockers": all_blockers,
        "source_evidence": evidence,
        "inputs": {
            "fills": str(args.fills),
            "cash_events": str(args.cash_events),
            "position_events": str(args.position_events) if args.position_events else None,
            "opening_snapshot": str(args.opening_snapshot),
            "closing_snapshot": str(args.closing_snapshot),
            "evidence_root": str(args.evidence_root),
        },
        "exactness_contract": (
            "The exact label is emitted only when the normalized broker ledger reconciles "
            "cash to the cent and positions exactly AND every referenced source document "
            "exists under evidence_root with the declared SHA-256. No market price, fee, "
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
