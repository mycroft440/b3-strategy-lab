from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.reconstruction_quality import (  # noqa: E402
    CERTIFIED_EXECUTION_POLICY,
    BrokerProfile,
    certified_replay_blockers,
    write_composite_fee_schedule,
)
from b3_strategy_lab.replay_scope import audit_small_account_replay  # noqa: E402


# File name retained for backward compatibility. This runner no longer emits an
# "exact" label: public daily COTAHIST cannot prove the fill of a hypothetical
# order in the opening auction. Exact labels are reserved for broker-source fills.
DEFAULT_B3_FEES = Path("data/fees/b3_equity_fee_schedule.json")
DEFAULT_EXECUTION = Path("data/execution/b3_standard_fractional_open.csv")
DEFAULT_AUDIT = Path("reports/certified_replay_input_audit.json")
DEFAULT_STATUS = Path("reports/certified_replay_status.json")
DEFAULT_SUMMARY = Path("reports/certified_replay_summary.json")
DEFAULT_CURVE = Path("reports/certified_replay_curve.csv")
DEFAULT_TRADES = Path("reports/certified_replay_trades.csv")
DEFAULT_DISTRIBUTIONS = Path("reports/certified_replay_distributions.csv")
DEFAULT_TAX = Path("reports/certified_replay_tax.csv")


def _run(arguments: list[str]) -> None:
    print("+", " ".join(arguments), flush=True)
    subprocess.run(arguments, cwd=ROOT, check=True)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _execution_end(path: Path, requested_end: str | None) -> str:
    dates: list[str] = []
    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            value = str(row.get("date", ""))[:10]
            if value and (requested_end is None or value <= requested_end):
                dates.append(value)
    if not dates:
        raise ValueError("Execution book has no date in the requested period.")
    return max(dates)


