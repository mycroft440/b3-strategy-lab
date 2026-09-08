"""Explicit source-backed settlement rules for fractions and capital returns.

Auction proceeds are unavailable to the model until the documented realization
date. Before then, fractional rights are marked but cannot fund ordinary orders.
"""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

from .source_evidence import verify_source_documents


def load_corporate_settlements(path):
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("events"), list):
        raise ValueError("Corporate settlements require schema_version 1 and events.")
    rules = {}
    for row in payload["events"]:
        for key in ("effective_date", "realization_date", "payment_date", "announcement_date"):
            if date.fromisoformat(row[key]).isoformat() != row[key]:
                raise ValueError("Corporate settlement dates must use ISO format.")
        if not row["announcement_date"] <= row["effective_date"] <= row["realization_date"] <= row["payment_date"]:
            raise ValueError("Corporate settlement dates are not causal.")
        if row.get("kind") not in {"fractional_sale", "return_of_capital"}:
            raise ValueError("Unsupported corporate settlement tax treatment.")
        if row["kind"] == "fractional_sale" and row.get("quantity_event") not in {"split", "reverse_split"}:
            raise ValueError("Fractional settlement currently requires a reviewed split/reverse_split; bonus basis is unsupported.")
        url = urlparse(str(row.get("source_url", "")))
        if (row.get("source_authority") not in {"B3", "CVM", "issuer"}
                or url.scheme != "https" or not url.hostname
                or not row.get("source_reference") or not row.get("reviewed_by") or not row.get("isin")):
            raise ValueError("Corporate settlement requires reviewed primary-source evidence and ISIN.")
        domain = {"B3": "b3.com.br", "CVM": "cvm.gov.br"}.get(row["source_authority"])
        if domain and url.hostname != domain and not url.hostname.endswith("." + domain):
            raise ValueError("Corporate settlement source authority/domain mismatch.")
        required_amount = "price_per_fractional_share" if row["kind"] == "fractional_sale" else "cash_per_old_share"
        for field in (required_amount, "share_ratio"):
            if not math.isfinite(float(row[field])) or float(row[field]) <= 0:
                raise ValueError(f"Corporate settlement requires positive {field}.")
        key = (row["effective_date"], row["ticker"])
        if key in rules:
            raise ValueError("Duplicate corporate settlement rule.")
        rules[key] = dict(row)
    verification = verify_source_documents(source.parent, [SimpleNamespace(**row) for row in rules.values()])
    if not verification["verified"]:
        raise ValueError(f"Unverified corporate settlement documents: {verification['blockers']}")
    return rules


def _claims(account):
    if not hasattr(account, "_corporate_receivables"):
        account._corporate_receivables = {}
        account.corporate_action_ledger = []
    return account._corporate_receivables


def apply_fractional_split(account, data, current, original):
    """Delegate unsupported events to the existing fail-closed split processor."""
    rules = getattr(account, "_corporate_settlement_rules", {})
    handled = {}
    for ticker, position in list(account.positions.items()):
        rule = rules.get((current, ticker))
        if not rule or rule["kind"] != "fractional_sale" or position.shares <= 0:
            continue
        index = data.index_by_date.get(ticker, {}).get(current)
        if index is None or index <= 0:
            raise ValueError("Fraction settlement requires the prior official instrument session.")
        previous, candle = data.candles[ticker][index - 1:index + 1]
        ratio = candle.adjustment_factor / previous.adjustment_factor
        if not math.isclose(ratio, float(rule["share_ratio"]), rel_tol=1e-10) or candle.isin != rule["isin"]:
            raise ValueError("Fraction settlement ratio/ISIN differs from official candles.")
        exact = position.shares * ratio
        whole = math.floor(exact + 1e-9)
        fraction = max(0.0, exact - whole)
        basis_per_share = position.average_cost / ratio
        if fraction:
            _claims(account)[(current, ticker)] = dict(
                rule=rule, units=fraction, basis=fraction * basis_per_share,
                net=None, withholding=0.0, value=0.0,
            )
        position.shares = whole
        position.average_cost = basis_per_share if whole else 0.0
        handled[ticker] = account.positions.pop(ticker)
    try:
        original(account, data, current)
    finally:
        account.positions.update(handled)


