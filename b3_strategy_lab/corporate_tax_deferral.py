from __future__ import annotations

"""Causal tax closing for source-delayed corporate settlement prices.

A fractional auction can economically realize in one month while its official
price is not published until the next. Ordinary tax must remain attributed to
the realization month, but that month cannot be finalized before the price is
causally known. This patch defers month finalization only while such a reviewed
corporate receivable is unpriced, then finalizes deferred months in order after
the source-backed price becomes available.

The settlement ledger and its source documents are also read from the
point-in-time manifest directory, which is already included byte-for-byte in the
realistic input snapshot. This prevents a certified snapshot from being replayed
against a different corporate-settlement rule or evidence file.
"""

from pathlib import Path

from . import corporate_settlements as _settlements
from . import realistic as _realistic


_SNAPSHOT_SETTLEMENTS = (
    Path(__file__).resolve().parents[1]
    / "data/manifests_point_in_time/corporate_settlements.json"
)

# The normal checkout contains these source-bound files, and the realistic
# snapshot archives the whole manifests_point_in_time directory. On snapshot
# reuse extraction restores the certified bytes before replay.
if _settlements.DEFAULT_CORPORATE_SETTLEMENTS != _SNAPSHOT_SETTLEMENTS:
    _settlements.DEFAULT_CORPORATE_SETTLEMENTS = _SNAPSHOT_SETTLEMENTS
    _settlements._DEFAULT_RULES = None

_ORIGINAL_FINALIZE_ATTR = "_corporate_tax_deferral_original_finalize_month"
if not hasattr(_realistic.RealCashAccount, _ORIGINAL_FINALIZE_ATTR):
    setattr(
        _realistic.RealCashAccount,
        _ORIGINAL_FINALIZE_ATTR,
        _realistic.RealCashAccount.__dict__["finalize_month"],
    )
_ORIGINAL_FINALIZE = getattr(_realistic.RealCashAccount, _ORIGINAL_FINALIZE_ATTR)

_ORIGINAL_MARK_ATTR = "_corporate_tax_deferral_original_mark_and_pay"
if not hasattr(_settlements, _ORIGINAL_MARK_ATTR):
    setattr(_settlements, _ORIGINAL_MARK_ATTR, _settlements.mark_and_pay_corporate_receivables)
_ORIGINAL_MARK_AND_PAY = getattr(_settlements, _ORIGINAL_MARK_ATTR)


def _unpriced_realization_months(account) -> set[str]:
    months: set[str] = set()
    for claim in getattr(account, "_corporate_receivables", {}).values():
        if claim.get("net") is not None:
            continue
        rule = claim.get("rule") or {}
        realization_date = str(rule.get("realization_date", ""))
        if len(realization_date) >= 7:
            months.add(realization_date[:7])
    return months


def _deferred_months(account) -> set[str]:
    months = getattr(account, "_corporate_tax_deferred_months", None)
    if months is None:
        months = set()
        account._corporate_tax_deferred_months = months
    return months


def _finalize_ready_deferred_months(account) -> None:
    deferred = _deferred_months(account)
    while deferred:
        month = min(deferred)
        unresolved = _unpriced_realization_months(account)
        if any(value <= month for value in unresolved):
            break
        _ORIGINAL_FINALIZE(account, month)
        deferred.remove(month)


def _causal_finalize_month(self, month: str):
    deferred = _deferred_months(self)
    unresolved = _unpriced_realization_months(self)
    # Preserve chronological loss-carry/IRRF semantics: once an earlier month is
    # waiting for a source-delayed sale price, later months cannot close first.
    if deferred or any(value <= month for value in unresolved):
        deferred.add(month)
        return None, 0.0
    return _ORIGINAL_FINALIZE(self, month)


def _mark_and_pay_then_finalize(account, data, current):
    _ORIGINAL_MARK_AND_PAY(account, data, current)
    _finalize_ready_deferred_months(account)


def install() -> None:
    _realistic.RealCashAccount.finalize_month = _causal_finalize_month
    _settlements.mark_and_pay_corporate_receivables = _mark_and_pay_then_finalize
    _realistic.RealCashAccount._corporate_tax_deferral_installed = True


install()
