from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable


ALLOWED_CASH_KINDS = {
    "DEPOSIT",
    "WITHDRAWAL",
    "DIVIDEND",
    "JCP",
    "TAX",
    "B3_FEE",
    "BROKER_FEE",
    "CUSTODY_FEE",
    "INTEREST",
    "OTHER_CERTIFIED",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ActualFill:
    trade_date: str
    settlement_date: str
    sequence: int
    execution_id: str
    order_id: str
    side: str
    ticker: str
    shares: int
    price: float
    source_document: str
    source_sha256: str

    @property
    def notional(self) -> float:
        return self.shares * self.price


@dataclass(frozen=True)
class CashEvent:
    value_date: str
    sequence: int
    event_id: str
    kind: str
    amount: float
    source_document: str
    source_sha256: str
    ticker: str = ""


@dataclass(frozen=True)
class PositionEvent:
    value_date: str
    sequence: int
    event_id: str
    ticker: str
    share_delta: int
    source_document: str
    source_sha256: str


@dataclass(frozen=True)
class AccountSnapshot:
    value_date: str
    cash_balance: float
    positions: dict[str, int]
    source_document: str
    source_sha256: str


@dataclass(frozen=True)
class AccountReconciliation:
    opening_date: str
    closing_date: str
    opening_cash: float
    reconstructed_cash: float
    snapshot_cash: float
    cash_difference: float
    reconstructed_positions: dict[str, int]
    snapshot_positions: dict[str, int]
    position_differences: dict[str, int]
    fills: int
    cash_events: int
    position_events: int
    ledger_reconciles: bool
    blockers: tuple[str, ...]

    @property
    def exact(self) -> bool:
        """Compatibility property: only means the normalized ledger reconciles.

        Final personal-account exactness is decided by
        scripts/reconcile_actual_personal_account.py after source-byte and coverage
        verification. This property must never be used alone to emit an exact label.
        """

        return self.ledger_reconciles

    def as_dict(self) -> dict[str, object]:
        return {
            "classification": (
                "PERSONAL_ACCOUNT_LEDGER_RECONCILED"
                if self.ledger_reconciles
                else "PERSONAL_ACCOUNT_LEDGER_RECONCILIATION_REJECTED"
            ),
            "opening_date": self.opening_date,
            "closing_date": self.closing_date,
            "opening_cash": self.opening_cash,
            "reconstructed_cash": self.reconstructed_cash,
            "snapshot_cash": self.snapshot_cash,
            "cash_difference": self.cash_difference,
            "reconstructed_positions": self.reconstructed_positions,
            "snapshot_positions": self.snapshot_positions,
            "position_differences": self.position_differences,
            "fills": self.fills,
            "cash_events": self.cash_events,
            "position_events": self.position_events,
            "ledger_reconciles": self.ledger_reconciles,
            "blockers": list(self.blockers),
            "interpretation": (
                "This result verifies only the normalized ledger arithmetic between the "
                "opening and closing snapshots. Final exact-account classification also "
                "requires source-byte verification and complete-period evidence coverage."
            ),
        }


def _require_source(value: str, label: str) -> str:
    source = value.strip()
    if not source:
        raise ValueError(f"{label}: source_document is required for ledger reconciliation")
    return source


def _require_sha256(value: str, label: str) -> str:
    digest = value.strip().lower()
    if not SHA256_RE.fullmatch(digest):
        raise ValueError(f"{label}: source_sha256 must be a 64-character lowercase SHA-256")
    return digest


def _date(value: object, label: str) -> str:
    text = str(value or "").strip()[:10]
    if len(text) != 10:
        raise ValueError(f"{label}: ISO date is required")
    date.fromisoformat(text)
    return text


def _sequence(value: object) -> int:
    result = int(value or 0)
    if result < 0:
        raise ValueError("sequence must be non-negative")
    return result


def load_actual_fills(path: Path | str) -> list[ActualFill]:
    seen: set[str] = set()
    result: list[ActualFill] = []
    with Path(path).open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            execution_id = str(row.get("execution_id", "")).strip()
            if not execution_id:
                raise ValueError("actual fills require execution_id")
            if execution_id in seen:
                raise ValueError(f"duplicate execution_id: {execution_id}")
            seen.add(execution_id)

            trade_date = _date(row.get("trade_date"), execution_id)
            settlement_date = _date(row.get("settlement_date"), execution_id)
            if settlement_date < trade_date:
                raise ValueError(
                    f"settlement_date precedes trade_date: {execution_id}"
                )

            side = str(row.get("side", "")).strip().upper()
            if side not in {"BUY", "SELL"}:
                raise ValueError(f"invalid side for {execution_id}: {side}")
            ticker = str(row.get("ticker", "")).strip().upper()
            if not ticker:
                raise ValueError(f"ticker is required: {execution_id}")
            shares = int(row.get("shares", 0) or 0)
            price = float(row.get("price", 0) or 0)
            if shares <= 0 or price <= 0 or not math.isfinite(price):
                raise ValueError(f"invalid fill quantity/price: {execution_id}")

            result.append(
                ActualFill(
                    trade_date=trade_date,
                    settlement_date=settlement_date,
                    sequence=_sequence(row.get("sequence")),
                    execution_id=execution_id,
                    order_id=str(row.get("order_id", "")).strip(),
                    side=side,
                    ticker=ticker,
                    shares=shares,
                    price=price,
                    source_document=_require_source(
                        str(row.get("source_document", "")), execution_id
                    ),
                    source_sha256=_require_sha256(
                        str(row.get("source_sha256", "")), execution_id
                    ),
                )
            )
    return sorted(result, key=lambda item: (item.trade_date, item.sequence, item.execution_id))


def load_cash_events(path: Path | str) -> list[CashEvent]:
    seen: set[str] = set()
    result: list[CashEvent] = []
    with Path(path).open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            event_id = str(row.get("event_id", "")).strip()
            if not event_id:
                raise ValueError("cash events require event_id")
            if event_id in seen:
                raise ValueError(f"duplicate cash event_id: {event_id}")
            seen.add(event_id)
            kind = str(row.get("kind", "")).strip().upper()
            if kind not in ALLOWED_CASH_KINDS:
                raise ValueError(f"unsupported cash event kind: {kind}")
            amount = float(row.get("amount", 0) or 0)
            if not math.isfinite(amount):
                raise ValueError(f"non-finite cash amount: {event_id}")
            if kind in {"WITHDRAWAL", "TAX", "B3_FEE", "BROKER_FEE", "CUSTODY_FEE"} and amount > 0:
                raise ValueError(f"{kind} must be signed negative: {event_id}")
            if kind in {"DEPOSIT", "DIVIDEND", "JCP", "INTEREST"} and amount < 0:
                raise ValueError(f"{kind} must be signed positive: {event_id}")
            result.append(
                CashEvent(
                    value_date=_date(row.get("value_date"), event_id),
                    sequence=_sequence(row.get("sequence")),
                    event_id=event_id,
                    kind=kind,
                    amount=amount,
                    source_document=_require_source(str(row.get("source_document", "")), event_id),
                    source_sha256=_require_sha256(str(row.get("source_sha256", "")), event_id),
                    ticker=str(row.get("ticker", "")).strip().upper(),
                )
            )
    return sorted(result, key=lambda item: (item.value_date, item.sequence, item.event_id))


def load_position_events(path: Path | str) -> list[PositionEvent]:
    source = Path(path)
    if not source.exists():
        return []
    seen: set[str] = set()
    result: list[PositionEvent] = []
    with source.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            event_id = str(row.get("event_id", "")).strip()
            if not event_id:
                raise ValueError("position events require event_id")
            if event_id in seen:
                raise ValueError(f"duplicate position event_id: {event_id}")
            seen.add(event_id)
            ticker = str(row.get("ticker", "")).strip().upper()
            if not ticker:
                raise ValueError(f"ticker is required: {event_id}")
            delta = int(row.get("share_delta", 0) or 0)
            if delta == 0:
                raise ValueError(f"zero share adjustment is not meaningful: {event_id}")
            result.append(
                PositionEvent(
                    value_date=_date(row.get("value_date"), event_id),
                    sequence=_sequence(row.get("sequence")),
                    event_id=event_id,
                    ticker=ticker,
                    share_delta=delta,
                    source_document=_require_source(str(row.get("source_document", "")), event_id),
                    source_sha256=_require_sha256(str(row.get("source_sha256", "")), event_id),
                )
            )
    return sorted(result, key=lambda item: (item.value_date, item.sequence, item.event_id))


def load_snapshot(path: Path | str) -> AccountSnapshot:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("account snapshot requires schema_version=1")
    cash = float(payload.get("cash_balance", 0) or 0)
    if not math.isfinite(cash):
        raise ValueError("snapshot cash_balance must be finite")
    positions = {
        str(ticker).strip().upper(): int(shares)
        for ticker, shares in dict(payload.get("positions") or {}).items()
    }
    if any(not ticker for ticker in positions):
        raise ValueError("snapshot ticker cannot be empty")
    if any(shares < 0 for shares in positions.values()):
        raise ValueError("snapshot cannot contain negative long-only share quantities")
    return AccountSnapshot(
        value_date=_date(payload.get("value_date"), "snapshot"),
        cash_balance=cash,
        positions=positions,
        source_document=_require_source(str(payload.get("source_document", "")), "snapshot"),
        source_sha256=_require_sha256(str(payload.get("source_sha256", "")), "snapshot"),
    )


def reconcile_actual_account(
    *,
    opening_snapshot: AccountSnapshot,
    closing_snapshot: AccountSnapshot,
    fills: Iterable[ActualFill],
    cash_events: Iterable[CashEvent],
    position_events: Iterable[PositionEvent],
    cent_tolerance: float = 0.005,
) -> AccountReconciliation:
    if opening_snapshot.value_date > closing_snapshot.value_date:
        raise ValueError("opening snapshot must precede closing snapshot")
    if cent_tolerance < 0 or not math.isfinite(cent_tolerance):
        raise ValueError("cent_tolerance must be finite and non-negative")

    cash = float(opening_snapshot.cash_balance)
    positions: dict[str, int] = defaultdict(int, opening_snapshot.positions)
    fill_list = list(fills)
    cash_list = list(cash_events)
    position_list = list(position_events)

    # Ownership changes on trade date. Principal cash changes on settlement date.
    # Fees, taxes and every non-principal movement remain explicit CashEvent rows.
    timeline: list[tuple[str, int, int, str, object]] = []
    for item in fill_list:
        timeline.append((item.trade_date, item.sequence, 0, item.execution_id, item))
        timeline.append((item.settlement_date, item.sequence, 1, item.execution_id, item))
    timeline.extend((item.value_date, item.sequence, 2, item.event_id, item) for item in cash_list)
    timeline.extend((item.value_date, item.sequence, 3, item.event_id, item) for item in position_list)
    timeline.sort(key=lambda item: (item[0], item[1], item[2], item[3]))

    blockers: list[str] = []
    for value_date, _, effect_kind, _, item in timeline:
        if value_date < opening_snapshot.value_date:
            blockers.append("ledger_contains_event_before_opening_snapshot")
            continue
        if value_date > closing_snapshot.value_date:
            blockers.append("ledger_contains_event_after_closing_snapshot")
            continue

        if isinstance(item, ActualFill):
            if effect_kind == 0:
                if item.side == "BUY":
                    positions[item.ticker] += item.shares
                else:
                    if positions[item.ticker] < item.shares:
                        blockers.append(f"sell_exceeds_reconstructed_position:{item.execution_id}")
                    positions[item.ticker] -= item.shares
            else:
                cash += item.notional if item.side == "SELL" else -item.notional
        elif isinstance(item, CashEvent):
            cash += item.amount
        elif isinstance(item, PositionEvent):
            positions[item.ticker] += item.share_delta
            if positions[item.ticker] < 0:
                blockers.append(f"position_event_makes_quantity_negative:{item.event_id}")

    reconstructed_positions = {
        ticker: shares for ticker, shares in sorted(positions.items()) if shares != 0
    }
    snapshot_positions = {
        ticker: shares for ticker, shares in sorted(closing_snapshot.positions.items()) if shares != 0
    }
    all_tickers = sorted(set(reconstructed_positions) | set(snapshot_positions))
    position_differences = {
        ticker: reconstructed_positions.get(ticker, 0) - snapshot_positions.get(ticker, 0)
        for ticker in all_tickers
        if reconstructed_positions.get(ticker, 0) != snapshot_positions.get(ticker, 0)
    }
    cash_difference = cash - closing_snapshot.cash_balance
    if abs(cash_difference) > cent_tolerance:
        blockers.append("cash_does_not_reconcile_to_cent")
    if position_differences:
        blockers.append("positions_do_not_reconcile_exactly")

    return AccountReconciliation(
        opening_date=opening_snapshot.value_date,
        closing_date=closing_snapshot.value_date,
        opening_cash=opening_snapshot.cash_balance,
        reconstructed_cash=cash,
        snapshot_cash=closing_snapshot.cash_balance,
        cash_difference=cash_difference,
        reconstructed_positions=reconstructed_positions,
        snapshot_positions=snapshot_positions,
        position_differences=position_differences,
        fills=len(fill_list),
        cash_events=len(cash_list),
        position_events=len(position_list),
        ledger_reconciles=not blockers,
        blockers=tuple(sorted(set(blockers))),
    )
