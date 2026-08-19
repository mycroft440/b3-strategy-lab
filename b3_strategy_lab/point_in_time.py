from __future__ import annotations

import csv
import re
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

from .cotahist import parse_cotahist_lines


TICKER_RE = re.compile(r"^[A-Z]{4}\d{1,2}$")
STANDARD_MARKET = "010"
FRACTIONAL_MARKET = "020"
STANDARD_BDI = "02"
FRACTIONAL_BDI = "96"


def parse_years(values: list[str]) -> list[int]:
    result: set[int] = set()
    for value in values:
        if ":" in value:
            start, end = value.split(":", 1)
            result.update(range(int(start), int(end) + 1))
        else:
            result.add(int(value))
    if not result:
        raise ValueError("At least one year is required.")
    return sorted(result)


def is_company_equity(quote) -> bool:
    ticker = quote.ticker.strip().upper()
    if not TICKER_RE.fullmatch(ticker):
        return False
    specification = quote.specification.strip().upper()
    return specification.startswith(("ON", "PN", "UNT"))


def base_fractional_ticker(ticker: str) -> str:
    value = ticker.strip().upper()
    if value.endswith("F") and len(value) > 1 and value[-2].isdigit():
        return value[:-1]
    return value


def _mask_non_company_equity_records(
    lines,
    *,
    bdi_code: str,
    market_type: str,
):
    """Keep the COTAHIST envelope/count intact while skipping irrelevant instruments.

    parse_cotahist_lines counts every detail record before applying its BDI/market
    filters. For point-in-time stock selection, records outside ON/PN/UNT are not
    investable and should not be able to fail stock-specific OHLC validation. We
    therefore mask only their BDI code in-memory so the generic parser skips them
    after counting the detail row. Company equities are passed through unchanged
    and remain subject to all strict validations.
    """
    for raw_line in lines:
        line = raw_line.decode("latin-1") if isinstance(raw_line, bytes) else raw_line
        if len(line.rstrip("\r\n")) < 49 or line[:2] != "01":
            yield line
            continue
        if line[10:12] != bdi_code or line[24:27] != market_type:
            yield line
            continue

        ticker = line[12:24].strip().upper()
        base_ticker = base_fractional_ticker(ticker)
        specification = line[39:49].strip().upper()
        company_equity = bool(
            TICKER_RE.fullmatch(base_ticker)
            and specification.startswith(("ON", "PN", "UNT"))
        )
        if company_equity:
            yield line
        else:
            # Preserve line length and trailer accounting; force the parser's
            # normal BDI filter to skip a non-company-equity detail record.
            yield line[:10] + "ZZ" + line[12:]


def _read_company_equity_cotahist(
    path: Path | str,
    *,
    bdi_code: str,
    market_type: str,
) -> list:
    source = Path(path)
    kwargs = {
        "bdi_codes": (bdi_code,),
        "market_types": (market_type,),
        "require_envelope": True,
    }

    def parse(lines) -> list:
        return parse_cotahist_lines(
            _mask_non_company_equity_records(
                lines,
                bdi_code=bdi_code,
                market_type=market_type,
            ),
            **kwargs,
        )

    if source.suffix.lower() != ".zip":
        with source.open("rb") as file:
            return parse(file)
    with zipfile.ZipFile(source) as archive:
        members = [name for name in archive.namelist() if not name.endswith("/")]
        if len(members) != 1:
            raise ValueError(f"{source}: expected one COTAHIST member.")
        with archive.open(members[0]) as file:
            return parse(file)


def read_standard_company_equity_cotahist(path: Path | str) -> list:
    """Read only standard-lot company equities used by the point-in-time universe."""
    return _read_company_equity_cotahist(
        path,
        bdi_code=STANDARD_BDI,
        market_type=STANDARD_MARKET,
    )


def read_fractional_cotahist(path: Path | str) -> list:
    """Read B3 fractional-market company-equity records.

    COTAHIST identifies the fractional segment with market type 020 and BDI 96.
    Both filters must be changed together; keeping the standard-lot BDI 02 while
    requesting market 020 yields an empty book.
    """
    return _read_company_equity_cotahist(
        path,
        bdi_code=FRACTIONAL_BDI,
        market_type=FRACTIONAL_MARKET,
    )


def week_key(value: str) -> tuple[int, int]:
    point = date.fromisoformat(value)
    iso = point.isocalendar()
    return iso.year, iso.week


def weekly_decision_dates(all_dates: list[str], start: str, end: str) -> list[str]:
    result: list[str] = []
    for index, current in enumerate(all_dates):
        if current < start or current > end:
            continue
        following = all_dates[index + 1] if index + 1 < len(all_dates) else None
        if following is None or week_key(current) != week_key(following):
            result.append(current)
    return result


def snapshot_rows(
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
        if not is_company_equity(quote):
            continue
        by_date[quote.date].append(quote)
        all_dates.add(quote.date)
    dates = sorted(all_dates)
    date_index = {value: index for index, value in enumerate(dates)}
    decisions = weekly_decision_dates(dates, start, end)
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


def execution_rows(
    standard_quotes: list,
    fractional_quotes: list,
    *,
    union: set[str],
    start: str,
    end: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for quote in standard_quotes:
        ticker = quote.ticker.upper()
        if ticker in union and start <= quote.date <= end:
            rows.append(
                {
                    "date": quote.date,
                    "ticker": ticker,
                    "market_type": STANDARD_MARKET,
                    "open": quote.open,
                    "close": quote.close,
                    "financial_volume": quote.financial_volume,
                }
            )
    for quote in fractional_quotes:
        base = base_fractional_ticker(quote.ticker)
        if base in union and start <= quote.date <= end:
            rows.append(
                {
                    "date": quote.date,
                    "ticker": quote.ticker.upper(),
                    "market_type": FRACTIONAL_MARKET,
                    "open": quote.open,
                    "close": quote.close,
                    "financial_volume": quote.financial_volume,
                }
            )
    rows.sort(
        key=lambda row: (str(row["date"]), str(row["ticker"]), str(row["market_type"]))
    )
    return rows


def write_csv(path: Path | str, rows: list[dict[str, object]], fields: list[str]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
