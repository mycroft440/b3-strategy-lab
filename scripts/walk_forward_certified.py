from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.realistic import (  # noqa: E402
    RealCashAccount,
    cash_coverage_certification_issues,
)
from b3_strategy_lab.statistical_validation import oos_evidence_summary  # noqa: E402
from scripts.backtest_strategy_management_realistic import (  # noqa: E402
    DEFAULT_CASH_CERTIFICATION,
    DEFAULT_CASH_EVENTS,
    DEFAULT_CASH_MANIFEST,
    DEFAULT_UNIVERSE,
)
from scripts import walk_forward_realistic as _walk  # noqa: E402


def _value_after(argv: list[str], flag: str, default: str) -> str:
    if flag not in argv:
        return default
    index = argv.index(flag)
    if index + 1 >= len(argv):
        raise ValueError(f"{flag} requires a value")
    return argv[index + 1]


def _force_certified_semantics(argv: list[str]) -> list[str]:
    """Make strategy and account semantics deterministic in the certified path."""

    result = list(argv)
    for required_flag in ("--economic-gap-adjustment", "--continuous-oos-account"):
        if required_flag not in result:
            result.append(required_flag)
    return result


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--cash-certification",
        type=Path,
        default=DEFAULT_CASH_CERTIFICATION,
    )
    parser.add_argument("--require-full-scope", action="store_true")
    parser.add_argument(
        "--max-causal-adv-participation",
        type=float,
        default=0.01,
        help=(
            "Fail-closed maximum share of trailing causal financial-volume ADV used "
            "by any opening execution leg. Default: 0.01 (1%)."
        ),
    )
    known, forwarded = parser.parse_known_args(raw)
    if not 0 < known.max_causal_adv_participation <= 1:
        parser.error("--max-causal-adv-participation must be in (0, 1].")
    forwarded = _force_certified_semantics(forwarded)

    universe_path = Path(
        _value_after(forwarded, "--universe-manifest", str(DEFAULT_UNIVERSE))
    )
    cash_events_path = Path(
        _value_after(forwarded, "--cash-events", str(DEFAULT_CASH_EVENTS))
    )
    cash_manifest_path = Path(
        _value_after(forwarded, "--cash-manifest", str(DEFAULT_CASH_MANIFEST))
    )
    start = _value_after(forwarded, "--start", "2018-01-02")

    universe_manifest = json.loads(universe_path.read_text(encoding="utf-8"))
    cash_manifest = json.loads(cash_manifest_path.read_text(encoding="utf-8"))
    if not known.cash_certification.exists():
        raise SystemExit(
            f"Cash-distribution coverage certification is missing: {known.cash_certification}"
        )
    certification = json.loads(known.cash_certification.read_text(encoding="utf-8"))
    end = _value_after(
        forwarded,
        "--end",
        str(cash_manifest.get("end") or certification.get("end") or ""),
    )
    if not end:
        raise SystemExit(
            "Certified walk-forward requires --end or a certified cash-manifest end date."
        )

    market_data_tickers = sorted(
        {
            str(item).strip().upper()
            for item in universe_manifest.get(
                "market_data_tickers", universe_manifest.get("tickers", [])
            )
            if str(item).strip()
        }
    )
    issues = cash_coverage_certification_issues(
        certification,
        cash_events_path=cash_events_path,
        cash_manifest_path=cash_manifest_path,
        tickers=market_data_tickers,
        start=start,
        end=end,
    )
    if issues:
        raise SystemExit(
            "Certified walk-forward refuses incomplete cash-event coverage: "
            + ", ".join(issues)
        )

    original_run = _walk.run_realistic
    sentinel = object()
    original_capacity = getattr(
        RealCashAccount, "_max_causal_adv_participation", sentinel
    )
    RealCashAccount._max_causal_adv_participation = float(  # type: ignore[attr-defined]
        known.max_causal_adv_participation
    )

    def certified_run(*args, **kwargs):
        kwargs["cash_events_complete"] = True
        kwargs["economic_gap_adjustment"] = True
        return original_run(*args, **kwargs)

    _walk.run_realistic = certified_run
    try:
        return_code = _walk.main(forwarded)
    finally:
        _walk.run_realistic = original_run
        if original_capacity is sentinel:
            delattr(RealCashAccount, "_max_causal_adv_participation")
        else:
            RealCashAccount._max_causal_adv_participation = original_capacity  # type: ignore[attr-defined]

    summary_path = Path(
        _value_after(
            forwarded,
            "--summary-output",
            str(_walk.DEFAULT_SUMMARY),
        )
    )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["cash_events_complete"] = True
    summary["cash_certification_verified"] = True
    summary["cash_certification"] = str(known.cash_certification)
    summary["causal_opening_liquidity_required"] = True
    summary["economic_gap_adjustment_required"] = True
    summary["continuous_oos_account_required"] = True
    summary["certified_strategy_semantics"] = "economic_gap_adjustment_for_gap_momentum"
    summary["execution_capacity_gate_required"] = True
    summary["execution_capacity_gate"] = "reject_above_causal_adv_participation"
    summary["max_causal_adv_participation"] = float(
        known.max_causal_adv_participation
    )
    summary["partial_fill_model"] = False
    summary["capacity_interpretation"] = (
        "Certified execution rejects any leg above the configured fraction of trailing "
        "causal financial-volume ADV. It intentionally does not invent an order-book or "
        "partial-fill reconstruction that the daily source data cannot support."
    )

    summary.update(
        oos_evidence_summary(
            positive_folds=int(summary.get("positive_test_folds", 0)),
            folds=int(summary.get("folds", 0)),
        )
    )
    summary["formal_multiple_testing_significance_correction"] = False
    summary["formal_multiple_testing_correction_required_for_ex_ante_claim"] = True
    summary["matrix_role"] = "retrospective_hypothesis_generation_only"
    summary["multiple_testing_interpretation"] = (
        "Selecting from the full catalog using training data and evaluating the selected "
        "procedure on untouched test folds prevents direct test-set leakage. It does not, "
        "by itself, constitute a formal multiple-testing significance correction such as "
        "a reality check, SPA/PBO or deflated-Sharpe analysis."
    )

    research_claim_allowed = (
        summary.get("full_multiple_testing_scope") is True
        and summary.get("selection_uses_test_data") is False
        and summary.get("survivorship_safe_universe") is True
        and summary.get("continuous_oos_account") is True
        and summary.get("test_accounts_are_independent") is False
        and summary.get("continuous_tax_account_claim") is True
        and summary.get("execution_capacity_gate_required") is True
    )
    summary["research_claim_allowed"] = research_claim_allowed
    # Fail closed: until a formal multiple-testing significance correction is present,
    # the workflow may report OOS research evidence but must not label the selected
    # strategy as an ex-ante statistically established winner.
    summary["ex_ante_selection_claim_allowed"] = False

    if known.require_full_scope:
        required = {
            "full_multiple_testing_scope": True,
            "selection_uses_test_data": False,
            "survivorship_safe_universe": True,
            "continuous_oos_account": True,
            "test_accounts_are_independent": False,
            "continuous_tax_account_claim": True,
            "execution_capacity_gate_required": True,
            "research_claim_allowed": True,
            "ex_ante_selection_claim_allowed": False,
            "formal_multiple_testing_significance_correction": False,
        }
        failures = [
            f"{key}={summary.get(key)!r}"
            for key, expected in required.items()
            if summary.get(key) is not expected
        ]
        if failures:
            raise SystemExit(
                "Walk-forward research gate failed: " + ", ".join(failures)
            )
        summary["selection_gate"] = "FULL_CATALOG_CONTINUOUS_OOS_RESEARCH_ONLY"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
