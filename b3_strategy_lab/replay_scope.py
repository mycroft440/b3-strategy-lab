from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


SMALL_ACCOUNT_EXACT_LIMIT = 20_000.0


def audit_small_account_replay(
    curve_path: Path | str,
    trades_path: Path | str,
    *,
    limit: float = SMALL_ACCOUNT_EXACT_LIMIT,
) -> dict[str, object]:
    """Fail closed when the replay leaves the small-account exactness envelope.

    The existing tax engine intentionally models the economic tax burden rather
    than every IRRF/DARF cash-timing detail. For a strict deterministic replay we
    therefore require a conservative envelope: close equity and aggregate daily
    stock sales must remain at or below R$20,000. This also keeps a retail replay
    far below the B3 high-ADTV transaction-fee tiers.
    """

    if limit <= 0:
        raise ValueError("limit must be positive")
    curve_source = Path(curve_path)
    trades_source = Path(trades_path)
    if not curve_source.exists():
        raise FileNotFoundError(curve_source)
    if not trades_source.exists():
        raise FileNotFoundError(trades_source)

    max_equity = 0.0
    max_equity_date = ""
    with curve_source.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    if not rows:
        raise ValueError("replay curve is empty")
    for row in rows:
        equity = float(row.get("equity", 0.0) or 0.0)
        if equity < 0:
            raise ValueError("replay curve contains negative equity")
        if equity > max_equity:
            max_equity = equity
            max_equity_date = str(row.get("date", ""))

    sales_by_day: dict[str, float] = defaultdict(float)
    with trades_source.open(newline="", encoding="utf-8") as file:
        trade_rows = list(csv.DictReader(file))
    for row in trade_rows:
        if str(row.get("side", "")).upper() != "SELL":
            continue
        value_date = str(row.get("date", ""))[:10]
        sales_by_day[value_date] += float(row.get("notional", 0.0) or 0.0)
    max_daily_sales_date = max(sales_by_day, key=sales_by_day.get) if sales_by_day else ""
    max_daily_sales = sales_by_day.get(max_daily_sales_date, 0.0)

    blockers: list[str] = []
    if max_equity > limit + 1e-9:
        blockers.append("portfolio_exceeds_small_account_exact_tax_custody_scope")
    if max_daily_sales > limit + 1e-9:
        blockers.append("daily_sales_exceed_small_account_irrf_safe_scope")

    return {
        "scope_limit": limit,
        "max_equity": max_equity,
        "max_equity_date": max_equity_date,
        "max_daily_sales": max_daily_sales,
        "max_daily_sales_date": max_daily_sales_date,
        "small_account_scope_passed": not blockers,
        "blockers": blockers,
        "interpretation": (
            "Passing this guard means the deterministic replay stayed inside the "
            "conservative R$20,000 small-account envelope used by the strict runner. "
            "It does not turn a counterfactual strategy replay into proof of actual "
            "broker fills or of the user's complete personal tax history."
        ),
    }
