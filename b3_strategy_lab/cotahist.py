from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

from .candles import (
    DEFAULT_ACTIONS_DIR,
    DEFAULT_DATA_DIR,
    Candle,
    CorporateAction,
    actions_path,
    cache_path,
    load_actions,
    load_candles,
    save_candles,
    validate_candles,
)


COTAHIST_URL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{year}.ZIP"
VERIFIED_SOURCE = "B3_COTAHIST"
MANIFEST_SCHEMA_VERSION = 4
DEFAULT_MANIFESTS_DIR = Path("data/manifests")
USER_AGENT = "Mozilla/5.0 (compatible; b3-strategy-lab/0.2)"
PRICE_VERIFIED_STATUS = "price_verified"
VERIFIED_ACTION_STATUS = "verified"
UNVERIFIED_ACTION_STATUS = "unverified"


class CotahistError(ValueError):
    pass


class DataVerificationError(ValueError):
    pass


@dataclass(frozen=True)
class OfficialQuote:
    date: str
    ticker: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    trades: int
    financial_volume: float
    quotation_factor: int
    bdi_code: str
    market_type: str


@dataclass(frozen=True)
class SourceArchive:
    year: int
    filename: str
    sha256: str
    url: str


@dataclass(frozen=True)
class WarningReview:
    warning: str
    evidence: str


@dataclass(frozen=True)
class DataManifest:
    schema_version: int
    status: str
    ticker: str
    interval: str
    rows: int
    start: str
    end: str
    price_source: str
    price_basis: str
    adjustment_method: str
    corporate_action_source: str
    corporate_action_status: str
    candle_sha256: str
    split_actions_sha256: str
    source_archives: tuple[SourceArchive, ...]
    validation_issues: tuple[str, ...]
    warnings: tuple[str, ...]
    warning_reviews: tuple[WarningReview, ...]
    generated_at_utc: str


def parse_cotahist_lines(
    lines: Iterable[bytes | str],
    *,
    tickers: Iterable[str] | None = None,
    bdi_codes: Iterable[str] = ("02",),
    market_types: Iterable[str] = ("010",),
    require_envelope: bool = False,
) -> list[OfficialQuote]:
    selected_tickers = {ticker.strip().upper() for ticker in tickers or []}
    selected_bdi = set(bdi_codes)
    selected_markets = set(market_types)
    quotes: dict[tuple[str, str], OfficialQuote] = {}
    header_line: int | None = None
    trailer_line: int | None = None
    trailer_count: int | None = None
    detail_records = 0
    total_lines = 0

    for line_number, raw_line in enumerate(lines, start=1):
        total_lines = line_number
        line = raw_line.decode("latin-1") if isinstance(raw_line, bytes) else raw_line
        line = line.rstrip("\r\n")
        if not line:
            continue
        if len(line) < 245:
            raise CotahistError(f"Linha COTAHIST {line_number} truncada: {len(line)} caracteres.")
        record_type = line[:2]
        if record_type == "00":
            if header_line is not None:
                raise CotahistError("COTAHIST possui mais de um cabecalho.")
            header_line = line_number
            continue
        if record_type == "99":
            if trailer_line is not None:
                raise CotahistError("COTAHIST possui mais de um trailer.")
            trailer_line = line_number
            trailer_count = _integer_field(line, 31, 42, line_number, "TOTREG")
            continue
        if record_type != "01":
            continue
        detail_records += 1

        bdi_code = line[10:12]
        ticker = line[12:24].strip().upper()
        market_type = line[24:27]
        if bdi_code not in selected_bdi or market_type not in selected_markets:
            continue
        if selected_tickers and ticker not in selected_tickers:
            continue

        quotation_factor = _integer_field(line, 210, 217, line_number, "FATCOT")
        if quotation_factor <= 0:
            quotation_factor = 1
        quote_date = _date_field(line[2:10], line_number)

        def price(start: int, end: int, field: str) -> float:
            return _integer_field(line, start, end, line_number, field) / 100 / quotation_factor

        quote = OfficialQuote(
            date=quote_date,
            ticker=ticker,
            open=price(56, 69, "PREABE"),
            high=price(69, 82, "PREMAX"),
            low=price(82, 95, "PREMIN"),
            close=price(108, 121, "PREULT"),
            volume=_integer_field(line, 152, 170, line_number, "QUATOT"),
            trades=_integer_field(line, 147, 152, line_number, "TOTNEG"),
            financial_volume=_integer_field(line, 170, 188, line_number, "VOLTOT") / 100,
            quotation_factor=quotation_factor,
            bdi_code=bdi_code,
            market_type=market_type,
        )
        _validate_quote(quote, line_number)
        key = (quote.ticker, quote.date)
        if key in quotes:
            raise CotahistError(f"Cotacao duplicada no COTAHIST: {quote.ticker} {quote.date}.")
        quotes[key] = quote

    if require_envelope:
        if header_line != 1:
            raise CotahistError("Cabecalho COTAHIST ausente ou fora da primeira linha.")
        if trailer_line != total_lines:
            raise CotahistError("Trailer COTAHIST ausente ou fora da ultima linha.")
        if trailer_count not in {detail_records, total_lines}:
            raise CotahistError(
                "Contagem do trailer COTAHIST diverge do arquivo: "
                f"{trailer_count} nao corresponde a {detail_records} registros "
                f"ou {total_lines} linhas."
            )

    return sorted(quotes.values(), key=lambda item: (item.ticker, item.date))


