from __future__ import annotations

from bisect import bisect_right
from datetime import date
from typing import Mapping, Sequence

from .b3_official import b3_supplement_url


def parse_any_date(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.split("T", 1)[0]
    if "/" in text:
        day, month, year = text.split("/")
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return date.fromisoformat(text).isoformat()


def build_cash_events(
    tickers: Sequence[str],
    issuer_by_ticker: Mapping[str, str],
    payloads: Mapping[str, list[dict[str, object]]],
    quotes_by_ticker: Mapping[str, list],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Build a non-lossy B3 cash-distribution ledger.

    Event identity includes ticker, ISIN, entitlement date, payment date, label and
    rate. This deliberately preserves distinct installments that happen to share
    the same entitlement date/type/rate but settle on different payment dates.
    """
    normalized_tickers = [str(ticker).strip().upper() for ticker in tickers]
    isins_by_ticker = {
        ticker: {
            quote.isin.strip().upper()
            for quote in quotes_by_ticker[ticker]
            if getattr(quote, "isin", "")
        }
        for ticker in normalized_tickers
    }
    rows: list[dict[str, object]] = []
    issues: list[dict[str, object]] = []
    seen: set[tuple[str, str, str, str, str, float]] = set()

    for ticker in normalized_tickers:
        issuer = str(issuer_by_ticker[ticker]).strip().upper()
        payload = payloads.get(issuer)
        if payload is None:
            issues.append({"ticker": ticker, "issuer": issuer, "issue": "issuer_payload_missing"})
            continue
        company = next(
            (
                item
                for item in payload
                if str(item.get("code", "")).strip().upper() == issuer
            ),
            payload[0] if len(payload) == 1 else None,
        )
        if company is None:
            issues.append({"ticker": ticker, "issuer": issuer, "issue": "issuer_missing_in_b3_payload"})
            continue

        quotes = sorted(quotes_by_ticker[ticker], key=lambda quote: quote.date)
        quote_dates = [quote.date for quote in quotes]
        for event in company.get("cashDividends") or []:
            if not isinstance(event, dict):
                continue
            label = str(event.get("label", "")).strip().upper()
            if label not in {"DIVIDENDO", "DIVIDEND", "JCP", "JSCP"}:
                continue
            isin = str(event.get("isinCode", "")).strip().upper()
            if isins_by_ticker[ticker] and isin not in isins_by_ticker[ticker]:
                continue
            last_date_prior = parse_any_date(event.get("lastDatePrior"))
            payment_date = parse_any_date(event.get("paymentDate"))
            if not last_date_prior:
                issues.append({"ticker": ticker, "label": label, "isin": isin, "issue": "missing_last_date_prior"})
                continue
            index = bisect_right(quote_dates, last_date_prior)
            if index >= len(quote_dates):
                # The ex date lies outside the available price history; no event can
                # affect the simulated account inside this dataset.
                continue
            ex_date = quote_dates[index]
            if not payment_date:
                issues.append(
                    {
                        "ticker": ticker,
                        "label": label,
                        "isin": isin,
                        "last_date_prior": last_date_prior,
                        "issue": "missing_payment_date",
                    }
                )
                continue
            try:
                rate = float(str(event.get("rate", "0")).replace(",", "."))
            except ValueError:
                issues.append(
                    {
                        "ticker": ticker,
                        "label": label,
                        "isin": isin,
                        "last_date_prior": last_date_prior,
                        "payment_date": payment_date,
                        "issue": "invalid_rate",
                    }
                )
                continue
            if rate <= 0:
                continue
            key = (ticker, isin, last_date_prior, payment_date, label, rate)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "ticker": ticker,
                    "label": label,
                    "last_date_prior": last_date_prior,
                    "ex_date": ex_date,
                    "payment_date": payment_date,
                    "gross_per_share": f"{rate:.12g}",
                    "isin": isin,
                    "source_authority": "B3",
                    "source_url": b3_supplement_url(issuer),
                }
            )

    return (
        sorted(
            rows,
            key=lambda row: (
                str(row["payment_date"]),
                str(row["ticker"]),
                str(row["label"]),
                str(row["last_date_prior"]),
                str(row["isin"]),
                float(row["gross_per_share"]),
            ),
        ),
        issues,
    )
