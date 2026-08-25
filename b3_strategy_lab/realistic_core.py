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


class LiquidityCapacityError(ValueError):
    """A hypothetical order cannot be filled inside the declared capacity cap."""


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

    if certification.get("schema_version") != 1:
        issues.append("unsupported certification schema")
    if certification.get("coverage_certified") is not True:
        issues.append("coverage is not certified")
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
    b3_quality: str = ""
    broker_quality: str = ""

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
        rules = []
        for item in raw_rules:
            quality = str(item.get("quality", "modeled"))
            rules.append(
                FeeRule(
                    start=str(item["start"]),
                    end=str(item["end"]),
                    b3_bps=float(item["b3_bps"]),
                    brokerage_fixed=float(item.get("brokerage_fixed", 0.0)),
                    source=str(item.get("source", "")),
                    quality=quality,
                    b3_quality=str(
                        item.get(
                            "b3_quality",
                            "official" if quality in {"official", "certified"} else quality,
                        )
                    ),
                    broker_quality=str(
                        item.get(
                            "broker_quality",
                            "certified" if quality == "certified" else "unverified",
                        )
                    ),
                )
            )
        return cls(rules)

    def rule_on(self, value: str) -> FeeRule:
        matches = [rule for rule in self.rules if rule.contains(value)]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one fee rule for {value}; found {len(matches)}.")
        return matches[0]

    def cost(self, value: str, notional: float) -> float:
        if notional <= 0:
            return 0.0
        rule = self.rule_on(value)
        return notional * rule.b3_bps / 10_000 + rule.brokerage_fixed

    def quality_on(self, value: str) -> str:
        return self.rule_on(value).quality

    def b3_quality_on(self, value: str) -> str:
        rule = self.rule_on(value)
        return rule.b3_quality or rule.quality

    def broker_quality_on(self, value: str) -> str:
        rule = self.rule_on(value)
        return rule.broker_quality or "unverified"


@dataclass(frozen=True)
class SlippageModel:
    base_bps: float = 10.0
    participation_bps_at_1pct: float = 5.0
    max_bps: float = 100.0
    max_participation_rate: float = 0.01

    def __post_init__(self) -> None:
        values = (
            self.base_bps,
            self.participation_bps_at_1pct,
            self.max_bps,
            self.max_participation_rate,
        )
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValueError("Slippage and capacity parameters must be finite and non-negative.")
        if self.max_bps < self.base_bps:
            raise ValueError("max_bps cannot be smaller than base_bps.")
        if self.max_participation_rate <= 0 or self.max_participation_rate > 1:
            raise ValueError("max_participation_rate must be in (0, 1].")

    def participation(
        self,
        notional: float,
        financial_volume: float,
        *,
        quantity: int = 0,
        traded_quantity: float = 0.0,
    ) -> tuple[float, float]:
        if notional <= 0:
            return 0.0, 0.0
        if financial_volume <= 0 or not math.isfinite(financial_volume):
            raise ValueError("Pre-trade financial-volume reference is required.")
        financial_rate = notional / financial_volume
        quantity_rate = 0.0
        if quantity > 0:
            if traded_quantity <= 0 or not math.isfinite(traded_quantity):
                raise ValueError("Pre-trade quantity reference is required.")
            quantity_rate = quantity / traded_quantity
        observed = max(financial_rate, quantity_rate)
        if observed > self.max_participation_rate + 1e-12:
            raise LiquidityCapacityError(
                "Order exceeds the hard pre-trade liquidity-capacity limit: "
                f"participation={observed:.6%}, cap={self.max_participation_rate:.6%}."
            )
        return financial_rate, quantity_rate

    def bps(self, notional: float, daily_financial_volume: float) -> float:
        if notional <= 0:
            return 0.0
        participation, _ = self.participation(notional, daily_financial_volume)
        extra = self.participation_bps_at_1pct * (participation / 0.01)
        return min(self.max_bps, self.base_bps + max(0.0, extra))

    def price(
        self,
        side: str,
        raw_price: float,
        notional: float,
        daily_financial_volume: float,
        *,
        quantity: int = 0,
        daily_quantity: float = 0.0,
    ) -> tuple[float, float]:
        if raw_price <= 0 or not math.isfinite(raw_price):
            raise ValueError("Invalid raw execution price.")
        financial_rate, quantity_rate = self.participation(
            notional,
            daily_financial_volume,
            quantity=quantity,
            traded_quantity=daily_quantity,
        )
        participation = max(financial_rate, quantity_rate)
        extra = self.participation_bps_at_1pct * (participation / 0.01)
        bps = min(self.max_bps, self.base_bps + max(0.0, extra))
        rate = bps / 10_000
        if side == "BUY":
            fill = raw_price * (1 + rate)
        elif side == "SELL":
            fill = raw_price * (1 - rate)
        else:
            raise ValueError(f"Invalid side: {side}")
        actual_bps = abs(fill / raw_price - 1.0) * 10_000
        return fill, actual_bps


