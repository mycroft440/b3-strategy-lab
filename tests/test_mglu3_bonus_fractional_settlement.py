import math
from types import SimpleNamespace

from b3_strategy_lab.corporate_settlements import (
    DEFAULT_CORPORATE_SETTLEMENTS,
    apply_fractional_split,
    load_corporate_settlements,
    mark_and_pay_corporate_receivables,
)
from b3_strategy_lab.realistic import FeeRule, FeeSchedule, RealCashAccount, SlippageModel


BONUS_COST = 10.82550951208
AUCTION_PRICE = 9.1474173


def _account():
    result = RealCashAccount(
        0,
        FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 0)]),
        SlippageModel(),
    )
    result.positions["MGLU3"].shares = 122
    result.positions["MGLU3"].average_cost = 20
    return result


def _market():
    days = [
        "2025-12-29",
        "2025-12-30",
        "2026-03-05",
        "2026-03-18",
        "2026-03-25",
    ]
    candles = [
        SimpleNamespace(
            date=day,
            adjustment_factor=1.0 if i == 0 else 1.05,
            raw_close=10.0,
            isin="BRMGLUACNOR2",
        )
        for i, day in enumerate(days)
    ]
    return SimpleNamespace(
        dates=days,
        candles={"MGLU3": candles},
        by_date={"MGLU3": {c.date: c for c in candles}},
        index_by_date={"MGLU3": {day: i for i, day in enumerate(days)}},
    )


def test_repository_mglu3_bonus_fraction_rule_is_source_bound():
    rules = load_corporate_settlements(DEFAULT_CORPORATE_SETTLEMENTS)
    rule = rules[("2025-12-30", "MGLU3")]

    assert rule["quantity_event"] == "bonus"
    assert math.isclose(rule["share_ratio"], 1.05)
    assert math.isclose(rule["bonus_unit_cost"], BONUS_COST)
    assert math.isclose(rule["price_per_fractional_share"], AUCTION_PRICE)
    assert rule["realization_date"] == "2026-03-05"
    assert rule["price_known_date"] == "2026-03-18"
    assert rule["payment_date"] == "2026-03-25"


def test_mglu3_bonus_fraction_preserves_source_assigned_tax_basis_and_cash_timing():
    cash = _account()
    cash._corporate_settlement_rules = load_corporate_settlements(
        DEFAULT_CORPORATE_SETTLEMENTS
    )
    market = _market()

    apply_fractional_split(cash, market, "2025-12-30", lambda *_: None)

    assert cash.shares("MGLU3") == 128
    expected_retained_basis = 122 * 20 + 6 * BONUS_COST
    assert math.isclose(
        cash.positions["MGLU3"].average_cost,
        expected_retained_basis / 128,
        rel_tol=1e-12,
    )
    claim = cash._corporate_receivables[("2025-12-30", "MGLU3")]
    assert math.isclose(claim["units"], 0.1, abs_tol=1e-9)
    assert math.isclose(claim["basis"], 0.1 * BONUS_COST, rel_tol=1e-12)

    mark_and_pay_corporate_receivables(cash, market, "2026-03-05")
    assert claim["net"] is None
    assert cash.cash == 0

    mark_and_pay_corporate_receivables(cash, market, "2026-03-18")
    assert claim["net"] is not None
    assert cash.cash == 0
    assert math.isclose(
        cash.tax._gains["2026-03"],
        0.1 * (AUCTION_PRICE - BONUS_COST),
        rel_tol=1e-12,
        abs_tol=1e-12,
    )

    mark_and_pay_corporate_receivables(cash, market, "2026-03-25")
    assert cash.cash > 0
    assert cash._corporate_receivable_value == 0
    assert cash.corporate_action_ledger[-1]["credited_session"] == "2026-03-25"
