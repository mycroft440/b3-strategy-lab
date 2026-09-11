import hashlib
import json
from types import SimpleNamespace

import pytest

from b3_strategy_lab.corporate_settlements import (
    apply_cash_transition, apply_fractional_split, load_corporate_settlements,
    mark_and_pay_corporate_receivables,
)
from b3_strategy_lab.realistic import RealCashAccount, FeeSchedule, FeeRule, SlippageModel
from b3_strategy_lab.realistic_portfolio import _apply_split_from_adjustment_factors


def account():
    result = RealCashAccount(300, FeeSchedule([FeeRule("2000-01-01", "2099-12-31", 0)]), SlippageModel())
    result.cash = 0
    result.positions["AAA3"].shares = 3
    result.positions["AAA3"].average_cost = 100
    return result


def rule(tmp_path, kind="fractional_sale", price=220, price_known_date=None):
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("Synthetic reviewed event fixture", encoding="utf-8")
    event = dict(kind=kind, quantity_event="reverse_split", effective_date="2024-01-03", realization_date="2024-01-05",
                 payment_date="2024-01-08", announcement_date="2024-01-02",
                 ticker="AAA3", isin="BRAAAATEST00", share_ratio=0.5,
                 price_per_fractional_share=price, cash_per_old_share=10,
                 source_authority="issuer", source_url="https://example.org/event",
                 source_reference="Synthetic fixture page 1", reviewed_by="test",
                 source_document="evidence.txt", source_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest())
    if price_known_date is not None:
        event["price_known_date"] = price_known_date
    path = tmp_path / "events.json"
    path.write_text(json.dumps({"schema_version": 1, "events": [event]}), encoding="utf-8")
    return load_corporate_settlements(path)


def data():
    days = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"]
    candles = [SimpleNamespace(date=day, adjustment_factor=1 if i == 0 else 0.5,
                               raw_close=100 if i == 0 else 200, isin="BRAAAATEST00")
               for i, day in enumerate(days)]
    return SimpleNamespace(dates=days, candles={"AAA3": candles},
                           by_date={"AAA3": {c.date: c for c in candles}},
                           index_by_date={"AAA3": {day: i for i, day in enumerate(days)}})


def test_fractional_right_is_not_tradable_and_cash_waits_for_payment(tmp_path):
    cash = account()
    cash._corporate_settlement_rules = rule(tmp_path)
    market = data()
    _apply_split_from_adjustment_factors(cash, market, "2024-01-03")
    mark_and_pay_corporate_receivables(cash, market, "2024-01-03")
    assert cash.shares("AAA3") == 1
    assert cash.positions["AAA3"].average_cost == 200
    assert cash._corporate_receivable_value == 100
    assert cash.cash == 0
    mark_and_pay_corporate_receivables(cash, market, "2024-01-05")
    assert cash._corporate_receivable_value == 110
    assert cash.cash == 0
    assert cash.tax._gains["2024-01"] == 10
    mark_and_pay_corporate_receivables(cash, market, "2024-01-08")
    assert cash.cash == 110
    assert cash._corporate_receivable_value == 0
    assert cash.corporate_action_ledger[0]["credited_session"] == "2024-01-08"
    mark_and_pay_corporate_receivables(cash, market, "2024-01-08")
    assert cash.cash == 110


def test_future_auction_price_cannot_change_prior_equity(tmp_path):
    for price in (220, 400):
        cash = account()
        cash._corporate_settlement_rules = rule(tmp_path, price=price)
        market = data()
        _apply_split_from_adjustment_factors(cash, market, "2024-01-03")
        mark_and_pay_corporate_receivables(cash, market, "2024-01-03")
        assert cash.cash + cash.shares("AAA3") * 200 + cash._corporate_receivable_value == 300


def test_published_auction_price_is_not_used_before_price_known_date(tmp_path):
    cash = account()
    cash._corporate_settlement_rules = rule(tmp_path, price=400, price_known_date="2024-01-08")
    market = data()
    _apply_split_from_adjustment_factors(cash, market, "2024-01-03")

    mark_and_pay_corporate_receivables(cash, market, "2024-01-05")
    claim = cash._corporate_receivables[("2024-01-03", "AAA3")]
    assert claim["net"] is None
    assert cash._corporate_receivable_value == 100
    assert "2024-01" not in cash.tax._gains

    mark_and_pay_corporate_receivables(cash, market, "2024-01-08")
    assert cash.cash == 200
    assert cash._corporate_receivable_value == 0
    assert cash.tax._gains["2024-01"] == 100
    assert cash.corporate_action_ledger[0]["realization_date"] == "2024-01-05"
    assert cash.corporate_action_ledger[0]["price_known_date"] == "2024-01-08"


def test_capital_return_preserves_economic_value_and_defers_cash(tmp_path):
    cash = account()
    cash.positions["AAA3"].shares = 4
    cash._corporate_settlement_rules = rule(tmp_path, kind="return_of_capital")
    event = SimpleNamespace(effective_date="2024-01-03", old_ticker="AAA3", new_ticker="BBB3",
                            old_isin="BRAAAATEST00", share_ratio=0.5, cash_per_old_share=10,
                            certification_status="certified")
    assert apply_cash_transition(cash, event)
    assert cash.shares("AAA3") == 0
    assert cash.shares("BBB3") == 2
    assert cash.positions["BBB3"].average_cost == 180
    mark_and_pay_corporate_receivables(cash, data(), "2024-01-03")
    assert cash.cash == 0 and cash._corporate_receivable_value == 40
    mark_and_pay_corporate_receivables(cash, data(), "2024-01-08")
    assert cash.cash == 40


def test_modified_document_is_rejected(tmp_path):
    rule(tmp_path)
    (tmp_path / "evidence.txt").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="Unverified"):
        load_corporate_settlements(tmp_path / "events.json")
