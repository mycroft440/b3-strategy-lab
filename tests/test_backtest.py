from __future__ import annotations

import unittest

from b3_strategy_lab.backtest import (
    _action_buckets,
    run_strategy_vs_buy_hold,
    simulate_buy_and_hold,
    simulate_buy_and_hold_price_only,
    simulate_buy_and_hold_raw_events,
    simulate_single_asset,
)
from b3_strategy_lab.candles import Candle, CorporateAction


def candle(day: str, open_: float, close: float) -> Candle:
    return Candle(
        date=day,
        ticker="TEST3",
        source_symbol="TEST3.SA",
        open=open_,
        high=max(open_, close),
        low=min(open_, close),
        close=close,
        adj_close=close,
        volume=1000,
        raw_open=open_,
        raw_high=max(open_, close),
        raw_low=min(open_, close),
        raw_close=close,
        adjustment_factor=1.0,
    )


class BacktestTests(unittest.TestCase):
    def test_strategy_signal_trades_on_next_open(self) -> None:
        candles = [
            candle("2024-01-02", 100.0, 200.0),
            candle("2024-01-03", 300.0, 300.0),
        ]
        curve = simulate_single_asset(candles, [1, 1], initial_cash=900.0)

        self.assertEqual(curve[0].position, 0)
        self.assertEqual(curve[1].trade, "BUY")
        self.assertAlmostEqual(curve[1].shares, 3.0)
        self.assertAlmostEqual(curve[1].equity, 900.0)

    def test_buy_and_hold_enters_on_first_open(self) -> None:
        candles = [
            candle("2024-01-02", 100.0, 110.0),
            candle("2024-01-03", 120.0, 130.0),
        ]
        curve = simulate_buy_and_hold(candles, initial_cash=1000.0)

        self.assertEqual(curve[0].trade, "BUY")
        self.assertAlmostEqual(curve[0].shares, 10.0)
        self.assertAlmostEqual(curve[-1].equity, 1300.0)

    def test_price_only_ignores_dividend_actions_completely(self) -> None:
        candles = [
            candle("2024-01-02", 100.0, 100.0),
            candle("2024-01-03", 90.0, 90.0),
        ]
        actions = [
            CorporateAction(
                "2024-01-03",
                "TEST3",
                "TEST3.SA",
                dividend=2.0,
                split_ratio=1.0,
            )
        ]

        _summary, strategy_curve, benchmark_curve = run_strategy_vs_buy_hold(
            "TEST3",
            "buy_and_hold",
            candles,
            [1, 1],
            initial_cash=1000.0,
            actions=actions,
        )

        self.assertEqual(strategy_curve, benchmark_curve)
        self.assertAlmostEqual(benchmark_curve[-1].dividend_cash, 0.0)
        self.assertAlmostEqual(benchmark_curve[-1].cash, 0.0)
        self.assertAlmostEqual(benchmark_curve[-1].equity, 900.0)

    def test_price_only_buy_and_hold_uses_raw_ohlc(self) -> None:
        candles = [
            candle("2024-01-02", 100.0, 110.0),
            candle("2024-01-03", 120.0, 130.0),
        ]
        curve = simulate_buy_and_hold_price_only(candles, initial_cash=1000.0)

        self.assertAlmostEqual(curve[-1].equity, 1300.0)
        self.assertTrue(all(point.dividend_cash == 0.0 for point in curve))

    def test_slippage_worsens_buy_execution_price(self) -> None:
        candles = [
            candle("2024-01-02", 100.0, 100.0),
            candle("2024-01-03", 100.0, 100.0),
        ]
        curve = simulate_single_asset(candles, [1, 1], initial_cash=1010.0, slippage_bps=100)

        self.assertEqual(curve[1].trade, "BUY")
        self.assertAlmostEqual(curve[1].trade_price, 101.0)
        self.assertAlmostEqual(curve[1].shares, 10.0)
        self.assertAlmostEqual(curve[1].equity, 1000.0)

    def test_lot_size_keeps_uninvested_cash(self) -> None:
        candles = [
            candle("2024-01-02", 100.0, 100.0),
            candle("2024-01-03", 100.0, 100.0),
        ]
        curve = simulate_buy_and_hold(candles, initial_cash=1050.0, lot_size=10)

        self.assertAlmostEqual(curve[0].shares, 10.0)
        self.assertAlmostEqual(curve[0].cash, 50.0)
        self.assertAlmostEqual(curve[-1].equity, 1050.0)

    def test_raw_events_adds_dividend_cash(self) -> None:
        candles = [
            candle("2024-01-02", 100.0, 100.0),
            candle("2024-01-03", 90.0, 90.0),
        ]
        actions = {
            "2024-01-03": CorporateAction("2024-01-03", "TEST3", "TEST3.SA", dividend=2.0, split_ratio=1.0)
        }
        curve = simulate_buy_and_hold_raw_events(candles, actions, initial_cash=1000.0)

        self.assertAlmostEqual(curve[1].dividend_cash, 20.0)
        self.assertAlmostEqual(curve[1].cash, 20.0)
        self.assertAlmostEqual(curve[1].equity, 920.0)

    def test_raw_events_does_not_apply_normalized_split_twice(self) -> None:
        candles = [
            candle("2024-01-02", 100.0, 100.0),
            candle("2024-01-03", 100.0, 100.0),
        ]
        actions = {
            "2024-01-03": CorporateAction("2024-01-03", "TEST3", "TEST3.SA", dividend=0.0, split_ratio=2.0)
        }
        curve = simulate_buy_and_hold_raw_events(candles, actions, initial_cash=1000.0)

        self.assertAlmostEqual(curve[1].shares, 10.0)
        self.assertAlmostEqual(curve[1].split_ratio, 2.0)
        self.assertAlmostEqual(curve[1].equity, 1000.0)

    def test_weekly_mid_candle_dividend_is_applied_after_open_trade(self) -> None:
        candles = [
            candle("2024-01-01", 100.0, 100.0),
            candle("2024-01-08", 100.0, 100.0),
        ]
        actions = [
            CorporateAction("2024-01-03", "TEST3", "TEST3.SA", dividend=2.0, split_ratio=1.0)
        ]
        before_open, after_open = _action_buckets(candles, actions)
        curve = simulate_buy_and_hold_raw_events(candles, before_open, after_open, initial_cash=1000.0)

        self.assertAlmostEqual(curve[0].dividend_cash, 20.0)
        self.assertAlmostEqual(curve[0].cash, 20.0)
        self.assertAlmostEqual(curve[0].equity, 1020.0)

    def test_intraday_dividend_is_applied_before_first_ex_date_candle(self) -> None:
        candles = [
            candle("2024-01-01 14:00:00", 100.0, 100.0),
            candle("2024-01-02 10:00:00", 100.0, 100.0),
            candle("2024-01-02 14:00:00", 100.0, 100.0),
        ]
        actions = [
            CorporateAction("2024-01-02", "TEST3", "TEST3.SA", dividend=2.0, split_ratio=1.0)
        ]
        before_open, after_open = _action_buckets(candles, actions)
        curve = simulate_buy_and_hold_raw_events(candles, before_open, after_open, initial_cash=1000.0)

        self.assertAlmostEqual(curve[1].dividend_cash, 20.0)
        self.assertAlmostEqual(curve[2].dividend_cash, 0.0)


if __name__ == "__main__":
    unittest.main()
