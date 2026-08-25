from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.realistic import cash_coverage_certification_issues  # noqa: E402
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


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--cash-certification",
        type=Path,
        default=DEFAULT_CASH_CERTIFICATION,
    )
    parser.add_argument("--require-full-scope", action="store_true")
    known, forwarded = parser.parse_known_args(raw)

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

    def certified_run(*args, **kwargs):
        kwargs["cash_events_complete"] = True
        return original_run(*args, **kwargs)

    _walk.run_realistic = certified_run
    try:
        return_code = _walk.main(forwarded)
    finally:
        _walk.run_realistic = original_run

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
    if known.require_full_scope:
        required = {
            "full_multiple_testing_scope": True,
            "selection_uses_test_data": False,
            "survivorship_safe_universe": True,
            "ex_ante_selection_claim_allowed": True,
        }
        failures = [
            f"{key}={summary.get(key)!r}"
            for key, expected in required.items()
            if summary.get(key) is not expected
        ]
        if failures:
            raise SystemExit(
                "Walk-forward final-selection gate failed: " + ", ".join(failures)
            )
        summary["selection_gate"] = "FULL_CATALOG_OUT_OF_SAMPLE"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
