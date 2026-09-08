"""Download the BCB SGS 12 daily CDI series with reproducible source hashes."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


API = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados"


def normalize_payload(payload: object, start: date, end: date) -> dict[str, float]:
    if not isinstance(payload, list) or not payload:
        raise ValueError("BCB response must contain daily CDI observations.")
    result = {}
    for row in payload:
        day = datetime.strptime(row["data"], "%d/%m/%Y").date()
        value = float(row["valor"]) / 100.0  # SGS 12 is percent per day.
        if not start <= day <= end or not math.isfinite(value) or value <= -1:
            raise ValueError("Invalid date or daily return in BCB response.")
        key = day.isoformat()
        if key in result:
            raise ValueError(f"Duplicate BCB date: {key}")
        result[key] = value
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2017, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/benchmarks/cdi.csv"))
    args = parser.parse_args(argv)
    if args.start > args.end or args.end >= datetime.now(timezone.utc).date():
        parser.error("Use a nonempty interval ending before today.")
    observations = {}
    sources = []
    raw_files = []
    # Bounded annual requests also respect the SGS daily-series query window.
    for year in range(args.start.year, args.end.year + 1):
        start = max(args.start, date(year, 1, 1))
        end = min(args.end, date(year, 12, 31))
        query = urlencode({"formato": "json", "dataInicial": start.strftime("%d/%m/%Y"),
                           "dataFinal": end.strftime("%d/%m/%Y")})
        url = f"{API}?{query}"
        with urlopen(url, timeout=45) as response:
            raw = response.read()
        parsed = normalize_payload(json.loads(raw), start, end)
        observations.update(parsed)
        relative = f"{args.output.stem}_sources/{year}.json"
        raw_files.append((relative, raw))
        sources.append({"url": url, "path": relative,
                        "sha256": hashlib.sha256(raw).hexdigest()})
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["date", "return"])
    writer.writerows((day, format(value, ".12g")) for day, value in sorted(observations.items()))
    content = buffer.getvalue().encode("utf-8")
    manifest = {
        "schema_version": 1, "source_authority": "BCB", "series": 12,
        "name": "CDI", "unit": "decimal_daily_return", "benchmark_is_net_of_tax": False,
        "requested_start": args.start.isoformat(), "requested_end": args.end.isoformat(),
        "start": min(observations), "end": max(observations), "observations": len(observations),
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "csv_sha256": hashlib.sha256(content).hexdigest(), "sources": sources,
    }
    # Only replace outputs after every request and normalization has succeeded.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for relative, raw in raw_files:
        target = args.output.parent / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    args.output.write_bytes(content)
    args.output.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {len(observations)} CDI observations: {min(observations)} to {max(observations)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
