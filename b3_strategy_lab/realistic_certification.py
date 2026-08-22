from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Iterable


def sha256_file(path: Path | str) -> str:
    source = Path(path)
    digest = hashlib.sha256()
    with source.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def transition_binding_issues(
    transition_csv: Path | str,
    manifest_path: Path | str,
    *,
    expected_end: str | None = None,
) -> list[str]:
    """Verify that the transition manifest is cryptographically bound to its CSV."""

    csv_path = Path(transition_csv)
    manifest_file = Path(manifest_path)
    issues: list[str] = []
    if not csv_path.exists():
        return [f"ticker_transition_csv_missing:{csv_path}"]
    if not manifest_file.exists():
        return [f"ticker_transition_manifest_missing:{manifest_file}"]

    try:
        payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"ticker_transition_manifest_invalid:{error}"]

    actual_hash = sha256_file(csv_path)
    expected_hash = str(payload.get("transition_csv_sha256", "")).strip().lower()
    if not expected_hash:
        issues.append("ticker_transition_manifest_missing_csv_sha256")
    elif expected_hash != actual_hash:
        issues.append("ticker_transition_csv_sha256_mismatch")

    try:
        with csv_path.open(newline="", encoding="utf-8") as file:
            actual_rows = sum(1 for _ in csv.DictReader(file))
    except OSError as error:
        issues.append(f"ticker_transition_csv_unreadable:{error}")
        actual_rows = -1
    try:
        declared_rows = int(payload.get("transition_row_count", -1))
    except (TypeError, ValueError):
        declared_rows = -1
    if declared_rows != actual_rows:
        issues.append("ticker_transition_row_count_mismatch")

    declared_file = str(payload.get("transition_file", "")).strip()
    if declared_file:
        if Path(declared_file).resolve() != csv_path.resolve():
            issues.append("ticker_transition_manifest_file_path_mismatch")

    if expected_end:
        coverage_end = str(payload.get("coverage_end", ""))[:10]
        if not coverage_end or coverage_end < expected_end:
            issues.append("ticker_transition_manifest_does_not_cover_replay_end")

    if payload.get("complete") is not True:
        issues.append("ticker_transition_manifest_is_incomplete")
    return sorted(set(issues))


def _row_value(row: object, name: str, default: object = "") -> object:
    if isinstance(row, dict):
        return row.get(name, default)
    return getattr(row, name, default)


def _transition_rows(path: Path | str | None) -> list[dict[str, str]]:
    if path is None:
        return []
    source = Path(path)
    if not source.exists():
        return []
    with source.open(newline="", encoding="utf-8") as file:
        return [dict(row) for row in csv.DictReader(file)]


def bonus_tax_basis_dependencies(
    split_evidence_path: Path | str,
    trade_rows: Iterable[object],
    *,
    start: str,
    end: str,
    transition_csv_path: Path | str | None = None,
) -> list[dict[str, object]]:
    """Find realized sales that may depend on an unsupported stock-bonus tax basis.

    Receita Federal distinguishes bonificacoes from ordinary stock splits for cost
    basis. The current engine changes quantity for a bonus but does not yet add the
    issuer-specific capitalized-profit/reserve amount to acquisition cost. Therefore
    *no* stock-bonus event is considered tax-basis-supported yet, even if a future
    evidence file contains a candidate cost field. Certification stays fail-closed until
    the account engine actually consumes and tests that basis.

    Risk is propagated through source-backed 1:1 ticker transitions so a later sale of
    a renamed symbol cannot escape the gate.
    """

    source = Path(split_evidence_path)
    if not source.exists():
        return [
            {
                "reason": "split_evidence_missing",
                "split_evidence": str(source),
            }
        ]
    payload = json.loads(source.read_text(encoding="utf-8"))
    bonuses: list[dict[str, object]] = []
    for event in payload.get("events") or []:
        label = str(event.get("event", "")).strip().upper()
        ex_date = str(event.get("ex_date", ""))[:10]
        ticker = str(event.get("ticker", "")).strip().upper()
        if "BONIFICACAO" not in label or not ticker or not ex_date:
            continue
        if ex_date > end:
            continue
        bonuses.append(
            {
                "ticker": ticker,
                "ex_date": ex_date,
                "event": label,
                "affected_tickers": {ticker},
            }
        )

    if not bonuses:
        return []

    transitions = sorted(
        _transition_rows(transition_csv_path),
        key=lambda row: str(row.get("effective_date", "")),
    )
    for bonus in bonuses:
        affected = bonus["affected_tickers"]
        assert isinstance(affected, set)
        for transition in transitions:
            effective = str(transition.get("effective_date", ""))[:10]
            if not effective or effective < str(bonus["ex_date"]) or effective > end:
                continue
            old = str(transition.get("old_ticker", "")).strip().upper()
            new = str(transition.get("new_ticker", "")).strip().upper()
            if old in affected and new:
                affected.add(new)

    dependencies: list[dict[str, object]] = []
    for row in trade_rows:
        if str(_row_value(row, "side", "")).upper() != "SELL":
            continue
        ticker = str(_row_value(row, "ticker", "")).strip().upper()
        sale_date = str(_row_value(row, "date", ""))[:10]
        if not ticker or not sale_date or sale_date < start or sale_date > end:
            continue
        for bonus in bonuses:
            affected = bonus["affected_tickers"]
            assert isinstance(affected, set)
            if ticker in affected and sale_date >= str(bonus["ex_date"]):
                dependencies.append(
                    {
                        "ticker": ticker,
                        "original_bonus_ticker": bonus["ticker"],
                        "bonus_ex_date": bonus["ex_date"],
                        "sale_date": sale_date,
                        "event": bonus["event"],
                        "reason": "stock_bonus_tax_basis_not_applied_by_engine",
                    }
                )
    unique = {
        (
            item["ticker"],
            item["original_bonus_ticker"],
            item["bonus_ex_date"],
            item["sale_date"],
            item["event"],
        ): item
        for item in dependencies
    }
    return [unique[key] for key in sorted(unique)]


def terminal_month_tax_policy(end: str) -> dict[str, object]:
    """Describe the terminal-month assumption without pretending the month is complete."""

    return {
        "terminal_tax_month": end[:7],
        "terminal_tax_finalized_through": end[:10],
        "terminal_month_full_calendar_activity_known": False,
        "terminal_month_assumption": (
            "Tax is provisionally finalized using only strategy sales/gains observed through "
            "the replay end. If the replay ends before the actual end of that calendar month, "
            "the reported terminal liability assumes no additional strategy trades occur later "
            "in the same month; subsequent real-world trades could change exemption, loss carry, "
            "IRRF credits and DARF due."
        ),
    }
