from __future__ import annotations

"""Small fail-closed patches discovered by adversarial backtest auditing.

Keep these corrections isolated and automatically installed from the package
initializer so every normal entry point receives the same accounting semantics.
"""

from . import realistic_portfolio_core as _portfolio_core


def _provisional_ordinary_tax_after_irrf(account, value_date: str) -> float:
    """Return only the still-unfunded ordinary-tax liability for the month.

    Common-operation IRRF is removed from brokerage cash at sale time by the
    hardened ``RealCashAccount`` and becomes a credit against the monthly tax.
    Reserving the gross monthly tax again would therefore double-reserve both the
    current month's withholding and any IRRF credit carried from earlier months.
    """

    ledger = account.tax
    month = value_date[:7]
    if month in ledger._finalized:
        return 0.0

    sales = float(ledger._sales.get(month, 0.0))
    gain = float(ledger._gains.get(month, 0.0))
    if sales <= float(ledger.exemption_sales_limit) or gain <= 0:
        return 0.0

    offset = min(float(ledger.loss_carry), gain)
    gross_tax = max(0.0, gain - offset) * float(ledger.ordinary_rate)

    withheld_by_month = getattr(ledger, "_irrf_withheld", {})
    withheld_month = float(withheld_by_month.get(month, 0.0))
    carried_credit = float(getattr(ledger, "irrf_credit", 0.0))
    available_irrf_credit = max(0.0, withheld_month + carried_credit)

    return max(0.0, gross_tax - min(gross_tax, available_irrf_credit))


def install() -> None:
    if getattr(_portfolio_core, "_audit_hardening_installed", False):
        return
    _portfolio_core._provisional_ordinary_tax = _provisional_ordinary_tax_after_irrf
    _portfolio_core._audit_hardening_installed = True


install()
