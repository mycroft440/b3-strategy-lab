from __future__ import annotations

import csv
import hashlib
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
# The R$20k small-account tax guard is documented by Receita for shares (ações).
# B3 classifies UNITS separately as certificates of deposit of securities. Until a
# primary Receita source explicitly proves identical treatment for that exemption,
# certified/realistic point-in-time universes fail closed to ON/PN share classes.
CERTIFIED_SHARE_SPECIFICATIONS = ("ON", "PN")

# Audited against the official B3 COTAHIST_A2020 archive. These four positive-price
# company-equity records, all on 2020-06-08, have PREULT below PREMIN in the raw
# source. Only the OHLC envelope is repaired, preserving official open, close,
# average, trade count, quantity and financial volume. Hash pinning means any future
# source change fails closed instead of being silently normalized.
KNOWN_COTAHIST_OHLC_ENVELOPE_REPAIRS = {
    "8ac96d6b2dc976d06c90003952f92e5eee8ade0358b7afc06d81c2f7f83eeac1",  # EALT3
    "bfa588ef289a349ad8663c0c8dc88a05136ab7d57f8447c25343eee0959b63bd",  # RPAD6
    "baa1b7377ab67fa1b4d102ad2fdfc7515cbb7ff1aebba667329ace75ad28da9f",  # SULA3
    "fac58effbb5d77c898978362b061f15116798e7326c7f37c613c81bead312fe1",  # TRPL3
}


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
    return specification.startswith(CERTIFIED_SHARE_SPECIFICATIONS)


def base_fractional_ticker(ticker: str) -> str:
    value = ticker.strip().upper()
    if value.endswith("F") and len(value) > 1 and value[-2].isdigit():
        return value[:-1]
    return value


def _raw_record_sha256(line: str) -> str:
    core = line.rstrip("\r\n")
    return hashlib.sha256(core.encode("latin-1")).hexdigest()


def _all_ohlc_fields_zero(line: str) -> bool:
    core = line.rstrip("\r\n")
    if len(core) < 121:
        return False
    fields = (core[56:69], core[69:82], core[82:95], core[108:121])
    try:
        return all(int(value) == 0 for value in fields)
    except ValueError:
        return False


def _repair_known_ohlc_envelope(line: str) -> str:
    """Repair only hash-pinned official B3 envelope anomalies.

    Open and close are never changed. The high/low envelope is expanded only enough
    to contain the official open/close. Unknown positive-price inconsistencies are
    intentionally left untouched so the generic COTAHIST parser still fails closed.
    """
    if _raw_record_sha256(line) not in KNOWN_COTAHIST_OHLC_ENVELOPE_REPAIRS:
        return line
    core = line.rstrip("\r\n")
    suffix = line[len(core) :]
    open_raw = int(core[56:69])
    high_raw = int(core[69:82])
    low_raw = int(core[82:95])
    close_raw = int(core[108:121])
    repaired_high = max(high_raw, open_raw, close_raw)
    repaired_low = min(low_raw, open_raw, close_raw)
    repaired = (
        core[:69]
        + f"{repaired_high:013d}"
        + f"{repaired_low:013d}"
        + core[95:]
    )
    return repaired + suffix


def _mask_non_company_equity_records(
    lines,
    *,
    bdi_code: str,
    market_type: str,
):
    """Keep the COTAHIST envelope/count intact while sanitizing share inputs.

    Detail rows remain counted for trailer integrity. Records outside ON/PN company
    shares are masked before stock-specific validation. UNITS are deliberately
    excluded from this certified tax scope even though they trade in the cash
    market, because B3 classifies them as deposit certificates rather than shares.

    Company-share rows whose four official OHLC fields are all zero are also masked:
    they carry no usable official opening price, so they must be absent from the
    execution book rather than converted into a synthetic quote. If such a quote is
    later required by a real-money rebalance, the simulator fails closed.
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
            and specification.startswith(CERTIFIED_SHARE_SPECIFICATIONS)
        )
        if not company_equity or _all_ohlc_fields_zero(line):
            yield line[:10] + "ZZ" + line[12:]
            continue
        yield _repair_known_ohlc_envelope(line)


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
    """Read only standard-lot ON/PN company shares used by the certified universe."""
    return _read_company_equity_cotahist(
        path,
        bdi_code=STANDARD_BDI,
        market_type=STANDARD_MARKET,
    )


def read_fractional_cotahist(path: Path | str) -> list:
    """Read B3 fractional-market ON/PN company-share records.

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
                f"{decision}: only {len(selected)} point-in-time ON/PN shares satisfy the rules."
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
