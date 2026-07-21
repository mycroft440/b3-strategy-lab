from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_TICKERS = ("BBSE3", "VALE3", "GGBR3", "LOGG3", "PETR4", "TUPY3", "MLAS3")
SUPPORTED_INTERVALS = {"1d", "4h", "1wk", "1mo"}
DEFAULT_DATA_DIR = Path("data/candles")
DEFAULT_ACTIONS_DIR = Path("data/corporate_actions")
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
USER_AGENT = "Mozilla/5.0 (compatible; b3-strategy-lab/0.1)"


@dataclass(frozen=True)
class Candle:
    date: str
    ticker: str
    source_symbol: str
    open: float
    high: float
    low: float
    close: float
    adj_close: float
    volume: int
    raw_open: float
    raw_high: float
    raw_low: float
    raw_close: float
    adjustment_factor: float
    source_high: float = 0.0
    source_low: float = 0.0
    ohlc_repaired: int = 0


@dataclass(frozen=True)
class CorporateAction:
    date: str
    ticker: str
    source_symbol: str
    dividend: float
    split_ratio: float


CSV_FIELDS = [field for field in Candle.__dataclass_fields__]
ACTION_FIELDS = [field for field in CorporateAction.__dataclass_fields__]


def normalize_ticker(ticker: str) -> str:
    normalized = ticker.strip().upper().replace(" ", "")
    if not normalized:
        raise ValueError("Ticker vazio.")
    if normalized.endswith(".SA"):
        normalized = normalized.removesuffix(".SA")
    return normalized


def yahoo_symbol(ticker: str) -> str:
    return f"{normalize_ticker(ticker)}.SA"


def cache_path(ticker: str, interval: str = "1d", data_dir: Path | str = DEFAULT_DATA_DIR) -> Path:
    return Path(data_dir) / f"{normalize_ticker(ticker).lower()}_{interval}.csv"


def actions_path(ticker: str, data_dir: Path | str = DEFAULT_ACTIONS_DIR) -> Path:
    return Path(data_dir) / f"{normalize_ticker(ticker).lower()}_actions.csv"


def fetch_candles(
    ticker: str,
    *,
    interval: str = "1d",
    range_name: str = "max",
    start: str | None = None,
    end: str | None = None,
) -> list[Candle]:
    if interval not in SUPPORTED_INTERVALS:
        allowed = ", ".join(sorted(SUPPORTED_INTERVALS))
        raise ValueError(f"Intervalo invalido: {interval}. Use um destes: {allowed}.")

    candles, _actions = fetch_candles_and_actions(
        ticker,
        interval=interval,
        range_name=range_name,
        start=start,
        end=end,
    )
    return filter_candles(candles, start=start, end=end)


def fetch_candles_and_actions(
    ticker: str,
    *,
    interval: str = "1d",
    range_name: str = "max",
    start: str | None = None,
    end: str | None = None,
) -> tuple[list[Candle], list[CorporateAction]]:
    if interval not in SUPPORTED_INTERVALS:
        allowed = ", ".join(sorted(SUPPORTED_INTERVALS))
        raise ValueError(f"Intervalo invalido: {interval}. Use um destes: {allowed}.")

    symbol = yahoo_symbol(ticker)
    yahoo_interval = "60m" if interval == "4h" else interval
    effective_range = "730d" if interval == "4h" and range_name == "max" and not start and not end else range_name
    params = _chart_params(range_name=effective_range, interval=yahoo_interval, start=start, end=end)
    url = f"{YAHOO_CHART_URL.format(symbol=symbol)}?{urlencode(params)}"
    payload = _download_json(url)
    normalized = normalize_ticker(ticker)
    candles = parse_yahoo_chart(payload, normalized, symbol, include_time=interval == "4h")
    if interval == "4h":
        candles = resample_to_4h(candles)
    actions = parse_yahoo_actions(payload, normalized, symbol)
    return filter_candles(candles, start=start, end=end), filter_actions(actions, start=start, end=end)


def fetch_actions(ticker: str, *, range_name: str = "max") -> list[CorporateAction]:
    symbol = yahoo_symbol(ticker)
    params = _chart_params(range_name=range_name, interval="1d", start=None, end=None)
    url = f"{YAHOO_CHART_URL.format(symbol=symbol)}?{urlencode(params)}"
    payload = _download_json(url)
    normalized = normalize_ticker(ticker)
    return parse_yahoo_actions(payload, normalized, symbol)


