from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from b3_strategy_lab.historical_cash import (
    historical_cash_binding_issues, load_historical_cash, merge_historical_cash,
)
from scripts.run_realistic_pipeline import _require_input_mode
from scripts import run_realistic_pipeline as pipeline
from scripts.sync_point_in_time_universe import _write_cash


class HistoricalCashTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.document = self.root / "source.txt"
        self.document.write_text("Synthetic fixture: dividend 1.25, paid January 10", encoding="utf-8")
        self.path = self.root / "cash.json"
        self.quotes = {"AAAA3": [
            SimpleNamespace(date=value, isin="BRAAAAACNOR0")
            for value in ("2024-01-02", "2024-01-03", "2024-01-05")
        ]}
        self.source = {
            "source_authority": "CVM", "source_url": "https://www.cvm.gov.br/fixture",
            "source_document": "source.txt",
            "source_sha256": hashlib.sha256(self.document.read_bytes()).hexdigest(),
            "source_reference": "Synthetic test fixture, page 1",
        }
        self.event = dict(self.source, ticker="AAAA3", isin="BRAAAAACNOR0", label="DIVIDENDO",
                          announcement_date="2024-01-01", last_date_prior="2024-01-02",
                          ex_date="2024-01-03", payment_date="2024-01-10", gross_per_share="1.25")
        self.review = dict(self.source, ticker="AAAA3", isin="BRAAAAACNOR0", start="2024-01-02",
                           end="2024-01-05", complete=True, reviewed_by="test fixture", event_count=1)
        self.payload = {"schema_version": 1, "events": [self.event], "coverage_reviews": [self.review]}

    def load(self, payload=None):
        self.path.write_text(json.dumps(self.payload if payload is None else payload), encoding="utf-8")
        return load_historical_cash(self.path, self.quotes, start="2024-01-02", end="2024-01-05")

    def test_full_documented_history_clears_only_historical_source_issue(self):
        supplement = self.load()
        issues = [
            {"ticker": "AAAA3", "issue": "historical_cash_dividend_source_unavailable"},
            {"ticker": "AAAA3", "issue": "invalid_rate"},
        ]
        rows, unresolved = merge_historical_cash([], issues, supplement)
        self.assertEqual(len(rows), 1)
        self.assertEqual(unresolved, issues[1:])
        self.assertEqual(supplement["covered_tickers"], ["AAAA3"])
        self.assertEqual(historical_cash_binding_issues({"historical_cash_supplement": supplement}), [])

    def test_explicit_review_of_zero_events_can_cover_missing_history(self):
        self.payload["events"] = []
        self.review["event_count"] = 0
        supplement = self.load()
        rows, issues = merge_historical_cash([], [{"ticker": "AAAA3", "issue": "historical_cash_dividend_source_unavailable"}], supplement)
        self.assertEqual((rows, issues), ([], []))

    def test_partial_review_does_not_clear_missing_source(self):
        self.review["end"] = "2024-01-03"
        supplement = self.load()
        self.assertEqual(supplement["covered_tickers"], [])
        issue = {"ticker": "AAAA3", "issue": "historical_cash_dividend_source_unavailable"}
        self.assertEqual(merge_historical_cash([], [issue], supplement)[1], [issue])

    def test_deduplication_preserves_installments_and_canonicalizes_aliases(self):
        self.payload["events"].append(dict(self.event))
        self.payload["events"].append(dict(self.event, payment_date="2024-02-10"))
        self.review["event_count"] = 2
        supplement = self.load()
        b3 = dict(self.event, label="DIVIDEND", gross_per_share="1.2500")
        rows, issues = merge_historical_cash([b3], [], supplement)
        self.assertEqual(len(rows), 2)
        self.assertEqual(issues, [])
        self.assertEqual({row["payment_date"] for row in rows}, {"2024-01-10", "2024-02-10"})

    def test_conflicting_b3_amount_cannot_be_overwritten(self):
        supplement = self.load()
        with self.assertRaisesRegex(ValueError, "conflict"):
            merge_historical_cash([dict(self.event, gross_per_share="2.5")], [], supplement)

    def test_conflicting_supplement_duplicate_is_rejected(self):
        self.payload["events"].append(dict(self.event, gross_per_share="2.5"))
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            self.load()

    def test_missing_altered_and_escaping_source_documents_are_rejected(self):
        for field, value in (("source_document", "missing.txt"), ("source_sha256", "0" * 64),
                             ("source_document", "../source.txt")):
            with self.subTest(field=field, value=value):
                payload = copy.deepcopy(self.payload)
                payload["events"][0][field] = value
                with self.assertRaisesRegex(ValueError, "verification"):
                    self.load(payload)

    def test_identity_dates_announcements_scope_and_review_must_match(self):
        changes = (
            ("ticker", "BBBB3"), ("isin", "BRBBBBACNOR0"), ("ex_date", "2024-01-04"),
            ("last_date_prior", "2023-12-29"), ("announcement_date", "2024-01-04"),
            ("payment_date", "2024-01-02"), ("gross_per_share", "NaN"),
            ("source_url", "https://cvm.gov.br.evil.test/fixture"), ("source_reference", ""),
        )
        for field, value in changes:
            with self.subTest(field=field):
                payload = copy.deepcopy(self.payload)
                payload["events"][0][field] = value
                with self.assertRaises(ValueError):
                    self.load(payload)
        for field, value in (("complete", False), ("reviewed_by", ""), ("event_count", 2)):
            payload = copy.deepcopy(self.payload)
            payload["coverage_reviews"][0][field] = value
            with self.assertRaises(ValueError):
                self.load(payload)

    def test_review_cannot_cover_unreviewed_isin_period(self):
        self.quotes["AAAA3"].append(SimpleNamespace(date="2024-01-05", isin="BRAAAAACNOR1"))
        self.assertEqual(self.load()["covered_tickers"], [])

    def test_saved_binding_rechecks_source_and_registry_bytes(self):
        supplement = self.load()
        self.document.write_text("modified", encoding="utf-8")
        self.assertIn("source_document_hash_mismatch:source.txt", historical_cash_binding_issues({"historical_cash_supplement": supplement}))
        self.path.write_text("{}", encoding="utf-8")
        self.assertEqual(historical_cash_binding_issues({"historical_cash_supplement": supplement}), ["historical_cash_supplement_hash_mismatch_or_missing"])

    def test_csv_keeps_documentary_provenance(self):
        output = self.root / "events.csv"
        _write_cash(output, self.load()["rows"])
        text = output.read_text(encoding="utf-8")
        self.assertIn("announcement_date,source_document,source_sha256,source_reference", text)
        self.assertIn(self.source["source_sha256"], text)


