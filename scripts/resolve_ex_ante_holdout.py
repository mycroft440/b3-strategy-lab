from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.ex_ante_validation import (  # noqa: E402
    holdout_bounds,
    latest_complete_calendar_year,
)
from scripts.backtest_strategy_management_realistic import (  # noqa: E402
    DEFAULT_ACTIONS,
    DEFAULT_DATA,
    DEFAULT_MANIFESTS,
    DEFAULT_SPLIT_EVIDENCE,
    DEFAULT_UNIVERSE,
)
from scripts.research_portfolio_allocation import MarketData  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reserve the latest complete calendar year as a one-shot final holdout. "
            "All candidate selection must end before the first holdout session."
        )
    )
    parser.add_argument("--universe-manifest", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--actions-dir", type=Path, default=DEFAULT_ACTIONS)
    parser.add_argument("--manifests-dir", type=Path, default=DEFAULT_MANIFESTS)
    parser.add_argument("--split-evidence", type=Path, default=DEFAULT_SPLIT_EVIDENCE)
    parser.add_argument("--holdout-year", type=int)
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--end")
    parser.add_argument("--output", type=Path, default=Path("reports/HOLDOUT_WINDOW.json"))
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)

    as_of = date.fromisoformat(args.as_of)
    manifest = json.loads(args.universe_manifest.read_text(encoding="utf-8"))
    market_data_tickers = sorted(
        {
            str(item).strip().upper()
            for item in manifest.get("market_data_tickers", manifest["tickers"])
            if str(item).strip()
        }
    )
    data = MarketData(
        market_data_tickers,
        "1d",
        "adjusted",
        require_verified_splits_from=str(manifest["warmup_start"]),
        history_start=str(manifest["warmup_start"]),
        data_dir=args.data_dir,
        actions_dir=args.actions_dir,
        manifests_dir=args.manifests_dir,
        split_evidence_path=args.split_evidence,
    )
    cap = args.end or str(manifest["selection_end"])
    dates = [value for value in data.dates if value <= cap]
    if not dates:
        parser.error("No verified market sessions are available at or before --end.")
    holdout_year = args.holdout_year or latest_complete_calendar_year(dates, as_of=as_of)
    holdout_start, holdout_end = holdout_bounds(dates, holdout_year)
    if holdout_year >= as_of.year:
        parser.error("The final holdout must be a completed calendar year.")
    training_dates = [value for value in dates if value < holdout_start]
    if not training_dates:
        parser.error("No training session exists before the holdout.")
    research_end = max(training_dates)

    payload = {
        "schema_version": 1,
        "as_of": as_of.isoformat(),
        "holdout_year": holdout_year,
        "holdout_start": holdout_start,
        "holdout_end": holdout_end,
        "research_end": research_end,
        "selection_uses_holdout_data": False,
        "holdout_reuse_allowed": False,
        "fallback_candidate_allowed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as target:
            for key in ("holdout_year", "holdout_start", "holdout_end", "research_end"):
                target.write(f"{key}={payload[key]}\n")
    print(
        f"Training ends {research_end}; untouched holdout is "
        f"{holdout_start}..{holdout_end} ({holdout_year}).",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
