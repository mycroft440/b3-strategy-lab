from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.ex_ante_validation import (  # noqa: E402
    build_frozen_candidate,
    build_prospective_freeze,
    sha256_file,
)


DEFAULT_CANDIDATES = Path("reports/TOP_10.json")
DEFAULT_MATRIX_MANIFEST = Path(
    "reports/strategy_management_combinations_40_adjusted_no_dividends_1d.manifest.json"
)
DEFAULT_PIT_AUDIT = Path("reports/POINT_IN_TIME_VALIDATION.json")
DEFAULT_OUTPUT = Path("reports/FROZEN_CANDIDATE.json")


def _read(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze exactly one rank-1 candidate. By default the freeze is prospective: "
            "all already-seen history is treated only as research and future validation "
            "must begin after the wall-clock freeze. A historical holdout may be supplied "
            "only when the freeze itself demonstrably predates that holdout."
        )
    )
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--matrix-manifest", type=Path, default=DEFAULT_MATRIX_MANIFEST)
    parser.add_argument("--pit-audit", type=Path, default=DEFAULT_PIT_AUDIT)
    parser.add_argument("--holdout-start")
    parser.add_argument("--holdout-end")
    parser.add_argument("--frozen-at-utc")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    if bool(args.holdout_start) != bool(args.holdout_end):
        parser.error("--holdout-start and --holdout-end must be supplied together.")
    for path in (args.candidates, args.matrix_manifest, args.pit_audit):
        if not path.is_file():
            parser.error(f"Required input does not exist: {path}")

    source_bindings = {
        "candidates": sha256_file(args.candidates),
        "matrix_manifest": sha256_file(args.matrix_manifest),
        "pit_audit": sha256_file(args.pit_audit),
    }
    common = {
        "candidates": _read(args.candidates),
        "matrix_manifest": _read(args.matrix_manifest),
        "pit_audit": _read(args.pit_audit),
        "source_bindings": source_bindings,
        "frozen_at_utc": args.frozen_at_utc,
    }
    if args.holdout_start:
        frozen = build_frozen_candidate(
            **common,
            holdout_start=args.holdout_start,
            holdout_end=args.holdout_end,
        )
    else:
        frozen = build_prospective_freeze(**common)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(frozen, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        "Frozen candidate: "
        f"{frozen['candidate']['trading_strategy']} + "
        f"{frozen['candidate']['management_strategy']} "
        f"[{frozen['status']}] -> {args.output}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
