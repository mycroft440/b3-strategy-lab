from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
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


@dataclass(frozen=True)
class ActualFill:
    trade_date: str
    settlement_date: str
    execution_id: str
    order_id: str
    side: str
    ticker: str
    shares: int
    price: float
    source_document: str

    @property
    def notional(self) -> float:
        return self.shares * self.price


@dataclass(frozen=True)
class CashEvent:
    value_date: str
    event_id: str
    kind: str
    amount: float
    source_document: str
    ticker: str = ""


@dataclass(frozen=True)
class PositionEvent:
    value_date: str
    event_id: str
    ticker: str
    share_delta: int
    source_document: str


@dataclass(frozen=True)
class AccountSnapshot:
    value_date: str
    cash_balance: float
    positions: dict[str, int]
    source_document: str


@dataclass(frozen=True)
class AccountReconciliation:
    start_cash: float
    reconstructed_cash: float
    snapshot_cash: float
    cash_difference: float
    reconstructed_positions: dict[str, int]
    snapshot_positions: dict[str, int]
    position_differences: dict[str, int]
    fills: int
    cash_events: int
    position_events: int
    exact: bool
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "classification": (
                "ACTUAL_PERSONAL_ACCOUNT_EXACT_RECONCILIATION"
                if self.exact
                else "ACTUAL_PERSONAL_ACCOUNT_RECONCILIATION_REJECTED"
            ),
            "start_cash": self.start_cash,
            "reconstructed_cash": self.reconstructed_cash,
            "snapshot_cash": self.snapshot_cash,
            "cash_difference": self.cash_difference,
            "reconstructed_positions": self.reconstructed_positions,
            "snapshot_positions": self.snapshot_positions,
            "position_differences": self.position_differences,
            "fills": self.fills,
            "cash_events": self.cash_events,
            "position_events": self.position_events,
            "exact": self.exact,
            "blockers": list(self.blockers),
            "interpretation": (
                "Exact means the supplied broker-source ledger reconciles cash to the cent "
                "and every final share quantity exactly. It does not infer missing trades, "
                "fees, taxes, dividends or corporate-action quantities."
            ),
        }


def _require_source(value: str, label: str) -> str:
    source = value.strip()
    if not source:
        raise ValueError(f"{label}: source_document is required for exact reconciliation")
    return source


def load_actual_fills(path: Path | str) -> list[ActualFill]:
    source = Path(path)
    seen: set[str] = set()
    result: list[ActualFill] = []
    with source.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            execution_id = str(row.get("execution_id", "")).strip()
            if not execution_id:
                raise ValueError("actual fills require execution_id")
            if execution_id in seen:
                raise ValueError(f"duplicate execution_id: {execution_id}")
            seen.add(execution_id)
            side = str(row.get("side", "")).strip().upper()
            if side not in {"BUY", "SELL"}:
                raise ValueError(f"invalid side for {execution_id}: {side}")
            shares = int(row.get("shares", 0) or 0)
            price = float(row.get("price", 0) or 0)
            if shares <= 0 or price <= 0 or not math.isfinite(price):
                raise ValueError(f"invalid fill quantity/price: {execution_id}")
            result.append(
                ActualFill(
                    trade_date=str(row.get("trade_date", ""))[:10],
                    settlement_date=str(row.get("settlement_date", ""))[:10],
                    execution_id=execution_id,
                    order_id=str(row.get("order_id", "")).strip(),
                    side=side,
                    ticker=str(row.get("ticker", "")).strip().upper(),
                    shares=shares,
                    price=price,
                    source_document=_require_source(
                        str(row.get("source_document", "")), execution_id
                    ),
                )
            )
    return sorted(result, key=lambda item: (item.settlement_date, item.execution_id))


