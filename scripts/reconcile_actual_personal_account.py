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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile an actually executed personal account from broker-source fills, "
            "non-trade cash events, position adjustments and documentary opening/closing "
            "broker snapshots. This is the only path allowed to emit an exact "
            "personal-account reconciliation label."
        )
    )
    parser.add_argument("--fills", type=Path, required=True)
    parser.add_argument("--cash-events", type=Path, required=True)
    parser.add_argument("--position-events", type=Path)
    parser.add_argument("--opening-snapshot", type=Path, required=True)
    parser.add_argument("--closing-snapshot", type=Path, required=True)
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
    result = reconcile_actual_account(
        opening_snapshot=opening_snapshot,
        closing_snapshot=closing_snapshot,
        fills=fills,
        cash_events=cash_events,
        position_events=position_events,
    )
    payload = result.as_dict()
    payload["inputs"] = {
        "fills": str(args.fills),
        "cash_events": str(args.cash_events),
        "position_events": str(args.position_events) if args.position_events else None,
        "opening_snapshot": str(args.opening_snapshot),
        "closing_snapshot": str(args.closing_snapshot),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if result.exact else 5


if __name__ == "__main__":
    raise SystemExit(main())
