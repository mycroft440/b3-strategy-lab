from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import build_survivorship_safe_realistic_universe as builder


class ExcludedCertifiedSuccessorContinuityTests(unittest.TestCase):
    def test_excluded_successor_remains_unselectable_but_is_loaded_for_continuity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archives = root / "archives"
            archives.mkdir()
            for year in (2019, 2020):
                (archives / f"COTAHIST_A{year}.ZIP").write_bytes(b"fixture")

            def quote(ticker: str, day: str, isin: str) -> SimpleNamespace:
                return SimpleNamespace(
                    ticker=ticker,
                    date=day,
                    isin=isin,
                    issuer_name=ticker[:4],
                )

            standard = [
                quote("PCAR4", "2020-02-28", "BRPCARACNPR0"),
                quote("PCAR3", "2020-03-02", "BRPCARACNOR3"),
                quote("AAA3", "2020-03-03", "BRAAAAACNOR0"),
            ]
            fractional = [
                quote("PCAR4F", "2020-02-28", "BRPCARACNPR0"),
                quote("PCAR3F", "2020-03-02", "BRPCARACNOR3"),
            ]
            transition = SimpleNamespace(
                certification_status="certified",
                effective_date="2020-03-02",
                old_ticker="PCAR4",
                new_ticker="PCAR3",
            )
            manifest = root / "manifest.json"

            with (
                patch.object(builder, "read_standard_company_equity_cotahist", side_effect=[standard, []]),
                patch.object(builder, "read_fractional_cotahist", side_effect=[fractional, []]),
                patch.object(builder, "is_company_equity", return_value=True),
                patch.object(
                    builder,
                    "snapshot_rows",
                    return_value=[
                        {
                            "effective_date": "2020-01-03",
                            "ticker": "PCAR4",
                            "rank": 1,
                            "presence": 1.0,
                            "avg_financial_volume": 1.0,
                            "issuer_name": "PCAR",
                            "issuer_code": "PCAR",
                            "lookback_sessions": 252,
                        }
                    ],
                ),
                patch.object(builder, "write_csv"),
                patch.object(builder, "load_transition_reviews", return_value=[transition]),
                patch.object(
                    builder,
                    "execution_rows",
                    return_value=[{"market_type": "010"}, {"market_type": "020"}],
                ),
            ):
                self.assertEqual(
                    builder.main(
                        [
                            "--years",
                            "2019:2020",
                            "--archives-dir",
                            str(archives),
                            "--start",
                            "2020-01-02",
                            "--end",
                            "2020-03-03",
                            "--top-n",
                            "1",
                            "--manifest-output",
                            str(manifest),
                            "--snapshots-output",
                            str(root / "snapshots.csv"),
                            "--execution-output",
                            str(root / "execution.csv"),
                        ]
                    ),
                    0,
                )

            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertIn("PCAR3", builder.EXCLUDED_TICKERS)
            self.assertEqual(payload["tickers"], ["PCAR4"])
            self.assertIn("PCAR3", payload["market_data_tickers"])
            self.assertIn("PCAR3", payload["continuity_only_tickers"])
            self.assertIn("PCAR3", payload["source_reviewed_successor_tickers"])


if __name__ == "__main__":
    unittest.main()
