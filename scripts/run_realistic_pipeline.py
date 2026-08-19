from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATUS = Path("reports/realistic_pipeline_status.json")
FREEZE_DATE = "2026-08-19"


def _run(arguments: list[str]) -> None:
    print("+", " ".join(arguments), flush=True)
    subprocess.run(arguments, cwd=ROOT, check=True)


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _account_classification(audit: dict[str, object]) -> str:
    return (
        "EXACT_CONDITIONAL_ACCOUNT_RECONSTRUCTION"
        if audit.get("ready_for_exact_historical_account_claim")
        else "REALISTIC_ACCOUNT_ESTIMATE_NOT_EXACT"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "End-to-end realistic B3 validation pipeline. It preserves historical "
            "research artifacts and writes separate point-in-time/real-money-oriented "
            "reports. Account reconstruction quality and strategy-selection evidence "
            "are reported separately."
        )
    )
    parser.add_argument("--start", default="2018-01-02")
    parser.add_argument("--end")
    parser.add_argument("--initial-cash", type=float, default=1_000.0)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--refresh-actions", action="store_true")
    parser.add_argument("--skip-data-build", action="store_true")
    parser.add_argument("--skip-walk-forward", action="store_true")
    parser.add_argument(
        "--walk-forward-all-strategies",
        action="store_true",
        help=(
            "Use every strategy and every management config in each training fold. "
            "This is expensive but addresses the original across-strategy multiple-"
            "testing selection scope. Without it, walk-forward validates the frozen "
            "Gap Momentum hypothesis only across management choices."
        ),
    )
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

        sync = [python, "scripts/sync_point_in_time_universe_realistic.py"]
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

    runs: list[dict[str, object]] = []
    for label, economic in (("raw_gap", False), ("economic_gap", True)):
        summary_path = Path(f"reports/realistic_{label}_summary.json")
        command = [
            python,
            "scripts/backtest_strategy_management_realistic.py",
            "--start",
            args.start,
            "--initial-cash",
            str(args.initial_cash),
            "--selection-status",
            "retrospective_hypothesis_replay",
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
        summary["account_reconstruction_classification"] = _account_classification(audit)
        summary["strategy_selection_classification"] = "RETROSPECTIVE_HYPOTHESIS_REPLAY"
        summary["ex_ante_selection_claim_allowed"] = False
        summary["input_audit"] = str(audit_path)
        summary_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        runs.append({"label": label, **summary})

    walk_forward_reports: dict[str, object] = {}
    if not args.skip_walk_forward:
        for label, economic in (("raw_gap", False), ("economic_gap", True)):
            output = Path(f"reports/realistic_walk_forward_{label}.csv")
            summary_output = Path(f"reports/realistic_walk_forward_{label}_summary.json")
            walk = [
                python,
                "scripts/walk_forward_realistic.py",
                "--start",
                args.start,
                "--first-test-year",
                str(args.first_test_year),
                "--initial-cash",
                str(args.initial_cash),
                "--output",
                str(output),
                "--summary-output",
                str(summary_output),
            ]
            if args.walk_forward_all_strategies:
                walk.append("--all-strategies")
            if economic:
                walk.append("--economic-gap-adjustment")
            _run(walk)
            walk_forward_reports[label] = {
                "csv": str(output),
                "summary": _read(summary_output),
            }

    raw = next(item for item in runs if item["label"] == "raw_gap")
    economic = next(item for item in runs if item["label"] == "economic_gap")
    exact_conditional = bool(audit.get("ready_for_exact_historical_account_claim"))
    walk_scope = (
        "full_strategy_and_management_catalog"
        if args.walk_forward_all_strategies
        else "frozen_gap_momentum_managements_only"
    )
    status = {
        "schema_version": 3,
        "initial_cash": args.initial_cash,
        "start": args.start,
        "end": raw.get("end"),
        "methodology_frozen_at": FREEZE_DATE,
        "input_audit": audit,
        "continuous_replay": {
            "selection_status": "RETROSPECTIVE_HYPOTHESIS_REPLAY",
            "ex_ante_selection_claim_allowed": False,
            "interpretation": (
                "This answers the conditional question 'what if this exact frozen rule "
                "had been followed from the start?' It does not prove the rule could "
                "have been selected in 2018 without hindsight."
            ),
            "raw_gap": raw,
            "economic_gap": economic,
        },
        "walk_forward": {
            "requested_selection_scope": walk_scope,
            "full_multiple_testing_scope_requested": args.walk_forward_all_strategies,
            "reports": walk_forward_reports,
        },
        "gap_signal_sensitivity": {
            "final_equity_difference": float(raw["final_equity"]) - float(economic["final_equity"]),
            "total_return_difference": float(raw["total_return"]) - float(economic["total_return"]),
        },
        "conditional_account_reconstruction_exact": exact_conditional,
        "prospective_selection_validation_begins": FREEZE_DATE,
        "interpretation": (
            "Account reconstruction quality and strategy selection are separate claims. "
            "The economic-gap run removes known split-normalized cash-distribution "
            "mechanics from Gap Momentum signal construction. Gap-only walk-forward "
            "tests management selection within the frozen hypothesis; full across-"
            "strategy selection is tested only when --walk-forward-all-strategies is used. "
            "Data after the freeze can provide prospective evidence if no rules change."
        ),
    }
    args.status_output.parent.mkdir(parents=True, exist_ok=True)
    args.status_output.write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Pipeline status: {args.status_output}")
    if exact_conditional:
        print("Conditional account reconstruction: exact-input audit PASSED.")
    else:
        print(
            "Conditional account reconstruction: ESTIMATE ONLY; remaining input "
            "certifications still block an exact-account statement."
        )
    print(
        "2018 strategy-selection claim: RETROSPECTIVE only. For the original full "
        "multiple-testing scope, run with --walk-forward-all-strategies; prospective "
        "evidence starts after 2026-08-19 if the freeze is unchanged."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
