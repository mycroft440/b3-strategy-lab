"""Dated benchmark returns; absent observations never silently become zero."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from datetime import date
from pathlib import Path


def load_daily_benchmark(path: Path | str) -> dict[str, float]:
    source = Path(path)
    manifest_path = source.with_suffix(".manifest.json")
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("csv_sha256") != hashlib.sha256(source.read_bytes()).hexdigest():
            raise ValueError("Benchmark CSV differs from its source manifest.")
    result = {}
    with source.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if not {"date", "return"}.issubset(reader.fieldnames or []):
            raise ValueError("Benchmark requires CSV columns date,return (decimal returns).")
        for row in reader:
            day = date.fromisoformat(row["date"]).isoformat()
            value = float(row["return"])
            if day in result or not math.isfinite(value) or value <= -1:
                raise ValueError(f"Invalid or duplicate benchmark observation: {day}")
            result[day] = value
    if not result:
        raise ValueError("Benchmark contains no observations.")
    return dict(sorted(result.items()))


def benchmark_comparison(
    dates: list[str], equities: list[float], initial_equity: float,
    daily_returns: dict[str, float],
) -> dict[str, float]:
    if not dates or len(dates) != len(equities) or dates != sorted(set(dates)):
        raise ValueError("Benchmark comparison requires aligned, ordered, unique dates.")
    if any(not math.isfinite(value) or value <= 0 for value in [initial_equity, *equities]):
        raise ValueError("Equities must be finite and positive.")
    missing = [day for day in dates if day not in daily_returns]
    if missing:
        raise ValueError(f"Benchmark does not cover evaluation sessions: {missing[:5]}")
    observations = sorted((day, value) for day, value in daily_returns.items()
                          if dates[0] <= day <= dates[-1])
    if any(not math.isfinite(value) or value <= -1 for _, value in observations):
        raise ValueError("Invalid benchmark return.")
    # Compound banking days between exchange sessions (e.g. an exchange holiday).
    index = 0
    growth = 1.0
    prior_equity = initial_equity
    excess = []
    for day, equity in zip(dates, equities):
        period_growth = 1.0
        while index < len(observations) and observations[index][0] <= day:
            period_growth *= 1 + observations[index][1]
            index += 1
        growth *= period_growth
        excess.append(equity / prior_equity - period_growth)
        prior_equity = equity
    years = ((date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days + 1) / 365.25
    std = statistics.stdev(excess) if len(excess) > 1 else 0.0
    sharpe = statistics.mean(excess) / std * math.sqrt(len(excess) / years) if std > 1e-15 else 0.0
    benchmark_return = growth - 1
    return {
        "benchmark_total_return": benchmark_return,
        "excess_total_return": equities[-1] / initial_equity - 1 - benchmark_return,
        "excess_sharpe": sharpe,
    }
