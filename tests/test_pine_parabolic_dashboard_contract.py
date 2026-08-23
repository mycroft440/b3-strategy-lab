from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PINE = ROOT / "pine" / "parabolic_sar_portfolio_dashboard_v5.pine"
UNIVERSE = ROOT / "data" / "universes" / "fixed_40_2018.json"


class PineParabolicDashboardContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PINE.read_text(encoding="utf-8")
        cls.universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))

    def test_is_pine_v5_dynamic_dashboard(self) -> None:
        self.assertTrue(self.source.startswith("//@version=5\n"))
        self.assertIn("dynamic_requests=true", self.source)
        self.assertIn("table.new(position.top_right", self.source)

    def test_uses_exact_fixed_40_universe(self) -> None:
        declared = re.findall(
            r'ticker\.new\("BMFBOVESPA",\s*"([A-Z0-9]+)"',
            self.source,
        )
        self.assertEqual(len(declared), 40)
        self.assertEqual(declared, self.universe["tickers"])

    def test_requests_split_adjusted_not_dividend_adjusted_prices(self) -> None:
        self.assertEqual(self.source.count("adjustment.splits"), 40)
        self.assertNotIn("adjustment.dividends", self.source)

    def test_matches_winning_management_defaults(self) -> None:
        self.assertIn('input.float(0.02, "AF step"', self.source)
        self.assertIn('input.float(0.20, "AF max"', self.source)
        self.assertIn('input.int(252, "Momentum (pregoes)"', self.source)
        self.assertIn('input.int(63, "Volatilidade (pregoes)"', self.source)
        self.assertIn("close / close[momLen] - 1.0", self.source)
        self.assertIn("ta.stdev(dailyReturn, volLen, false)", self.source)
        self.assertIn("momentum / volatility", self.source)
        self.assertIn('timeframe.change("M")', self.source)
        self.assertIn("bull and not na(momentum) and momentum > 0", self.source)

    def test_matches_python_warmup_and_does_not_use_pre_2017_history(self) -> None:
        self.assertIn('timestamp("America/Sao_Paulo", 2017, 1, 1, 0, 0)', self.source)
        self.assertIn("firstWarmupBar", self.source)
        self.assertIn("ta.barssince(firstWarmupBar)", self.source)
        self.assertIn("historyIndex == 0 ? 0.0", self.source)
        self.assertIn("historyIndex >= momLen", self.source)
        self.assertIn("historyIndex >= volLen", self.source)
        self.assertIn("historyIndex == 1", self.source)
        self.assertIn("historyIndex >= 2", self.source)

    def test_top_five_is_informational_and_top_one_is_chosen(self) -> None:
        self.assertIn('r == 0 ? "INVESTIR"', self.source)
        self.assertIn('monthlyRank == 1 ? "TOP1"', self.source)
        self.assertIn("array.sort_indices(monthCandidateScore, order.descending)", self.source)
        self.assertIn("m.bullPrev and not na(m.scorePrev)", self.source)

    def test_stays_within_tradingview_unique_request_budget(self) -> None:
        # One dynamic request site iterates over the exact 40-symbol universe.
        self.assertEqual(self.source.count("request.security("), 1)
        self.assertEqual(len(self.universe["tickers"]), 40)


if __name__ == "__main__":
    unittest.main()
