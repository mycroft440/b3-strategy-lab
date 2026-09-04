from __future__ import annotations

"""Realistic point-in-time synchronization entry point.

The broad research catalog and the realistic replay deliberately share source
archives, but not generated candles, action ledgers or verification manifests.
This wrapper injects isolated storage roots before delegating to the base
synchronizer, so a short causal replay cannot truncate or invalidate research data.
"""

import json
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.b3_official import B3CorporateActionError  # noqa: E402
from scripts import sync_point_in_time_universe as base  # noqa: E402


DEFAULT_REALISTIC_DATA = Path("data/candles_point_in_time")
DEFAULT_REALISTIC_ACTIONS = Path("data/actions_point_in_time")
DEFAULT_REALISTIC_MANIFESTS = Path("data/manifests_point_in_time")
DEFAULT_REALISTIC_SPLIT_EVIDENCE = Path(
    "data/corporate_actions/point_in_time_split_evidence.json"
)
DEFAULT_REALISTIC_EVIDENCE_ADDENDUM = Path(
    "data/corporate_actions/realistic_split_evidence_addendum.json"
)
DEFAULT_ACTION_WORKERS = 1
SYNC_ATTEMPTS = 3
SYNC_RETRY_DELAYS_SECONDS = (20, 60)
_BASE_PARSE_SUPPLEMENTAL_SPLITS = base.parse_supplemental_split_events
_BASE_AUDIT_SHARE_MARKERS = base.audit_share_count_markers
_BASE_WRITE_JSON_ATOMIC = base._write_json_atomic


class HistoricalTickerReviewCoverageError(RuntimeError):
    """Deterministic evidence gap; unlike a B3 transport error it must not retry."""


def _is_retryable_b3_transport_error(error: B3CorporateActionError) -> bool:
    """Recognize transient B3/source-response failures without retrying evidence bugs.

    The downloader can surface its final exhausted transport error with the
    Portuguese ``Falha ao consultar...`` prefix. Existing callers/tests also use
    ``temporary invalid response`` for the same transient-source contract. Both
    remain bounded by ``SYNC_ATTEMPTS``. Deterministic validation/evidence errors
    propagate immediately and remain fail-closed.
    """
    message = str(error).strip()
    lowered = message.lower()
    return (
        message.startswith("Falha ao consultar eventos oficiais de ")
        or lowered.startswith("temporary invalid response")
    )


def _option_value(arguments: list[str], option: str) -> str | None:
    for index, value in enumerate(arguments):
        if value == option and index + 1 < len(arguments):
            return arguments[index + 1]
        prefix = option + "="
        if value.startswith(prefix):
            return value[len(prefix) :]
    return None


