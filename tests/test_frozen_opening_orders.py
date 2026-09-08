from types import SimpleNamespace

import pytest

from b3_strategy_lab.realistic import ExecutionPriceBook, ExecutionQuote, FeeRule, FeeSchedule, RealCashAccount, SlippageModel
from b3_strategy_lab.realistic_portfolio import _adjust_pending_quantities, rebalance_atomic


PRIOR = "2025-01-02"
CURRENT = "2025-01-03"


def account(cash=950.0):
    return RealCashAccount(cash, FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 0.0)]),
                           SlippageModel(base_bps=0.0, participation_bps_at_1pct=0.0, max_bps=0.0))


def book(opening=10.0, prior_volume=100_000_000.0, current_volume=100_000_000.0):
    return ExecutionPriceBook([
        ExecutionQuote(day, "AAA3", market, price, price, volume)
        for day, price, volume in ((PRIOR, 10.0, prior_volume), (CURRENT, opening, current_volume))
        for market in ("010", "020")
    ])


def test_cheaper_open_never_increases_the_frozen_order():
    result = rebalance_atomic(account(), None, book(opening=5), CURRENT, {"AAA3": 1.0})
    assert result.shares("AAA3") == 95
    assert result.cash == 475
    assert result.order_ledger[0]["requested_shares"] == 95
    assert result.order_ledger[0]["decision_date"] == PRIOR


def test_expensive_open_can_only_reduce_the_fill_and_keeps_cash_nonnegative():
    result = rebalance_atomic(account(), None, book(opening=20), CURRENT, {"AAA3": 1.0})
    assert result.shares("AAA3") == 47
    assert result.cash == 10
    row = result.order_ledger[0]
    assert (row["requested_shares"], row["filled_shares"], row["status"], row["reason"]) == (95, 47, "PARTIAL", "cash")


def test_capacity_is_default_causal_and_unfilled_orders_expire():
    one = rebalance_atomic(account(10_000), None, book(prior_volume=100_000, current_volume=1e12), CURRENT, {"AAA3": 1.0})
    two = rebalance_atomic(account(10_000), None, book(prior_volume=100_000, current_volume=1), CURRENT, {"AAA3": 1.0})
    assert one.shares("AAA3") == two.shares("AAA3") == 100
    assert one.cash == two.cash == 9000
    assert one.order_ledger[0]["requested_shares"] == 1000
    assert one.order_ledger[0]["status"] == "PARTIAL"
    assert one.order_ledger[0]["reason"] == "capacity"


def test_standard_partial_fill_does_not_invent_a_fractional_order():
    result = rebalance_atomic(account(1000), None, book(opening=20), CURRENT, {"AAA3": 1.0})
    assert result.shares("AAA3") == 0
    assert result.order_ledger[0]["market_type"] == "010"
    assert result.order_ledger[0]["status"] == "CANCELLED"


def test_missing_fractional_quote_cancels_without_standard_substitution():
    prices = book()
    del prices._quotes[(CURRENT, "AAA3", "020")]
    result = rebalance_atomic(account(), None, prices, CURRENT, {"AAA3": 1.0})
    assert result.shares("AAA3") == 0
    assert result.order_ledger[0]["reason"] == "unavailable_execution_reference"


def test_prior_liquidity_is_required_even_for_directly_constructed_book():
    prices = ExecutionPriceBook([ExecutionQuote(CURRENT, "AAA3", "020", 10, 10, 1e12)])
    result = rebalance_atomic(account(), None, prices, CURRENT, {"AAA3": 1.0},
                              frozen_quantities={"AAA3": 95}, decision_date=PRIOR)
    assert result.shares("AAA3") == 0
    assert result.order_ledger[0]["status"] == "CANCELLED"


def test_pending_quantity_tracks_split_and_conversion_without_open_resizing():
    data = SimpleNamespace(index_by_date={"AAA3": {CURRENT: 1}},
                           candles={"AAA3": [SimpleNamespace(adjustment_factor=1), SimpleNamespace(adjustment_factor=2)]})
    event = SimpleNamespace(old_ticker="AAA3", new_ticker="BBB3", share_ratio=0.5)
    assert _adjust_pending_quantities({"AAA3": 95}, data, CURRENT, []) == {"AAA3": 190}
    assert _adjust_pending_quantities({"AAA3": 95}, data, CURRENT, [event]) == {"BBB3": 95}


def test_no_prior_decision_cannot_fall_back_to_current_open():
    prices = ExecutionPriceBook([ExecutionQuote(CURRENT, "AAA3", "020", 10, 10, 1e12)])
    with pytest.raises(ValueError, match="prior decision session"):
        rebalance_atomic(account(), None, prices, CURRENT, {"AAA3": 1.0})


def test_frozen_quantity_reserves_fees_before_choosing_the_market_leg():
    cash = RealCashAccount(1000, FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 3.2)]), SlippageModel())
    result = rebalance_atomic(cash, None, book(), CURRENT, {"AAA3": 1.0})
    assert 0 < result.shares("AAA3") < 100
    assert result.order_ledger[0]["market_type"] == "020"
    assert result.cash > 0
