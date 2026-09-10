from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import backtest_strategy_management_combinations as matrix


class MatrixMarketDataContinuityScopeTests(unittest.TestCase):
    def _manifest(self, root: Path) -> Path:
        snapshot = root / "point_in_time_weekly.csv"
        snapshot.write_text("effective_date,ticker,rank\n2018-01-02,EMBR3,1\n", encoding="utf-8")
        manifest = root / "point_in_time_union.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": 8,
                    "id": "test_pit",
                    "selection_mode": "test",
                    "selected_as_of": "2018-01-02",
                    "selection_end": "2018-01-04",
                    "warmup_start": "2017-01-01",
                    "survivorship_safe": True,
                    "point_in_time": True,
                    "snapshot_file": str(snapshot),
                    "bias_disclosure": "test",
                    "selection_rules": {
                        "future_continuity_filter": False,
                        "future_return_filter": False,
                        "weekly_candidates": 1,
                    },
                    "tickers": ["EMBR3"],
                    "market_data_tickers": ["EMBR3", "EMBJ3"],
                }
            ),
            encoding="utf-8",
        )
        return manifest

    def test_main_loads_continuity_tickers_without_making_them_selectable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = self._manifest(Path(directory))
            fake_data = SimpleNamespace(
                dates=["2018-01-02", "2018-01-03", "2018-01-04"],
                tickers=["EMBR3", "EMBJ3"],
            )
            valid_row = {
                "trading_strategy": "demo",
                "management_strategy": "cfg",
                "validity": "VALID",
                "total_return": 0.1,
                "cagr": 0.1,
            }
            with (
                patch.object(matrix, "portfolio_strategies", return_value=["demo"]),
                patch.object(matrix, "strategy_parameters", return_value={}),
                patch.object(matrix, "MarketData", return_value=fake_data) as market_data,
                patch.object(matrix, "_load_point_in_time_membership", return_value={}) as membership,
                patch.object(matrix, "_build_eligibility", return_value={"demo": {}}),
                patch.object(matrix, "_configs", return_value=[SimpleNamespace(name="cfg")]),
                patch.object(matrix, "_strategy_rows", return_value=[valid_row]),
                patch.object(matrix, "_top_annual_sections", return_value=[]),
                patch.object(matrix, "_write_results"),
                patch.object(matrix, "_write_annual_report"),
                patch.object(matrix, "_write_manifest"),
                patch.object(matrix, "_print_top"),
            ):
                self.assertEqual(
                    matrix.main(
                        [
                            "--universe-manifest",
                            str(manifest),
                            "--strategies",
                            "demo",
                            "--workers",
                            "1",
                            "--top",
                            "1",
                        ]
                    ),
                    0,
                )

            self.assertEqual(market_data.call_args.args[0], ["EMBR3", "EMBJ3"])
            membership.assert_called_once()
            loaded_universe = membership.call_args.args[0]
            self.assertEqual(loaded_universe["tickers"], ["EMBR3"])

    def test_explicit_tickers_cannot_drop_certified_continuity_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = self._manifest(Path(directory))
            with patch.object(matrix, "portfolio_strategies", return_value=["demo"]):
                with self.assertRaises(SystemExit):
                    matrix.main(
                        [
                            "--universe-manifest",
                            str(manifest),
                            "--strategies",
                            "demo",
                            "--workers",
                            "1",
                            "--tickers",
                            "EMBR3",
                        ]
                    )


if __name__ == "__main__":
    unittest.main()
