from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.realistic_certification import transition_binding_issues  # noqa: E402


DEFAULT_STATUS = Path("reports/realistic_pipeline_status.json")
DEFAULT_TRANSITIONS = Path("data/corporate_actions/ticker_transitions.csv")
DEFAULT_TRANSITION_MANIFEST = Path("data/corporate_actions/ticker_transitions.manifest.json")
FREEZE_DATE = "2026-08-19"


def _run(arguments: list[str]) -> None:
    print("+", " ".join(arguments), flush=True)
    subprocess.run(arguments, cwd=ROOT, check=True)


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _account_classification(audit: dict[str, object], summary: dict[str, object]) -> str:
    if summary.get("bonus_tax_basis_affects_realized_gain") is True:
        return "REALISTIC_ACCOUNT_ESTIMATE_WITH_UNCERTIFIED_BONUS_TAX_BASIS"
    return (
        "CERTIFIED_MARKET_INPUTS_COUNTERFACTUAL_REPLAY"
        if audit.get("ready_for_certified_market_inputs")
        else "REALISTIC_ACCOUNT_ESTIMATE_WITH_UNCERTIFIED_INPUTS"
    )


def _source_year_range(start: str, end: str | None) -> str:
    start_year = int(start[:4])
    end_year = int(end[:4]) if end else date.today().year
    if end_year < start_year:
        raise ValueError("--end cannot precede --start")
    return f"{start_year - 1}:{end_year}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "End-to-end realistic B3 validation pipeline. It preserves historical "
            "research artifacts and writes separate point-in-time/real-money-oriented "
            "reports. Public-market counterfactual execution is never labeled exact; "
            "exact brokerage-account reconciliation requires actual broker fills."
        )
    )
    parser.add_argument("--start", default="2018-01-02")
    parser.add_argument("--end")
    parser.add_argument("--initial-cash", type=float, default=1_000.0)
    download_group = parser.add_mutually_exclusive_group()
    download_group.add_argument("--download", dest="download", action="store_true", default=True)
    download_group.add_argument("--no-download", dest="download", action="store_false")
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
    source_years = _source_year_range(args.start, args.end)

    if not args.skip_data_build:
        build = [
            python,
            "scripts/build_survivorship_safe_realistic_universe.py",
            "--start",
            args.start,
            "--years",
            source_years,
            *common_end,
        ]
        if args.download:
            build.append("--download")
        _run(build)

        transitions = [
            python,
            "scripts/build_ticker_transitions.py",
            "--years",
            source_years,
        ]
        if args.download:
            transitions.append("--download")
        _run(transitions)

        sync = [
            python,
            "scripts/sync_point_in_time_universe_realistic.py",
            "--years",
            source_years,
        ]
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

    audit_details = audit.get("details") if isinstance(audit.get("details"), dict) else {}
    audit_end = str(audit_details.get("audit_end", "")) if audit_details else ""
    transition_issues = transition_binding_issues(
        DEFAULT_TRANSITIONS,
        DEFAULT_TRANSITION_MANIFEST,
        expected_end=audit_end or None,
    )
    if transition_issues:
        audit["ready_for_certified_market_inputs"] = False
        existing = [
            str(item) for item in audit.get("certified_market_input_blockers", [])
        ]
        audit["certified_market_input_blockers"] = sorted(
            set([*existing, *transition_issues])
        )
    audit["ticker_transition_binding_issues"] = transition_issues

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
        summary["account_reconstruction_classification"] = _account_classification(
            audit, summary
        )
        summary["ticker_transition_binding_verified"] = not transition_issues
        summary["strategy_selection_classification"] = "RETROSPECTIVE_HYPOTHESIS_REPLAY"
        summary["ex_ante_selection_claim_allowed"] = False
        summary["counterfactual_execution_exact"] = False
        summary["actual_brokerage_account_exact"] = False
        summary["actual_brokerage_account_runner"] = "scripts/reconcile_actual_personal_account.py"
        # Deprecated compatibility aliases for older report readers.
        summary["actual_personal_account_exact"] = False
        summary["actual_personal_account_runner"] = summary["actual_brokerage_account_runner"]
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
                *common_end,
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
    certified_market_inputs = bool(audit.get("ready_for_certified_market_inputs"))
    if any(item.get("bonus_tax_basis_affects_realized_gain") is True for item in runs):
        certified_market_inputs = False
    walk_scope = (
        "full_strategy_and_management_catalog"
        if args.walk_forward_all_strategies
        else "frozen_gap_momentum_managements_only"
    )
    status = {
        "schema_version": 7,
        "initial_cash": args.initial_cash,
        "start": args.start,
        "end": raw.get("end"),
        "source_years": source_years,
        "methodology_frozen_at": FREEZE_DATE,
        "input_audit": audit,
        "ticker_transition_binding_issues": transition_issues,
        "continuous_replay": {
            "selection_status": "RETROSPECTIVE_HYPOTHESIS_REPLAY",
            "ex_ante_selection_claim_allowed": False,
            "counterfactual_execution_exact": False,
            "interpretation": (
                "This answers the conditional question 'what if this frozen rule had "
                "been followed from the start?' It does not prove an exact hypothetical "
                "fill and does not prove the rule could have been selected in 2018 without hindsight."
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
        "certified_market_inputs_ready": certified_market_inputs,
        "conditional_account_reconstruction_exact": False,
        "actual_brokerage_account_reconstruction_exact": False,
        "actual_brokerage_account_runner": "scripts/reconcile_actual_personal_account.py",
        # Deprecated compatibility aliases.
        "actual_personal_account_reconstruction_exact": False,
        "actual_personal_account_runner": "scripts/reconcile_actual_personal_account.py",
        "prospective_selection_validation_begins": FREEZE_DATE,
        "interpretation": (
            "Market-input certification, counterfactual execution, tax-basis completeness "
            "and strategy selection are separate claims. Certified COTAHIST inputs improve "
            "reproducibility but do not prove a hypothetical fill. A sale potentially "
            "affected by a stock bonus remains tax-basis-uncertified until source-backed "
            "bonus cost is provided. Exact brokerage-account reconciliation requires actual "
            "broker fills, cash events and documentary START_OF_DAY/END_OF_DAY snapshots."
        ),
    }
    args.status_output.parent.mkdir(parents=True, exist_ok=True)
    args.status_output.write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Pipeline status: {args.status_output}")
    if certified_market_inputs:
        print("Market inputs: certification gate PASSED; execution remains counterfactual.")
    else:
        print("Market inputs: realistic estimate only; some certifications remain incomplete.")
    print(
        "Exact brokerage-account status: NOT APPLICABLE to public-data backtests; use "
        "scripts/reconcile_actual_personal_account.py with broker-source evidence."
    )
    print(
        "Strategy-selection claim: RETROSPECTIVE for the continuous replay. Use full "
        "walk-forward or unchanged prospective evidence for selection validation."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
