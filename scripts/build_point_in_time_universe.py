from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import zipfile
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.cotahist import download_cotahist, parse_cotahist_lines, read_cotahist  # noqa: E402


TICKER_RE = re.compile(r"^[A-Z]{4}\d{1,2}$")
DEFAULT_SNAPSHOTS = Path("data/universes/point_in_time_weekly.csv")
DEFAULT_MANIFEST = Path("data/universes/point_in_time_union.json")
DEFAULT_EXECUTION = Path("data/execution/b3_standard_fractional_open.csv")


def _parse_years(values: list[str]) -> list[int]:
    result: set[int] = set()
    for value in values:
        if ":" in value:
            start, end = value.split(":", 1)
            result.update(range(int(start), int(end) + 1))
        else:
            result.add(int(value))
    return sorted(result)


def _is_company_equity(quote) -> bool:
    ticker = quote.ticker.strip().upper()
    if not TICKER_RE.fullmatch(ticker):
        return False
    specification = quote.specification.strip().upper()
    return specification.startswith(("ON", "PN", "UNT"))


def _week_key(value: str) -> tuple[int, int]:
    point = date.fromisoformat(value)
    iso = point.isocalendar()
    return iso.year, iso.week


def _base_fractional_ticker(ticker: str) -> str:
    value = ticker.strip().upper()
    if value.endswith("F") and len(value) > 1 and value[-2].isdigit():
        return value[:-1]
    return value


def _read_fractional(path: Path) -> list:
    if path.suffix.lower() != ".zip":
        with path.open("rb") as file:
            return parse_cotahist_lines(
                file,
                market_types=("020",),
                require_envelope=True,
            )
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if not name.endswith("/")]
        if len(members) != 1:
            raise ValueError(f"{path}: expected one COTAHIST member.")
        with archive.open(members[0]) as file:
            return parse_cotahist_lines(
                file,
                market_types=("020",),
                require_envelope=True,
            )


def _weekly_decision_dates(all_dates: list[str], start: str, end: str) -> list[str]:
    result: list[str] = []
    for index, current in enumerate(all_dates):
        if current < start or current > end:
            continue
        following = all_dates[index + 1] if index + 1 < len(all_dates) else None
        if following is None or _week_key(current) != _week_key(following):
            result.append(current)
    return result


