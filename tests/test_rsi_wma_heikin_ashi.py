from __future__ import annotations

import unittest

from b3_strategy_lab.rsi_wma_heikin_ashi import (
    _rsi,
    heikin_ashi_close,
    priority_flags,
    rsi_wma_heikin_ashi,
    wma,
)
from b3_strategy_lab.strategies import STRATEGIES, build_signals, rsi, strategy_parameters
from tests.test_trend_strategies import synthetic_candles


class RsiWmaHeikinAshiTests(unittest.TestCase):
    def test_registered_with_default_parameters(self) -> None:
        self.assertIn("rsi_wma_heikin_ashi", STRATEGIES)
        self.assertEqual(
            strategy_parameters("rsi_wma_heikin_ashi"),
            {"rsi_period": 14, "rsi_entry": 50.0, "rsi_exit": 50.0, "wma_period": 20},
        )

    def test_rsi_matches_catalog_rsi(self) -> None:
        closes = [candle.close for candle in synthetic_candles()]
        self.assertEqual(_rsi(closes, 14), rsi(closes, 14))

    def test_wma_weights_recent_values_more(self) -> None:
        self.assertEqual(wma([1.0, 2.0, 3.0], 3), [None, None, (1 + 4 + 9) / 6])

    def test_signal_follows_entry_and_exit_rules(self) -> None:
        candles = synthetic_candles()
        signals = build_signals("rsi_wma_heikin_ashi", candles)
        self.assertEqual(len(signals), len(candles))
        self.assertTrue(set(signals) <= {0, 1})
        self.assertIn(1, signals)
        closes = [candle.close for candle in candles]
        rsi_values = _rsi(closes, 14)
        ha_wma = wma(heikin_ashi_close(candles), 20)
        for index in range(1, len(candles)):
            if rsi_values[index] is None or ha_wma[index - 1] is None:
                self.assertEqual(signals[index], 0)
                continue
            rising = ha_wma[index] > ha_wma[index - 1]
            falling = ha_wma[index] < ha_wma[index - 1]
            if signals[index - 1] == 0 and signals[index] == 1:
                self.assertTrue(rsi_values[index] > 50 and rising)
            if signals[index - 1] == 1 and signals[index] == 0:
                self.assertTrue(rsi_values[index] < 50 or falling)
            if signals[index] == 1:
                self.assertFalse(rsi_values[index] < 50 or falling)

    def test_signal_and_priority_are_causal(self) -> None:
        candles = synthetic_candles()
        full = rsi_wma_heikin_ashi(candles)
        flags = priority_flags(candles)
        for cut in (30, 120, 260, 400):
            self.assertEqual(rsi_wma_heikin_ashi(candles[:cut]), full[:cut])
            self.assertEqual(priority_flags(candles[:cut]), flags[:cut])

    def test_priority_uses_price_or_sma20_above_sma50(self) -> None:
        candles = synthetic_candles()
        flags = priority_flags(candles)
        closes = [candle.close for candle in candles]
        for index in range(len(candles)):
            if index < 49:
                self.assertEqual(flags[index], 0)
                continue
            sma50 = sum(closes[index - 49 : index + 1]) / 50
            sma20 = sum(closes[index - 19 : index + 1]) / 20
            expected = int(closes[index] > sma50 or sma20 > sma50)
            self.assertEqual(flags[index], expected)


if __name__ == "__main__":
    unittest.main()


class _FakeMarketData:
    """Estrutura minima usada pelo simulador (tickers, candles, by_date, index_by_date)."""

    def __init__(self, closes: dict[str, list[float]]) -> None:
        from datetime import date, timedelta
        from types import SimpleNamespace

        self.tickers = sorted(closes)
        self.candles = {}
        self.by_date = {}
        self.index_by_date = {}
        start = date(2024, 1, 1)
        for ticker, series in closes.items():
            candles = [
                SimpleNamespace(date=(start + timedelta(days=i)).isoformat(), open=value, close=value)
                for i, value in enumerate(series)
            ]
            self.candles[ticker] = candles
            self.by_date[ticker] = {c.date: c for c in candles}
            self.index_by_date[ticker] = {c.date: i for i, c in enumerate(candles)}


