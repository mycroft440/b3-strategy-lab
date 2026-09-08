"""Document-bound cash events for issuers absent from the current B3 endpoint."""
from __future__ import annotations

import hashlib
import json
from bisect import bisect_right
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

from .source_evidence import verify_source_documents


def _iso(value: object) -> str:
    text = str(value)
    if date.fromisoformat(text).isoformat() != text:
        raise ValueError(f"Cash supplement requires an ISO date: {text!r}")
    return text


def _identity(row: dict) -> tuple[str, ...]:
    label = {"DIVIDEND": "DIVIDENDO", "JSCP": "JCP"}.get(str(row["label"]), str(row["label"]))
    return tuple(str(row[key]) for key in ("ticker", "isin", "last_date_prior", "payment_date")) + (label,)


def _amount(row: dict) -> Decimal:
    try:
        value = Decimal(str(row["gross_per_share"]))
    except (InvalidOperation, KeyError) as error:
        raise ValueError("Invalid supplemental cash amount") from error
    if not value.is_finite() or value <= 0:
        raise ValueError("Supplemental cash amount must be finite and positive")
    return value


def _source(row: dict) -> None:
    authority = row.get("source_authority")
    url = urlparse(str(row.get("source_url", "")))
    if authority not in {"B3", "CVM", "issuer"} or url.scheme != "https" or not url.hostname:
        raise ValueError("Cash supplement requires a primary https source")
    domain = {"B3": "b3.com.br", "CVM": "cvm.gov.br"}.get(authority)
    if domain and url.hostname != domain and not url.hostname.endswith("." + domain):
        raise ValueError("Cash supplement source authority/domain mismatch")
    if not str(row.get("source_reference", "")).strip():
        raise ValueError("Cash supplement requires a document page/table reference")


