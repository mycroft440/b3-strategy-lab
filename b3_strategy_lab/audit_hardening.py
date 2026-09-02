from __future__ import annotations

"""Fail-closed patches discovered by adversarial backtest auditing.

Keep the corrections isolated and automatically installed from the package
initializer so every normal entry point receives the same accounting semantics.
"""

import math

from . import realistic_core as _realistic_core
from . import realistic_portfolio_core as _portfolio_core

_original_buy_leg = _realistic_core.RealCashAccount.buy_leg
_original_sell_leg = _realistic_core.RealCashAccount.sell_leg


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


def _enforce_causal_capacity(account, value_date: str, ticker: str, quantity: int, quote) -> None:
    """Reject fills above the configured causal-ADV participation ceiling.

    The generic engine keeps this disabled for backwards-compatible research.
    Certified runners explicitly set ``_max_causal_adv_participation``. Once set,
    an oversized order is rejected instead of receiving an unrealistic full fill
    merely because the slippage curve reached its maximum bps.
    """

    if quantity <= 0:
        return
    limit = getattr(account, "_max_causal_adv_participation", None)
    if limit is None:
        return
    limit = float(limit)
    if not math.isfinite(limit) or not 0 < limit <= 1:
        raise ValueError("max causal ADV participation must be finite and in (0, 1].")

    raw_price = float(quote.open)
    liquidity = float(quote.financial_volume)
    if raw_price <= 0 or not math.isfinite(raw_price):
        raise ValueError(f"{value_date}/{ticker}: invalid raw price for capacity check.")
    if liquidity <= 0 or not math.isfinite(liquidity):
        raise ValueError(
            f"{value_date}/{ticker}: causal financial volume is required for capacity check."
        )
    raw_notional = int(quantity) * raw_price
    participation = raw_notional / liquidity
    if participation > limit + 1e-12:
        raise ValueError(
            f"{value_date}/{ticker}/{quote.market_type}: requested opening fill uses "
            f"{participation:.6%} of causal ADV, above certified limit {limit:.6%}. "
            "Refusing a full-fill assumption."
        )


def _capacity_checked_buy_leg(self, value_date, ticker: str, quantity: int, quote) -> None:
    _enforce_causal_capacity(self, value_date, ticker, quantity, quote)
    _original_buy_leg(self, value_date, ticker, quantity, quote)


def _capacity_checked_sell_leg(self, value_date, ticker: str, quantity: int, quote) -> None:
    _enforce_causal_capacity(self, value_date, ticker, quantity, quote)
    _original_sell_leg(self, value_date, ticker, quantity, quote)


def install() -> None:
    if getattr(_portfolio_core, "_audit_hardening_installed", False):
        return
    _portfolio_core._provisional_ordinary_tax = _provisional_ordinary_tax_after_irrf
    _realistic_core.RealCashAccount.buy_leg = _capacity_checked_buy_leg
    _realistic_core.RealCashAccount.sell_leg = _capacity_checked_sell_leg
    _portfolio_core._audit_hardening_installed = True


install()