def _load_evidence_addendum(path: Path = DEFAULT_REALISTIC_EVIDENCE_ADDENDUM) -> dict:
    if not path.exists():
        return {
            "schema_version": 1,
            "coverage_start": "2017-01-01",
            "events": [],
            "marker_evidence": [],
            "ticker_reviews": [],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise B3CorporateActionError("Schema do addendum de evidencia realista invalido.")
    if not isinstance(payload.get("events", []), list):
        raise B3CorporateActionError("Lista de eventos do addendum realista invalida.")
    if not isinstance(payload.get("marker_evidence", []), list):
        raise B3CorporateActionError("Lista de marcadores do addendum realista invalida.")
    if not isinstance(payload.get("ticker_reviews", []), list):
        raise B3CorporateActionError("Lista de revisoes historicas do addendum realista invalida.")
    return payload


def _validated_primary_source(
    *,
    ticker: str,
    authority: str,
    source_url: str,
    context: str,
) -> None:
    if authority not in {"issuer", "CVM"}:
        raise B3CorporateActionError(
            f"{ticker}: fonte {context} precisa ser issuer ou CVM."
        )
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise B3CorporateActionError(
            f"{ticker}: URL primaria de {context} invalida."
        )
    if authority == "CVM" and not (
        parsed.hostname == "cvm.gov.br" or parsed.hostname.endswith(".cvm.gov.br")
    ):
        raise B3CorporateActionError(
            f"{ticker}: evidencia CVM de {context} fora de dominio cvm.gov.br."
        )


def _validated_ticker_reviews(payload: dict) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for raw in payload.get("ticker_reviews", []):
        if not isinstance(raw, dict):
            raise B3CorporateActionError("Revisao historica explicita invalida.")
        ticker = str(raw.get("ticker", "")).strip().upper()
        authority = str(raw.get("source_authority", "")).strip()
        source_url = str(raw.get("source_url", "")).strip()
        review = str(raw.get("review", "")).strip()
        if not ticker or not review:
            raise B3CorporateActionError("Revisao historica sem ticker/review.")
        _validated_primary_source(
            ticker=ticker,
            authority=authority,
            source_url=source_url,
            context="revisao historica",
        )
        if ticker in result:
            raise B3CorporateActionError(
                f"Revisao historica explicita duplicada para {ticker}."
            )
        result[ticker] = {
            "source_authority": authority,
            "source_url": source_url,
            "review": review,
        }
    return result


def _unresolved_historical_review_tickers(reviews: object) -> tuple[str, ...]:
    """Return every generated historical review that still lacks primary binding."""
    if not isinstance(reviews, list):
        return ()
    unresolved: set[str] = set()
    for raw in reviews:
        if not isinstance(raw, dict):
            continue
        authority = str(raw.get("source_authority", "")).strip()
        raw_source_url = raw.get("source_url")
        source_url = "" if raw_source_url is None else str(raw_source_url).strip()
        if authority != "historical_primary_registry" or source_url:
            continue
        ticker = str(raw.get("ticker", "")).strip().upper()
        if ticker:
            unresolved.add(ticker)
    return tuple(sorted(unresolved))


def _validated_marker_evidence(payload: dict) -> dict[tuple[str, str, str], dict[str, str]]:
    result: dict[tuple[str, str, str], dict[str, str]] = {}
    for raw in payload.get("marker_evidence", []):
        if not isinstance(raw, dict):
            raise B3CorporateActionError("Evidencia explicita de marcador invalida.")
        ticker = str(raw.get("ticker", "")).strip().upper()
        marker_date = str(raw.get("marker_date", "")).strip()
        specification = " ".join(str(raw.get("specification", "")).strip().upper().split())
        event = str(raw.get("event", "")).strip()
        authority = str(raw.get("source_authority", "")).strip()
        source_url = str(raw.get("source_url", "")).strip()
        if not ticker or not specification or not event:
            raise B3CorporateActionError("Evidencia de marcador sem ticker/especificacao/evento.")
        try:
            if date.fromisoformat(marker_date).isoformat() != marker_date:
                raise ValueError
        except ValueError as error:
            raise B3CorporateActionError(
                f"{ticker}: marker_date explicita invalida: {marker_date!r}."
            ) from error
        _validated_primary_source(
            ticker=ticker,
            authority=authority,
            source_url=source_url,
            context=f"marcador {marker_date}",
        )
        key = (ticker, marker_date, specification)
        if key in result:
            raise B3CorporateActionError(
                f"Evidencia explicita duplicada para {ticker} {marker_date} {specification}."
            )
        result[key] = {
            "event": event,
            "source_authority": authority,
            "source_url": source_url,
        }
    return result


def _install_evidence_addendum(payload: dict) -> None:
    marker_evidence = _validated_marker_evidence(payload)
    ticker_reviews = _validated_ticker_reviews(payload)

    def parse_with_addendum(
        source_payload: object,
        *,
        tickers,
        quote_dates_by_ticker,
        coverage_start: str,
    ):
        # Both tickers and calendars may be one-shot iterators. The repository
        # supplement and primary-source addendum must see the exact same immutable
        # scope, otherwise the second strict parser could silently receive an empty
        # universe after the first parser consumes it.
        materialized_tickers = tuple(
            str(ticker).strip().upper() for ticker in tickers
        )
        materialized_quote_dates = {
            str(ticker).strip().upper(): tuple(values)
            for ticker, values in quote_dates_by_ticker.items()
        }
        primary = _BASE_PARSE_SUPPLEMENTAL_SPLITS(
            source_payload,
            tickers=materialized_tickers,
            quote_dates_by_ticker=materialized_quote_dates,
            coverage_start=coverage_start,
        )
        allowed = set(materialized_tickers)
        addendum = dict(payload)
        scoped_events: list[object] = []
        for event in payload.get("events", []):
            # Preserve malformed/unclassifiable records for the canonical parser
            # instead of hiding corruption behind universe scoping.
            if not isinstance(event, dict):
                scoped_events.append(event)
                continue
            raw_ticker = event.get("ticker")
            if not isinstance(raw_ticker, str):
                scoped_events.append(event)
                continue
            ticker = raw_ticker.strip().upper()
            if not ticker or ticker in allowed:
                scoped_events.append(event)
        addendum["events"] = scoped_events
        extra = _BASE_PARSE_SUPPLEMENTAL_SPLITS(
            addendum,
            tickers=materialized_tickers,
            quote_dates_by_ticker=materialized_quote_dates,
            coverage_start=coverage_start,
        )
        return base.merge_official_split_events(primary, extra)

    def audit_with_explicit_primary_evidence(
        quotes,
        events,
        *,
        coverage_start: str,
        maximum_marker_lag_days: int = 10,
    ):
        rows = _BASE_AUDIT_SHARE_MARKERS(
            quotes,
            events,
            coverage_start=coverage_start,
            maximum_marker_lag_days=maximum_marker_lag_days,
        )
        if not quotes:
            return rows
        ticker = str(getattr(quotes[0], "ticker", "")).strip().upper()
        for row in rows:
            if row.get("covered"):
                row["coverage_method"] = "economic_split_event"
                continue
            normalized_spec = " ".join(str(row.get("specification", "")).strip().upper().split())
            evidence = marker_evidence.get(
                (ticker, str(row.get("marker_date", "")), normalized_spec)
            )
            if evidence is None:
                continue
            row["covered"] = True
            row["covered_by_ex_date"] = ""
            row["lag_calendar_days"] = None
            row["coverage_method"] = "explicit_primary_marker_evidence"
            row["primary_event"] = evidence["event"]
            row["primary_source_authority"] = evidence["source_authority"]
            row["primary_source_url"] = evidence["source_url"]
        return rows

    def write_json_with_primary_ticker_reviews(path: Path, value: object) -> None:
        # The addendum may fill only unresolved historical rows. It must never
        # replace a current B3 review or any already-sourced generated review.
        if isinstance(value, dict) and value.get("schema_version") == 3:
            raw_reviews = value.get("ticker_reviews")
            if not isinstance(raw_reviews, list):
                raise HistoricalTickerReviewCoverageError(
                    "ticker_reviews schema 3 ausente/invalido; nenhum manifest foi assinado."
                )
            reviews = []
            for raw in raw_reviews:
                if not isinstance(raw, dict):
                    raise HistoricalTickerReviewCoverageError(
                        "ticker_reviews schema 3 contem registro invalido; nenhum manifest foi assinado."
                    )
                ticker = str(raw.get("ticker", "")).strip().upper()
                generated_authority = str(raw.get("source_authority", "")).strip()
                raw_source_url = raw.get("source_url")
                generated_source_url = (
                    "" if raw_source_url is None else str(raw_source_url).strip()
                )
                primary_review = ticker_reviews.get(ticker)
                if (
                    primary_review is None
                    or generated_authority != "historical_primary_registry"
                    or generated_source_url
                ):
                    reviews.append(raw)
                    continue
                row = dict(raw)
                row["source_authority"] = primary_review["source_authority"]
                row["source_url"] = primary_review["source_url"]
                row["result"] = (
                    str(row.get("result", "")).rstrip()
                    + " Revisao primaria historica: "
                    + primary_review["review"]
                ).strip()
                reviews.append(row)
            unresolved = _unresolved_historical_review_tickers(reviews)
            if unresolved:
                raise HistoricalTickerReviewCoverageError(
                    "Revisoes historicas sem fonte primaria explicita: "
                    + ", ".join(unresolved)
                    + ". Adicione issuer/CVM verificavel ao addendum; "
                    "nenhum manifest foi assinado."
                )
            value = dict(value)
            value["ticker_reviews"] = reviews
        _BASE_WRITE_JSON_ATOMIC(path, value)

    # Always install directly over the immutable base functions. Repeated calls in
    # tests/retries therefore replace the wrapper instead of recursively stacking it.
    base.parse_supplemental_split_events = parse_with_addendum
    base.audit_share_count_markers = audit_with_explicit_primary_evidence
    base._write_json_atomic = write_json_with_primary_ticker_reviews


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)

    defaults = (
        ("--data-dir", DEFAULT_REALISTIC_DATA),
        ("--actions-dir", DEFAULT_REALISTIC_ACTIONS),
        ("--manifests-dir", DEFAULT_REALISTIC_MANIFESTS),
    )
    for option, path in defaults:
        if _option_value(arguments, option) is None:
            arguments.extend([option, str(path)])

    split_evidence = (
        _option_value(arguments, "--split-evidence")
        or str(DEFAULT_REALISTIC_SPLIT_EVIDENCE)
    )
    if _option_value(arguments, "--split-evidence") is None:
        arguments.extend(["--split-evidence", split_evidence])

    # The evidence hashed into the point-in-time manifests must be the exact same
    # file that is later audited for the replay. One --split-evidence override is
    # sufficient; if a caller explicitly supplies --dataset-split-evidence too, the
    # base synchronizer rejects the invocation unless both paths are identical.
    if _option_value(arguments, "--dataset-split-evidence") is None:
        arguments.extend(["--dataset-split-evidence", split_evidence])

    # The public listed-company endpoint is sensitive to bursts. Realistic mode
    # favors deterministic evidence collection over throughput; callers can still
    # opt into more workers explicitly when they control their own cache/rate limit.
    if _option_value(arguments, "--action-workers") is None:
        arguments.extend(["--action-workers", str(DEFAULT_ACTION_WORKERS)])

    _install_evidence_addendum(_load_evidence_addendum())

    # Successful issuer supplements are written atomically by the base synchronizer.
    # The B3 downloader already retries each request internally. Only explicitly
    # transient source/transport failures receive a bounded whole-sync retry so
    # cached successes can be reused; deterministic evidence/integrity errors
    # propagate immediately and remain fail-closed.
    for attempt in range(1, SYNC_ATTEMPTS + 1):
        try:
            return base.main(arguments)
        except B3CorporateActionError as error:
            if not _is_retryable_b3_transport_error(error):
                raise
            if attempt >= SYNC_ATTEMPTS:
                raise
            delay = SYNC_RETRY_DELAYS_SECONDS[attempt - 1]
            print(
                f"B3 supplement sync transient failure (attempt {attempt}/{SYNC_ATTEMPTS}): "
                f"{error}. Retrying cached resume after {delay}s.",
                flush=True,
            )
            time.sleep(delay)

    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