@dataclass(frozen=True)
class ExecutionQuote:
    date: str
    ticker: str
    market_type: str
    open: float
    close: float
    financial_volume: float
    high: float = 0.0
    low: float = 0.0
    quantity: int = 0
    trades: int = 0
    liquidity_reference_financial_volume: float = 0.0
    liquidity_reference_quantity: float = 0.0
    liquidity_reference_sessions: int = 0
    liquidity_reference_end: str = ""

    @property
    def capacity_financial_volume(self) -> float:
        return (
            self.liquidity_reference_financial_volume
            if self.liquidity_reference_financial_volume > 0
            else self.financial_volume
        )

    @property
    def capacity_quantity(self) -> float:
        if self.liquidity_reference_quantity > 0:
            return self.liquidity_reference_quantity
        if self.quantity > 0:
            return float(self.quantity)
        # Backward-compatible approximation for in-memory unit fixtures only.
        # Production CSV loading requires the explicit causal quantity reference.
        return self.financial_volume / self.open if self.open > 0 else 0.0


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
                high=quote.high,
                low=quote.low,
                quantity=quote.quantity,
                trades=quote.trades,
                liquidity_reference_financial_volume=quote.liquidity_reference_financial_volume,
                liquidity_reference_quantity=quote.liquidity_reference_quantity,
                liquidity_reference_sessions=quote.liquidity_reference_sessions,
                liquidity_reference_end=quote.liquidity_reference_end,
            )

    @classmethod
    def from_csv(
        cls,
        path: Path | str,
        standard_lot: int = STANDARD_LOT,
        *,
        require_causal_liquidity: bool = True,
    ) -> "ExecutionPriceBook":
        rows: list[ExecutionQuote] = []
        with Path(path).open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            causal_fields = {
                "high",
                "low",
                "quantity",
                "trades",
                "liquidity_reference_financial_volume",
                "liquidity_reference_quantity",
                "liquidity_reference_sessions",
                "liquidity_reference_end",
            }
            missing = causal_fields - set(reader.fieldnames or [])
            if require_causal_liquidity and missing:
                raise ValueError(
                    "Execution book lacks causal liquidity/OHLC fields: "
                    + ", ".join(sorted(missing))
                )
            for row in reader:
                value_date = str(row["date"])[:10]
                reference_end = str(row.get("liquidity_reference_end", ""))[:10]
                if require_causal_liquidity and (
                    not reference_end
                    or reference_end >= value_date
                    or float(row.get("liquidity_reference_financial_volume", 0) or 0) <= 0
                    or float(row.get("liquidity_reference_quantity", 0) or 0) <= 0
                    or int(row.get("liquidity_reference_sessions", 0) or 0) <= 0
                ):
                    raise ValueError(
                        f"{value_date}/{row.get('ticker', '')}/{row.get('market_type', '')}: "
                        "execution quote lacks a strictly pre-trade liquidity reference."
                    )
                rows.append(
                    ExecutionQuote(
                        date=value_date,
                        ticker=str(row["ticker"]).upper(),
                        market_type=str(row["market_type"]),
                        open=float(row["open"]),
                        close=float(row["close"]),
                        financial_volume=float(row["financial_volume"]),
                        high=float(row.get("high", 0) or 0),
                        low=float(row.get("low", 0) or 0),
                        quantity=int(row.get("quantity", 0) or 0),
                        trades=int(row.get("trades", 0) or 0),
                        liquidity_reference_financial_volume=float(
                            row.get("liquidity_reference_financial_volume", 0) or 0
                        ),
                        liquidity_reference_quantity=float(
                            row.get("liquidity_reference_quantity", 0) or 0
                        ),
                        liquidity_reference_sessions=int(
                            row.get("liquidity_reference_sessions", 0) or 0
                        ),
                        liquidity_reference_end=reference_end,
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
        self.exemption_sales_limit = exemption_sales_limit
        self.ordinary_rate = ordinary_rate
        self._sales: dict[str, float] = defaultdict(float)
        self._gains: dict[str, float] = defaultdict(float)
        self._finalized: dict[str, MonthTax] = {}
        self.loss_carry = 0.0

    def record_sale(self, value_date: str, gross_sale: float, realized_gain: float) -> None:
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
        rate = 0.175 if payment_date >= "2026-01-01" else 0.15
        tax = gross * rate
        return gross - tax, tax

    def record_dividend(self, payment_date: str, payer: str, gross: float) -> None:
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
    financial_participation: float = 0.0
    quantity_participation: float = 0.0
    capacity_reference_end: str = ""
    fill_outside_daily_range: bool = False


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
        if initial_cash <= 0:
            raise ValueError("initial_cash must be positive.")
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
        financial_participation, quantity_participation = self.slippage.participation(
            raw_notional,
            quote.capacity_financial_volume,
            quantity=quantity,
            traded_quantity=quote.capacity_quantity,
        )
        fill, slip_bps = self.slippage.price(
            "BUY",
            quote.open,
            raw_notional,
            quote.capacity_financial_volume,
            quantity=quantity,
            daily_quantity=quote.capacity_quantity,
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
                financial_participation=financial_participation,
                quantity_participation=quantity_participation,
                capacity_reference_end=quote.liquidity_reference_end,
                fill_outside_daily_range=(
                    quote.low > 0
                    and quote.high > 0
                    and not (quote.low - 1e-12 <= fill <= quote.high + 1e-12)
                ),
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
        financial_participation, quantity_participation = self.slippage.participation(
            raw_notional,
            quote.capacity_financial_volume,
            quantity=quantity,
            traded_quantity=quote.capacity_quantity,
        )
        fill, slip_bps = self.slippage.price(
            "SELL",
            quote.open,
            raw_notional,
            quote.capacity_financial_volume,
            quantity=quantity,
            daily_quantity=quote.capacity_quantity,
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
                financial_participation=financial_participation,
                quantity_participation=quantity_participation,
                capacity_reference_end=quote.liquidity_reference_end,
                fill_outside_daily_range=(
                    quote.low > 0
                    and quote.high > 0
                    and not (quote.low - 1e-12 <= fill <= quote.high + 1e-12)
                ),
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
