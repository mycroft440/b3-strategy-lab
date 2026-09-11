from __future__ import annotations

import math
from types import SimpleNamespace

from b3_strategy_lab.corporate_settlements import (
    DEFAULT_CORPORATE_SETTLEMENTS,
    default_corporate_settlement_rules,
    load_corporate_settlements,
)
from b3_strategy_lab.realistic import FeeRule, FeeSchedule, RealCashAccount, SlippageModel
from b3_strategy_lab.realistic_portfolio import _apply_split_from_adjustment_factors


def _account() -> RealCashAccount:
    account = RealCashAccount(
        10_000,
        FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 0)]),
        SlippageModel(),
    )
    account.positions["HAPV3"].shares = 337
    account.positions["HAPV3"].average_cost = 2.0
    return account


def _data():
    candles = [
        SimpleNamespace(
            date="2025-06-05",
            adjustment_factor=1.0,
            raw_close=2.50,
            isin="BRHAPVACNOR4",
        ),
        SimpleNamespace(
            date="2025-06-06",
            adjustment_factor=1.0 / 15.0,
            raw_close=37.50,
            isin="BRHAPVACNOR4",
        ),
    ]
    return SimpleNamespace(
        dates=[item.date for item in candles],
        candles={"HAPV3": candles},
        by_date={"HAPV3": {item.date: item for item in candles}},
        index_by_date={"HAPV3": {item.date: index for index, item in enumerate(candles)}},
    )


def test_hapv3_source_bound_fractional_settlement_is_repository_default():
    rules = load_corporate_settlements(DEFAULT_CORPORATE_SETTLEMENTS)
    rule = rules[("2025-06-06", "HAPV3")]
    assert rule["kind"] == "fractional_sale"
    assert rule["quantity_event"] == "reverse_split"
    assert rule["isin"] == "BRHAPVACNOR4"
    assert math.isclose(float(rule["share_ratio"]), 1.0 / 15.0)
    assert math.isclose(float(rule["price_per_fractional_share"]), 36.87159881563)
    assert rule["realization_date"] == "2025-06-30"
    assert rule["price_known_date"] == "2025-07-04"
    assert rule["payment_date"] == "2025-07-11"
    assert default_corporate_settlement_rules()[("2025-06-06", "HAPV3")] == rule

    account = _account()
    market = _data()
    _apply_split_from_adjustment_factors(account, market, "2025-06-06")

    assert account.shares("HAPV3") == 22
    claim = account._corporate_receivables[("2025-06-06", "HAPV3")]
    assert math.isclose(claim["units"], 7.0 / 15.0, abs_tol=1e-12)
    assert claim["net"] is None
