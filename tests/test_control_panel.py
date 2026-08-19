from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.realistic_backtest_control_panel import (
    EXCLUDED_TICKERS,
    HTML,
    MIN_START,
    _load_available_tickers,
    _parse_run_request,
    _selected_payload,
)


class ControlPanelTests(unittest.TestCase):
    def test_boac34_is_never_available(self) -> None:
        self.assertIn("BOAC34", EXCLUDED_TICKERS)
        self.assertNotIn("BOAC34", _load_available_tickers())

    def test_selected_payload_keeps_only_user_subset(self) -> None:
        payload = _selected_payload(["PETR4", "VALE3"])
        self.assertEqual(payload["tickers"], ["PETR4", "VALE3"])
        self.assertTrue(payload["control_panel"]["no_replacements"])
        self.assertIn("BOAC34", payload["control_panel"]["excluded_tickers"])

    def test_selected_payload_rejects_outside_ticker(self) -> None:
        with self.assertRaises(ValueError):
            _selected_payload(["PETR4", "BOAC34"])
        with self.assertRaises(ValueError):
            _selected_payload(["PETR4", "XXXX3"])

    def test_request_accepts_simple_period_and_cash(self) -> None:
        parsed = _parse_run_request(
            {
                "tickers": ["PETR4", "VALE3"],
                "start": "2018-01-02",
                "end": "2025-12-31",
                "initial_cash": 1000,
                "download": False,
            }
        )
        self.assertEqual(parsed["tickers"], ["PETR4", "VALE3"])
        self.assertEqual(parsed["initial_cash"], 1000.0)
        self.assertFalse(parsed["download"])

    def test_request_rejects_inverted_period(self) -> None:
        with self.assertRaises(ValueError):
            _parse_run_request(
                {
                    "tickers": ["PETR4"],
                    "start": "2025-01-02",
                    "end": "2024-12-31",
                    "initial_cash": 1000,
                }
            )

    def test_request_rejects_period_before_supported_history(self) -> None:
        self.assertEqual(MIN_START.isoformat(), "2018-01-02")
        with self.assertRaises(ValueError):
            _parse_run_request(
                {
                    "tickers": ["PETR4"],
                    "start": "2017-12-29",
                    "end": "2018-12-31",
                    "initial_cash": 1000,
                }
            )

    def test_request_rejects_non_finite_cash(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _parse_run_request(
                        {
                            "tickers": ["PETR4"],
                            "start": "2018-01-02",
                            "end": "2018-12-31",
                            "initial_cash": value,
                        }
                    )

    def test_html_formats_decimal_return_as_percentage(self) -> None:
        self.assertIn("const n=Number(v)*100", HTML)
        self.assertIn('min="2018-01-02"', HTML)

    def test_generated_subset_json_remains_serializable(self) -> None:
        payload = _selected_payload(["ABEV3", "PETR4", "VALE3"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "selected.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            restored = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(restored["tickers"], ["ABEV3", "PETR4", "VALE3"])


if __name__ == "__main__":
    unittest.main()
