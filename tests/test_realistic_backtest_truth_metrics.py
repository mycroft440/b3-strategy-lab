from __future__ import annotations

import csv
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from b3_strategy_lab.realistic_portfolio_core import RealisticSummary
from scripts.backtest_strategy_management_combinations import _write_results
from scripts.realistic_backtest_control_panel import _result_summary
from scripts.realistic_combination_backtest_control_panel import _read_winner


class RealisticBacktestTruthMetricsTests(unittest.TestCase):
    def test_realistic_summary_dataclass_fields(self) -> None:
        summary = RealisticSummary(
            strategy="gap_momentum",
            management="top1_adjusted",
            start="2018-01-02",
            end="2026-08-19",
            initial_cash=1000.0,
            final_equity=2500.0,
            total_return=1.5,
            cagr=0.15,
            max_drawdown=-0.25,
            annual_volatility=0.20,
            sharpe=0.85,
            average_annual_return=0.16,
            trades=150,
            fees_paid=45.2,
            ordinary_income_tax_paid=12.0,
            distribution_tax_paid=0.0,
            distributions_net=0.0,
            validity="REALISTIC_POINT_IN_TIME",
            point_in_time_universe=True,
            survivorship_safe=True,
            fractional_execution=True,
            cash_events_complete=True,
            fee_quality="official",
            economic_gap_adjustment=True,
            selection_status="retrospective_hypothesis_replay",
            calmar=0.60,
            sortino=1.10,
        )
        self.assertEqual(summary.calmar, 0.60)
        self.assertEqual(summary.sortino, 1.10)
        self.assertEqual(summary.strategy, "gap_momentum")
        self.assertTrue(summary.economic_gap_adjustment)

    def test_control_panel_result_summary_extracts_truth_metrics(self) -> None:
        mock_payload = {
            "selected_count": 5,
            "selected_tickers": ["ABEV3", "B3SA3", "ITUB4", "PETR4", "VALE3"],
            "raw_gap": {
                "final_equity": 3500.0,
                "total_return": 2.5,
                "cagr": 0.18,
                "max_drawdown": -0.32,
                "sharpe": 0.92,
                "calmar": 0.5625,
                "sortino": 1.25,
                "trades": 180,
                "fees_paid": 60.5,
                "ordinary_income_tax_paid": 45.0,
            },
            "economic_gap": {
                "final_equity": 3400.0,
                "total_return": 2.4,
                "cagr": 0.175,
                "max_drawdown": -0.315,
                "sharpe": 0.90,
                "calmar": 0.555,
                "sortino": 1.21,
                "trades": 180,
                "fees_paid": 60.5,
                "ordinary_income_tax_paid": 45.0,
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_status = Path(tmp) / "status.json"
            tmp_status.write_text(json.dumps(mock_payload), encoding="utf-8")
            with patch("scripts.realistic_backtest_control_panel.STATUS_PATH", tmp_status):
                summary = _result_summary()

        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertEqual(summary["selected_count"], 5)
        self.assertEqual(summary["raw_final_equity"], 3500.0)
        self.assertEqual(summary["raw_total_return"], 2.5)
        self.assertEqual(summary["raw_cagr"], 0.18)
        self.assertEqual(summary["raw_max_drawdown"], -0.32)
        self.assertEqual(summary["raw_sharpe"], 0.92)
        self.assertEqual(summary["raw_calmar"], 0.5625)
        self.assertEqual(summary["raw_sortino"], 1.25)
        self.assertEqual(summary["raw_trades"], 180)
        self.assertEqual(summary["raw_fees"], 60.5)
        self.assertEqual(summary["raw_tax"], 45.0)

        self.assertEqual(summary["economic_final_equity"], 3400.0)
        self.assertEqual(summary["economic_total_return"], 2.4)
        self.assertEqual(summary["economic_cagr"], 0.175)
        self.assertEqual(summary["economic_max_drawdown"], -0.315)
        self.assertEqual(summary["economic_sharpe"], 0.90)
        self.assertEqual(summary["economic_calmar"], 0.555)
        self.assertEqual(summary["economic_sortino"], 1.21)

    def test_combinations_csv_writes_and_reads_calmar_and_sortino(self) -> None:
        rows = [
            {
                "rank": 1,
                "trading_strategy": "gap_momentum",
                "strategy_params": "",
                "management_strategy": "top1_test",
                "validity": "VALID",
                "invalid_reason": "",
                "start": "2018-01-02",
                "end": "2026-08-19",
                "candles": 2100,
                "trades": 180,
                "exposure": 0.45,
                "avg_positions": 1.0,
                "initial_equity": 1000.0,
                "final_equity": 32168.9,
                "total_return": 31.1689,
                "cagr": 0.49,
                "average_annual_return": 0.52,
                "max_drawdown": -0.56,
                "annual_volatility": 0.35,
                "sharpe": 1.15,
                "calmar": 0.875,
                "sortino": 1.65,
                "turnover": 4.5,
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out_csv = Path(tmp) / "combinations.csv"
            _write_results(rows, out_csv)
            with out_csv.open(newline="", encoding="utf-8") as f:
                reader = list(csv.DictReader(f))
                self.assertEqual(len(reader), 1)
                row = reader[0]
                self.assertIn("calmar", row)
                self.assertIn("sortino", row)
                self.assertAlmostEqual(float(row["calmar"]), 0.875)
                self.assertAlmostEqual(float(row["sortino"]), 1.65)
                self.assertAlmostEqual(float(row["sharpe"]), 1.15)

    def test_combination_winner_reader_reads_risk_adjusted_metrics(self) -> None:
        fields = [
            "rank",
            "trading_strategy",
            "management_strategy",
            "final_equity",
            "total_return",
            "cagr",
            "max_drawdown",
            "sharpe",
            "calmar",
            "sortino",
            "trades",
        ]
        rows = [
            {
                "rank": 1,
                "trading_strategy": "range_expansion_breakout",
                "management_strategy": "top1_conservative",
                "final_equity": 4500.0,
                "total_return": 3.5,
                "cagr": 0.22,
                "max_drawdown": -0.21,
                "sharpe": 1.25,
                "calmar": 1.0476,
                "sortino": 1.85,
                "trades": 95,
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "matrix.csv.gz"
            with gzip.open(path, "wt", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            path.with_name("matrix.manifest.json").write_text(
                json.dumps(
                    {
                        "start": "2018-01-02",
                        "end": "2026-08-19",
                        "cost_bps": 3.2,
                        "slippage_bps": 10.0,
                    }
                ),
                encoding="utf-8",
            )
            winner = _read_winner(path)

        self.assertIsNotNone(winner)
        assert winner is not None
        self.assertEqual(winner["strategy"], "range_expansion_breakout")
        self.assertAlmostEqual(winner["sharpe"], 1.25)
        self.assertAlmostEqual(winner["calmar"], 1.0476)
        self.assertAlmostEqual(winner["sortino"], 1.85)
        self.assertEqual(winner["trades"], 95)


if __name__ == "__main__":
    unittest.main()
