from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from b3_strategy_lab.candles import DEFAULT_TICKERS, cache_path, load_candles  # noqa: E402
from b3_strategy_lab.cotahist import load_manifest, manifest_path  # noqa: E402


PRICE_FIELDS = ("raw_open", "raw_high", "raw_low", "raw_close")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compara uma base candidata verificada com outra base de candles."
    )
    parser.add_argument("--reference-data-dir", required=True)
    parser.add_argument("--candidate-data-dir", required=True)
    parser.add_argument("--candidate-manifests-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=list(DEFAULT_TICKERS))
    parser.add_argument("--intervals", nargs="+", default=["1d", "1wk"])
    parser.add_argument("--output", default="reports/market_data_source_comparison.csv")
    args = parser.parse_args(argv)

    rows = []
    for ticker in sorted({value.strip().upper() for value in args.tickers}):
        for interval in args.intervals:
            reference = load_candles(cache_path(ticker, interval, args.reference_data_dir))
            candidate = load_candles(cache_path(ticker, interval, args.candidate_data_dir))
            manifest = load_manifest(manifest_path(ticker, interval, args.candidate_manifests_dir))
            rows.append(_comparison_row(ticker, interval, reference, candidate, manifest))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Salvo: {output} ({len(rows)} linhas)")
    return 0


def _comparison_row(ticker, interval, reference, candidate, manifest) -> dict:
    reference_by_date = {candle.date: candle for candle in reference}
    candidate_by_date = {candle.date: candle for candle in candidate}
    shared_dates = sorted(reference_by_date.keys() & candidate_by_date.keys())
    only_reference = sorted(reference_by_date.keys() - candidate_by_date.keys())
    only_candidate = sorted(candidate_by_date.keys() - reference_by_date.keys())

    differences: list[float] = []
    differences_over_cent = 0
    differences_over_two_cents = 0
    largest = (0.0, "", "")
    volume_differences = 0
    for candle_date in shared_dates:
        old = reference_by_date[candle_date]
        new = candidate_by_date[candle_date]
        for field in PRICE_FIELDS:
            difference = abs(getattr(old, field) - getattr(new, field))
            differences.append(difference)
            differences_over_cent += int(difference > 0.01)
            differences_over_two_cents += int(difference > 0.02)
            if difference > largest[0]:
                largest = (difference, candle_date, field)
        volume_differences += int(old.volume != new.volume)

    return {
        "ticker": ticker,
        "interval": interval,
        "reference_rows": len(reference),
        "candidate_rows": len(candidate),
        "reference_start": reference[0].date if reference else "",
        "reference_end": reference[-1].date if reference else "",
        "candidate_start": candidate[0].date if candidate else "",
        "candidate_end": candidate[-1].date if candidate else "",
        "shared_dates": len(shared_dates),
        "dates_only_reference": len(only_reference),
        "dates_only_candidate": len(only_candidate),
        "first_only_reference": only_reference[0] if only_reference else "",
        "first_only_candidate": only_candidate[0] if only_candidate else "",
        "ohlc_values_compared": len(differences),
        "ohlc_differences_gt_0_01": differences_over_cent,
        "ohlc_differences_gt_0_02": differences_over_two_cents,
        "ohlc_difference_p95": _percentile(differences, 0.95),
        "ohlc_difference_max": largest[0],
        "max_difference_date": largest[1],
        "max_difference_field": largest[2],
        "volume_different_rows": volume_differences,
        "candidate_price_status": manifest.status,
        "candidate_action_status": manifest.corporate_action_status,
        "candidate_warnings": len(manifest.warnings),
        "candidate_warning_reviews": len(manifest.warning_reviews),
    }


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(value for value in values if math.isfinite(value))
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * quantile) - 1))
    return ordered[index]


if __name__ == "__main__":
    raise SystemExit(main())
