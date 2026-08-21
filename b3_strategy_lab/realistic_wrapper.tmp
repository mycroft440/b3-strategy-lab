from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from b3_strategy_lab import realistic_core as _core


IRRF_COMMON_RATE = 0.00005
IRRF_RETENTION_MINIMUM = 1.0


@dataclass
class MonthTax(_core.MonthTax):
    gross_tax_before_irrf: float = 0.0
    irrf_withheld_month: float = 0.0
    irrf_credit_in: float = 0.0
    irrf_credit_used: float = 0.0
    irrf_credit_out: float = 0.0


class BrazilEquityTaxLedger(_core.BrazilEquityTaxLedger):
    """Ordinary-stock tax ledger including common-operation IRRF credits.

    The 0.005% withholding is accumulated by calendar month. Retention is
    dispensed while the month's theoretical amount is <= R$1. Once the monthly
    total exceeds that threshold, the full cumulative amount becomes withheld;
    later sales withhold only the incremental amount. Withheld IRRF is credited
    against monthly ordinary tax and then carried to later months when unused.
    """

    def __init__(
        self,
        *,
        exemption_sales_limit: float = 20_000.0,
        ordinary_rate: float = 0.15,
    ) -> None:
        super().__init__(
            exemption_sales_limit=exemption_sales_limit,
            ordinary_rate=ordinary_rate,
        )
        self._irrf_incident: dict[str, float] = defaultdict(float)
        self._irrf_withheld: dict[str, float] = defaultdict(float)
        self.irrf_credit = 0.0
        self._last_withholding_delta = 0.0

    def record_sale(self, value_date: str, gross_sale: float, realized_gain: float) -> None:
        super().record_sale(value_date, gross_sale, realized_gain)
        month = value_date[:7]
        self._irrf_incident[month] += max(0.0, float(gross_sale)) * IRRF_COMMON_RATE
        incident = self._irrf_incident[month]
        target_withheld = incident if incident > IRRF_RETENTION_MINIMUM + 1e-12 else 0.0
        prior_withheld = self._irrf_withheld[month]
        delta = max(0.0, target_withheld - prior_withheld)
        self._irrf_withheld[month] = target_withheld
        self._last_withholding_delta = delta

    def take_last_withholding_delta(self) -> float:
        value = self._last_withholding_delta
        self._last_withholding_delta = 0.0
        return value

    def finalize(self, month: str) -> MonthTax:
        if month in self._finalized:
            return self._finalized[month]  # type: ignore[return-value]

        sales = float(self._sales.get(month, 0.0))
        gain = float(self._gains.get(month, 0.0))
        carry_in = float(self.loss_carry)
        taxable_gain = 0.0
        exempt_gain = 0.0
        gross_tax = 0.0

        if gain < 0:
            self.loss_carry += -gain
        elif gain > 0 and sales <= self.exemption_sales_limit:
            exempt_gain = gain
        elif gain > 0:
            offset = min(float(self.loss_carry), gain)
            taxable_gain = gain - offset
            self.loss_carry -= offset
            gross_tax = taxable_gain * float(self.ordinary_rate)

        withheld_month = float(self._irrf_withheld.get(month, 0.0))
        credit_in = float(self.irrf_credit)
        credit_available = credit_in + withheld_month
        credit_used = min(credit_available, gross_tax)
        tax_due = max(0.0, gross_tax - credit_used)
        self.irrf_credit = max(0.0, credit_available - credit_used)

        result = MonthTax(
            month=month,
            sales=sales,
            realized_gain=gain,
            taxable_gain=taxable_gain,
            exempt_gain=exempt_gain,
            loss_carry_in=carry_in,
            loss_carry_out=float(self.loss_carry),
            tax_due=tax_due,
            gross_tax_before_irrf=gross_tax,
            irrf_withheld_month=withheld_month,
            irrf_credit_in=credit_in,
            irrf_credit_used=credit_used,
            irrf_credit_out=float(self.irrf_credit),
        )
        self._finalized[month] = result
        return result

    def finalized(self) -> list[MonthTax]:
        return [self._finalized[key] for key in sorted(self._finalized)]  # type: ignore[list-item]


class RealCashAccount(_core.RealCashAccount):
    def __init__(
        self,
        initial_cash: float,
        fee_schedule,
        slippage,
        tax_ledger: BrazilEquityTaxLedger | None = None,
    ) -> None:
        super().__init__(
            initial_cash,
            fee_schedule,
            slippage,
            tax_ledger=tax_ledger or BrazilEquityTaxLedger(),
        )
        self.ordinary_irrf_withheld = 0.0

    def sell_leg(self, value_date, ticker: str, quantity: int, quote) -> None:
        # Core sale computes gain and records the sale. Our ledger then exposes the
        # incremental source withholding caused by this leg.
        super().sell_leg(value_date, ticker, quantity, quote)
        delta = self.tax.take_last_withholding_delta()  # type: ignore[attr-defined]
        if delta <= 0:
            return
        if delta > self.cash + 1e-9:
            raise ValueError(
                f"IRRF withholding for {value_date} exceeds available sale cash: "
                f"{delta:.6f} > {self.cash:.6f}."
            )
        self.cash -= delta
        self.ordinary_irrf_withheld += delta
        # tax_paid is a cumulative cash-tax field in realistic curves/summaries.
        # The later DARF is net of this credit, so adding it here does not double count.
        self.tax_paid += delta


# Explicit public names changed by this hardening layer.


def __getattr__(name: str):
    return getattr(_core, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_core)))
