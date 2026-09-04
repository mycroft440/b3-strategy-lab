from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Sequence


STANDARD_MARKET = "010"
FRACTIONAL_MARKET = "020"
STANDARD_LOT = 100


def cash_coverage_certification_issues(
    certification: dict[str, object],
    *,
    cash_events_path: Path | str,
    cash_manifest_path: Path | str,
    tickers: Iterable[str],
    start: str,
    end: str,
) -> list[str]:
    """Validate and bind an independent cash-event coverage certificate."""

    issues: list[str] = []
    try:
        required_start = date.fromisoformat(start).isoformat()
        required_end = date.fromisoformat(end).isoformat()
        certified_start = date.fromisoformat(
            str(certification.get("start", ""))
        ).isoformat()
        certified_end = date.fromisoformat(
            str(certification.get("end", ""))
        ).isoformat()
    except ValueError:
        issues.append("certification dates must be valid ISO dates")
        required_start = required_end = certified_start = certified_end = ""

    if certification.get("schema_version") != 2:
        issues.append("unsupported certification schema")
    if certification.get("coverage_certified") is not True:
        issues.append("coverage is not certified")
    if certification.get("announcement_timing_certified") is not True:
        issues.append("announcement timing is not certified")
    timing_evidence = certification.get("announcement_timing_evidence")
    if not isinstance(timing_evidence, list) or not timing_evidence:
        issues.append("announcement timing evidence is missing")
    else:
        for raw in timing_evidence:
            if not isinstance(raw, dict):
                issues.append("announcement timing evidence record is malformed")
                continue
            authority = str(raw.get("source_authority", "")).strip()
            url = str(raw.get("source_url", "")).strip()
            scope = str(raw.get("scope", "")).strip()
            conclusion = str(raw.get("conclusion", "")).strip()
            if authority not in {"B3", "CVM", "issuer"}:
                issues.append("announcement timing evidence authority is not accepted")
            if not url.startswith("https://"):
                issues.append("announcement timing evidence requires https source_url")
            if not scope or not conclusion:
                issues.append("announcement timing evidence requires scope and conclusion")
    if required_start and (
        certified_start > required_start or certified_end < required_end
    ):
        issues.append("certified period does not cover the backtest")
    if certification.get("source_authority") not in {
        "B3",
        "CVM",
        "B3+CVM+issuer",
    }:
        issues.append("source authority is not accepted")
    if not str(certification.get("reviewed_by", "")).strip():
        issues.append("independent reviewer is missing")
    try:
        reviewed_at = datetime.fromisoformat(
            str(certification.get("reviewed_at_utc", "")).replace("Z", "+00:00")
        )
        if reviewed_at.tzinfo is None:
            raise ValueError
    except ValueError:
        issues.append("review timestamp must be timezone-aware ISO datetime")
    evidence = certification.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        issues.append("primary-source evidence is missing")

    expected_tickers = sorted({str(ticker).strip().upper() for ticker in tickers})
    certified_tickers = (
        sorted(
            {
                str(ticker).strip().upper()
                for ticker in certification.get("tickers", [])
                if str(ticker).strip()
            }
        )
        if isinstance(certification.get("tickers"), list)
        else []
    )
    if certified_tickers != expected_tickers:
        issues.append("certified ticker set does not match the backtest")

    for field, path in (
        ("cash_events_sha256", Path(cash_events_path)),
        ("cash_manifest_sha256", Path(cash_manifest_path)),
    ):
        if not path.exists():
            issues.append(f"certified input is missing: {path}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if certification.get(field) != actual:
            issues.append(f"{field} does not match the certified input")
    return issues


def _month(value: str) -> str:
    return value[:7]


@dataclass(frozen=True)
class UniverseSnapshot:
    effective_date: str
    tickers: frozenset[str]


class PointInTimeUniverse:
    """Historical investable universe known on each effective date."""

    def __init__(self, snapshots: Sequence[UniverseSnapshot]) -> None:
        ordered = sorted(snapshots, key=lambda item: item.effective_date)
        if not ordered:
            raise ValueError("Point-in-time universe is empty.")
        if len({item.effective_date for item in ordered}) != len(ordered):
            raise ValueError("Duplicate effective_date in point-in-time universe.")
        self.snapshots = tuple(ordered)

    @classmethod
    def from_csv(cls, path: Path | str) -> "PointInTimeUniverse":
        grouped: dict[str, set[str]] = defaultdict(set)
        with Path(path).open(newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                effective = str(row.get("effective_date", "")).strip()
                ticker = str(row.get("ticker", "")).strip().upper()
                if not effective or not ticker:
                    raise ValueError("point-in-time CSV requires effective_date and ticker.")
                grouped[effective].add(ticker)
        return cls(
            [
                UniverseSnapshot(effective, frozenset(sorted(tickers)))
                for effective, tickers in grouped.items()
            ]
        )

    def tickers_on(self, decision_date: str) -> set[str]:
        chosen: UniverseSnapshot | None = None
        for snapshot in self.snapshots:
            if snapshot.effective_date > decision_date:
                break
            chosen = snapshot
        if chosen is None:
            raise ValueError(
                f"No point-in-time universe is known by {decision_date}; "
                f"first snapshot is {self.snapshots[0].effective_date}."
            )
        return set(chosen.tickers)

    @property
    def union(self) -> set[str]:
        result: set[str] = set()
        for snapshot in self.snapshots:
            result.update(snapshot.tickers)
        return result


@dataclass(frozen=True)
class CashDistribution:
    ticker: str
    label: str
    last_date_prior: str
    ex_date: str
    payment_date: str
    gross_per_share: float
    source_authority: str = "B3"
    source_url: str = ""

    def __post_init__(self) -> None:
        if self.gross_per_share < 0 or not math.isfinite(self.gross_per_share):
            raise ValueError("gross_per_share must be finite and non-negative.")
        if self.label.upper() not in {"DIVIDENDO", "DIVIDEND", "JCP", "JSCP"}:
            raise ValueError(f"Unsupported cash distribution label: {self.label}")


def load_cash_distributions(path: Path | str) -> list[CashDistribution]:
    result: list[CashDistribution] = []
    with Path(path).open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            result.append(
                CashDistribution(
                    ticker=str(row["ticker"]).strip().upper(),
                    label=str(row["label"]).strip().upper(),
                    last_date_prior=str(row["last_date_prior"]).strip()[:10],
                    ex_date=str(row["ex_date"]).strip()[:10],
                    payment_date=str(row["payment_date"]).strip()[:10],
                    gross_per_share=float(row["gross_per_share"]),
                    source_authority=str(row.get("source_authority", "B3")).strip() or "B3",
                    source_url=str(row.get("source_url", "")).strip(),
                )
            )
    return sorted(result, key=lambda item: (item.payment_date, item.ticker, item.label))


@dataclass(frozen=True)
class FeeRule:
    start: str
    end: str
    b3_bps: float
    brokerage_fixed: float = 0.0
    source: str = ""
    quality: str = "modeled"

    def __post_init__(self) -> None:
        try:
            start = date.fromisoformat(self.start)
            end = date.fromisoformat(self.end)
        except ValueError as exc:
            raise ValueError("Fee-rule dates must be valid ISO dates.") from exc
        if start > end:
            raise ValueError("Fee-rule start cannot exceed end.")
        if not math.isfinite(self.b3_bps) or self.b3_bps < 0:
            raise ValueError("b3_bps must be finite and non-negative.")
        if not math.isfinite(self.brokerage_fixed) or self.brokerage_fixed < 0:
            raise ValueError("brokerage_fixed must be finite and non-negative.")

    def contains(self, value: str) -> bool:
        return self.start <= value <= self.end


class FeeSchedule:
    def __init__(self, rules: Sequence[FeeRule]) -> None:
        self.rules = tuple(sorted(rules, key=lambda item: item.start))
        if not self.rules:
            raise ValueError("Fee schedule is empty.")

    @classmethod
    def from_json(cls, path: Path | str) -> "FeeSchedule":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        raw_rules = payload.get("rules")
        if not isinstance(raw_rules, list) or not raw_rules:
            raise ValueError("Fee schedule JSON requires non-empty rules.")
        return cls(
            [
                FeeRule(
                    start=str(item["start"]),
                    end=str(item["end"]),
                    b3_bps=float(item["b3_bps"]),
                    brokerage_fixed=float(item.get("brokerage_fixed", 0.0)),
                    source=str(item.get("source", "")),
                    quality=str(item.get("quality", "modeled")),
                )
                for item in raw_rules
            ]
        )

    def rule_on(self, value: str) -> FeeRule:
        matches = [rule for rule in self.rules if rule.contains(value)]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one fee rule for {value}; found {len(matches)}.")
        return matches[0]

    def cost(self, value: str, notional: float) -> float:
        if not math.isfinite(notional) or notional < 0:
            raise ValueError("Notional must be finite and non-negative.")
        if notional == 0:
            return 0.0
        rule = self.rule_on(value)
        return notional * rule.b3_bps / 10_000 + rule.brokerage_fixed

    def quality_on(self, value: str) -> str:
        return self.rule_on(value).quality


@dataclass(frozen=True)
class SlippageModel:
    base_bps: float = 10.0
    participation_bps_at_1pct: float = 5.0
    max_bps: float = 100.0

    def __post_init__(self) -> None:
        values = (
            self.base_bps,
            self.participation_bps_at_1pct,
            self.max_bps,
        )
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValueError("Slippage parameters must be finite and non-negative.")
        if self.max_bps < self.base_bps:
            raise ValueError("max_bps cannot be lower than base_bps.")
        if self.max_bps >= 10_000:
            raise ValueError("max_bps must keep sell execution prices positive.")

    def bps(self, notional: float, daily_financial_volume: float) -> float:
        if not math.isfinite(notional) or notional < 0:
            raise ValueError("Notional must be finite and non-negative.")
        if notional == 0:
            return 0.0
        if daily_financial_volume <= 0 or not math.isfinite(daily_financial_volume):
            raise ValueError("Financial volume is required for liquidity-aware slippage.")
        participation = notional / daily_financial_volume
        extra = self.participation_bps_at_1pct * (participation / 0.01)
        return min(self.max_bps, self.base_bps + max(0.0, extra))

    def price(
        self,
        side: str,
        raw_price: float,
        notional: float,
        daily_financial_volume: float,
    ) -> tuple[float, float]:
        if raw_price <= 0 or not math.isfinite(raw_price):
            raise ValueError("Invalid raw execution price.")
        bps = self.bps(notional, daily_financial_volume)
        rate = bps / 10_000
        if side == "BUY":
            return raw_price * (1 + rate), bps
        if side == "SELL":
            return raw_price * (1 - rate), bps
        raise ValueError(f"Invalid side: {side}")


@dataclass(frozen=True)
class ExecutionQuote:
    date: str
    ticker: str
    market_type: str
    open: float
    close: float
    financial_volume: float


def _base_fractional_ticker(ticker: str) -> str:
    value = ticker.strip().upper()
    if value.endswith("F") and len(value) >= 3 and value[-2].isdigit():
        return value[:-1]
    return value


class ExecutionPriceBook:
    """Opening prices for standard and fractional B3 markets.

    Quantities not divisible by 100 are split into a round-lot leg and a
    fractional leg. Missing fractional quotations raise an error instead of
    silently reusing the standard-market opening.
    """

    def __init__(self, quotes: Iterable[ExecutionQuote], standard_lot: int = STANDARD_LOT) -> None:
        if standard_lot <= 0:
            raise ValueError("standard_lot must be positive.")
        self.standard_lot = standard_lot
        self._quotes: dict[tuple[str, str, str], ExecutionQuote] = {}
        for quote in quotes:
            ticker = (
                _base_fractional_ticker(quote.ticker)
                if quote.market_type == FRACTIONAL_MARKET
                else quote.ticker.strip().upper()
            )
            key = (quote.date, ticker, quote.market_type)
            if key in self._quotes:
                raise ValueError(f"Duplicate execution quote: {key}")
            self._quotes[key] = ExecutionQuote(
                date=quote.date,
                ticker=ticker,
                market_type=quote.market_type,
                open=quote.open,
                close=quote.close,
                financial_volume=quote.financial_volume,
            )

    @classmethod
    def from_csv(cls, path: Path | str, standard_lot: int = STANDARD_LOT) -> "ExecutionPriceBook":
        rows: list[ExecutionQuote] = []
        with Path(path).open(newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                rows.append(
                    ExecutionQuote(
                        date=str(row["date"])[:10],
                        ticker=str(row["ticker"]).upper(),
                        market_type=str(row["market_type"]),
                        open=float(row["open"]),
                        close=float(row["close"]),
                        financial_volume=float(row["financial_volume"]),
                    )
                )
        return cls(rows, standard_lot=standard_lot)

    def legs(self, value_date: str, ticker: str, quantity: int) -> list[tuple[int, ExecutionQuote]]:
        if quantity < 0:
            raise ValueError("quantity cannot be negative.")
        if quantity == 0:
            return []
        ticker = ticker.upper()
        round_qty = quantity // self.standard_lot * self.standard_lot
        frac_qty = quantity - round_qty
        result: list[tuple[int, ExecutionQuote]] = []
        if round_qty:
            key = (value_date, ticker, STANDARD_MARKET)
            if key not in self._quotes:
                raise ValueError(f"Missing standard-market open for {ticker} on {value_date}.")
            result.append((round_qty, self._quotes[key]))
        if frac_qty:
            key = (value_date, ticker, FRACTIONAL_MARKET)
            if key not in self._quotes:
                raise ValueError(
                    f"Missing fractional-market open for {ticker} on {value_date}; "
                    "realistic execution refuses to substitute the standard-market price."
                )
            result.append((frac_qty, self._quotes[key]))
        return result


@dataclass
class Position:
    shares: int = 0
    average_cost: float = 0.0


@dataclass
class MonthTax:
    month: str
    sales: float = 0.0
    realized_gain: float = 0.0
    taxable_gain: float = 0.0
    exempt_gain: float = 0.0
    loss_carry_in: float = 0.0
    loss_carry_out: float = 0.0
    tax_due: float = 0.0


class BrazilEquityTaxLedger:
    """Monthly Brazilian tax model for ordinary cash-equity trades.

    The model targets the economic tax burden rather than IRRF cash timing.
    Ordinary stock sales up to R$20,000/month make positive net gains exempt;
    taxable gains above the threshold are taxed at 15% after prior ordinary
    losses are carried forward.
    """

    def __init__(
        self,
        *,
        exemption_sales_limit: float = 20_000.0,
        ordinary_rate: float = 0.15,
    ) -> None:
        if (
            not math.isfinite(exemption_sales_limit)
            or exemption_sales_limit < 0
        ):
            raise ValueError(
                "exemption_sales_limit must be finite and non-negative."
            )
        if not math.isfinite(ordinary_rate) or not 0 <= ordinary_rate <= 1:
            raise ValueError("ordinary_rate must be finite and between zero and one.")
        self.exemption_sales_limit = exemption_sales_limit
        self.ordinary_rate = ordinary_rate
        self._sales: dict[str, float] = defaultdict(float)
        self._gains: dict[str, float] = defaultdict(float)
        self._finalized: dict[str, MonthTax] = {}
        self.loss_carry = 0.0

    def record_sale(self, value_date: str, gross_sale: float, realized_gain: float) -> None:
        if not math.isfinite(gross_sale) or gross_sale < 0:
            raise ValueError("gross_sale must be finite and non-negative.")
        if not math.isfinite(realized_gain):
            raise ValueError("realized_gain must be finite.")
        month = _month(value_date)
        if month in self._finalized:
            raise ValueError(f"Tax month {month} already finalized.")
        self._sales[month] += gross_sale
        self._gains[month] += realized_gain

    def finalize(self, month: str) -> MonthTax:
        if month in self._finalized:
            return self._finalized[month]
        sales = self._sales.get(month, 0.0)
        gain = self._gains.get(month, 0.0)
        carry_in = self.loss_carry
        taxable_gain = 0.0
        exempt_gain = 0.0
        tax_due = 0.0

        if gain < 0:
            self.loss_carry += -gain
        elif gain > 0 and sales <= self.exemption_sales_limit:
            exempt_gain = gain
        elif gain > 0:
            offset = min(self.loss_carry, gain)
            taxable_gain = gain - offset
            self.loss_carry -= offset
            tax_due = taxable_gain * self.ordinary_rate

        result = MonthTax(
            month=month,
            sales=sales,
            realized_gain=gain,
            taxable_gain=taxable_gain,
            exempt_gain=exempt_gain,
            loss_carry_in=carry_in,
            loss_carry_out=self.loss_carry,
            tax_due=tax_due,
        )
        self._finalized[month] = result
        return result

    def finalized(self) -> list[MonthTax]:
        return [self._finalized[key] for key in sorted(self._finalized)]


@dataclass
class CashDistributionTaxLedger:
    monthly_dividends: dict[tuple[str, str], float] = field(
        default_factory=lambda: defaultdict(float)
    )
    settled_months: set[str] = field(default_factory=set)

    def net_jcp(self, payment_date: str, gross: float) -> tuple[float, float]:
        if not math.isfinite(gross) or gross < 0:
            raise ValueError("gross JCP must be finite and non-negative.")
        rate = 0.175 if payment_date >= "2026-01-01" else 0.15
        tax = gross * rate
        return gross - tax, tax

    def record_dividend(self, payment_date: str, payer: str, gross: float) -> None:
        if not math.isfinite(gross) or gross < 0:
            raise ValueError("gross dividend must be finite and non-negative.")
        self.monthly_dividends[(_month(payment_date), payer.upper())] += gross

    def settle_dividend_month(self, month: str) -> float:
        if month in self.settled_months:
            return 0.0
        self.settled_months.add(month)
        if int(month[:4]) < 2026:
            return 0.0
        for (one_month, payer), gross in self.monthly_dividends.items():
            if one_month == month and gross > 50_000.0:
                raise ValueError(
                    f"{month}/{payer}: dividends exceed R$50,000 in 2026+ but the "
                    "B3 event ledger does not certify whether the payment is covered "
                    "by the transitional/grandfathering exceptions of Lei 15.270/2025. "
                    "Refusing to invent the 10% withholding treatment."
                )
        return 0.0


@dataclass(frozen=True)
class TradeLedgerRow:
    date: str
    side: str
    ticker: str
    shares: int
    market_type: str
    raw_open: float
    execution_price: float
    notional: float
    fee: float
    slippage_bps: float
    realized_gain: float = 0.0


@dataclass(frozen=True)
class CashLedgerRow:
    date: str
    ticker: str
    label: str
    shares_entitled: int
    gross: float
    tax: float
    net: float


class RealCashAccount:
    def __init__(
        self,
        initial_cash: float,
        fee_schedule: FeeSchedule,
        slippage: SlippageModel,
        tax_ledger: BrazilEquityTaxLedger | None = None,
    ) -> None:
        if not math.isfinite(initial_cash) or initial_cash <= 0:
            raise ValueError("initial_cash must be finite and positive.")
        self.cash = float(initial_cash)
        self.fee_schedule = fee_schedule
        self.slippage = slippage
        self.tax = tax_ledger or BrazilEquityTaxLedger()
        self.distribution_tax = CashDistributionTaxLedger()
        self.positions: dict[str, Position] = defaultdict(Position)
        self.trade_ledger: list[TradeLedgerRow] = []
        self.cash_ledger: list[CashLedgerRow] = []
        self.tax_paid = 0.0
        self.fees_paid = 0.0
        self.dividend_jcp_tax_paid = 0.0

    def shares(self, ticker: str) -> int:
        return self.positions[ticker.upper()].shares

    def buy_leg(
        self,
        value_date: str,
        ticker: str,
        quantity: int,
        quote: ExecutionQuote,
    ) -> None:
        if quantity <= 0:
            return
        raw_notional = quantity * quote.open
        fill, slip_bps = self.slippage.price(
            "BUY", quote.open, raw_notional, quote.financial_volume
        )
        notional = quantity * fill
        fee = self.fee_schedule.cost(value_date, notional)
        debit = notional + fee
        if debit > self.cash + 1e-9:
            raise ValueError(
                f"Insufficient cash for {ticker}: need {debit:.2f}, have {self.cash:.2f}."
            )
        position = self.positions[ticker.upper()]
        old_total_cost = position.shares * position.average_cost
        position.shares += quantity
        position.average_cost = (old_total_cost + debit) / position.shares
        self.cash -= debit
        self.fees_paid += fee
        self.trade_ledger.append(
            TradeLedgerRow(
                date=value_date,
                side="BUY",
                ticker=ticker.upper(),
                shares=quantity,
                market_type=quote.market_type,
                raw_open=quote.open,
                execution_price=fill,
                notional=notional,
                fee=fee,
                slippage_bps=slip_bps,
            )
        )

    def sell_leg(
        self,
        value_date: str,
        ticker: str,
        quantity: int,
        quote: ExecutionQuote,
    ) -> None:
        if quantity <= 0:
            return
        position = self.positions[ticker.upper()]
        if quantity > position.shares:
            raise ValueError(f"Cannot sell {quantity} {ticker}; only {position.shares} held.")
        raw_notional = quantity * quote.open
        fill, slip_bps = self.slippage.price(
            "SELL", quote.open, raw_notional, quote.financial_volume
        )
        notional = quantity * fill
        fee = self.fee_schedule.cost(value_date, notional)
        proceeds = notional - fee
        cost_basis = quantity * position.average_cost
        realized_gain = proceeds - cost_basis
        self.cash += proceeds
        self.fees_paid += fee
        position.shares -= quantity
        if position.shares == 0:
            position.average_cost = 0.0
        self.tax.record_sale(value_date, notional, realized_gain)
        self.trade_ledger.append(
            TradeLedgerRow(
                date=value_date,
                side="SELL",
                ticker=ticker.upper(),
                shares=quantity,
                market_type=quote.market_type,
                raw_open=quote.open,
                execution_price=fill,
                notional=notional,
                fee=fee,
                slippage_bps=slip_bps,
                realized_gain=realized_gain,
            )
        )

    def finalize_month(self, month: str) -> tuple[MonthTax, float]:
        tax = self.tax.finalize(month)
        dividend_tax = self.distribution_tax.settle_dividend_month(month)
        total = tax.tax_due + dividend_tax
        if total > self.cash + 1e-9:
            raise ValueError(
                f"Taxes for {month} exceed available cash: {total:.2f} > {self.cash:.2f}."
            )
        self.cash -= total
        self.tax_paid += tax.tax_due
        self.dividend_jcp_tax_paid += dividend_tax
        return tax, dividend_tax

    def credit_distribution(
        self,
        payment_date: str,
        ticker: str,
        label: str,
        shares_entitled: int,
        gross_per_share: float,
    ) -> CashLedgerRow:
        gross = max(0, shares_entitled) * gross_per_share
        label = label.upper()
        if label in {"JCP", "JSCP"}:
            net, tax = self.distribution_tax.net_jcp(payment_date, gross)
            self.dividend_jcp_tax_paid += tax
        else:
            net, tax = gross, 0.0
            self.distribution_tax.record_dividend(payment_date, ticker, gross)
        self.cash += net
        row = CashLedgerRow(
            date=payment_date,
            ticker=ticker.upper(),
            label=label,
            shares_entitled=shares_entitled,
            gross=gross,
            tax=tax,
            net=net,
        )
        self.cash_ledger.append(row)
        return row


def write_dataclass_csv(path: Path | str, rows: Sequence[object]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        output.write_text("", encoding="utf-8")
        return output
    fields = list(rows[0].__dataclass_fields__)  # type: ignore[attr-defined]
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: getattr(row, field) for field in fields})
    return output