def _chart_params(*, range_name: str, interval: str, start: str | None, end: str | None) -> dict[str, str | int]:
    params: dict[str, str | int] = {
        "interval": interval,
        "events": "history,div,splits",
        "includeAdjustedClose": "true",
    }

    if range_name == "max" or start or end:
        params["period1"] = _period_start(start)
        params["period2"] = _period_end(end)
    else:
        params["range"] = range_name

    return params


def parse_yahoo_chart(payload: dict, ticker: str, source_symbol: str, *, include_time: bool = False) -> list[Candle]:
    chart = payload.get("chart", {})
    error = chart.get("error")
    if error:
        description = error.get("description") or str(error)
        raise RuntimeError(f"Erro da fonte ao buscar {source_symbol}: {description}")

    results = chart.get("result") or []
    if not results:
        raise RuntimeError(f"Nenhum candle retornado para {source_symbol}.")

    result = results[0]
    exchange_tz = _exchange_timezone(result)
    timestamps = result.get("timestamp") or []
    indicators = result.get("indicators") or {}
    quote = (indicators.get("quote") or [{}])[0]
    adjclose = (indicators.get("adjclose") or [{}])[0].get("adjclose") or []

    parsed: dict[str, Candle] = {}
    for index, timestamp in enumerate(timestamps):
        raw_open = _number_at(quote, "open", index)
        source_high = _number_at(quote, "high", index)
        source_low = _number_at(quote, "low", index)
        raw_close = _number_at(quote, "close", index)
        volume = _int_at(quote, "volume", index)
        adjusted_close = _value_at(adjclose, index)

        if None in (raw_open, source_high, source_low, raw_close):
            continue
        if raw_open <= 0 or source_high <= 0 or source_low <= 0 or raw_close <= 0:
            continue

        raw_high = max(source_high, raw_open, raw_close)
        raw_low = min(source_low, raw_open, raw_close)
        ohlc_repaired = int(raw_high != source_high or raw_low != source_low)

        if adjusted_close is None or adjusted_close <= 0:
            adjusted_close = raw_close

        factor = adjusted_close / raw_close
        if not math.isfinite(factor) or factor <= 0:
            factor = 1.0

        candle_datetime = datetime.fromtimestamp(int(timestamp), exchange_tz)
        if include_time:
            candle_date = candle_datetime.replace(tzinfo=None).isoformat(sep=" ", timespec="seconds")
        else:
            candle_date = candle_datetime.date().isoformat()
        parsed[candle_date] = Candle(
            date=candle_date,
            ticker=ticker,
            source_symbol=source_symbol,
            open=raw_open * factor,
            high=raw_high * factor,
            low=raw_low * factor,
            close=adjusted_close,
            adj_close=adjusted_close,
            volume=volume or 0,
            raw_open=raw_open,
            raw_high=raw_high,
            raw_low=raw_low,
            raw_close=raw_close,
            adjustment_factor=factor,
            source_high=source_high,
            source_low=source_low,
            ohlc_repaired=ohlc_repaired,
        )

    return [parsed[key] for key in sorted(parsed)]


def resample_to_4h(candles: list[Candle]) -> list[Candle]:
    grouped: dict[str, list[Candle]] = {}
    for candle in candles:
        grouped.setdefault(_date_part(candle.date), []).append(candle)

    result: list[Candle] = []
    for day in sorted(grouped):
        day_candles = sorted(grouped[day], key=lambda candle: candle.date)
        if len(day_candles) < 8:
            continue
        for start in range(0, len(day_candles), 4):
            bucket = day_candles[start : start + 4]
            if len(bucket) < 4:
                continue
            first = bucket[0]
            last = bucket[-1]
            raw_high = max(candle.raw_high for candle in bucket)
            raw_low = min(candle.raw_low for candle in bucket)
            raw_close = last.raw_close
            adj_close = last.adj_close
            factor = adj_close / raw_close if raw_close else 1.0
            if not math.isfinite(factor) or factor <= 0:
                factor = 1.0
            result.append(
                Candle(
                    date=first.date,
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
                    source_high=max(candle.source_high for candle in bucket),
                    source_low=min(candle.source_low for candle in bucket),
                    ohlc_repaired=int(any(candle.ohlc_repaired for candle in bucket)),
                )
            )
    return result


