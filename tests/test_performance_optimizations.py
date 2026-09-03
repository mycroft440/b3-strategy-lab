from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from b3_strategy_lab.realistic import ExecutionPriceBook
from scripts import research_portfolio_allocation as public
from scripts import research_portfolio_allocation_core as core


class PortfolioPerformanceCacheTests(unittest.TestCase):
    def _data(self):
        prices = [100.0]
        for index in range(1, 320):
            prices.append(prices[-1] * (1.0005 + (index % 7) * 0.00003))
        return SimpleNamespace(
            signal_prices={"AAA3": prices},
            raw_returns={"AAA3": core._returns(prices)},
            candidate_profile_cache={},
            trend_average_cache={},
            volatility_window_cache={},
            price_roc_cache={},
            eligibility_tickers_cache={},
            tickers=["AAA3"],
            index_by_date={"AAA3": {"2026-01-02": 319}},
        )

    def test_cached_candidate_math_matches_canonical_implementation_exactly(self) -> None:
        configs = [
            core.PortfolioConfig(
                name="momentum",
                lookback=63,
                trend_window=200,
                vol_window=21,
                score="momentum",
            ),
            core.PortfolioConfig(
                name="risk_adjusted",
                lookback=126,
                skip=21,
                trend_window=200,
                vol_window=63,
                score="risk_adjusted",
            ),
            core.PortfolioConfig(
                name="roc_combo",
                lookback=126,
                trend_window=200,
                vol_window=63,
                score="roc_combo_risk_adjusted",
                roc_windows="21,63,126",
                roc_weights="1,2,3",
                positive_rule="all_windows",
            ),
            core.PortfolioConfig(
                name="short_blend",
                lookback=126,
                trend_window=0,
                vol_window=21,
                score="roc_short_blend",
                roc_windows="21,63,126",
                roc_weights="1,1,1",
                short_window=21,
                short_weight=1.0,
            ),
        ]
        for config in configs:
            with self.subTest(config=config.name):
                baseline_data = self._data()
                optimized_data = self._data()
                expected = core._candidate_profile_uncached(
                    baseline_data, "AAA3", 319, config
                )
                actual = public._candidate_profile_uncached(
                    optimized_data, "AAA3", 319, config
                )
                self.assertEqual(actual, expected)

    def test_invariant_subexpressions_are_reused_across_management_configs(self) -> None:
        data = self._data()
        first = core.PortfolioConfig(
            name="momentum",
            lookback=63,
            trend_window=200,
            vol_window=21,
            score="momentum",
        )
        second = core.PortfolioConfig(
            name="risk_adjusted",
            lookback=63,
            trend_window=200,
            vol_window=21,
            score="risk_adjusted",
        )
        public._candidate_profile_uncached(data, "AAA3", 319, first)
        cache_sizes = (
            len(data.trend_average_cache),
            len(data.volatility_window_cache),
            len(data.price_roc_cache),
        )
        public._candidate_profile_uncached(data, "AAA3", 319, second)
        self.assertEqual(
            (
                len(data.trend_average_cache),
                len(data.volatility_window_cache),
                len(data.price_roc_cache),
            ),
            cache_sizes,
        )

    def test_eligibility_is_cached_per_signal_object_and_session(self) -> None:
        data = SimpleNamespace(
            tickers=["AAA3", "BBB3"],
            index_by_date={
                "AAA3": {"2026-01-02": 0},
                "BBB3": {"2026-01-02": 0},
            },
            eligibility_tickers_cache={},
        )
        eligibility = {"AAA3": [1], "BBB3": [0]}
        first = public._eligible_tickers(data, "2026-01-02", eligibility)
        second = public._eligible_tickers(data, "2026-01-02", eligibility)
        self.assertIs(first, second)
        self.assertEqual(first, frozenset({"AAA3"}))


class CausalLiquidityCacheTests(unittest.TestCase):
    def _book(self) -> ExecutionPriceBook:
        rows = [
            {
                "date": "2024-01-02",
                "ticker": "AAA3",
                "market_type": "010",
                "open": 10,
                "close": 10,
                "financial_volume": 1_000_000,
            },
            {
                "date": "2024-01-03",
                "ticker": "AAA3",
                "market_type": "010",
                "open": 10,
                "close": 10,
                "financial_volume": 3_000_000,
            },
            {
                "date": "2024-01-04",
                "ticker": "AAA3",
                "market_type": "010",
                "open": 10,
                "close": 10,
                "financial_volume": 9_000_000,
            },
        ]
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "execution.csv"
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return ExecutionPriceBook.from_csv(path)

    def test_causal_reference_is_memoized_without_changing_value(self) -> None:
        book = self._book()
        first = book.causal_liquidity_reference(
            "2024-01-04", "AAA3", "010", lookback_sessions=20
        )
        cache = getattr(book, "_causal_liquidity_reference_cache")
        self.assertEqual(len(cache), 1)
        second = book.causal_liquidity_reference(
            "2024-01-04", "AAA3", "010", lookback_sessions=20
        )
        self.assertEqual(first, 2_000_000.0)
        self.assertEqual(second, first)
        self.assertEqual(len(cache), 1)

    def test_causal_execution_legs_are_reused_without_mutating_results(self) -> None:
        book = self._book()
        first = book.legs("2024-01-04", "AAA3", 100)
        cache = getattr(book, "_causal_liquidity_legs_cache")
        self.assertEqual(len(cache), 1)
        second = book.legs("2024-01-04", "AAA3", 100)
        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertEqual(len(cache), 1)


if __name__ == "__main__":
    unittest.main()
