from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from b3_strategy_lab.cotahist import load_verified_candles  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audita alinhamento e proveniencia do universo padrao de backtest."
    )
    parser.add_argument("--universe", type=Path, default=Path("data/universes/fixed_40_2018.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/backtest_data_audit_40.json"))
    parser.add_argument(
        "--max-age-calendar-days",
        type=int,
        default=4,
        help="Falha se o último pregão comum estiver mais antigo que este limite.",
    )
    parser.add_argument(
        "--expected-end",
        help="Cutoff certificado esperado (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--allow-historical-cutoff",
        action="store_true",
        help=(
            "Aceita explicitamente um snapshot historico que coincida com "
            "--expected-end, sem classifica-lo como recente."
        ),
    )
    args = parser.parse_args(argv)
    if args.max_age_calendar_days < 0:
        parser.error("--max-age-calendar-days não pode ser negativo.")
    try:
        expected_end = (
            date.fromisoformat(args.expected_end) if args.expected_end else None
        )
    except ValueError:
        parser.error("--expected-end precisa estar no formato YYYY-MM-DD.")
    if args.allow_historical_cutoff and expected_end is None:
        parser.error("--allow-historical-cutoff exige --expected-end.")

    universe = json.loads(args.universe.read_text(encoding="utf-8"))
    tickers = [str(ticker).upper() for ticker in universe["tickers"]]
    evaluation_start = str(universe["selected_as_of"])
    coverage_start = str(universe["warmup_start"])
    candles_by_ticker = {}
    manifests = {}
    for ticker in tickers:
        candles, manifest = load_verified_candles(
            ticker,
            "1d",
            require_verified_splits_from=coverage_start,
        )
        candles_by_ticker[ticker] = candles
        manifests[ticker] = manifest

    evaluation_end = min(candles[-1].date for candles in candles_by_ticker.values())
    date_sets = {
        ticker: {
            candle.date
            for candle in candles
            if evaluation_start <= candle.date <= evaluation_end
        }
        for ticker, candles in candles_by_ticker.items()
    }
    common_dates = set.intersection(*date_sets.values())
    union_dates = set.union(*date_sets.values())
    rows = []
    for ticker in tickers:
        window = [
            candle
            for candle in candles_by_ticker[ticker]
            if evaluation_start <= candle.date <= evaluation_end
        ]
        rows.append(
            {
                "ticker": ticker,
                "rows": len(window),
                "missing_sessions_vs_union": len(union_dates - date_sets[ticker]),
                "raw_close_differs_from_normalized_rows": sum(
                    abs(candle.raw_close - candle.close) > 1e-9 for candle in window
                ),
                "missing_isin_rows": sum(not candle.isin for candle in window),
                "zero_trade_rows": sum(candle.trades == 0 for candle in window),
                "candle_sha256": manifests[ticker].candle_sha256,
                "split_status": manifests[ticker].split_action_status,
                "split_verified_from": manifests[ticker].split_verified_from,
            }
        )

    evaluation_end_date = date.fromisoformat(evaluation_end)
    freshness_reference = date.today()
    age_calendar_days = (freshness_reference - evaluation_end_date).days
    data_is_recent = 0 <= age_calendar_days <= args.max_age_calendar_days
    historical_cutoff_accepted = bool(
        args.allow_historical_cutoff
        and expected_end is not None
        and evaluation_end_date == expected_end
    )
    checks = {
        "all_tickers_share_every_evaluation_session": common_dates == union_dates,
        "all_rows_have_isin": all(row["missing_isin_rows"] == 0 for row in rows),
        "all_rows_have_trades": all(row["zero_trade_rows"] == 0 for row in rows),
        "all_split_ledgers_verified_for_warmup": all(
            row["split_status"] == "verified"
            and row["split_verified_from"] <= coverage_start
            for row in rows
        ),
        "universe_discloses_survivorship_bias": universe["survivorship_safe"] is False,
        "evaluation_end_does_not_exceed_reference_date": (
            evaluation_end_date <= freshness_reference
        ),
        "freshness_policy_is_satisfied": (
            data_is_recent or historical_cutoff_accepted
        ),
    }
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "universe_id": universe["id"],
        "universe_manifest": str(args.universe),
        "survivorship_safe": universe["survivorship_safe"],
        "bias_disclosure": universe["bias_disclosure"],
        "warmup_start": coverage_start,
        "evaluation_start": evaluation_start,
        "evaluation_end": evaluation_end,
        "freshness_reference_date": freshness_reference.isoformat(),
        "expected_end": expected_end.isoformat() if expected_end else None,
        "data_is_recent": data_is_recent,
        "historical_cutoff_accepted": historical_cutoff_accepted,
        "age_calendar_days": age_calendar_days,
        "maximum_age_calendar_days": args.max_age_calendar_days,
        "common_sessions": len(common_dates),
        "union_sessions": len(union_dates),
        "checks": checks,
        "tickers": rows,
        "ready": all(checks.values()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    print(
        f"{args.output}: ready={payload['ready']}, "
        f"sessoes={payload['common_sessions']}, fim={payload['evaluation_end']}"
    )
    return 0 if payload["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