def parse_yahoo_actions(payload: dict, ticker: str, source_symbol: str) -> list[CorporateAction]:
    results = (payload.get("chart", {}).get("result") or [])
    if not results:
        return []

    result = results[0]
    exchange_tz = _exchange_timezone(result)
    events = result.get("events") or {}
    by_date: dict[str, dict[str, float]] = {}

    for event in (events.get("dividends") or {}).values():
        action_date = datetime.fromtimestamp(int(event["date"]), exchange_tz).date().isoformat()
        values = by_date.setdefault(action_date, {"dividend": 0.0, "split_ratio": 1.0})
        values["dividend"] += float(event.get("amount") or 0.0)

    for event in (events.get("splits") or {}).values():
        numerator = float(event.get("numerator") or 1.0)
        denominator = float(event.get("denominator") or 1.0)
        if denominator == 0:
            continue
        action_date = datetime.fromtimestamp(int(event["date"]), exchange_tz).date().isoformat()
        values = by_date.setdefault(action_date, {"dividend": 0.0, "split_ratio": 1.0})
        values["split_ratio"] *= numerator / denominator

    return [
        CorporateAction(
            date=action_date,
            ticker=ticker,
            source_symbol=source_symbol,
            dividend=values["dividend"],
            split_ratio=values["split_ratio"],
        )
        for action_date, values in sorted(by_date.items())
    ]


def filter_candles(candles: Iterable[Candle], *, start: str | None = None, end: str | None = None) -> list[Candle]:
    start_date = date.fromisoformat(start) if start else None
    end_date = date.fromisoformat(end) if end else None
    filtered: list[Candle] = []

    for candle in candles:
        candle_date = date.fromisoformat(_date_part(candle.date))
        if start_date and candle_date < start_date:
            continue
        if end_date and candle_date > end_date:
            continue
        filtered.append(candle)

    return filtered


def _date_part(value: str) -> str:
    return value.split("T", 1)[0].split(" ", 1)[0]


def filter_actions(actions: Iterable[CorporateAction], *, start: str | None = None, end: str | None = None) -> list[CorporateAction]:
    start_date = date.fromisoformat(start) if start else None
    end_date = date.fromisoformat(end) if end else None
    filtered: list[CorporateAction] = []

    for action in actions:
        action_date = date.fromisoformat(action.date)
        if start_date and action_date < start_date:
            continue
        if end_date and action_date > end_date:
            continue
        filtered.append(action)

    return filtered


def save_candles(candles: list[Candle], path: Path | str) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for candle in candles:
            writer.writerow(asdict(candle))
    return output


def save_actions(actions: list[CorporateAction], path: Path | str) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=ACTION_FIELDS)
        writer.writeheader()
        for action in actions:
            writer.writerow(asdict(action))
    return output


def load_candles(path: Path | str, *, start: str | None = None, end: str | None = None) -> list[Candle]:
    candles: list[Candle] = []
    with Path(path).open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            candles.append(
                Candle(
                    date=row["date"],
                    ticker=row["ticker"],
                    source_symbol=row["source_symbol"],
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    adj_close=float(row["adj_close"]),
                    volume=int(float(row["volume"])),
                    raw_open=float(row["raw_open"]),
                    raw_high=float(row["raw_high"]),
                    raw_low=float(row["raw_low"]),
                    raw_close=float(row["raw_close"]),
                    adjustment_factor=float(row["adjustment_factor"]),
                    source_high=float(row.get("source_high") or row["raw_high"]),
                    source_low=float(row.get("source_low") or row["raw_low"]),
                    ohlc_repaired=int(float(row.get("ohlc_repaired") or 0)),
                )
            )
    return filter_candles(candles, start=start, end=end)


def load_actions(path: Path | str, *, start: str | None = None, end: str | None = None) -> list[CorporateAction]:
    if not Path(path).exists():
        return []

    actions: list[CorporateAction] = []
    with Path(path).open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            actions.append(
                CorporateAction(
                    date=row["date"],
                    ticker=row["ticker"],
                    source_symbol=row["source_symbol"],
                    dividend=float(row["dividend"]),
                    split_ratio=float(row["split_ratio"]),
                )
            )
    return filter_actions(actions, start=start, end=end)


def fetch_and_cache(
    ticker: str,
    *,
    interval: str = "1d",
    range_name: str = "max",
    data_dir: Path | str = DEFAULT_DATA_DIR,
    actions_dir: Path | str = DEFAULT_ACTIONS_DIR,
    start: str | None = None,
    end: str | None = None,
) -> tuple[Path, list[Candle], Path, list[CorporateAction]]:
    candles, actions = fetch_candles_and_actions(ticker, interval=interval, range_name=range_name, start=start, end=end)
    path = cache_path(ticker, interval, data_dir)
    action_path = actions_path(ticker, actions_dir)
    if interval == "4h" or start or end or range_name != "max":
        actions = fetch_actions(ticker)
    save_candles(candles, path)
    save_actions(actions, action_path)
    return path, candles, action_path, actions