def load_historical_cash(path: Path | str, quotes_by_ticker: dict, *, start: str, end: str) -> dict:
    """Validate the exact replay scope and source bytes; never infer completeness.

    Coverage reviews explicitly attest each ticker/ISIN interval, including zero
    events. A URL or a successful parse alone never clears a missing-source issue.
    Files are relative to the supplement's parent, through source_evidence's path
    containment and SHA256 validation.
    """
    source = Path(path).resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("Historical cash supplement requires schema_version 1")
    events, reviews = payload.get("events"), payload.get("coverage_reviews")
    if not isinstance(events, list) or not isinstance(reviews, list) or not reviews:
        raise ValueError("Historical cash supplement requires events and nonempty coverage_reviews")
    records = [*events, *reviews]
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("Historical cash records must be objects")
        if row.get("ticker") not in quotes_by_ticker:
            raise ValueError(f"Cash supplement ticker outside replay scope: {row.get('ticker')}")
        if not row.get("isin") or row["isin"] not in {q.isin for q in quotes_by_ticker[row["ticker"]]}:
            raise ValueError(f"Cash supplement ISIN outside ticker history: {row.get('ticker')}")
        _source(row)
    documents = verify_source_documents(source.parent, [SimpleNamespace(**row) for row in records])
    if not documents["verified"]:
        raise ValueError(f"Historical cash source documents failed verification: {documents['blockers']}")

    coverage: dict[tuple[str, str], dict] = {}
    for review in reviews:
        key = (review["ticker"], review["isin"])
        first, last = _iso(review.get("start")), _iso(review.get("end"))
        if key in coverage or last < first:
            raise ValueError("Duplicate/reversed historical cash coverage interval")
        if review.get("complete") is not True or not str(review.get("reviewed_by", "")).strip():
            raise ValueError("Historical cash coverage requires explicit complete review and reviewer")
        if type(review.get("event_count")) is not int or review["event_count"] < 0:
            raise ValueError("Historical cash coverage requires a nonnegative event_count")
        coverage[key] = review

    rows: dict[tuple[str, ...], dict] = {}
    for event in events:
        key = (event["ticker"], event["isin"])
        review = coverage.get(key)
        if review is None:
            raise ValueError("Historical cash event lacks ticker/ISIN coverage review")
        last = _iso(event.get("last_date_prior"))
        ex = _iso(event.get("ex_date"))
        pay = _iso(event.get("payment_date"))
        announced = _iso(event.get("announcement_date"))
        if not (review["start"] <= last <= review["end"] and start <= last <= end):
            raise ValueError("Historical cash event lies outside reviewed replay scope")
        if not announced <= last < ex <= pay:
            raise ValueError("Historical cash announcement/entitlement/ex/payment ordering invalid")
        quotes = sorted(quotes_by_ticker[event["ticker"]], key=lambda q: q.date)
        dates = [q.date for q in quotes]
        index = bisect_right(dates, last)
        if not index or quotes[index - 1].date != last or quotes[index - 1].isin != event["isin"]:
            raise ValueError("Historical cash entitlement date/ISIN does not match COTAHIST")
        if index < len(dates) and dates[index] != ex:
            raise ValueError("Historical cash ex-date does not match the next observed session")
        identity = _identity(event)
        if identity[-1] not in {"DIVIDENDO", "JCP"}:
            raise ValueError("Historical cash supports dividends/JCP only")
        row = dict(event, label=identity[-1], gross_per_share=str(_amount(event)))
        prior = rows.get(identity)
        if prior is not None:
            if _amount(prior) != _amount(row) or prior["ex_date"] != ex:
                raise ValueError("Conflicting historical cash events; reconcile original sources")
            continue
        rows[identity] = row

    for key, review in coverage.items():
        count = sum((row["ticker"], row["isin"]) == key for row in rows.values())
        if count != review["event_count"]:
            raise ValueError(f"Historical cash reviewed event_count mismatch: {key}")
    covered_tickers = []
    for ticker, quotes in quotes_by_ticker.items():
        by_isin: dict[str, list[str]] = {}
        for quote in quotes:
            if start <= quote.date <= end:
                by_isin.setdefault(quote.isin, []).append(quote.date)
        if by_isin and all(
            (review := coverage.get((ticker, isin))) is not None
            and review["start"] <= min(dates) and review["end"] >= max(dates)
            for isin, dates in by_isin.items()
        ):
            covered_tickers.append(ticker)
    return {
        "rows": list(rows.values()),
        "covered_tickers": sorted(covered_tickers),
        "source_file": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_documents": records,
        "coverage_reviews": reviews,
        "documents_verified": documents["verified_documents"],
    }


def merge_historical_cash(rows: list[dict], issues: list[dict], supplement: dict) -> tuple[list[dict], list[dict]]:
    """Keep separate installments; reject conflicting amounts instead of choosing one."""
    result = list(rows)
    for row in supplement["rows"]:
        identity = _identity(row)
        existing = [item for item in result if _identity(item) == identity]
        if existing and any(_amount(item) != _amount(row) or item["ex_date"] != row["ex_date"] for item in existing):
            raise ValueError(f"B3/historical cash conflict: {identity}; reconcile source documents")
        result = [item for item in result if _identity(item) != identity]
        result.append(row)
    covered = set(supplement["covered_tickers"])
    unresolved = [
        issue for issue in issues
        if not (issue.get("issue") == "historical_cash_dividend_source_unavailable" and issue.get("ticker") in covered)
    ]
    return sorted(result, key=lambda row: (_identity(row), _amount(row))), unresolved


def historical_cash_binding_issues(manifest: dict) -> list[str]:
    """Recheck supplement and documentary bytes when auditing a saved ledger."""
    binding = manifest.get("historical_cash_supplement")
    if binding is None:
        return []
    if not isinstance(binding, dict):
        return ["historical_cash_supplement_binding_invalid"]
    source = Path(str(binding.get("source_file", "")))
    if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != binding.get("source_sha256"):
        return ["historical_cash_supplement_hash_mismatch_or_missing"]
    records = binding.get("source_documents")
    if not isinstance(records, list) or not records or not all(isinstance(row, dict) for row in records):
        return ["historical_cash_source_document_records_invalid"]
    result = verify_source_documents(source.parent, [SimpleNamespace(**row) for row in records])
    return list(result["blockers"]) if not result["verified"] else []
