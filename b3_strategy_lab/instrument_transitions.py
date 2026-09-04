from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path


SUPPORTED_EVENT_TYPES = frozenset(
    {
        "ticker_change",
        "class_change",
        "merger",
        "incorporation",
        "spin_off",
        "going_private",
        "registration_cancelled",
        "liquidation",
        "reorganization",
        "economic_termination",
    }
)
SUPPORTED_FRACTIONAL_TREATMENTS = frozenset(
    {"preserve_units", "require_integer", "cash_in_lieu", "not_applicable"}
)
SUPPORTED_TAX_BASIS_TREATMENTS = frozenset(
    {"carry_total_basis", "source_specific", "terminal_unresolved", "terminal_worthless"}
)
SUPPORTED_CERTIFICATION_STATUSES = frozenset({"certified", "unresolved", "modeled"})


def _iso(value: str, label: str) -> str:
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO date") from exc


@dataclass(frozen=True)
class InstrumentTransition:
    """Source-bound economic continuity between exchange instruments.

    The first five fields intentionally match the legacy TickerTransition positional
    contract. New metadata describes the instrument itself rather than pretending a
    quotation-factor change is a split. `share_ratio` is the economic quantity
    conversion: quotation-factor changes are stored separately and never multiplied
    into position quantity.
    """

    effective_date: str
    old_ticker: str
    new_ticker: str
    share_ratio: float = 1.0
    cash_per_old_share: float = 0.0
    old_isin: str = ""
    new_isin: str = ""
    old_quotation_factor: int = 1
    new_quotation_factor: int = 1
    cutoff_date: str = ""
    first_successor_trade_date: str = ""
    event_type: str = "ticker_change"
    fractional_treatment: str = "require_integer"
    tax_basis_treatment: str = "carry_total_basis"
    source_authority: str = ""
    source_url: str = ""
    source_reference: str = ""
    certification_status: str = "unresolved"

    def __post_init__(self) -> None:
        object.__setattr__(self, "effective_date", _iso(self.effective_date, "effective_date"))
        object.__setattr__(self, "old_ticker", self.old_ticker.strip().upper())
        object.__setattr__(self, "new_ticker", self.new_ticker.strip().upper())
        object.__setattr__(self, "old_isin", self.old_isin.strip().upper())
        object.__setattr__(self, "new_isin", self.new_isin.strip().upper())
        object.__setattr__(self, "event_type", self.event_type.strip().lower())
        object.__setattr__(self, "fractional_treatment", self.fractional_treatment.strip().lower())
        object.__setattr__(self, "tax_basis_treatment", self.tax_basis_treatment.strip().lower())
        object.__setattr__(self, "source_authority", self.source_authority.strip())
        object.__setattr__(self, "source_url", self.source_url.strip())
        object.__setattr__(self, "source_reference", self.source_reference.strip())
        object.__setattr__(self, "certification_status", self.certification_status.strip().lower())
        if self.cutoff_date:
            object.__setattr__(self, "cutoff_date", _iso(self.cutoff_date, "cutoff_date"))
        if self.first_successor_trade_date:
            object.__setattr__(
                self,
                "first_successor_trade_date",
                _iso(self.first_successor_trade_date, "first_successor_trade_date"),
            )
        if not self.old_ticker:
            raise ValueError("old_ticker is required")
        if not math.isfinite(self.share_ratio) or self.share_ratio <= 0:
            raise ValueError("share_ratio must be finite and positive")
        if not math.isfinite(self.cash_per_old_share) or self.cash_per_old_share < 0:
            raise ValueError("cash_per_old_share must be finite and non-negative")
        if self.old_quotation_factor <= 0 or self.new_quotation_factor <= 0:
            raise ValueError("quotation factors must be positive")
        if self.event_type not in SUPPORTED_EVENT_TYPES:
            raise ValueError(f"unsupported instrument event_type: {self.event_type}")
        if self.fractional_treatment not in SUPPORTED_FRACTIONAL_TREATMENTS:
            raise ValueError(
                f"unsupported fractional_treatment: {self.fractional_treatment}"
            )
        if self.tax_basis_treatment not in SUPPORTED_TAX_BASIS_TREATMENTS:
            raise ValueError(
                f"unsupported tax_basis_treatment: {self.tax_basis_treatment}"
            )
        if self.certification_status not in SUPPORTED_CERTIFICATION_STATUSES:
            raise ValueError(
                f"unsupported certification_status: {self.certification_status}"
            )
        if self.new_ticker and not self.first_successor_trade_date:
            object.__setattr__(self, "first_successor_trade_date", self.effective_date)
        if self.certification_status == "certified":
            if not self.source_authority or not self.source_url.startswith("https://"):
                raise ValueError(
                    "certified instrument transitions require source_authority and https source_url"
                )
            if not self.source_reference:
                raise ValueError("certified instrument transitions require source_reference")

    @property
    def changes_isin(self) -> bool:
        return bool(self.old_isin and self.new_isin and self.old_isin != self.new_isin)

    @property
    def is_terminal(self) -> bool:
        return not self.new_ticker

    @property
    def quotation_factor_ratio(self) -> float:
        return self.new_quotation_factor / self.old_quotation_factor


# Backward-compatible public name used throughout the existing realistic engine.
TickerTransition = InstrumentTransition


def _float(row: dict[str, str], key: str, default: float) -> float:
    value = str(row.get(key, "")).strip()
    return default if not value else float(value)


def _int(row: dict[str, str], key: str, default: int) -> int:
    value = str(row.get(key, "")).strip()
    return default if not value else int(value)


def instrument_transition_from_row(row: dict[str, str]) -> InstrumentTransition:
    """Load both legacy five-column rows and the extended transition schema."""

    return InstrumentTransition(
        effective_date=str(row["effective_date"])[:10],
        old_ticker=str(row["old_ticker"]),
        new_ticker=str(row.get("new_ticker", "")),
        share_ratio=_float(row, "share_ratio", 1.0),
        cash_per_old_share=_float(row, "cash_per_old_share", 0.0),
        old_isin=str(row.get("old_isin", "")),
        new_isin=str(row.get("new_isin", "")),
        old_quotation_factor=_int(row, "old_quotation_factor", 1),
        new_quotation_factor=_int(row, "new_quotation_factor", 1),
        cutoff_date=str(row.get("cutoff_date", "")),
        first_successor_trade_date=str(row.get("first_successor_trade_date", "")),
        event_type=str(row.get("event_type", "ticker_change") or "ticker_change"),
        fractional_treatment=str(
            row.get("fractional_treatment", "require_integer") or "require_integer"
        ),
        tax_basis_treatment=str(
            row.get("tax_basis_treatment", "carry_total_basis") or "carry_total_basis"
        ),
        source_authority=str(row.get("source_authority", "")),
        source_url=str(row.get("source_url", row.get("source", ""))),
        source_reference=str(row.get("source_reference", row.get("reference", ""))),
        certification_status=str(
            row.get("certification_status", "unresolved") or "unresolved"
        ),
    )


def load_instrument_transitions(path: Path | str) -> dict[str, list[InstrumentTransition]]:
    source = Path(path)
    if not source.exists():
        return {}
    result: dict[str, list[InstrumentTransition]] = {}
    with source.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            item = instrument_transition_from_row(row)
            result.setdefault(item.effective_date, []).append(item)
    for value in result.values():
        value.sort(key=lambda item: (item.old_ticker, item.new_ticker, item.event_type))
    return result
