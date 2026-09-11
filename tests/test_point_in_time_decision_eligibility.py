from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

from b3_strategy_lab.point_in_time import snapshot_rows


def _sessions(start: date, count: int) -> list[str]:
    result: list[str] = []
    current = start
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current.isoformat())
        current += timedelta(days=1)
    return result


def _quote(day: str, ticker: str, volume: float, issuer: str):
    return SimpleNamespace(
        date=day,
        ticker=ticker,
        specification="ON",
        issuer_name=issuer,
        financial_volume=volume,
    )


def test_snapshot_requires_quote_on_decision_session():
    sessions = _sessions(date(2026, 1, 5), 20)
    quotes = []
    for day in sessions:
        quotes.append(_quote(day, "LIVE3", 100.0, "LIVE SA"))
    for day in sessions[:-1]:
        # STAL3 dominates trailing liquidity and satisfies 95% presence, but it has
        # already stopped trading by the final decision session and must not remain
        # selectable merely because its historical window is strong.
        quotes.append(_quote(day, "STAL3", 10_000.0, "STALE SA"))

    rows = snapshot_rows(
        quotes,
        start=sessions[0],
        end=sessions[-1],
        lookback_sessions=20,
        top_n=1,
        minimum_presence=0.90,
    )
    final = [row for row in rows if row["effective_date"] == sessions[-1]]
    assert [row["ticker"] for row in final] == ["LIVE3"]
