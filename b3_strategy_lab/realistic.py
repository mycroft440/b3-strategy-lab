from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from b3_strategy_lab import realistic_core as _core


IRRF_COMMON_RATE = 0.00005
IRRF_RETENTION_MINIMUM = 1.0
DARF_MINIMUM_PAYMENT = 10.0


def _next_month(month: str) -> str:
    year, number = (int(item) for item in month.split("-"))
    if number == 12:
        return f"{year + 1:04d}-01"
    return f"{year:04d}-{number + 1:02d}"


@dataclass
class MonthTax(_core.MonthTax):
    gross_tax_before_irrf: float = 0.0
    irrf_withheld_month: float = 0.0
    irrf_credit_in: float = 0.0
    irrf_credit_used: float = 0.0
    irrf_credit_out: float = 0.0


class BrazilEquityTaxLedger(_core.BrazilEquityTaxLedger):
    """Ordinary-stock tax ledger including common-operation IRRF credits."""

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
    """Cash account with tax escrow and earned-but-unpaid distribution receivables.

    Ordinary tax already determined by the closed month is removed from investable
    cash into ``tax_escrow``. Separately, a dividend/JCP right is recognized only
    after the cum-right close, as a non-investable receivable. On payment the
    receivable is replaced by cash instead of creating a second economic gain.
    """

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
        self.darf_paid = 0.0
        self.tax_escrow = 0.0
        self._darf_carry = 0.0
        self._scheduled_darfs: dict[str, float] = defaultdict(float)
        self._scheduled_tax_months: set[str] = set()
        self._due_session_cache: dict[str, str] = {}
        self._distribution_receivables: dict[
            object, tuple[float, float, str, str, str]
        ] = {}
        self._pending_dividend_gross: dict[tuple[str, str], float] = defaultdict(float)

    def sell_leg(self, value_date, ticker: str, quantity: int, quote) -> None:
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
        self.tax_paid += delta

    def register_distribution_receivable(
        self,
        event_key: object,
        *,
        ticker: str,
        label: str,
        shares_entitled: int,
        gross_per_share: float,
        payment_date: str,
    ) -> float:
        """Recognize a distribution right without making it spendable cash."""

        if event_key in self._distribution_receivables:
            return self._distribution_receivables[event_key][0]
        shares = max(0, int(shares_entitled))
        gross = shares * max(0.0, float(gross_per_share))
        normalized_label = str(label).upper()
        payer = str(ticker).upper()
        payment_month = str(payment_date)[:7]

        if normalized_label in {"JCP", "JSCP"}:
            rate = 0.175 if str(payment_date) >= "2026-01-01" else 0.15
            net = gross * (1.0 - rate)
        else:
            key = (payment_month, payer)
            previous = self._pending_dividend_gross[key]
            updated = previous + gross
            # For 2026+, dividends above R$50k/month from the same payer can require
            # source withholding subject to transitional exceptions. The isolated B3
            # event ledger cannot prove those exceptions, so fail before overstating
            # the receivable as gross when its net amount is uncertain.
            if int(payment_month[:4]) >= 2026 and updated > 50_000.0 + 1e-9:
                raise ValueError(
                    f"{payment_month}/{payer}: pending dividends exceed R$50,000 but "
                    "the event ledger does not certify the Lei 15.270/2025 transitional "
                    "withholding treatment."
                )
            self._pending_dividend_gross[key] = updated
            net = gross

        self._distribution_receivables[event_key] = (
            net,
            gross,
            payment_month,
            payer,
            normalized_label,
        )
        return net

    def settle_distribution_receivable(self, event_key: object) -> float:
        """Remove the economic receivable immediately before the cash credit."""

        item = self._distribution_receivables.pop(event_key, None)
        if item is None:
            return 0.0
        net, gross, payment_month, payer, label = item
        if label not in {"JCP", "JSCP"}:
            key = (payment_month, payer)
            self._pending_dividend_gross[key] = max(
                0.0, self._pending_dividend_gross[key] - gross
            )
        return net

    def distribution_receivable_value(self) -> float:
        return float(sum(item[0] for item in self._distribution_receivables.values()))

    def finalize_month(self, month: str):
        tax = self.tax.finalize(month)
        dividend_tax = self.distribution_tax.settle_dividend_month(month)
        if dividend_tax:
            raise ValueError(
                "A nonzero dividend tax settlement requires explicit source-withholding "
                "cash timing; refusing to treat it as an ordinary DARF."
            )
        if month not in self._scheduled_tax_months:
            self._scheduled_tax_months.add(month)
            accrued = max(0.0, float(tax.tax_due))
            if accrued > self.cash + 1e-9:
                raise ValueError(
                    f"Accrued ordinary tax for {month} exceeds investable brokerage cash: "
                    f"{accrued:.2f} > {self.cash:.2f}."
                )
            self.cash -= accrued
            self.tax_escrow += accrued
            self._darf_carry += accrued
            if self._darf_carry + 1e-12 >= DARF_MINIMUM_PAYMENT:
                self._scheduled_darfs[_next_month(month)] += self._darf_carry
                self._darf_carry = 0.0
        return tax, dividend_tax

    def known_darf_reserve(self) -> float:
        return float(self.tax_escrow)

    def outstanding_tax_liability(self) -> float:
        return float(self.tax_escrow)

    def gross_brokerage_cash_before_unpaid_tax(self) -> float:
        return float(self.cash + self.tax_escrow)

    def process_due_taxes(self, value_date: str, market_dates) -> float:
        """Settle scheduled escrow on the final B3 session of its due month."""

        month = value_date[:7]
        overdue = sorted(due_month for due_month in self._scheduled_darfs if due_month < month)
        if overdue:
            raise ValueError(
                "Unpaid DARF passed its modeled due month: " + ", ".join(overdue)
            )
        amount = float(self._scheduled_darfs.get(month, 0.0))
        if amount <= 0:
            return 0.0
        due_session = self._due_session_cache.get(month)
        if due_session is None:
            sessions = [str(day)[:10] for day in market_dates if str(day)[:7] == month]
            if not sessions:
                raise ValueError(f"No B3 session is available to place DARF due in {month}.")
            due_session = max(sessions)
            self._due_session_cache[month] = due_session
        if value_date != due_session:
            return 0.0
        if amount > self.tax_escrow + 1e-9:
            raise ValueError(
                f"DARF due on {value_date} exceeds accrued tax escrow: "
                f"{amount:.2f} > {self.tax_escrow:.2f}."
            )
        self.tax_escrow -= amount
        if abs(self.tax_escrow) < 1e-10:
            self.tax_escrow = 0.0
        self.tax_paid += amount
        self.darf_paid += amount
        del self._scheduled_darfs[month]
        return amount


# Explicit public names changed by this hardening layer.


def __getattr__(name: str):
    return getattr(_core, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_core)))
