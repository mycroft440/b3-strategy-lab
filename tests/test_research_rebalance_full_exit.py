from __future__ import annotations

import unittest
from types import SimpleNamespace

from scripts import research_portfolio_allocation_core as core


class ResearchRebalanceFullExitTests(unittest.TestCase):
    def test_zero_target_sells_entire_position_despite_float_rounding(self) -> None:
        # (3 * 1.56) / 1.56 == 2.9999999999999996 in binary floating point.
        self.assertLess((3 * 1.56) / 1.56, 3)
        candles = {
            "OLD3": SimpleNamespace(open=1.56, close=1.56),
            "NEW3": SimpleNamespace(open=10.0, close=10.0),
        }
        shares = {"OLD3": 3.0, "NEW3": 0.0}

        trades, _turnover, cash = core._rebalance(
            "2019-02-01", ["OLD3", "NEW3"], candles, {}, shares, 0.0, {"NEW3": 1.0}, 0.0, 0.0, 1
        )

        self.assertEqual(shares["OLD3"], 0.0)
        self.assertGreaterEqual(cash, 0.0)
        self.assertEqual(trades, 1)

    def test_partial_reduction_still_respects_lot_floor(self) -> None:
        candles = {"AAA3": SimpleNamespace(open=10.0, close=10.0)}
        shares = {"AAA3": 10.0}

        core._rebalance("2019-02-01", ["AAA3"], candles, {}, shares, 0.0, {"AAA3": 0.45}, 0.0, 0.0, 1)

        self.assertEqual(shares["AAA3"], 5.0)


if __name__ == "__main__":
    unittest.main()