def _snapshot_rows(
    quotes: list,
    *,
    start: str,
    end: str,
    lookback_sessions: int,
    top_n: int,
    minimum_presence: float,
) -> list[dict[str, object]]:
    by_date: dict[str, list] = defaultdict(list)
    all_dates: set[str] = set()
    for quote in quotes:
        if not _is_company_equity(quote):
            continue
        by_date[quote.date].append(quote)
        all_dates.add(quote.date)
    dates = sorted(all_dates)
    date_index = {value: index for index, value in enumerate(dates)}
    decisions = _weekly_decision_dates(dates, start, end)
    rows: list[dict[str, object]] = []

    for decision in decisions:
        end_index = date_index[decision]
        first = max(0, end_index - lookback_sessions + 1)
        window_dates = dates[first : end_index + 1]
        if len(window_dates) < max(20, lookback_sessions // 2):
            continue
        stats: dict[str, dict[str, object]] = {}
        for current in window_dates:
            for quote in by_date[current]:
                ticker = quote.ticker.upper()
                item = stats.setdefault(
                    ticker,
                    {
                        "ticker": ticker,
                        "issuer_name": quote.issuer_name.strip().upper(),
                        "issuer_code": ticker[:4],
                        "days": 0,
                        "financial_volume": 0.0,
                    },
                )
                item["days"] = int(item["days"]) + 1
                item["financial_volume"] = float(item["financial_volume"]) + float(
                    quote.financial_volume
                )
        candidates: list[dict[str, object]] = []
        for item in stats.values():
            presence = int(item["days"]) / len(window_dates)
            if presence < minimum_presence:
                continue
            avg_financial = float(item["financial_volume"]) / max(1, int(item["days"]))
            candidates.append(
                {
                    **item,
                    "presence": presence,
                    "avg_financial_volume": avg_financial,
                }
            )

        candidates.sort(
            key=lambda item: (
                float(item["avg_financial_volume"]),
                float(item["presence"]),
                str(item["ticker"]),
            ),
            reverse=True,
        )
        selected: list[dict[str, object]] = []
        used_issuers: set[str] = set()
        for item in candidates:
            issuer_key = str(item["issuer_name"]) or str(item["issuer_code"])
            if issuer_key in used_issuers:
                continue
            used_issuers.add(issuer_key)
            selected.append(item)
            if len(selected) >= top_n:
                break
        if len(selected) < top_n:
            raise ValueError(
                f"{decision}: only {len(selected)} point-in-time company equities satisfy the rules."
            )
        for rank, item in enumerate(selected, start=1):
            rows.append(
                {
                    "effective_date": decision,
                    "ticker": item["ticker"],
                    "rank": rank,
                    "presence": f"{float(item['presence']):.8f}",
                    "avg_financial_volume": f"{float(item['avg_financial_volume']):.2f}",
                    "issuer_name": item["issuer_name"],
                    "issuer_code": item["issuer_code"],
                    "lookback_sessions": len(window_dates),
                }
            )
    if not rows:
        raise ValueError("No point-in-time snapshots were generated.")
    return rows


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a survivorship-safe weekly stock universe from full B3 COTAHIST "
            "using only trailing information, and build standard/fractional "
            "execution openings for the union of selected symbols."
        )
    )
    parser.add_argument("--years", nargs="+", default=[f"2017:{date.today().year}"])
    parser.add_argument("--archives-dir", type=Path, default=Path(".cache/cotahist"))
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--start", default="2018-01-02")
    parser.add_argument("--end")
    parser.add_argument("--lookback-sessions", type=int, default=252)
    parser.add_argument("--top-n", type=int, default=40)
    parser.add_argument("--minimum-presence", type=float, default=0.90)
    parser.add_argument("--snapshots-output", type=Path, default=DEFAULT_SNAPSHOTS)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--execution-output", type=Path, default=DEFAULT_EXECUTION)
    args = parser.parse_args(argv)

    if args.lookback_sessions <= 20 or args.top_n <= 0:
        parser.error("lookback-sessions must be >20 and top-n must be positive.")
    if not 0 < args.minimum_presence <= 1:
        parser.error("minimum-presence must be in (0, 1].")

    years = _parse_years(args.years)
    archives: list[Path] = []
    for year in years:
        path = args.archives_dir / f"COTAHIST_A{year}.ZIP"
        if args.download:
            path = download_cotahist(
                year,
                args.archives_dir,
                refresh=year == date.today().year,
            )
        if not path.exists():
            raise FileNotFoundError(
                f"{path} is missing; use --download or provide the full COTAHIST archive."
            )
        archives.append(path)

    standard_quotes = []
    fractional_quotes = []
    for archive in archives:
        standard_quotes.extend(read_cotahist(archive))
        fractional_quotes.extend(_read_fractional(archive))

    end = args.end or max(quote.date for quote in standard_quotes)
    snapshots = _snapshot_rows(
        standard_quotes,
        start=args.start,
        end=end,
        lookback_sessions=args.lookback_sessions,
        top_n=args.top_n,
        minimum_presence=args.minimum_presence,
    )
    _write_csv(
        args.snapshots_output,
        snapshots,
        [
            "effective_date",
            "ticker",
            "rank",
            "presence",
            "avg_financial_volume",
            "issuer_name",
            "issuer_code",
            "lookback_sessions",
        ],
    )

    union = sorted({str(row["ticker"]) for row in snapshots})
    issuer_by_ticker: dict[str, str] = {}
    isin_by_ticker: dict[str, set[str]] = defaultdict(set)
    issuer_names: dict[str, str] = {}
    for quote in standard_quotes:
        ticker = quote.ticker.upper()
        if ticker not in union:
            continue
        issuer_by_ticker[ticker] = ticker[:4]
        issuer_names[ticker] = quote.issuer_name.strip().upper()
        if quote.isin:
            isin_by_ticker[ticker].add(quote.isin)

    manifest = {
        "schema_version": 1,
        "id": "point_in_time_trailing_liquidity_weekly",
        "selection_mode": "weekly_trailing_liquidity_only_past_information",
        "selected_as_of": args.start,
        "warmup_start": f"{min(years):04d}-01-01",
        "survivorship_safe": True,
        "point_in_time": True,
        "snapshot_file": str(args.snapshots_output),
        "selection_rules": {
            "source": "B3_COTAHIST_full_market",
            "instrument_filter": "BDI02_market010_and_specification_ON_PN_UNT",
            "lookback_sessions": args.lookback_sessions,
            "minimum_presence": args.minimum_presence,
            "top_n": args.top_n,
            "issuer_deduplication": True,
            "decision_frequency": "weekly",
            "future_continuity_filter": False
        },
        "tickers": union,
        "issuing_company_by_ticker": issuer_by_ticker,
        "issuer_name_by_ticker": issuer_names,
        "isins_by_ticker": {ticker: sorted(values) for ticker, values in isin_by_ticker.items()},
        "bias_disclosure": (
            "Each snapshot is selected only from COTAHIST observations at or before "
            "its effective_date. Historical symbols are not removed because they later "
            "delist or cease satisfying liquidity rules. Delisted and renamed symbols "
            "therefore remain in the historical candidate set while they actually traded."
        ),
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_output.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    execution_rows: list[dict[str, object]] = []
    union_set = set(union)
    for quote in standard_quotes:
        if quote.ticker.upper() in union_set and args.start <= quote.date <= end:
            execution_rows.append(
                {
                    "date": quote.date,
                    "ticker": quote.ticker.upper(),
                    "market_type": "010",
                    "open": quote.open,
                    "close": quote.close,
                    "financial_volume": quote.financial_volume,
                }
            )
    for quote in fractional_quotes:
        base = _base_fractional_ticker(quote.ticker)
        if base in union_set and args.start <= quote.date <= end:
            execution_rows.append(
                {
                    "date": quote.date,
                    "ticker": quote.ticker.upper(),
                    "market_type": "020",
                    "open": quote.open,
                    "close": quote.close,
                    "financial_volume": quote.financial_volume,
                }
            )
    execution_rows.sort(
        key=lambda row: (str(row["date"]), str(row["ticker"]), str(row["market_type"]))
    )
    _write_csv(
        args.execution_output,
        execution_rows,
        ["date", "ticker", "market_type", "open", "close", "financial_volume"],
    )

    print(f"Snapshots: {args.snapshots_output} ({len(snapshots)} rows)")
    print(f"Union: {args.manifest_output} ({len(union)} historical symbols)")
    print(f"Execution quotes: {args.execution_output} ({len(execution_rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