def read_cotahist(path: Path | str, *, tickers: Iterable[str] | None = None) -> list[OfficialQuote]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    if source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as archive:
            members = [name for name in archive.namelist() if not name.endswith("/")]
            if len(members) != 1:
                raise CotahistError(
                    f"{source}: esperado exatamente um arquivo COTAHIST; encontrados {members}."
                )
            with archive.open(members[0]) as file:
                return parse_cotahist_lines(file, tickers=tickers, require_envelope=True)
    with source.open("rb") as file:
        return parse_cotahist_lines(file, tickers=tickers, require_envelope=True)


def download_cotahist(
    year: int,
    output_dir: Path | str,
    *,
    refresh: bool = False,
) -> Path:
    if year < 1986 or year > date.today().year:
        raise ValueError(f"Ano COTAHIST invalido: {year}.")
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / f"COTAHIST_A{year}.ZIP"
    url = COTAHIST_URL.format(year=year)

    if output.exists() and not refresh:
        _check_zip(output)
        return output

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    fd, temporary_name = tempfile.mkstemp(prefix=f".cotahist-{year}-", suffix=".zip", dir=directory)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as file:
            while chunk := response.read(1024 * 1024):
                file.write(chunk)
        _check_zip(temporary)
        temporary.replace(output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return output


def build_verified_daily_candles(
    ticker: str,
    quotes: Iterable[OfficialQuote],
    actions: Iterable[CorporateAction],
) -> tuple[list[Candle], list[str]]:
    normalized_ticker = ticker.strip().upper()
    ticker_quotes = sorted(
        (quote for quote in quotes if quote.ticker == normalized_ticker),
        key=lambda quote: quote.date,
    )
    if not ticker_quotes:
        raise CotahistError(f"Nenhuma cotacao oficial encontrada para {normalized_ticker}.")
    if len({quote.date for quote in ticker_quotes}) != len(ticker_quotes):
        raise CotahistError(f"Datas oficiais duplicadas para {normalized_ticker}.")

    ticker_actions = _merge_actions(
        action for action in actions if action.ticker.upper() == normalized_ticker
    )
    final_quote_date = ticker_quotes[-1].date
    ticker_actions = [action for action in ticker_actions if action.date <= final_quote_date]
    split_actions = [action for action in ticker_actions if action.split_ratio != 1.0]
    raw_values: dict[str, tuple[float, float, float, float, int]] = {}
    for quote in ticker_quotes:
        future_split = math.prod(
            action.split_ratio
            for action in split_actions
            if action.date > quote.date
        )
        if not math.isfinite(future_split) or future_split <= 0:
            raise CotahistError(f"Fator de split invalido para {normalized_ticker} {quote.date}: {future_split}.")
        prices = tuple(value / future_split for value in (quote.open, quote.high, quote.low, quote.close))
        normalized_volume = int(round(quote.volume * future_split))
        values = (*prices, normalized_volume)
        raw_values[quote.date] = values

    warnings: list[str] = []

    candles: list[Candle] = []
    for quote in ticker_quotes:
        raw_open, raw_high, raw_low, raw_close, normalized_volume = raw_values[quote.date]
        candles.append(
            Candle(
                date=quote.date,
                ticker=normalized_ticker,
                source_symbol=normalized_ticker,
                open=raw_open,
                high=raw_high,
                low=raw_low,
                close=raw_close,
                adj_close=raw_close,
                volume=normalized_volume,
                raw_open=raw_open,
                raw_high=raw_high,
                raw_low=raw_low,
                raw_close=raw_close,
                adjustment_factor=1.0,
                source_high=raw_high,
                source_low=raw_low,
                ohlc_repaired=0,
            )
        )

    issues = validate_candles(candles)
    if issues:
        raise CotahistError(f"Dados oficiais invalidos para {normalized_ticker}: {issues[0]}")
    warnings.extend(_large_move_warnings(candles, split_actions))
    return candles, warnings


def resample_daily_to_weekly(candles: list[Candle]) -> list[Candle]:
    if not candles:
        return []
    grouped: dict[tuple[int, int], list[Candle]] = {}
    for candle in candles:
        point = date.fromisoformat(candle.date)
        iso = point.isocalendar()
        grouped.setdefault((iso.year, iso.week), []).append(candle)

    result: list[Candle] = []
    for key in sorted(grouped):
        bucket = sorted(grouped[key], key=lambda candle: candle.date)
        first = bucket[0]
        last = bucket[-1]
        adjusted_high = max(candle.high for candle in bucket)
        adjusted_low = min(candle.low for candle in bucket)
        raw_high = max(candle.raw_high for candle in bucket)
        raw_low = min(candle.raw_low for candle in bucket)
        result.append(
            Candle(
                date=first.date,
                ticker=first.ticker,
                source_symbol=first.source_symbol,
                open=first.open,
                high=adjusted_high,
                low=adjusted_low,
                close=last.close,
                adj_close=last.adj_close,
                volume=sum(candle.volume for candle in bucket),
                raw_open=first.raw_open,
                raw_high=raw_high,
                raw_low=raw_low,
                raw_close=last.raw_close,
                adjustment_factor=last.adjustment_factor,
                source_high=max(candle.source_high for candle in bucket),
                source_low=min(candle.source_low for candle in bucket),
                ohlc_repaired=0,
            )
        )
    issues = validate_candles(result)
    if issues:
        raise CotahistError(f"Serie semanal derivada invalida: {issues[0]}")
    return result


def manifest_path(
    ticker: str,
    interval: str,
    manifests_dir: Path | str = DEFAULT_MANIFESTS_DIR,
) -> Path:
    return Path(manifests_dir) / f"{ticker.strip().lower()}_{interval}.json"


def create_manifest(
    *,
    ticker: str,
    interval: str,
    candles_path: Path | str,
    actions_path: Path | str,
    source_archives: Iterable[SourceArchive],
    corporate_action_source: str = "Yahoo Chart events",
    corporate_action_status: str = UNVERIFIED_ACTION_STATUS,
    warnings: Iterable[str] = (),
    warning_reviews: Mapping[str, str] | None = None,
    validation_issues: Iterable[str] = (),
) -> DataManifest:
    candles = load_candles(candles_path)
    issues = tuple(validation_issues) or tuple(validate_candles(candles))
    warning_values = tuple(warnings)
    review_values = warning_reviews or {}
    return DataManifest(
        schema_version=MANIFEST_SCHEMA_VERSION,
        status=PRICE_VERIFIED_STATUS if not issues else "rejected",
        ticker=ticker.strip().upper(),
        interval=interval,
        rows=len(candles),
        start=candles[0].date if candles else "",
        end=candles[-1].date if candles else "",
        price_source=VERIFIED_SOURCE,
        price_basis=(
            "B3 official per-share quotes normalized for splits; "
            "cash distributions excluded"
        ),
        adjustment_method=(
            "split normalization only; dividends and JCP ignored; no tax; no fees"
        ),
        corporate_action_source=corporate_action_source,
        corporate_action_status=corporate_action_status,
        candle_sha256=sha256_file(candles_path),
        split_actions_sha256=(
            sha256_split_actions(actions_path) if Path(actions_path).exists() else ""
        ),
        source_archives=tuple(source_archives),
        validation_issues=issues,
        warnings=warning_values,
        warning_reviews=tuple(
            WarningReview(warning=warning, evidence=review_values[warning])
            for warning in warning_values
            if warning in review_values
        ),
        generated_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )


def write_manifest(manifest: DataManifest, path: Path | str) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(manifest)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(output)
    return output


def load_manifest(path: Path | str) -> DataManifest:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if "split_actions_sha256" not in payload and "actions_sha256" in payload:
        payload["split_actions_sha256"] = payload.pop("actions_sha256")
    payload["source_archives"] = tuple(SourceArchive(**item) for item in payload.get("source_archives", []))
    payload["validation_issues"] = tuple(payload.get("validation_issues", []))
    payload["warnings"] = tuple(payload.get("warnings", []))
    payload["warning_reviews"] = tuple(
        WarningReview(**item) for item in payload.get("warning_reviews", [])
    )
    return DataManifest(**payload)


def verify_dataset(
    candles_path: Path | str,
    actions_path: Path | str,
    manifest_file: Path | str,
    *,
    ticker: str | None = None,
    interval: str | None = None,
    require_verified_actions: bool = False,
) -> DataManifest:
    candle_file = Path(candles_path)
    action_file = Path(actions_path)
    manifest_path_value = Path(manifest_file)
    if not candle_file.exists():
        raise DataVerificationError(f"Arquivo de candles ausente: {candle_file}.")
    if not manifest_path_value.exists():
        raise DataVerificationError(
            f"Manifesto ausente para {candle_file}. Gere os dados oficiais antes do backtest."
        )
    manifest = load_manifest(manifest_path_value)
    expected_ticker = ticker.strip().upper() if ticker else None
    if manifest.schema_version != MANIFEST_SCHEMA_VERSION:
        raise DataVerificationError(
            f"Schema de manifesto nao suportado: {manifest.schema_version}; esperado {MANIFEST_SCHEMA_VERSION}."
        )
    if manifest.status != PRICE_VERIFIED_STATUS or manifest.validation_issues:
        raise DataVerificationError(f"Dataset rejeitado no manifesto: {manifest.validation_issues}.")
    reviewed_warnings = {review.warning for review in manifest.warning_reviews}
    unreviewed_warnings = [
        warning for warning in manifest.warnings if warning not in reviewed_warnings
    ]
    if unreviewed_warnings:
        raise DataVerificationError(
            f"Dataset possui anomalia sem revisao: {unreviewed_warnings[0]}"
        )
    if expected_ticker and manifest.ticker != expected_ticker:
        raise DataVerificationError(f"Ticker do manifesto {manifest.ticker} != {expected_ticker}.")
    if interval and manifest.interval != interval:
        raise DataVerificationError(f"Intervalo do manifesto {manifest.interval} != {interval}.")
    if manifest.price_source != VERIFIED_SOURCE:
        raise DataVerificationError(f"Fonte nao verificada: {manifest.price_source}.")
    if require_verified_actions and manifest.corporate_action_status != VERIFIED_ACTION_STATUS:
        raise DataVerificationError(
            "Eventos corporativos ainda nao foram certificados por uma fonte oficial estruturada. "
            "O preco COTAHIST esta verificado, mas um backtest com proventos brutos nao e seguro."
        )
    if sha256_file(candle_file) != manifest.candle_sha256:
        raise DataVerificationError(f"Hash dos candles diverge do manifesto: {candle_file}.")
    current_split_hash = sha256_split_actions(action_file) if action_file.exists() else ""
    if current_split_hash != manifest.split_actions_sha256:
        raise DataVerificationError(
            f"Hash das razoes de split diverge do manifesto: {action_file}."
        )

    candles = load_candles(candle_file)
    issues = validate_candles(candles)
    if issues:
        raise DataVerificationError(f"Dataset possui candles invalidos: {issues[0]}")
    if len(candles) != manifest.rows:
        raise DataVerificationError(f"Quantidade de candles diverge do manifesto: {len(candles)} != {manifest.rows}.")
    if candles and (candles[0].date != manifest.start or candles[-1].date != manifest.end):
        raise DataVerificationError("Janela dos candles diverge do manifesto.")
    return manifest


def load_verified_candles(
    ticker: str,
    interval: str,
    *,
    data_dir: Path | str = DEFAULT_DATA_DIR,
    actions_dir: Path | str = DEFAULT_ACTIONS_DIR,
    manifests_dir: Path | str = DEFAULT_MANIFESTS_DIR,
    start: str | None = None,
    end: str | None = None,
    require_verified_actions: bool = False,
) -> tuple[list[Candle], DataManifest]:
    candle_file = cache_path(ticker, interval, data_dir)
    action_file = actions_path(ticker, actions_dir)
    manifest_file = manifest_path(ticker, interval, manifests_dir)
    manifest = verify_dataset(
        candle_file,
        action_file,
        manifest_file,
        ticker=ticker,
        interval=interval,
        require_verified_actions=require_verified_actions,
    )
    return load_candles(candle_file, start=start, end=end), manifest


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_split_actions(path: Path | str) -> str:
    split_rows = sorted(
        (
            {
                "date": action.date,
                "ticker": action.ticker,
                "source_symbol": action.source_symbol,
                "split_ratio": action.split_ratio,
            }
            for action in load_actions(path)
            if action.split_ratio != 1.0
        ),
        key=lambda row: (
            row["date"],
            row["ticker"],
            row["source_symbol"],
            row["split_ratio"],
        ),
    )
    payload = json.dumps(
        split_rows,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def source_archive(path: Path | str, year: int) -> SourceArchive:
    source = Path(path)
    return SourceArchive(
        year=year,
        filename=source.name,
        sha256=sha256_file(source),
        url=COTAHIST_URL.format(year=year),
    )


def save_verified_candles(candles: list[Candle], path: Path | str) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    save_candles(candles, temporary)
    temporary.replace(output)
    return output


def _integer_field(line: str, start: int, end: int, line_number: int, field: str) -> int:
    value = line[start:end]
    if not value.strip():
        return 0
    try:
        return int(value)
    except ValueError as error:
        raise CotahistError(f"Linha {line_number}: campo {field} invalido: {value!r}.") from error


def _date_field(value: str, line_number: int) -> str:
    try:
        return datetime.strptime(value, "%Y%m%d").date().isoformat()
    except ValueError as error:
        raise CotahistError(f"Linha {line_number}: data invalida: {value!r}.") from error


def _validate_quote(quote: OfficialQuote, line_number: int) -> None:
    values = (quote.open, quote.high, quote.low, quote.close)
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise CotahistError(f"Linha {line_number}: OHLC nao positivo para {quote.ticker} {quote.date}.")
    if quote.high < max(quote.open, quote.close) or quote.low > min(quote.open, quote.close):
        raise CotahistError(f"Linha {line_number}: OHLC inconsistente para {quote.ticker} {quote.date}.")
    if quote.high < quote.low:
        raise CotahistError(f"Linha {line_number}: maxima menor que minima para {quote.ticker} {quote.date}.")
    if quote.volume < 0 or quote.trades < 0 or quote.financial_volume < 0:
        raise CotahistError(f"Linha {line_number}: volume/negocios negativos para {quote.ticker} {quote.date}.")


def _check_zip(path: Path) -> None:
    if not zipfile.is_zipfile(path):
        raise CotahistError(f"Arquivo baixado nao e ZIP valido: {path}.")
    with zipfile.ZipFile(path) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise CotahistError(f"CRC invalido no COTAHIST: {bad_member}.")


def _large_move_warnings(candles: list[Candle], split_actions: list[CorporateAction]) -> list[str]:
    split_dates = {action.date for action in split_actions}
    warnings: list[str] = []
    for previous, current in zip(candles, candles[1:]):
        if previous.raw_close <= 0:
            continue
        move = current.raw_close / previous.raw_close - 1
        if abs(move) > 0.15 and current.date in split_dates:
            warnings.append(
                f"{current.ticker} {current.date}: variacao de fechamento apos "
                f"normalizacao de split de {move:.2%}."
            )
        elif abs(move) > 0.5:
            warnings.append(
                f"{current.ticker} {current.date}: variacao de fechamento sem split de {move:.2%}."
            )
    return warnings


def _merge_actions(actions: Iterable[CorporateAction]) -> list[CorporateAction]:
    merged: dict[str, CorporateAction] = {}
    for action in sorted(actions, key=lambda item: item.date):
        existing = merged.get(action.date)
        if existing is None:
            merged[action.date] = action
            continue
        merged[action.date] = CorporateAction(
            date=action.date,
            ticker=action.ticker,
            source_symbol=action.source_symbol,
            dividend=existing.dividend + action.dividend,
            split_ratio=existing.split_ratio * action.split_ratio,
        )
    return [merged[action_date] for action_date in sorted(merged)]
