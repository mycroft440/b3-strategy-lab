from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from b3_strategy_lab.candles import Candle
from scripts import research_portfolio_allocation as research


def _candle(day: str, ticker: str, raw_open: float, raw_close: float, factor: float) -> Candle:
    return Candle(
        date=day,
        ticker=ticker,
        source_symbol=ticker,
        open=raw_open * factor,
        high=max(raw_open, raw_close) * factor,
        low=min(raw_open, raw_close) * factor,
        close=raw_close * factor,
        adj_close=raw_close * factor,
        volume=1000,
        raw_open=raw_open,
        raw_high=max(raw_open, raw_close),
        raw_low=min(raw_open, raw_close),
        raw_close=raw_close,
        adjustment_factor=factor,
    )


class TransitionAdjustmentBasisTests(unittest.TestCase):
    """BTOW3 -> AMER3: the successor is normalized by a later 100:1 reverse split."""

    def setUp(self) -> None:
        self.old = _candle("2021-07-16", "OLD3", 65.59, 68.0, 1.0)
        self.new = _candle("2021-07-19", "NEW3", 67.7, 61.92, 100.0)
        self.transitions = patch.object(
            research,
            "_certified_unit_transitions",
            return_value={"2021-07-19": (("OLD3", "NEW3"),)},
        )
        self.transitions.start()
        self.data = SimpleNamespace(
            by_date={"OLD3": {self.old.date: self.old}, "NEW3": {self.new.date: self.new}},
            candles={"OLD3": [self.old], "NEW3": [self.new]},
        )
        research._install_transition_price_aliases(self.data)

    def tearDown(self) -> None:
        self.transitions.stop()

    def test_alias_keeps_the_predecessor_basis(self) -> None:
        alias = self.data.by_date["OLD3"]["2021-07-19"]
        self.assertAlmostEqual(alias.open, 67.7)
        self.assertAlmostEqual(alias.close, 61.92)
        self.assertAlmostEqual(alias.raw_close, 61.92)
        # One session of traded price change, not the ratio of adjustment factors.
        self.assertAlmostEqual(alias.close / self.old.close - 1, 61.92 / 68.0 - 1)

    def test_carried_quantity_preserves_position_value(self) -> None:
        today = {ticker: self.data.by_date[ticker]["2021-07-19"] for ticker in ("OLD3", "NEW3")}
        shares = {"OLD3": 10.0, "NEW3": 0.0}
        value_before = shares["OLD3"] * today["OLD3"].open

        research._rebalance(
            "2021-07-19", ["OLD3", "NEW3"], today, {}, shares, 0.0, {"OLD3": 1.0}, 0.0, 0.0, 0
        )

        self.assertEqual(shares["OLD3"], 0.0)
        self.assertAlmostEqual(shares["NEW3"] * self.new.open, value_before)
        self.assertAlmostEqual(shares["NEW3"] * self.new.close, 10.0 * 61.92)


if __name__ == "__main__":
    unittest.main()