class MaximumFidelityTests(unittest.TestCase):
    def test_maximum_fidelity_requires_certification_even_with_clean_parse(self):
        audit = {"ready_for_realistic_estimate": True, "ready_for_certified_market_inputs": False,
                 "certified_market_input_blockers": ["cash_history_coverage_certified"]}
        with self.assertRaisesRegex(RuntimeError, "cash_history_coverage_certified"):
            _require_input_mode(audit, "maximum_fidelity")
        _require_input_mode(audit, "research")
        audit["ready_for_certified_market_inputs"] = True
        _require_input_mode(audit, "maximum_fidelity")

    def test_research_cannot_silently_ignore_structural_cash_errors(self):
        for mode in ("research", "maximum_fidelity"):
            with self.assertRaisesRegex(RuntimeError, "refusing estimate"):
                _require_input_mode({"ready_for_realistic_estimate": False}, mode)

    def test_default_pipeline_stops_before_any_backtest_without_certified_cash(self):
        audit = {"ready_for_realistic_estimate": True, "ready_for_certified_market_inputs": False,
                 "certified_market_input_blockers": ["cash_history_coverage_certified"]}
        with (
            patch.object(pipeline.subprocess, "run", return_value=SimpleNamespace(returncode=0)),
            patch.object(pipeline.Path, "exists", return_value=True),
            patch.object(pipeline, "_read", return_value=audit),
            patch.object(pipeline, "transition_binding_issues", return_value=[]),
            patch.object(pipeline, "_run") as run,
        ):
            with self.assertRaisesRegex(RuntimeError, "Maximum fidelity"):
                pipeline.main(["--skip-data-build", "--skip-walk-forward", "--end", "2024-01-05"])
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
