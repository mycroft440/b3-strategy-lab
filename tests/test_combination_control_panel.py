from __future__ import annotations

import csv
import gzip
import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.realistic_combination_backtest_control_panel import (
    EXCLUDED_TICKERS,
    MIN_START,
    RECOMMENDED_WORKERS,
    _load_available_tickers,
    _parse_combination_progress,
    _parse_run_request,
    _read_winner,
    _selected_payload,
)
from scripts.backtest_strategy_management_combinations import _load_universe


class CombinationControlPanelTests(unittest.TestCase):
    def test_boac34_is_excluded(self) -> None:
        self.assertIn("BOAC34", EXCLUDED_TICKERS)
        self.assertNotIn("BOAC34", _load_available_tickers())

    def test_selected_subset_has_no_replacements(self) -> None:
        payload = _selected_payload(["PETR4", "VALE3"])
        self.assertEqual(payload["tickers"], ["PETR4", "VALE3"])
        self.assertTrue(payload["control_panel"]["no_replacements"])
        self.assertIn("BOAC34", payload["control_panel"]["excluded_tickers"])

    def test_request_validates_period_and_cash(self) -> None:
        parsed = _parse_run_request(
            {
                "tickers": ["PETR4", "VALE3"],
                "start": "2018-01-02",
                "end": "2025-12-31",
                "initial_cash": 1000,
            }
        )
        self.assertEqual(parsed["tickers"], ["PETR4", "VALE3"])
        self.assertEqual(parsed["initial_cash"], 1000.0)
        self.assertEqual(parsed["cost_bps"], 3.2)
        self.assertEqual(parsed["slippage_bps"], 10.0)
        self.assertEqual(parsed["workers"], RECOMMENDED_WORKERS)
        self.assertTrue(parsed["refresh_data"])
        self.assertEqual(MIN_START.isoformat(), "2018-01-02")

    def test_request_rejects_more_workers_than_available_cpus(self) -> None:
        with self.assertRaisesRegex(ValueError, "Processos"):
            _parse_run_request(
                {
                    "tickers": ["PETR4"],
                    "workers": max(1, os.cpu_count() or 1) + 1,
                }
            )

    def test_user_subset_is_a_valid_universe_manifest(self) -> None:
        payload = _selected_payload(["PETR4", "VALE3"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "subset.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = _load_universe(path)
        self.assertEqual(loaded["tickers"], ["PETR4", "VALE3"])

    def test_progress_parser_reports_combinations(self) -> None:
        progress = _parse_combination_progress(
            "12/156 estrategias; 5736/74568 combinacoes; 120.0s"
        )
        assert progress is not None
        self.assertEqual(progress["combinations_completed"], 5736)
        self.assertEqual(progress["combinations_total"], 74568)
        self.assertEqual(progress["strategies_completed"], 12)
        self.assertEqual(progress["strategies_total"], 156)
        self.assertAlmostEqual(progress["progress_percent"], 5736 / 74568 * 100, places=2)
        self.assertAlmostEqual(progress["combinations_per_second"], 47.8, places=1)

    def test_progress_parser_ignores_other_output(self) -> None:
        self.assertIsNone(_parse_combination_progress("Salvo: reports/test.csv.gz"))

    def test_winner_reader_uses_first_ranked_row(self) -> None:
        fields = [
            "rank",
            "trading_strategy",
            "management_strategy",
            "final_equity",
            "total_return",
            "cagr",
            "max_drawdown",
            "trades",
        ]
        rows = [
            {
                "rank": 1,
                "trading_strategy": "gap_momentum",
                "management_strategy": "top1_test",
                "final_equity": 32168.9,
                "total_return": 31.1689,
                "cagr": 0.49,
                "max_drawdown": -0.56,
                "trades": 200,
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
        assert winner is not None
        self.assertEqual(winner["strategy"], "gap_momentum")
        self.assertEqual(winner["management"], "top1_test")
        self.assertAlmostEqual(winner["total_return"], 31.1689)
        self.assertEqual(winner["end"], "2026-08-19")
        self.assertEqual(winner["cost_bps"], 3.2)

    def test_selected_payload_is_serializable(self) -> None:
        payload = _selected_payload(["ABEV3", "PETR4"])
        json.dumps(payload)


if __name__ == "__main__":
    unittest.main()
