from __future__ import annotations

"""Fail-closed patches discovered by adversarial backtest auditing.

Keep the corrections isolated and automatically installed from the package
initializer so every normal entry point receives the same accounting semantics.
"""

import math

from . import realistic_core as _realistic_core
from . import realistic_portfolio_core as _portfolio_core


# Store immutable canonical methods on the class itself. On importlib.reload(),
# this module dictionary is reused while the class still contains the installed
# wrappers; recapturing those wrappers as "originals" would make the old wrapper
# recurse into itself on its next call.
_ORIGINAL_BUY_ATTR = "_audit_hardening_original_buy_leg"
_ORIGINAL_SELL_ATTR = "_audit_hardening_original_sell_leg"
if not hasattr(_realistic_core.RealCashAccount, _ORIGINAL_BUY_ATTR):
    setattr(
        _realistic_core.RealCashAccount,
        _ORIGINAL_BUY_ATTR,
        _realistic_core.RealCashAccount.__dict__["buy_leg"],
    )
if not hasattr(_realistic_core.RealCashAccount, _ORIGINAL_SELL_ATTR):
    setattr(
        _realistic_core.RealCashAccount,
        _ORIGINAL_SELL_ATTR,
        _realistic_core.RealCashAccount.__dict__["sell_leg"],
    )
_original_buy_leg = getattr(_realistic_core.RealCashAccount, _ORIGINAL_BUY_ATTR)
_original_sell_leg = getattr(_realistic_core.RealCashAccount, _ORIGINAL_SELL_ATTR)


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


def remaining_causal_capacity(account, value_date: str, ticker: str, quote) -> float:
    """Remaining daily notional under the causal ADV limit, across both sides."""

    limit = float(getattr(account, "_max_causal_adv_participation", 0.01))
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
    key = (value_date, ticker.upper(), quote.market_type)
    used = getattr(account, "_causal_capacity_used", {}).get(key, 0.0)
    return max(0.0, limit * liquidity - used)


def _enforce_causal_capacity(account, value_date: str, ticker: str, quantity: int, quote) -> None:
    if quantity <= 0:
        return
    remaining = remaining_causal_capacity(account, value_date, ticker, quote)
    if int(quantity) * float(quote.open) > remaining + 1e-9:
        raise ValueError(
            f"{value_date}/{ticker}/{quote.market_type}: requested opening fill uses "
            "more than the remaining daily causal ADV capacity. "
            "Refusing a full-fill assumption."
        )


def _record_capacity(account, value_date, ticker, quantity, quote) -> None:
    if not hasattr(account, "_causal_capacity_used"):
        account._causal_capacity_used = {}
    key = (value_date, ticker.upper(), quote.market_type)
    account._causal_capacity_used[key] = (
        account._causal_capacity_used.get(key, 0.0) + max(0, quantity) * float(quote.open)
    )


def _capacity_checked_buy_leg(self, value_date, ticker: str, quantity: int, quote) -> None:
    _enforce_causal_capacity(self, value_date, ticker, quantity, quote)
    _original_buy_leg(self, value_date, ticker, quantity, quote)
    _record_capacity(self, value_date, ticker, quantity, quote)


def _capacity_checked_sell_leg(self, value_date, ticker: str, quantity: int, quote) -> None:
    _enforce_causal_capacity(self, value_date, ticker, quantity, quote)
    _original_sell_leg(self, value_date, ticker, quantity, quote)
    _record_capacity(self, value_date, ticker, quantity, quote)


def install() -> None:
    # Stable canonical references make reassignment safe and idempotent. Always
    # rebind all targets so reloads of this module or either core module cannot
    # leave stale wrapper bytecode or an unpatched replacement class/function.
    _portfolio_core._provisional_ordinary_tax = _provisional_ordinary_tax_after_irrf
    _realistic_core.RealCashAccount.buy_leg = _capacity_checked_buy_leg
    _realistic_core.RealCashAccount.sell_leg = _capacity_checked_sell_leg
    _realistic_core.RealCashAccount._audit_hardening_installed = True
    _portfolio_core._audit_hardening_installed = True


install()