def apply_cash_transition(account, transition):
    if account.shares(transition.old_ticker) <= 0 or not transition.cash_per_old_share:
        return False
    rule = getattr(account, "_corporate_settlement_rules", {}).get(
        (transition.effective_date, transition.old_ticker))
    if not rule or rule["kind"] != "return_of_capital":
        return False
    if (transition.certification_status != "certified" or not transition.new_ticker
            or transition.new_ticker == transition.old_ticker
            or transition.old_isin != rule["isin"]
            or not math.isclose(transition.share_ratio, float(rule["share_ratio"]))
            or not math.isclose(transition.cash_per_old_share, float(rule["cash_per_old_share"]))):
        raise ValueError("Cash transition differs from the reviewed capital-return rule.")
    old = account.positions[transition.old_ticker]
    cash = old.shares * transition.cash_per_old_share
    basis = old.shares * old.average_cost
    quantity = old.shares * transition.share_ratio
    if cash > basis + 1e-9 or not math.isclose(quantity, round(quantity), abs_tol=1e-9):
        raise ValueError("Cash above acquisition cost or mixed fractional transitions need a separate tax rule.")
    successor = account.positions[transition.new_ticker]
    total_basis = successor.shares * successor.average_cost + basis - cash
    successor.shares += round(quantity)
    successor.average_cost = total_basis / successor.shares
    old.shares = 0
    old.average_cost = 0.0
    _claims(account)[(transition.effective_date, transition.old_ticker)] = dict(
        rule=rule, units=0.0, basis=0.0, net=cash, withholding=0.0, value=cash,
    )
    return True


def mark_and_pay_corporate_receivables(account, data, current):
    claims = _claims(account)
    for key, claim in list(claims.items()):
        rule = claim["rule"]
        if claim["net"] is None and current >= rule["realization_date"]:
            gross = claim["units"] * float(rule["price_per_fractional_share"])
            account.tax.record_sale(rule["realization_date"], gross, gross - claim["basis"])
            withheld = account.tax.take_last_withholding_delta()
            if withheld > gross + 1e-9:
                raise ValueError("Fractional sale withholding exceeds proceeds; source-specific cash treatment required.")
            claim["net"], claim["withholding"] = gross - withheld, withheld
        if claim["net"] is not None:
            claim["value"] = claim["net"]
        else:
            candle = data.by_date.get(rule["ticker"], {}).get(current)
            if candle is None or candle.raw_close <= 0:
                raise ValueError("Unliquidated fractional right requires a fresh official close.")
            index = data.index_by_date.get(rule["ticker"], {}).get(current)
            if current > rule["effective_date"] and index is not None and index > 0:
                previous = data.candles[rule["ticker"]][index - 1]
                if not math.isclose(candle.adjustment_factor, previous.adjustment_factor):
                    raise ValueError("A second quantity event on an unliquidated fraction requires a reviewed settlement rule.")
            claim["value"] = claim["units"] * candle.raw_close
        if current >= rule["payment_date"]:
            account.cash += claim["net"]
            account.tax_paid += claim["withholding"]
            account.ordinary_irrf_withheld += claim["withholding"]
            account.corporate_action_ledger.append(dict(
                event_date=rule["effective_date"], realization_date=rule["realization_date"],
                payment_date=rule["payment_date"], credited_session=current,
                ticker=rule["ticker"], kind=rule["kind"], net=claim["net"],
                withholding=claim["withholding"], source_sha256=rule["source_sha256"],
            ))
            del claims[key]
    account._corporate_receivable_value = sum(claim["value"] for claim in claims.values())
