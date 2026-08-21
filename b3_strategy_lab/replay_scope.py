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
    """Fail closed when a certified replay leaves the small-account envelope.

    The realistic engine now models ordinary-operation IRRF credits and dated
    DARF liabilities. The stricter certified deterministic replay nevertheless
    keeps a conservative R$20,000 envelope. If aggregate stock sales remain at
    or below that threshold, positive ordinary stock gains stay inside the
    monthly cash-market exemption and the theoretical 0.005% source withholding
    remains at or below R$1, avoiding reliance on DARF timing for certification.

    This is an isolated brokerage-replay scope. It does not and cannot prove the
    person's CPF-wide annual income, including the separate 2026+ minimum tax for
    high-income individuals.
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
    sales_by_month: dict[str, float] = defaultdict(float)
    with trades_source.open(newline="", encoding="utf-8") as file:
        trade_rows = list(csv.DictReader(file))
    for row in trade_rows:
        if str(row.get("side", "")).upper() != "SELL":
            continue
        value_date = str(row.get("date", ""))[:10]
        notional = float(row.get("notional", 0.0) or 0.0)
        if notional < 0:
            raise ValueError("replay trade ledger contains negative sell notional")
        sales_by_day[value_date] += notional
        sales_by_month[value_date[:7]] += notional

    max_daily_sales_date = max(sales_by_day, key=sales_by_day.get) if sales_by_day else ""
    max_daily_sales = sales_by_day.get(max_daily_sales_date, 0.0)
    max_monthly_sales_month = max(sales_by_month, key=sales_by_month.get) if sales_by_month else ""
    max_monthly_sales = sales_by_month.get(max_monthly_sales_month, 0.0)

    blockers: list[str] = []
    if max_equity > limit + 1e-9:
        blockers.append("portfolio_exceeds_small_account_exact_tax_custody_scope")
    if max_daily_sales > limit + 1e-9:
        blockers.append("single_day_sales_exceed_irrf_safe_scope")
    if max_monthly_sales > limit + 1e-9:
        blockers.append("monthly_sales_exceed_stock_gain_exemption_scope")

    return {
        "scope_limit": limit,
        "max_equity": max_equity,
        "max_equity_date": max_equity_date,
        "max_daily_sales": max_daily_sales,
        "max_daily_sales_date": max_daily_sales_date,
        "max_monthly_sales": max_monthly_sales,
        "max_monthly_sales_month": max_monthly_sales_month,
        "small_account_scope_passed": not blockers,
        "ordinary_stock_monthly_exemption_guard": True,
        "ordinary_irrf_retention_guard": "monthly sales <= R$20,000 implies 0.005% <= R$1",
        "cpf_wide_annual_minimum_tax_scope": "OUT_OF_SCOPE",
        "blockers": blockers,
        "interpretation": (
            "Passing this guard means the deterministic replay stayed inside the "
            "conservative R$20,000 brokerage envelope: close equity, any single day's "
            "sales and aggregate stock sales in each month all remain at or below the "
            "limit. It does not turn a counterfactual strategy replay into proof of "
            "actual broker fills, and it does not prove the person's complete CPF-wide "
            "tax position or the 2026+ annual minimum high-income tax."
        ),
    }