def _normalized_certified_validity(summary: dict[str, object]) -> str:
    engine_validity = str(summary.get("validity", ""))
    if str(summary.get("fee_quality", "")) == "certified":
        return engine_validity.replace("__MODELED_FEES", "__CERTIFIED_COMPOSITE_FEES")
    return engine_validity


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fail-closed certified deterministic B3 counterfactual replay. It uses a "
            "survivorship-safe historical universe, official B3 opening prices, certified "
            "cash/split/transition inputs, zero modeled slippage and a certified broker "
            "fee profile. It does NOT claim an exact hypothetical fill."
        )
    )
    parser.add_argument("--broker-profile", type=Path, required=True)
    parser.add_argument("--strategy", default="gap_momentum")
    parser.add_argument(
        "--management",
        default="top1_momentum_lb63_skip0_trend0_vol21_equal_weekly_abs_cap1_adjusted",
    )
    parser.add_argument("--start", default="2018-01-02")
    parser.add_argument("--end")
    parser.add_argument("--initial-cash", type=float, default=1_000.0)
    parser.add_argument("--skip-data-build", action="store_true")
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument("--refresh-actions", action="store_true")
    parser.add_argument("--b3-fee-schedule", type=Path, default=DEFAULT_B3_FEES)
    parser.add_argument("--execution-prices", type=Path, default=DEFAULT_EXECUTION)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--status-output", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--output", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args(argv)

    if args.initial_cash <= 0:
        parser.error("--initial-cash must be positive.")
    python = sys.executable

    if not args.skip_data_build:
        builder = [
            python,
            "scripts/build_survivorship_safe_realistic_universe.py",
            "--start",
            args.start,
        ]
        if args.end:
            builder.extend(["--end", args.end])
        if not args.no_download:
            builder.append("--download")
        _run(builder)

        transitions = [python, "scripts/build_ticker_transitions.py"]
        if not args.no_download:
            transitions.append("--download")
        _run(transitions)

        sync = [python, "scripts/sync_point_in_time_universe_realistic.py"]
        if not args.no_download:
            sync.append("--download")
        if args.refresh_actions:
            sync.append("--refresh-actions")
        _run(sync)

    audit_command = [
        python,
        "scripts/audit_realistic_backtest_inputs.py",
        "--output",
        str(args.audit_output),
    ]
    audit_proc = subprocess.run(audit_command, cwd=ROOT, check=False)
    if audit_proc.returncode not in {0, 2} or not args.audit_output.exists():
        raise RuntimeError("Realistic input audit did not complete correctly.")
    audit = _read_json(args.audit_output)

    end = _execution_end(args.execution_prices, args.end)
    profile = BrokerProfile.from_json(args.broker_profile)
    preflight_blockers = certified_replay_blockers(
        audit,
        profile,
        start=args.start,
        end=end,
        execution_policy=CERTIFIED_EXECUTION_POLICY,
        base_slippage_bps=0.0,
        participation_bps_at_1pct=0.0,
        max_slippage_bps=0.0,
    )

    status: dict[str, object] = {
        "schema_version": 3,
        "start": args.start,
        "end": end,
        "initial_cash": args.initial_cash,
        "execution_policy": CERTIFIED_EXECUTION_POLICY,
        "market_input_audit": str(args.audit_output),
        "broker_profile": str(args.broker_profile),
        "preflight_passed": not preflight_blockers,
        "strict_blockers": preflight_blockers,
        "certified_deterministic_replay_passed": False,
        "counterfactual_execution_exact": False,
        "strategy_selection_status": "RETROSPECTIVE_HYPOTHESIS_REPLAY",
        "actual_personal_account_reconstruction_exact": False,
        "actual_personal_account_runner": "scripts/reconcile_actual_personal_account.py",
        "interpretation": (
            "The public-data runner can certify its inputs and deterministic official-open "
            "assumption. It cannot prove the exact fill of a hypothetical order. Only the "
            "broker-source reconciliation runner may emit an exact personal-account label."
        ),
    }
    args.status_output.parent.mkdir(parents=True, exist_ok=True)
    args.status_output.write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if preflight_blockers:
        print(json.dumps(status, indent=2, ensure_ascii=False))
        print("Certified replay refused; resolve every preflight blocker above.", flush=True)
        return 3

    composite_fees = Path("reports/certified_composite_fee_schedule.json")
    write_composite_fee_schedule(
        b3_fee_schedule=args.b3_fee_schedule,
        broker_profile=profile,
        start=args.start,
        end=end,
        output=composite_fees,
    )

    command = [
        python,
        "scripts/backtest_strategy_management_realistic.py",
        "--strategy",
        args.strategy,
        "--management",
        args.management,
        "--start",
        args.start,
        "--end",
        end,
        "--initial-cash",
        str(args.initial_cash),
        "--base-slippage-bps",
        "0",
        "--participation-bps-at-1pct",
        "0",
        "--max-slippage-bps",
        "0",
        "--fee-schedule",
        str(composite_fees),
        "--selection-status",
        "retrospective_hypothesis_replay",
        "--output",
        str(args.output),
        "--curve-output",
        str(DEFAULT_CURVE),
        "--trades-output",
        str(DEFAULT_TRADES),
        "--cash-ledger-output",
        str(DEFAULT_DISTRIBUTIONS),
        "--tax-output",
        str(DEFAULT_TAX),
    ]
    if args.strategy.strip().lower() == "gap_momentum":
        command.append("--economic-gap-adjustment")
    _run(command)

    summary = _read_json(args.output)
    replay_scope = audit_small_account_replay(DEFAULT_CURVE, DEFAULT_TRADES)
    postflight_blockers = list(replay_scope["blockers"])
    if summary.get("survivorship_safe") is not True:
        postflight_blockers.append("backtest_summary_is_not_survivorship_safe")
    if summary.get("point_in_time_universe") is not True:
        postflight_blockers.append("backtest_summary_is_not_point_in_time")
    if summary.get("cash_events_complete") is not True:
        postflight_blockers.append("backtest_summary_cash_events_are_not_certified")
    if str(summary.get("fee_quality", "")) != "certified":
        postflight_blockers.append("backtest_summary_fee_schedule_is_not_certified")
    if args.strategy.strip().lower() == "gap_momentum" and summary.get("economic_gap_adjustment") is not True:
        postflight_blockers.append("gap_momentum_requires_economic_gap_adjustment")
    postflight_blockers = sorted(set(postflight_blockers))

    engine_validity = str(summary.get("validity", ""))
    summary["engine_validity"] = engine_validity
    summary["validity"] = _normalized_certified_validity(summary)
    summary["small_account_scope"] = replay_scope
    summary["modeled_slippage"] = False
    summary["certified_broker_fees"] = True
    summary["execution_policy"] = CERTIFIED_EXECUTION_POLICY
    summary["strategy_selection_status"] = "RETROSPECTIVE_HYPOTHESIS_REPLAY"
    summary["counterfactual_execution_exact"] = False
    summary["actual_personal_account_exact"] = False
    summary["actual_personal_account_requires"] = [
        "documentary opening and closing broker snapshots",
        "actual broker order/fill records with source hashes",
        "complete broker cash ledger including fees, taxes and distributions",
        "source-backed corporate-action position adjustments when applicable",
    ]

    if postflight_blockers:
        all_blockers = sorted(set(preflight_blockers + postflight_blockers))
        summary["reconstruction_classification"] = "CERTIFIED_REPLAY_REJECTED"
        summary["strict_blockers"] = all_blockers
        args.output.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        status["postflight_passed"] = False
        status["strict_blockers"] = all_blockers
        status["small_account_scope"] = replay_scope
        status["summary"] = str(args.output)
        args.status_output.write_text(
            json.dumps(status, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(status, indent=2, ensure_ascii=False))
        print("Certified deterministic replay rejected after postflight audit.", flush=True)
        return 4

    summary.update(
        {
            "reconstruction_classification": "CERTIFIED_DETERMINISTIC_OFFICIAL_OPEN_REPLAY",
            "strict_blockers": [],
            "survivorship_safe_universe_required": True,
        }
    )
    args.output.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    status["postflight_passed"] = True
    status["strict_blockers"] = []
    status["small_account_scope"] = replay_scope
    status["summary"] = str(args.output)
    status["final_equity"] = summary.get("final_equity")
    status["certified_deterministic_replay_passed"] = True
    args.status_output.write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(status, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
