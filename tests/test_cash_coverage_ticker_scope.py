from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from b3_strategy_lab.realistic import cash_coverage_certification_issues
from scripts.build_cash_distribution_coverage_certification import _required_cash_tickers


class CashCoverageTickerScopeTests(unittest.TestCase):
    def test_required_scope_includes_continuity_only_market_data_symbols(self) -> None:
        selectable = {"AAA3"}
        manifest = {
            "tickers": ["AAA3"],
            "market_data_tickers": ["AAA3", "OLD3"],
        }
        self.assertEqual(
            _required_cash_tickers(manifest, selectable),
            {"AAA3", "OLD3"},
        )

    def test_certification_missing_continuity_symbol_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = root / "events.csv"
            manifest = root / "manifest.json"
            events.write_text("ticker,label\n", encoding="utf-8")
            manifest.write_text(json.dumps({"complete": True}), encoding="utf-8")
            certification = {
                "schema_version": 1,
                "coverage_certified": True,
                "start": "2018-01-02",
                "end": "2018-12-28",
                "tickers": ["AAA3"],
                "source_authority": "B3",
                "reviewed_by": "reviewer",
                "reviewed_at_utc": "2019-01-02T12:00:00+00:00",
                "evidence": [{"source": "B3 review"}],
                "cash_events_sha256": hashlib.sha256(events.read_bytes()).hexdigest(),
                "cash_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            }
            issues = cash_coverage_certification_issues(
                certification,
                cash_events_path=events,
                cash_manifest_path=manifest,
                tickers={"AAA3", "OLD3"},
                start="2018-01-02",
                end="2018-12-28",
            )
            self.assertIn("certified ticker set does not match the backtest", issues)

            certification["tickers"] = ["AAA3", "OLD3"]
            issues = cash_coverage_certification_issues(
                certification,
                cash_events_path=events,
                cash_manifest_path=manifest,
                tickers={"AAA3", "OLD3"},
                start="2018-01-02",
                end="2018-12-28",
            )
            self.assertNotIn("certified ticker set does not match the backtest", issues)


if __name__ == "__main__":
    unittest.main()