class OneStockRocSelectionTests(unittest.TestCase):
    def test_rate_of_change_and_signal_ages(self) -> None:
        from scripts.backtest_rsi_wma_heikin_ashi import rate_of_change, signal_ages

        data = _FakeMarketData({"AAAA3": [10.0, 11.0, 12.0, 15.0]})
        values = rate_of_change(data.candles["AAAA3"], 2)
        self.assertEqual(values[:2], [None, None])
        self.assertAlmostEqual(values[2], 0.2)
        self.assertAlmostEqual(values[3], 15 / 11 - 1)
        self.assertEqual(signal_ages([0, 1, 1, 0, 1]), [None, 0, 1, None, 0])

    def test_enters_only_on_first_signal_candle_with_best_roc(self) -> None:
        from scripts.backtest_rsi_wma_heikin_ashi import rate_of_change, signal_ages, simulate_portfolio

        closes = {
            "AAAA3": [10, 10, 10, 12, 12, 12, 12, 12],  # ROC alto, mas sinal antigo
            "BBBB3": [10, 10, 10, 11, 11, 11, 11, 11],  # sinal recente, ROC medio
            "CCCC3": [10, 10, 10, 10.5, 10.5, 10.5, 10.5, 10.5],  # sinal recente, ROC baixo
        }
        signals = {
            "AAAA3": [1, 1, 1, 1, 1, 1, 1, 1],
            "BBBB3": [0, 0, 0, 1, 1, 1, 0, 0],
            "CCCC3": [0, 0, 0, 1, 1, 1, 1, 1],
        }
        data = _FakeMarketData({k: [float(v) for v in vals] for k, vals in closes.items()})
        roc = {t: rate_of_change(data.candles[t], 2) for t in data.tickers}
        ages = {t: signal_ages(signals[t]) for t in data.tickers}
        priority = {t: [0] * 8 for t in data.tickers}
        dates = [c.date for c in data.candles["AAAA3"]]
        result = simulate_portfolio(
            data, signals, priority, dates, name="t", max_positions=1, use_priority=False,
            initial_cash=1000.0, cost_bps=0.0, slippage_bps=0.0, lot_size=1,
            roc=roc, signal_age=ages, recent_window=1,
        )
        buys = [row for row in result.ledger if row["side"] == "BUY"]
        sells = [row for row in result.ledger if row["side"] == "SELL"]
        # Decisao no fechamento do pregao 3 (BBBB3 e CCCC3 com sinal novo), compra no pregao 4.
        self.assertEqual(buys[0]["ticker"], "BBBB3")
        self.assertEqual(buys[0]["date"], dates[4])
        # Nunca mais de 1 acao ao mesmo tempo.
        held = 0
        for row in result.ledger:
            held += 1 if row["side"] == "BUY" else -1
            self.assertLessEqual(held, 1)
        # BBBB3 sai no pregao 7; CCCC3 nao esta mais no primeiro candle do sinal, entao nunca entra.
        self.assertEqual(sells[0]["date"], dates[7])
        self.assertEqual(len(buys), 1)


class SignalTradesFreshEntryTests(unittest.TestCase):
    def test_signal_already_active_at_start_is_not_entered_late(self) -> None:
        from scripts.backtest_rsi_wma_heikin_ashi import signal_trades

        data = _FakeMarketData({"AAAA3": [10.0] * 8})
        signals = [1, 1, 1, 0, 0, 1, 1, 0]
        start = data.candles["AAAA3"][2].date
        end = data.candles["AAAA3"][-1].date
        trades = signal_trades("AAAA3", data, signals, [0] * 8, start, end, 0.0, 0.0)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["entry_date"], data.candles["AAAA3"][6].date)
        self.assertEqual(trades[0]["exit_date"], data.candles["AAAA3"][-1].date)
