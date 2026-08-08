from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from b3_strategy_lab.candles import (
    DEFAULT_LEGACY_DATA_DIR,
    Candle,
    cache_path,
    load_candles,
    save_candles,
)


DEFAULT_DATA_DIR = DEFAULT_LEGACY_DATA_DIR
DAILY_START_DATES = {"GGBR3": "2000-05-19"}
DAILY_DROP_DATES = {"VALE3": {"2008-06-12"}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Repara apenas candles legados sem manifesto. A base canonica "
            "COTAHIST deve ser reconstruida, nunca alterada manualmente."
        )
    )
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    daily_by_ticker = _repair_daily_files(data_dir)
    _repair_weekly_files(data_dir, daily_by_ticker)
    _repair_four_hour_files(data_dir, daily_by_ticker)
    return 0


def _repair_daily_files(data_dir: Path) -> dict[str, list[Candle]]:
    daily_by_ticker: dict[str, list[Candle]] = {}

    for path in sorted(data_dir.glob("*_1d.csv")):
        ticker = path.stem.rsplit("_", 1)[0].upper()
        original = load_candles(path)
        candles = [_repair_known_daily_candle(candle) for candle in original]
        candles = [
            candle
            for candle in candles
            if candle.volume > 0
            and candle.date >= DAILY_START_DATES.get(ticker, "0001-01-01")
            and candle.date not in DAILY_DROP_DATES.get(ticker, set())
        ]
        save_candles(candles, path)
        daily_by_ticker[ticker] = candles
        print(f"{path}: {len(original)} -> {len(candles)} candles diarios")

    return daily_by_ticker


def _repair_known_daily_candle(candle: Candle) -> Candle:
    if candle.ticker == "PETR4" and candle.date == "2003-08-04":
        return _with_raw_values(candle, raw_high=6.75, source_high=6.75)
    if candle.ticker == "PETR4" and candle.date == "2003-08-05":
        return _with_raw_values(
            candle,
            raw_open=6.75,
            raw_high=6.85,
            raw_low=6.75,
            source_high=6.75,
            source_low=6.75,
        )
    return candle


def _with_raw_values(
    candle: Candle,
    *,
    raw_open: float | None = None,
    raw_high: float | None = None,
    raw_low: float | None = None,
    raw_close: float | None = None,
    source_high: float | None = None,
    source_low: float | None = None,
) -> Candle:
    fixed_raw_open = candle.raw_open if raw_open is None else raw_open
    fixed_raw_high = candle.raw_high if raw_high is None else raw_high
    fixed_raw_low = candle.raw_low if raw_low is None else raw_low
    fixed_raw_close = candle.raw_close if raw_close is None else raw_close
    fixed_source_high = candle.source_high if source_high is None else source_high
    fixed_source_low = candle.source_low if source_low is None else source_low
    factor = candle.adj_close / fixed_raw_close if fixed_raw_close else 1.0

    return replace(
        candle,
        open=fixed_raw_open * factor,
        high=fixed_raw_high * factor,
        low=fixed_raw_low * factor,
        close=candle.adj_close,
        raw_open=fixed_raw_open,
        raw_high=fixed_raw_high,
        raw_low=fixed_raw_low,
        raw_close=fixed_raw_close,
        adjustment_factor=factor,
        source_high=fixed_source_high,
        source_low=fixed_source_low,
        ohlc_repaired=int(fixed_raw_high != fixed_source_high or fixed_raw_low != fixed_source_low),
    )


def _repair_weekly_files(data_dir: Path, daily_by_ticker: dict[str, list[Candle]]) -> None:
    for ticker, candles in sorted(daily_by_ticker.items()):
        path = cache_path(ticker, "1wk", data_dir)
        if not path.exists():
            continue
        weekly = _resample_to_weekly(candles)
        original = load_candles(path)
        save_candles(weekly, path)
        print(f"{path}: {len(original)} -> {len(weekly)} candles semanais")


def _resample_to_weekly(candles: list[Candle]) -> list[Candle]:
    grouped: dict[str, list[Candle]] = defaultdict(list)
    for candle in candles:
        candle_day = date.fromisoformat(_date_part(candle.date))
        week_start = candle_day - timedelta(days=candle_day.weekday())
        grouped[week_start.isoformat()].append(candle)

    weekly: list[Candle] = []
    for week_start in sorted(grouped):
        bucket = sorted(grouped[week_start], key=lambda candle: candle.date)
        first = bucket[0]
        last = bucket[-1]
        raw_close = last.raw_close
        adj_close = last.adj_close
        factor = adj_close / raw_close if raw_close else 1.0
        raw_high = max(candle.raw_high for candle in bucket)
        raw_low = min(candle.raw_low for candle in bucket)
        source_high = max(candle.source_high for candle in bucket)
        source_low = min(candle.source_low for candle in bucket)
        weekly.append(
            Candle(
                date=week_start,
                ticker=first.ticker,
                source_symbol=first.source_symbol,
                open=first.raw_open * factor,
                high=raw_high * factor,
                low=raw_low * factor,
                close=adj_close,
                adj_close=adj_close,
                volume=sum(candle.volume for candle in bucket),
                raw_open=first.raw_open,
                raw_high=raw_high,
                raw_low=raw_low,
                raw_close=raw_close,
                adjustment_factor=factor,
                source_high=source_high,
                source_low=source_low,
                ohlc_repaired=int(any(candle.ohlc_repaired for candle in bucket)),
            )
        )
    return weekly


def _repair_four_hour_files(data_dir: Path, daily_by_ticker: dict[str, list[Candle]]) -> None:
    for path in sorted(data_dir.glob("*_4h.csv")):
        ticker = path.stem.rsplit("_", 1)[0].upper()
        daily_by_day = {candle.date: candle for candle in daily_by_ticker.get(ticker, [])}
        original = load_candles(path)
        grouped: dict[str, list[Candle]] = defaultdict(list)
        for candle in original:
            grouped[_date_part(candle.date)].append(candle)

        repaired: list[Candle] = []
        for day in sorted(grouped):
            bucket = sorted(grouped[day], key=lambda candle: candle.date)
            if len(bucket) != 2 or day not in daily_by_day or any(_bad_zero_volume_bucket(candle) for candle in bucket):
                continue
            if _has_large_daily_mismatch(bucket, daily_by_day[day]):
                continue
            repaired.extend(bucket)

        save_candles(repaired, path)
        print(f"{path}: {len(original)} -> {len(repaired)} candles 4h")


def _bad_zero_volume_bucket(candle: Candle) -> bool:
    if candle.volume != 0:
        return False
    return candle.raw_high != candle.raw_low or candle.raw_open != candle.raw_close


def _has_large_daily_mismatch(bucket: list[Candle], daily: Candle) -> bool:
    raw_open = bucket[0].raw_open
    raw_high = max(candle.raw_high for candle in bucket)
    raw_low = min(candle.raw_low for candle in bucket)
    raw_close = bucket[-1].raw_close

    return any(
        _relative_difference(left, right) >= 0.05
        for left, right in (
            (raw_open, daily.raw_open),
            (raw_high, daily.raw_high),
            (raw_low, daily.raw_low),
            (raw_close, daily.raw_close),
        )
    )


def _relative_difference(left: float, right: float) -> float:
    if right == 0:
        return float("inf")
    return abs(left / right - 1)


def _date_part(value: str) -> str:
    return value.split("T", 1)[0].split(" ", 1)[0]


if __name__ == "__main__":
    raise SystemExit(main())
