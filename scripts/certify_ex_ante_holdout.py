from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.ex_ante_validation import (  # noqa: E402
    build_holdout_validation_report,
    sha256_file,
)


DEFAULT_FROZEN = Path("reports/FROZEN_CANDIDATE.json")
DEFAULT_REALISTIC = Path("reports/EX_ANTE_HOLDOUT_REALISTIC.json")
DEFAULT_PIT_AUDIT = Path("reports/POINT_IN_TIME_VALIDATION.json")
DEFAULT_OUTPUT = Path("reports/EX_ANTE_HOLDOUT_VALIDATION.json")


def _read(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Certify a single frozen candidate on one untouched historical holdout. "
            "This command never reranks candidates and never permits fallback after "
            "observing holdout performance."
        )
    )
    parser.add_argument("--frozen-candidate", type=Path, default=DEFAULT_FROZEN)
    parser.add_argument("--realistic-summary", type=Path, default=DEFAULT_REALISTIC)
    parser.add_argument("--pit-audit", type=Path, default=DEFAULT_PIT_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    for path in (args.frozen_candidate, args.realistic_summary, args.pit_audit):
        if not path.is_file():
            parser.error(f"Required input does not exist: {path}")

    report = build_holdout_validation_report(
        frozen=_read(args.frozen_candidate),
        realistic_summary=_read(args.realistic_summary),
        pit_audit=_read(args.pit_audit),
        source_bindings={
            "frozen_candidate": sha256_file(args.frozen_candidate),
            "realistic_summary": sha256_file(args.realistic_summary),
            "pit_audit": sha256_file(args.pit_audit),
        },
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Ex-ante holdout validation: {report['status']} -> {args.output}", flush=True)
    if report["status"] != "PASS":
        for issue in report["issues"]:
            print(f"BLOCKER {issue}", flush=True)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
