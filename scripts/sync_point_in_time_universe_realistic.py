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
        return {"schema_version": 1, "coverage_start": "2017-01-01", "events": [], "marker_evidence": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise B3CorporateActionError("Schema do addendum de evidencia realista invalido.")
    if not isinstance(payload.get("events", []), list):
        raise B3CorporateActionError("Lista de eventos do addendum realista invalida.")
    if not isinstance(payload.get("marker_evidence", []), list):
        raise B3CorporateActionError("Lista de marcadores do addendum realista invalida.")
    return payload


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
        if authority not in {"issuer", "CVM"}:
            raise B3CorporateActionError(
                f"{ticker} {marker_date}: fonte de marcador precisa ser issuer ou CVM."
            )
        parsed = urlparse(source_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise B3CorporateActionError(
                f"{ticker} {marker_date}: URL primaria de marcador invalida."
            )
        if authority == "CVM" and not (
            parsed.hostname == "cvm.gov.br" or parsed.hostname.endswith(".cvm.gov.br")
        ):
            raise B3CorporateActionError(
                f"{ticker} {marker_date}: evidencia CVM fora de dominio cvm.gov.br."
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

    def parse_with_addendum(
        source_payload: object,
        *,
        tickers,
        quote_dates_by_ticker,
        coverage_start: str,
    ):
        primary = _BASE_PARSE_SUPPLEMENTAL_SPLITS(
            source_payload,
            tickers=tickers,
            quote_dates_by_ticker=quote_dates_by_ticker,
            coverage_start=coverage_start,
        )
        allowed = {str(ticker).strip().upper() for ticker in tickers}
        addendum = dict(payload)
        addendum["events"] = [
            event
            for event in payload.get("events", [])
            if str(event.get("ticker", "")).strip().upper() in allowed
        ]
        extra = _BASE_PARSE_SUPPLEMENTAL_SPLITS(
            addendum,
            tickers=allowed,
            quote_dates_by_ticker=quote_dates_by_ticker,
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

    # Always install directly over the immutable base functions. Repeated calls in
    # tests/retries therefore replace the wrapper instead of recursively stacking it.
    base.parse_supplemental_split_events = parse_with_addendum
    base.audit_share_count_markers = audit_with_explicit_primary_evidence


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
    # If the B3 endpoint transiently returns an empty/non-JSON response, a retry of
    # the full sync therefore resumes from those cached successes and only fetches
    # the missing issuers. We retry only the explicit B3 transport/data error and
    # preserve fail-closed behavior after the bounded attempts are exhausted.
    for attempt in range(1, SYNC_ATTEMPTS + 1):
        try:
            return base.main(arguments)
        except B3CorporateActionError as error:
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