def load_cash_events(path: Path | str) -> list[CashEvent]:
    source = Path(path)
    seen: set[str] = set()
    result: list[CashEvent] = []
    with source.open(newline="", encoding="utf-8") as file:
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
                    value_date=str(row.get("value_date", ""))[:10],
                    event_id=event_id,
                    kind=kind,
                    amount=amount,
                    source_document=_require_source(
                        str(row.get("source_document", "")), event_id
                    ),
                    ticker=str(row.get("ticker", "")).strip().upper(),
                )
            )
    return sorted(result, key=lambda item: (item.value_date, item.event_id))


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
            delta = int(row.get("share_delta", 0) or 0)
            if delta == 0:
                raise ValueError(f"zero share adjustment is not meaningful: {event_id}")
            result.append(
                PositionEvent(
                    value_date=str(row.get("value_date", ""))[:10],
                    event_id=event_id,
                    ticker=str(row.get("ticker", "")).strip().upper(),
                    share_delta=delta,
                    source_document=_require_source(
                        str(row.get("source_document", "")), event_id
                    ),
                )
            )
    return sorted(result, key=lambda item: (item.value_date, item.event_id))


def load_snapshot(path: Path | str) -> AccountSnapshot:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("account snapshot requires schema_version=1")
    positions = {
        str(ticker).strip().upper(): int(shares)
        for ticker, shares in dict(payload.get("positions") or {}).items()
    }
    if any(shares < 0 for shares in positions.values()):
        raise ValueError("snapshot cannot contain negative long-only share quantities")
    return AccountSnapshot(
        value_date=str(payload.get("value_date", ""))[:10],
        cash_balance=float(payload.get("cash_balance", 0) or 0),
        positions=positions,
        source_document=_require_source(
            str(payload.get("source_document", "")), "snapshot"
        ),
    )


def reconcile_actual_account(
    *,
    start_cash: float,
    fills: Iterable[ActualFill],
    cash_events: Iterable[CashEvent],
    position_events: Iterable[PositionEvent],
    snapshot: AccountSnapshot,
    cent_tolerance: float = 0.005,
) -> AccountReconciliation:
    if not math.isfinite(start_cash):
        raise ValueError("start_cash must be finite")
    cash = float(start_cash)
    positions: dict[str, int] = defaultdict(int)
    fill_list = list(fills)
    cash_list = list(cash_events)
    position_list = list(position_events)

    timeline: list[tuple[str, int, object]] = []
    timeline.extend((item.settlement_date, 0, item) for item in fill_list)
    timeline.extend((item.value_date, 1, item) for item in cash_list)
    timeline.extend((item.value_date, 2, item) for item in position_list)
    timeline.sort(key=lambda item: (item[0], item[1]))

    blockers: list[str] = []
    for value_date, _, item in timeline:
        if value_date and snapshot.value_date and value_date > snapshot.value_date:
            blockers.append("ledger_contains_event_after_snapshot")
            continue
        if isinstance(item, ActualFill):
            ticker = item.ticker
            if item.side == "BUY":
                cash -= item.notional
                positions[ticker] += item.shares
            else:
                if positions[ticker] < item.shares:
                    blockers.append(f"sell_exceeds_reconstructed_position:{item.execution_id}")
                positions[ticker] -= item.shares
                cash += item.notional
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
        ticker: shares for ticker, shares in sorted(snapshot.positions.items()) if shares != 0
    }
    all_tickers = sorted(set(reconstructed_positions) | set(snapshot_positions))
    position_differences = {
        ticker: reconstructed_positions.get(ticker, 0) - snapshot_positions.get(ticker, 0)
        for ticker in all_tickers
        if reconstructed_positions.get(ticker, 0) != snapshot_positions.get(ticker, 0)
    }
    cash_difference = cash - snapshot.cash_balance
    if abs(cash_difference) > cent_tolerance:
        blockers.append("cash_does_not_reconcile_to_cent")
    if position_differences:
        blockers.append("positions_do_not_reconcile_exactly")

    return AccountReconciliation(
        start_cash=start_cash,
        reconstructed_cash=cash,
        snapshot_cash=snapshot.cash_balance,
        cash_difference=cash_difference,
        reconstructed_positions=reconstructed_positions,
        snapshot_positions=snapshot_positions,
        position_differences=position_differences,
        fills=len(fill_list),
        cash_events=len(cash_list),
        position_events=len(position_list),
        exact=not blockers,
        blockers=tuple(sorted(set(blockers))),
    )
