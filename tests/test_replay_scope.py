from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from b3_strategy_lab.replay_scope import audit_small_account_replay


class ReplayScopeTests(unittest.TestCase):
    def _write_csv(self, path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_small_account_scope_passes_below_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            curve = root / "curve.csv"
            trades = root / "trades.csv"
            self._write_csv(
                curve,
                ["date", "equity"],
                [
                    {"date": "2018-01-02", "equity": 1000},
                    {"date": "2020-01-02", "equity": 12500},
                ],
            )
            self._write_csv(
                trades,
                ["date", "side", "notional"],
                [
                    {"date": "2020-01-02", "side": "SELL", "notional": 9000},
                    {"date": "2020-01-02", "side": "BUY", "notional": 8500},
                ],
            )
            result = audit_small_account_replay(curve, trades)
            self.assertTrue(result["small_account_scope_passed"])
            self.assertEqual(result["blockers"], [])

    def test_equity_above_limit_blocks_exact_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            curve = root / "curve.csv"
            trades = root / "trades.csv"
            self._write_csv(
                curve,
                ["date", "equity"],
                [{"date": "2026-01-02", "equity": 20000.01}],
            )
            self._write_csv(trades, ["date", "side", "notional"], [])
            result = audit_small_account_replay(curve, trades)
            self.assertIn(
                "portfolio_exceeds_small_account_exact_tax_custody_scope",
                result["blockers"],
            )

    def test_single_day_sales_above_limit_blocks_exact_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            curve = root / "curve.csv"
            trades = root / "trades.csv"
            self._write_csv(
                curve,
                ["date", "equity"],
                [{"date": "2026-01-02", "equity": 19000}],
            )
            self._write_csv(
                trades,
                ["date", "side", "notional"],
                [
                    {"date": "2026-01-02", "side": "SELL", "notional": 11000},
                    {"date": "2026-01-02", "side": "SELL", "notional": 9500},
                ],
            )
            result = audit_small_account_replay(curve, trades)
            self.assertIn("single_day_sales_exceed_irrf_safe_scope", result["blockers"])
            self.assertIn("monthly_sales_exceed_stock_gain_exemption_scope", result["blockers"])

    def test_monthly_sales_are_aggregated_across_rebalances(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            curve = root / "curve.csv"
            trades = root / "trades.csv"
            self._write_csv(
                curve,
                ["date", "equity"],
                [{"date": "2026-02-28", "equity": 15000}],
            )
            self._write_csv(
                trades,
                ["date", "side", "notional"],
                [
                    {"date": "2026-02-06", "side": "SELL", "notional": 6000},
                    {"date": "2026-02-13", "side": "SELL", "notional": 6000},
                    {"date": "2026-02-20", "side": "SELL", "notional": 6000},
                    {"date": "2026-02-27", "side": "SELL", "notional": 6000},
                ],
            )
            result = audit_small_account_replay(curve, trades)
            self.assertNotIn("single_day_sales_exceed_irrf_safe_scope", result["blockers"])
            self.assertIn("monthly_sales_exceed_stock_gain_exemption_scope", result["blockers"])
            self.assertEqual(result["max_monthly_sales"], 24000.0)


if __name__ == "__main__":
    unittest.main()
