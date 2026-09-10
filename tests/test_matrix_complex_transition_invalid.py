from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts import backtest_strategy_management_combinations as matrix
from scripts import research_portfolio_allocation as research


class ComplexTransitionInvalidationTests(unittest.TestCase):
    def test_gndi3_certified_complex_transition_is_classified(self) -> None:
        reason = research._research_invalid_transition_reason(
            "2022-02-14: abertura fresca obrigatoria ausente para GNDI3"
        )
        self.assertIsNotNone(reason)
        self.assertIn("GNDI3->HAPV3", reason)
        self.assertIn("CERTIFIED_COMPLEX_TRANSITION", reason)

    def test_unrelated_missing_price_remains_fatal(self) -> None:
        self.assertIsNone(
            research._research_invalid_transition_reason(
                "2022-02-14: abertura fresca obrigatoria ausente para PETR4"
            )
        )

    def test_strategy_rows_marks_only_certified_complex_transition_invalid(self) -> None:
        class Data:
            dates = ["2022-02-11", "2022-02-14"]
        config = type("Config", (), {"name": "management"})()
        with patch.object(
            matrix,
            "run_portfolio",
            side_effect=ValueError("2022-02-14: abertura fresca obrigatoria ausente para GNDI3"),
        ):
            rows = matrix._strategy_rows(
                Data(), [config], "strategy", {}, {},
                universe_membership={}, start="2022-02-11", end="2022-02-14",
                initial_cash=1000.0, cost_bps=3.2, slippage_bps=10.0, lot_size=1,
            )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["validity"], "INVALID_UNSUPPORTED_CERTIFIED_CORPORATE_TRANSITION")

    def test_strategy_rows_does_not_swallow_ordinary_value_error(self) -> None:
        class Data:
            dates = ["2022-02-11", "2022-02-14"]
        config = type("Config", (), {"name": "management"})()
        with patch.object(matrix, "run_portfolio", side_effect=ValueError("ordinary bug")):
            with self.assertRaisesRegex(ValueError, "ordinary bug"):
                matrix._strategy_rows(
                    Data(), [config], "strategy", {}, {},
                    universe_membership={}, start="2022-02-11", end="2022-02-14",
                    initial_cash=1000.0, cost_bps=3.2, slippage_bps=10.0, lot_size=1,
                )


if __name__ == "__main__":
    unittest.main()
