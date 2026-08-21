from __future__ import annotations

import math
import unittest
from types import SimpleNamespace

from b3_strategy_lab.portfolio_risk import historical_portfolio_volatility


class PortfolioCovarianceTests(unittest.TestCase):
    def _data(self, returns_a: list[float], returns_b: list[float]):
        dates = [f"2026-01-{index + 1:02d}" for index in range(len(returns_a) + 1)]

        def prices(returns: list[float]) -> list[float]:
            result = [100.0]
            for value in returns:
                result.append(result[-1] * (1.0 + value))
            return result

        candles_a = [SimpleNamespace(date=day) for day in dates]
        candles_b = [SimpleNamespace(date=day) for day in dates]
        return SimpleNamespace(
            candles={"AAA3": candles_a, "BBB3": candles_b},
            signal_prices={"AAA3": prices(returns_a), "BBB3": prices(returns_b)},
        ), dates

    def test_perfect_positive_correlation_is_not_treated_as_diversification(self) -> None:
        returns = [0.01, -0.005, 0.012, -0.008, 0.006, 0.004, -0.003, 0.009]
        data, dates = self._data(returns, returns)
        portfolio_vol = historical_portfolio_volatility(
            data,
            dates[-1],
            {"AAA3": 0.5, "BBB3": 0.5},
            len(returns),
        )
        single_vol = math.sqrt(252.0) * __import__("statistics").stdev(returns)
        self.assertIsNotNone(portfolio_vol)
        self.assertAlmostEqual(float(portfolio_vol), single_vol, places=12)

    def test_only_history_at_or_before_decision_date_is_used(self) -> None:
        prefix = [0.01, -0.005, 0.012, -0.008, 0.006, 0.004]
        data_one, dates_one = self._data(prefix + [0.25], prefix + [-0.25])
        data_two, dates_two = self._data(prefix + [-0.40], prefix + [0.40])
        decision = dates_one[len(prefix)]
        one = historical_portfolio_volatility(
            data_one,
            decision,
            {"AAA3": 0.5, "BBB3": 0.5},
            len(prefix),
        )
        two = historical_portfolio_volatility(
            data_two,
            decision,
            {"AAA3": 0.5, "BBB3": 0.5},
            len(prefix),
        )
        self.assertAlmostEqual(float(one), float(two), places=12)

    def test_insufficient_aligned_history_fails_closed(self) -> None:
        data, dates = self._data([0.01, 0.02, -0.01], [0.01, 0.02, -0.01])
        self.assertIsNone(
            historical_portfolio_volatility(
                data,
                dates[-1],
                {"AAA3": 0.5, "BBB3": 0.5},
                10,
            )
        )


if __name__ == "__main__":
    unittest.main()
