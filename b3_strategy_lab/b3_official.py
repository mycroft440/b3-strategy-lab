from __future__ import annotations

import base64
import hashlib
import json
import math
import subprocess
import time
import unicodedata
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Iterable, Mapping, Sequence
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .candles import CorporateAction


B3_LISTED_COMPANIES_URL = (
    "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/"
    "CompanyCall/GetListedSupplementCompany/{payload}"
)
USER_AGENT = "Mozilla/5.0 (compatible; b3-strategy-lab/0.3)"
SHARE_COUNT_EVENT_LABELS = {"BONIFICACAO", "DESDOBRAMENTO", "GRUPAMENTO"}


class B3CorporateActionError(ValueError):
    pass


@dataclass(frozen=True)
class OfficialSplitEvent:
    ticker: str
    ex_date: str
    last_date_prior: str
    split_ratio: float
    event: str
    source_url: str
    source_authority: str = "B3"
    source_symbol: str = "B3_LISTED_COMPANIES"

    def action(self) -> CorporateAction:
        return CorporateAction(
            date=self.ex_date,
            ticker=self.ticker,
            source_symbol=self.source_symbol,
            dividend=0.0,
            split_ratio=self.split_ratio,
        )

    def evidence(self) -> dict[str, object]:
        return {
            "ticker": self.ticker,
            "ex_date": self.ex_date,
            "last_date_prior": self.last_date_prior,
            "split_ratio": self.split_ratio,
            "event": self.event,
            "source_authority": self.source_authority,
            "source_url": self.source_url,
        }