def validate_candles(candles: list[Candle]) -> list[str]:
    issues: list[str] = []
    previous_date: str | None = None
    previous_close: float | None = None
    tolerance = 1e-8

    for candle in candles:
        if previous_date and candle.date <= previous_date:
            issues.append(f"{candle.ticker} {candle.date}: datas fora de ordem ou duplicadas.")
        previous_date = candle.date

        if candle.high + tolerance < max(candle.open, candle.close) or candle.low - tolerance > min(candle.open, candle.close):
            issues.append(f"{candle.ticker} {candle.date}: OHLC ajustado inconsistente.")
        if candle.raw_high + tolerance < max(candle.raw_open, candle.raw_close) or candle.raw_low - tolerance > min(candle.raw_open, candle.raw_close):
            issues.append(f"{candle.ticker} {candle.date}: OHLC cru inconsistente.")
        if candle.high + tolerance < candle.low or candle.raw_high + tolerance < candle.raw_low:
            issues.append(f"{candle.ticker} {candle.date}: maxima menor que minima.")
        if min(candle.open, candle.high, candle.low, candle.close, candle.adj_close) <= 0:
            issues.append(f"{candle.ticker} {candle.date}: OHLC ajustado nao positivo.")
        if min(candle.raw_open, candle.raw_high, candle.raw_low, candle.raw_close) <= 0:
            issues.append(f"{candle.ticker} {candle.date}: OHLC cru nao positivo.")
        if min(candle.source_high, candle.source_low) <= 0:
            issues.append(f"{candle.ticker} {candle.date}: maxima/minima da fonte nao positiva.")
        if candle.volume < 0:
            issues.append(f"{candle.ticker} {candle.date}: volume negativo.")
        if candle.volume == 0 and (
            abs(candle.raw_high - candle.raw_low) > tolerance
            or abs(candle.raw_open - candle.raw_close) > tolerance
        ):
            issues.append(f"{candle.ticker} {candle.date}: volume zero com OHLC variando.")
        if candle.close <= 0 or candle.raw_close <= 0:
            issues.append(f"{candle.ticker} {candle.date}: fechamento nao positivo.")
        expected_open = candle.raw_open * candle.adjustment_factor
        expected_high = candle.raw_high * candle.adjustment_factor
        expected_low = candle.raw_low * candle.adjustment_factor
        expected_close = candle.raw_close * candle.adjustment_factor
        if (
            abs(candle.open - expected_open) > 1e-5
            or abs(candle.high - expected_high) > 1e-5
            or abs(candle.low - expected_low) > 1e-5
            or abs(candle.close - expected_close) > 1e-5
            or abs(candle.adj_close - expected_close) > 1e-5
        ):
            issues.append(f"{candle.ticker} {candle.date}: fator de ajuste inconsistente.")
        if candle.raw_low > 0 and candle.raw_high / candle.raw_low - 1 > 5:
            issues.append(f"{candle.ticker} {candle.date}: range cru extremo.")
        if previous_close and previous_close > 0 and abs(candle.raw_close / previous_close - 1) > 2:
            issues.append(f"{candle.ticker} {candle.date}: retorno cru extremo.")
        previous_close = candle.raw_close

    return issues


def _period_start(start: str | None) -> int:
    if not start:
        return 0
    start_date = date.fromisoformat(start)
    return int(datetime.combine(start_date, datetime_time.min, tzinfo=timezone.utc).timestamp())


def _period_end(end: str | None) -> int:
    if not end:
        return int(datetime.now(tz=timezone.utc).timestamp())
    end_date = date.fromisoformat(end) + timedelta(days=1)
    return int(datetime.combine(end_date, datetime_time.min, tzinfo=timezone.utc).timestamp())


def _download_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def _exchange_timezone(result: dict):
    timezone_name = result.get("meta", {}).get("exchangeTimezoneName") or "UTC"
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return timezone.utc


def _number_at(values: dict, key: str, index: int) -> float | None:
    value = _value_at(values.get(key) or [], index)
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _int_at(values: dict, key: str, index: int) -> int | None:
    value = _value_at(values.get(key) or [], index)
    if value is None:
        return None
    return int(value)


def _value_at(values: list, index: int):
    if index >= len(values):
        return None
    return values[index]
