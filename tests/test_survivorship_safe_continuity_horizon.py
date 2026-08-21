from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import build_survivorship_safe_realistic_universe as builder


class SurvivorshipSafeContinuityHorizonTests(unittest.TestCase):
    def test_post_horizon_same_isin_symbol_is_not_added_to_market_data_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archives = root / "archives"
            archives.mkdir()
            for year in (2017, 2018):
                (archives / f"COTAHIST_A{year}.ZIP").write_bytes(b"fixture")

            warm = SimpleNamespace(
                date="2017-12-29",
                ticker="AAA3",
                isin="BRAAAACNOR00",
                issuer_name="AAA SA",
            )
            selected = SimpleNamespace(
                date="2018-01-02",
                ticker="AAA3",
                isin="BRAAAACNOR00",
                issuer_name="AAA SA",
            )
            future_rename = SimpleNamespace(
                date="2018-12-31",
                ticker="BBB3",
                isin="BRAAAACNOR00",
                issuer_name="AAA SA",
            )
            snapshot = {
                "effective_date": "2018-01-02",
                "ticker": "AAA3",
                "rank": 1,
                "presence": 1.0,
                "avg_financial_volume": 1_000_000.0,
                "issuer_name": "AAA SA",
                "issuer_code": "AAA3",
                "lookback_sessions": 21,
            }
            execution = [
                {
                    "date": "2018-01-02",
                    "ticker": "AAA3",
                    "market_type": "010",
                    "open": 10.0,
                    "close": 10.0,
                    "financial_volume": 1_000_000.0,
                },
                {
                    "date": "2018-01-02",
                    "ticker": "AAA3F",
                    "market_type": "020",
                    "open": 10.0,
                    "close": 10.0,
                    "financial_volume": 10_000.0,
                },
            ]
            manifest_path = root / "universe.json"

            with (
                patch.object(
                    builder,
                    "read_standard_company_equity_cotahist",
                    side_effect=[[warm], [selected, future_rename]],
                ),
                patch.object(builder, "read_fractional_cotahist", side_effect=[[], []]),
                patch.object(builder, "is_company_equity", return_value=True),
                patch.object(builder, "snapshot_rows", return_value=[snapshot]),
                patch.object(builder, "execution_rows", return_value=execution) as execution_builder,
            ):
                result = builder.main(
                    [
                        "--years",
                        "2017:2018",
                        "--archives-dir",
                        str(archives),
                        "--start",
                        "2018-01-02",
                        "--end",
                        "2018-06-30",
                        "--lookback-sessions",
                        "21",
                        "--top-n",
                        "1",
                        "--snapshots-output",
                        str(root / "snapshots.csv"),
                        "--manifest-output",
                        str(manifest_path),
                        "--execution-output",
                        str(root / "execution.csv"),
                    ]
                )

            self.assertEqual(result, 0)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["selection_end"], "2018-01-02")
            self.assertEqual(manifest["market_data_tickers"], ["AAA3"])
            self.assertEqual(manifest["continuity_only_tickers"], [])
            self.assertNotIn("BBB3", manifest["issuing_company_by_ticker"])
            self.assertEqual(
                manifest["selection_rules"]["continuity_scope_end"],
                "2018-01-02",
            )
            union = execution_builder.call_args.kwargs["union"]
            self.assertEqual(union, {"AAA3"})


if __name__ == "__main__":
    unittest.main()
