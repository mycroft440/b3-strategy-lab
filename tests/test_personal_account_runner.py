from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.reconcile_actual_personal_account import main


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PersonalAccountRunnerTests(unittest.TestCase):
    def _csv(self, path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_runner_requires_complete_source_and_normalization_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            evidence.mkdir()
            trade_doc = evidence / "trade.bin"
            statement_doc = evidence / "statement.bin"
            trade_doc.write_bytes(b"source-trade")
            statement_doc.write_bytes(b"source-statement")
            trade_hash = _sha256(trade_doc)
            statement_hash = _sha256(statement_doc)

            fills = root / "fills.csv"
            cash = root / "cash.csv"
            opening = root / "opening.json"
            closing = root / "closing.json"
            coverage = root / "coverage.json"
            output = root / "result.json"

            self._csv(
                fills,
                ["trade_date", "settlement_date", "sequence", "execution_id", "order_id", "side", "ticker", "shares", "price", "source_document", "source_sha256"],
                [{"trade_date": "2026-01-02", "settlement_date": "2026-01-06", "sequence": 10, "execution_id": "e1", "order_id": "o1", "side": "BUY", "ticker": "ABCD3", "shares": 10, "price": 10, "source_document": "trade.bin", "source_sha256": trade_hash}],
            )
            self._csv(
                cash,
                ["value_date", "sequence", "event_id", "kind", "amount", "ticker", "source_document", "source_sha256"],
                [{"value_date": "2026-01-06", "sequence": 20, "event_id": "fee", "kind": "B3_FEE", "amount": -0.10, "ticker": "ABCD3", "source_document": "trade.bin", "source_sha256": trade_hash}],
            )
            opening.write_text(
                json.dumps({"schema_version": 1, "value_date": "2026-01-01", "boundary": "START_OF_DAY", "cash_balance": 1000.0, "positions": {}, "source_document": "statement.bin", "source_sha256": statement_hash}),
                encoding="utf-8",
            )
            closing.write_text(
                json.dumps({"schema_version": 1, "value_date": "2026-01-06", "boundary": "END_OF_DAY", "cash_balance": 899.90, "positions": {"ABCD3": 10}, "source_document": "statement.bin", "source_sha256": statement_hash}),
                encoding="utf-8",
            )

            normalized_manifest = [
                {"role": "fills", "sha256": _sha256(fills)},
                {"role": "cash_events", "sha256": _sha256(cash)},
                {"role": "opening_snapshot", "sha256": _sha256(opening)},
                {"role": "closing_snapshot", "sha256": _sha256(closing)},
            ]
            coverage.write_text(
                json.dumps({
                    "schema_version": 2,
                    "coverage_start": "2026-01-01",
                    "coverage_end": "2026-01-06",
                    "coverage_complete": True,
                    "reviewed_by": "test-reviewer",
                    "reviewed_at_utc": "2026-01-07T12:00:00+00:00",
                    "normalization_verified": True,
                    "normalization_reviewed_by": "test-normalization-reviewer",
                    "normalization_reviewed_at_utc": "2026-01-07T12:00:00+00:00",
                    "normalization_attestation": "Every normalized value was checked against the referenced source bytes.",
                    "documents": [
                        {"path": "trade.bin", "sha256": trade_hash, "kind": "trade_note"},
                        {"path": "statement.bin", "sha256": statement_hash, "kind": "account_statement", "coverage_start": "2026-01-01", "coverage_end": "2026-01-06"}
                    ],
                    "normalized_inputs": normalized_manifest,
                }),
                encoding="utf-8",
            )

            args = [
                "--fills", str(fills),
                "--cash-events", str(cash),
                "--opening-snapshot", str(opening),
                "--closing-snapshot", str(closing),
                "--coverage-manifest", str(coverage),
                "--evidence-root", str(evidence),
                "--output", str(output),
            ]
            self.assertEqual(main(args), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["exact"])
            self.assertTrue(payload["coverage_audit"]["verified"])
            self.assertEqual(payload["opening_boundary"], "START_OF_DAY")
            self.assertEqual(payload["closing_boundary"], "END_OF_DAY")

            # Mutating an original source revokes exactness.
            trade_doc.write_bytes(b"changed-source")
            self.assertEqual(main(args), 5)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(payload["exact"])
            self.assertIn("source_document_hash_mismatch:trade.bin", payload["blockers"])

            # Restoring the source but mutating a normalized input also revokes exactness.
            trade_doc.write_bytes(b"source-trade")
            fills.write_text(fills.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            self.assertEqual(main(args), 5)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(payload["exact"])
            self.assertIn("normalized_input_hash_mismatch:fills", payload["blockers"])


if __name__ == "__main__":
    unittest.main()