def b3_supplement_url(issuing_company: str) -> str:
    code = issuing_company.strip().upper()
    if not code:
        raise ValueError("Codigo da companhia emissora vazio.")
    encoded = base64.b64encode(
        json.dumps(
            {"issuingCompany": code, "language": "pt-br"},
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).decode("ascii")
    return B3_LISTED_COMPANIES_URL.format(payload=encoded)


def download_b3_supplement(
    issuing_company: str,
    *,
    attempts: int = 6,
    timeout: int = 60,
) -> list[dict[str, object]]:
    if attempts <= 0:
        raise ValueError("attempts precisa ser positivo.")
    url = b3_supplement_url(issuing_company)
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = Request(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": USER_AGENT,
                },
            )
            with urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
            if not isinstance(payload, list) or not payload:
                raise B3CorporateActionError(
                    f"Resposta vazia/invalida para {issuing_company.strip().upper()}."
                )
            if not all(isinstance(item, dict) for item in payload):
                raise B3CorporateActionError(
                    f"Resposta inesperada para {issuing_company.strip().upper()}."
                )
            return payload
        except Exception as error:  # pragma: no cover - rede real
            last_error = error
            try:
                completed = subprocess.run(
                    [
                        "curl",
                        "-L",
                        "--fail",
                        "--silent",
                        "--show-error",
                        "--max-time",
                        str(timeout),
                        url,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout + 5,
                )
                payload = json.loads(completed.stdout)
                if isinstance(payload, list) and payload and all(
                    isinstance(item, dict) for item in payload
                ):
                    return payload
                raise B3CorporateActionError(
                    f"Resposta cURL vazia/invalida para {issuing_company.strip().upper()}."
                )
            except Exception as curl_error:
                last_error = curl_error
            if attempt < attempts:
                time.sleep(min(20, 2 ** attempt))
    raise B3CorporateActionError(
        f"Falha ao consultar eventos oficiais de {issuing_company.strip().upper()}: "
        f"{last_error}"
    ) from last_error


def extract_official_split_events(
    payload: list[dict[str, object]],
    *,
    ticker: str,
    issuing_company: str,
    quote_dates: Iterable[str],
    quote_isins: Iterable[str],
    coverage_start: str,
) -> list[OfficialSplitEvent]:
    normalized_ticker = ticker.strip().upper()
    normalized_issuer = issuing_company.strip().upper()
    dates = sorted(set(quote_dates))
    if not dates:
        raise B3CorporateActionError(
            f"{normalized_ticker}: datas COTAHIST ausentes para cruzar eventos."
        )
    observed_isins = {value.strip().upper() for value in quote_isins if value.strip()}
    company = next(
        (
            item
            for item in payload
            if str(item.get("code", "")).strip().upper() == normalized_issuer
        ),
        payload[0] if len(payload) == 1 else None,
    )
    if company is None:
        raise B3CorporateActionError(
            f"{normalized_ticker}: companhia {normalized_issuer} ausente na resposta B3."
        )

    unique: dict[tuple[str, str, str, str], tuple[str, float, str]] = {}
    for raw_event in company.get("stockDividends") or []:
        if not isinstance(raw_event, dict):
            continue
        label = _normalize_label(str(raw_event.get("label", "")))
        if label not in SHARE_COUNT_EVENT_LABELS:
            continue
        event_isin = str(raw_event.get("isinCode", "")).strip().upper()
        if observed_isins and event_isin not in observed_isins:
            continue
        last_date_prior = _parse_brazilian_date(
            str(raw_event.get("lastDatePrior", ""))
        )
        if last_date_prior < dates[0]:
            distance = (
                datetime.fromisoformat(dates[0])
                - datetime.fromisoformat(last_date_prior)
            ).days
            if distance > 14:
                continue
        index = bisect_right(dates, last_date_prior)
        if index >= len(dates):
            continue
        ex_date = dates[index]
        if ex_date < coverage_start:
            continue
        factor_text = str(raw_event.get("factor", ""))
        split_ratio = _split_ratio(label, factor_text)
        key = (ex_date, label, factor_text, last_date_prior)
        unique[key] = (last_date_prior, split_ratio, label)

    grouped: dict[str, list[tuple[str, float, str]]] = {}
    for (ex_date, _label, _factor, _last), event in unique.items():
        grouped.setdefault(ex_date, []).append(event)

    source_url = b3_supplement_url(normalized_issuer)
    result: list[OfficialSplitEvent] = []
    for ex_date in sorted(grouped):
        events = sorted(grouped[ex_date], key=lambda item: (item[0], item[2], item[1]))
        ratio = 1.0
        for _last_date, one_ratio, _label in events:
            ratio *= one_ratio
        if ratio <= 0:
            raise B3CorporateActionError(
                f"{normalized_ticker} {ex_date}: razao oficial combinada invalida {ratio}."
            )
        if math.isclose(ratio, 1.0, rel_tol=1e-12, abs_tol=1e-12):
            continue
        result.append(
            OfficialSplitEvent(
                ticker=normalized_ticker,
                ex_date=ex_date,
                last_date_prior=max(item[0] for item in events),
                split_ratio=ratio,
                event=" + ".join(item[2] for item in events),
                source_url=source_url,
            )
        )
    return result


def parse_supplemental_split_events(
    payload: object,
    *,
    tickers: Iterable[str],
    quote_dates_by_ticker: Mapping[str, Iterable[str]],
    coverage_start: str,
) -> list[OfficialSplitEvent]:
    """Valida eventos historicos que sumiram da consulta corrente da B3.

    O registro suplementar so aceita fontes primarias do emissor ou da CVM. A
    ultima data com direito e o ``ex_date`` tambem precisam reconciliar com o
    calendario observado no COTAHIST do proprio ativo.
    """
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise B3CorporateActionError("Schema do registro suplementar invalido.")
    registry_start = payload.get("coverage_start")
    if registry_start is not None and registry_start != coverage_start:
        raise B3CorporateActionError(
            "coverage_start do registro suplementar diverge da sincronizacao."
        )
    allowed_tickers = {ticker.strip().upper() for ticker in tickers}
    normalized_dates = {
        ticker.strip().upper(): sorted(set(values))
        for ticker, values in quote_dates_by_ticker.items()
    }
    raw_events = payload.get("events")
    if not isinstance(raw_events, list):
        raise B3CorporateActionError("Lista de eventos suplementares ausente.")

    result: list[OfficialSplitEvent] = []
    seen: set[tuple[str, str]] = set()
    for raw_event in raw_events:
        if not isinstance(raw_event, dict):
            raise B3CorporateActionError(
                f"Evento suplementar invalido: {raw_event!r}."
            )
        ticker = str(raw_event.get("ticker", "")).strip().upper()
        if ticker not in allowed_tickers:
            raise B3CorporateActionError(
                f"Ticker suplementar fora do universo: {ticker or '<vazio>'}."
            )
        ex_date = _parse_iso_date(raw_event.get("ex_date"), field="ex_date")
        last_date_prior = _parse_iso_date(
            raw_event.get("last_date_prior"),
            field="last_date_prior",
        )
        if ex_date < coverage_start:
            continue
        dates = normalized_dates.get(ticker, [])
        if not dates:
            raise B3CorporateActionError(
                f"{ticker}: calendario COTAHIST ausente para evento suplementar."
            )
        if last_date_prior not in dates:
            raise B3CorporateActionError(
                f"{ticker} {ex_date}: last_date_prior {last_date_prior} "
                "nao existe no COTAHIST."
            )
        index = bisect_right(dates, last_date_prior)
        expected_ex_date = dates[index] if index < len(dates) else ""
        if ex_date != expected_ex_date:
            raise B3CorporateActionError(
                f"{ticker} {ex_date}: primeiro pregao posterior a "
                f"{last_date_prior} e {expected_ex_date or '<ausente>'}."
            )
        try:
            split_ratio = float(raw_event["split_ratio"])
        except (KeyError, TypeError, ValueError) as error:
            raise B3CorporateActionError(
                f"{ticker} {ex_date}: split_ratio suplementar invalido."
            ) from error
        if (
            not math.isfinite(split_ratio)
            or split_ratio <= 0
            or math.isclose(split_ratio, 1.0, rel_tol=1e-12, abs_tol=1e-12)
        ):
            raise B3CorporateActionError(
                f"{ticker} {ex_date}: split_ratio suplementar invalido "
                f"{split_ratio}."
            )
        event = str(raw_event.get("event", "")).strip().upper()
        if not event:
            raise B3CorporateActionError(
                f"{ticker} {ex_date}: descricao do evento ausente."
            )
        source_authority = str(raw_event.get("source_authority", "")).strip()
        if source_authority not in {"CVM", "issuer"}:
            raise B3CorporateActionError(
                f"{ticker} {ex_date}: fonte suplementar precisa ser CVM ou issuer."
            )
        source_url = str(raw_event.get("source_url", "")).strip()
        if not source_url.startswith("https://"):
            raise B3CorporateActionError(
                f"{ticker} {ex_date}: URL oficial suplementar invalida."
            )
        hostname = (urlparse(source_url).hostname or "").lower()
        if source_authority == "CVM" and not (
            hostname == "cvm.gov.br" or hostname.endswith(".cvm.gov.br")
        ):
            raise B3CorporateActionError(
                f"{ticker} {ex_date}: documento CVM fora de dominio cvm.gov.br."
            )
        key = (ticker, ex_date)
        if key in seen:
            raise B3CorporateActionError(
                f"Evento suplementar duplicado para {ticker} {ex_date}."
            )
        seen.add(key)
        result.append(
            OfficialSplitEvent(
                ticker=ticker,
                ex_date=ex_date,
                last_date_prior=last_date_prior,
                split_ratio=split_ratio,
                event=event,
                source_url=source_url,
                source_authority=source_authority,
                source_symbol=(
                    "CVM_IPE" if source_authority == "CVM" else "ISSUER_RI"
                ),
            )
        )
    return sorted(result, key=lambda item: (item.ex_date, item.ticker))


def merge_official_split_events(
    *event_groups: Iterable[OfficialSplitEvent],
) -> list[OfficialSplitEvent]:
    """Une fontes oficiais, rejeitando divergencias de data ou proporcao."""
    by_key: dict[tuple[str, str], OfficialSplitEvent] = {}
    for event in (item for group in event_groups for item in group):
        key = (event.ticker, event.ex_date)
        previous = by_key.get(key)
        if previous is None:
            by_key[key] = event
            continue
        if not math.isclose(
            previous.split_ratio,
            event.split_ratio,
            rel_tol=1e-10,
            abs_tol=1e-12,
        ):
            raise B3CorporateActionError(
                f"{event.ticker} {event.ex_date}: fontes oficiais divergem "
                f"({previous.split_ratio} x {event.split_ratio})."
            )
        if previous.last_date_prior != event.last_date_prior:
            raise B3CorporateActionError(
                f"{event.ticker} {event.ex_date}: fontes oficiais divergem na "
                "ultima data com direito."
            )
        if previous.source_authority != "B3" and event.source_authority == "B3":
            by_key[key] = event
    return sorted(by_key.values(), key=lambda item: (item.ex_date, item.ticker))


def audit_share_count_markers(
    quotes: Sequence[object],
    events: Iterable[OfficialSplitEvent],
    *,
    coverage_start: str,
    maximum_marker_lag_days: int = 10,
) -> list[dict[str, object]]:
    """Confere marcadores EB/EG do COTAHIST contra os eventos oficiais.

    Alguns marcadores permanecem ou reaparecem poucos pregoes depois do evento;
    por isso e aceita uma defasagem curta, registrada explicitamente no resultado.
    """
    if maximum_marker_lag_days < 0:
        raise ValueError("maximum_marker_lag_days nao pode ser negativo.")
    ordered_quotes = sorted(quotes, key=lambda item: str(item.date))
    event_values = sorted(events, key=lambda item: item.ex_date)
    markers: list[dict[str, object]] = []
    previous = None
    for quote in ordered_quotes:
        quote_date = str(quote.date)
        current_has_marker = _has_share_count_marker(
            str(getattr(quote, "specification", ""))
        )
        previous_has_marker = (
            _has_share_count_marker(str(getattr(previous, "specification", "")))
            if previous is not None
            else False
        )
        if (
            previous is not None
            and quote_date >= coverage_start
            and current_has_marker
            and not previous_has_marker
        ):
            marker_point = datetime.fromisoformat(quote_date)
            candidates = [
                event
                for event in event_values
                if datetime.fromisoformat(event.ex_date) <= marker_point
                and marker_point - datetime.fromisoformat(event.ex_date)
                <= timedelta(days=maximum_marker_lag_days)
            ]
            covered = candidates[-1] if candidates else None
            markers.append(
                {
                    "marker_date": quote_date,
                    "specification": str(getattr(quote, "specification", "")).strip(),
                    "covered": covered is not None,
                    "covered_by_ex_date": covered.ex_date if covered else "",
                    "lag_calendar_days": (
                        (marker_point - datetime.fromisoformat(covered.ex_date)).days
                        if covered
                        else None
                    ),
                }
            )
        previous = quote
    return markers


def payload_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_iso_date(value: object, *, field: str) -> str:
    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%d").date().isoformat()
    except ValueError as error:
        raise B3CorporateActionError(
            f"{field} de evento suplementar invalido: {value!r}."
        ) from error
    if parsed != str(value):
        raise B3CorporateActionError(
            f"{field} de evento suplementar nao canonico: {value!r}."
        )
    return parsed


def _has_share_count_marker(specification: str) -> bool:
    return any(
        token.lstrip("*").startswith("E") and ("B" in token or "G" in token)
        for token in specification.strip().upper().split()
    )


def _parse_brazilian_date(value: str) -> str:
    try:
        return datetime.strptime(value.strip(), "%d/%m/%Y").date().isoformat()
    except ValueError as error:
        raise B3CorporateActionError(f"Data de evento B3 invalida: {value!r}.") from error


def _decimal_pt(value: str) -> Decimal:
    normalized = value.strip().replace(".", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation as error:
        raise B3CorporateActionError(f"Fator de evento B3 invalido: {value!r}.") from error


def _split_ratio(label: str, factor_text: str) -> float:
    factor = _decimal_pt(factor_text)
    if label in {"BONIFICACAO", "DESDOBRAMENTO"}:
        ratio = Decimal(1) + factor / Decimal(100)
    elif label == "GRUPAMENTO":
        ratio = factor
    else:  # pragma: no cover - protegido pelo filtro acima
        raise B3CorporateActionError(f"Evento de quantidade nao suportado: {label}.")
    if ratio <= 0 or ratio == 1:
        raise B3CorporateActionError(
            f"Razao de evento B3 invalida para {label}: {factor_text!r}."
        )
    return float(ratio)


def _normalize_label(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().upper())
    return "".join(character for character in normalized if not unicodedata.combining(character))
