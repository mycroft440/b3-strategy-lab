from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.ex_ante_validation import (  # noqa: E402
    canonical_sha256,
    point_in_time_contract_issues,
    sha256_file,
)
from b3_strategy_lab.realistic import cash_coverage_certification_issues  # noqa: E402
from b3_strategy_lab.realistic_certification import transition_binding_issues  # noqa: E402
from scripts.backtest_strategy_management_realistic import (  # noqa: E402
    DEFAULT_ACTIONS,
    DEFAULT_CASH_CERTIFICATION,
    DEFAULT_CASH_EVENTS,
    DEFAULT_CASH_MANIFEST,
    DEFAULT_DATA,
    DEFAULT_MANIFESTS,
    DEFAULT_SNAPSHOTS,
    DEFAULT_SPLIT_EVIDENCE,
    DEFAULT_TRANSITIONS,
    DEFAULT_TRANSITION_MANIFEST,
    DEFAULT_UNIVERSE,
)
from scripts.research_portfolio_allocation import MarketData  # noqa: E402


DEFAULT_OUTPUT = Path("reports/POINT_IN_TIME_VALIDATION.json")


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _snapshot_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def _binding(path: Path) -> str:
    return sha256_file(path) if path.is_file() else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fail-closed audit proving that the historical information set is point-in-time. "
            "This gate validates universe snapshots, isolated PIT storage, verified market "
            "data, cash-event publication timing and ticker-transition binding."
        )
    )
    parser.add_argument("--universe-manifest", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--snapshots", type=Path, default=DEFAULT_SNAPSHOTS)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--actions-dir", type=Path, default=DEFAULT_ACTIONS)
    parser.add_argument("--manifests-dir", type=Path, default=DEFAULT_MANIFESTS)
    parser.add_argument("--split-evidence", type=Path, default=DEFAULT_SPLIT_EVIDENCE)
    parser.add_argument("--cash-events", type=Path, default=DEFAULT_CASH_EVENTS)
    parser.add_argument("--cash-manifest", type=Path, default=DEFAULT_CASH_MANIFEST)
    parser.add_argument("--cash-certification", type=Path, default=DEFAULT_CASH_CERTIFICATION)
    parser.add_argument("--ticker-transitions", type=Path, default=DEFAULT_TRANSITIONS)
    parser.add_argument(
        "--ticker-transition-manifest",
        type=Path,
        default=DEFAULT_TRANSITION_MANIFEST,
    )
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    required_files = [
        args.universe_manifest,
        args.snapshots,
        args.split_evidence,
        args.cash_events,
        args.cash_manifest,
        args.cash_certification,
        args.ticker_transitions,
        args.ticker_transition_manifest,
    ]
    missing = [str(path) for path in required_files if not path.is_file()]
    missing.extend(
        str(path)
        for path in (args.data_dir, args.actions_dir, args.manifests_dir)
        if not path.is_dir()
    )

    issues: list[str] = [f"missing_input:{item}" for item in missing]
    universe: dict[str, object] = {}
    cash_certification: dict[str, object] = {}
    snapshots: list[dict[str, str]] = []
    cash_timing_certified = False
    verified_market_data = False
    transition_issues: list[str] = []

    if not missing:
        universe = _load_json(args.universe_manifest)
        cash_manifest = _load_json(args.cash_manifest)
        cash_certification = _load_json(args.cash_certification)
        snapshots = _snapshot_rows(args.snapshots)
        start = args.start or str(universe.get("selected_as_of", ""))[:10]
        end = args.end or str(universe.get("selection_end", ""))[:10]

        issues.extend(
            point_in_time_contract_issues(
                universe=universe,
                snapshots=snapshots,
                data_dir=args.data_dir,
                actions_dir=args.actions_dir,
                manifests_dir=args.manifests_dir,
                split_evidence=args.split_evidence,
                cash_certification=cash_certification,
                require_cash_announcement_timing=True,
            )
        )

        selectable = {
            str(item).strip().upper()
            for item in universe.get("tickers", [])
            if str(item).strip()
        }
        market_data_tickers = sorted(
            {
                str(item).strip().upper()
                for item in universe.get("market_data_tickers", universe.get("tickers", []))
                if str(item).strip()
            }
        )
        if not selectable.issubset(set(market_data_tickers)):
            issues.append("market_data_tickers_missing_selectable_names")

        cash_scope = {
            str(item).strip().upper()
            for item in cash_manifest.get("market_data_tickers", [])
            if str(item).strip()
        }
        if cash_scope != set(market_data_tickers):
            issues.append("cash_manifest_scope_mismatch")

        cash_issues = cash_coverage_certification_issues(
            cash_certification,
            cash_events_path=args.cash_events,
            cash_manifest_path=args.cash_manifest,
            tickers=market_data_tickers,
            start=start,
            end=end,
        )
        issues.extend(f"cash_certification:{item}" for item in cash_issues)
        cash_timing_certified = (
            not cash_issues
            and cash_certification.get("announcement_timing_certified") is True
        )

        transition_issues = transition_binding_issues(
            args.ticker_transitions,
            args.ticker_transition_manifest,
            expected_end=end,
        )
        issues.extend(f"ticker_transition:{item}" for item in transition_issues)

        try:
            data = MarketData(
                market_data_tickers,
                "1d",
                "adjusted",
                require_verified_splits_from=str(universe["warmup_start"]),
                history_start=str(universe["warmup_start"]),
                data_dir=args.data_dir,
                actions_dir=args.actions_dir,
                manifests_dir=args.manifests_dir,
                split_evidence_path=args.split_evidence,
            )
            requested = [value for value in data.dates if start <= value <= end]
            if len(requested) < 2:
                issues.append("verified_market_period_insufficient")
            else:
                verified_market_data = True
        except Exception as error:  # fail-closed audit: preserve diagnostic type only
            issues.append(f"verified_market_data_error:{type(error).__name__}")

    issues = sorted(set(issues))
    bindings = {
        str(path): _binding(path)
        for path in required_files
        if path.is_file()
    }
    report: dict[str, object] = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not issues else "BLOCKED",
        "point_in_time_validation_complete": not issues,
        "universe_point_in_time": universe.get("point_in_time") is True,
        "survivorship_safe": universe.get("survivorship_safe") is True,
        "future_continuity_filter_disabled": (
            isinstance(universe.get("selection_rules"), dict)
            and universe["selection_rules"].get("future_continuity_filter") is False
        ),
        "future_return_filter_disabled": (
            isinstance(universe.get("selection_rules"), dict)
            and universe["selection_rules"].get("future_return_filter") is False
        ),
        "future_snapshot_backfill_allowed": False,
        "pit_storage_isolated": all(
            (
                args.data_dir.name == "candles_point_in_time",
                args.actions_dir.name == "actions_point_in_time",
                args.manifests_dir.name == "manifests_point_in_time",
                args.split_evidence.name == "point_in_time_split_evidence.json",
            )
        ),
        "verified_market_data_loaded": verified_market_data,
        "cash_event_coverage_certified": cash_certification.get("coverage_certified") is True,
        "cash_announcement_timing_certified": cash_timing_certified,
        "ticker_transition_binding_verified": not transition_issues,
        "strict_signal_information_claim_allowed": not issues,
        "issues": issues,
        "source_bindings": bindings,
    }
    report["report_sha256"] = canonical_sha256(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Point-in-time validation: {report['status']} -> {args.output}",
        flush=True,
    )
    if issues:
        for issue in issues:
            print(f"BLOCKER {issue}", flush=True)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
