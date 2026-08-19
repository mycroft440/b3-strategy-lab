from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATUS = Path("reports/realistic_pipeline_status.json")


def _run(arguments: list[str]) -> None:
    print("+", " ".join(arguments), flush=True)
    subprocess.run(arguments, cwd=ROOT, check=True)


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "End-to-end realistic B3 validation pipeline. It preserves historical "
            "research artifacts and writes separate point-in-time/real-money-oriented "
            "reports. Exact-account wording is prohibited unless the input audit says so."
        )
    )
    parser.add_argument("--start", default="2018-01-02")
    parser.add_argument("--end")
    parser.add_argument("--initial-cash", type=float, default=1_000.0)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--refresh-actions", action="store_true")
    parser.add_argument("--skip-data-build", action="store_true")
    parser.add_argument("--skip-walk-forward", action="store_true")
    parser.add_argument("--first-test-year", type=int, default=2021)
    parser.add_argument("--status-output", type=Path, default=DEFAULT_STATUS)
    args = parser.parse_args(argv)

    python = sys.executable
    common_end = ["--end", args.end] if args.end else []

    if not args.skip_data_build:
        build = [
            python,
            "scripts/build_point_in_time_universe.py",
            "--start",
            args.start,
            *common_end,
        ]
        if args.download:
            build.append("--download")
        _run(build)

        transitions = [python, "scripts/build_ticker_transitions.py"]
        if args.download:
            transitions.append("--download")
        _run(transitions)

        sync = [python, "scripts/sync_point_in_time_universe.py"]
        if args.download:
            sync.append("--download")
        if args.refresh_actions:
            sync.append("--refresh-actions")
        _run(sync)

    audit_path = Path("reports/realistic_input_audit.json")
    audit_proc = subprocess.run(
        [python, "scripts/audit_realistic_backtest_inputs.py"],
        cwd=ROOT,
        check=False,
    )
    if not audit_path.exists():
        raise RuntimeError("Input audit did not produce its report.")
    audit = _read(audit_path)
    if not audit.get("ready_for_realistic_estimate"):
        raise RuntimeError(
            "Realistic input audit failed; refusing to run a portfolio estimate. "
            f"Blockers: {audit.get('blockers', [])}"
        )
    if audit_proc.returncode not in {0, 2}:
        raise RuntimeError(f"Input audit exited with {audit_proc.returncode}.")

    runs = []
    for label, economic in (("raw_gap", False), ("economic_gap", True)):
        summary_path = Path(f"reports/realistic_{label}_summary.json")
        command = [
            python,
            "scripts/backtest_strategy_management_realistic.py",
            "--start",
            args.start,
            "--initial-cash",
            str(args.initial_cash),
            "--output",
            str(summary_path),
            "--curve-output",
            f"reports/realistic_{label}_curve.csv",
            "--trades-output",
            f"reports/realistic_{label}_trades.csv",
            "--cash-ledger-output",
            f"reports/realistic_{label}_distributions.csv",
            "--tax-output",
            f"reports/realistic_{label}_tax.csv",
            *common_end,
        ]
        if economic:
            command.append("--economic-gap-adjustment")
        _run(command)
        summary = _read(summary_path)
        summary["claim_classification"] = (
            "EXACT_HISTORICAL_ACCOUNT_RECONSTRUCTION"
            if audit.get("ready_for_exact_historical_account_claim")
            else "REALISTIC_ESTIMATE_NOT_EXACT_ACCOUNT_CLAIM"
        )
        summary["input_audit"] = str(audit_path)
        summary_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        runs.append({"label": label, **summary})

    if not args.skip_walk_forward:
        walk = [
            python,
            "scripts/walk_forward_realistic.py",
            "--start",
            args.start,
            "--first-test-year",
            str(args.first_test_year),
            "--initial-cash",
            str(args.initial_cash),
        ]
        _run(walk)

    raw = next(item for item in runs if item["label"] == "raw_gap")
    economic = next(item for item in runs if item["label"] == "economic_gap")
    status = {
        "schema_version": 1,
        "initial_cash": args.initial_cash,
        "start": args.start,
        "end": raw.get("end"),
        "input_audit": audit,
        "raw_gap": raw,
        "economic_gap": economic,
        "gap_signal_sensitivity": {
            "final_equity_difference": float(raw["final_equity"]) - float(economic["final_equity"]),
            "total_return_difference": float(raw["total_return"]) - float(economic["total_return"]),
        },
        "exact_account_claim_allowed": bool(
            audit.get("ready_for_exact_historical_account_claim")
        ),
        "interpretation": (
            "The economic-gap run removes known cash-distribution mechanical gaps "
            "from Gap Momentum signal construction. The raw-gap run preserves actual "
            "quoted openings. Large divergence is a warning that the strategy depends "
            "materially on ex-distribution price mechanics."
        ),
    }
    args.status_output.parent.mkdir(parents=True, exist_ok=True)
    args.status_output.write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Pipeline status: {args.status_output}")
    if status["exact_account_claim_allowed"]:
        print("Exact historical-account claim: ALLOWED by current input audit.")
    else:
        print(
            "Exact historical-account claim: NOT ALLOWED; outputs are realistic estimates "
            "until the remaining input certifications are completed."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
