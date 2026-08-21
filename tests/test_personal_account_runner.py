from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.reconcile_actual_personal_account import main


class PersonalAccountRunnerTests(unittest.TestCase):
    def _csv(self, path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_runner_requires_complete_source_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            evidence.mkdir()
            doc_a = evidence / "doc_a.bin"
            doc_b = evidence / "doc_b.bin"
            doc_a.write_bytes(b"source-a")
            doc_b.write_bytes(b"source-b")
            hash_a = hashlib.sha256(doc_a.read_bytes()).hexdigest()
            hash_b = hashlib.sha256(doc_b.read_bytes()).hexdigest()

            fills = root / "fills.csv"
            cash = root / "cash.csv"
            opening = root / "opening.json"
            closing = root / "closing.json"
            coverage = root / "coverage.json"
            output = root / "result.json"

            self._csv(
                fills,
                ["trade_date", "settlement_date", "sequence", "execution_id", "order_id", "side", "ticker", "shares", "price", "source_document", "source_sha256"],
                [{"trade_date": "2026-01-02", "settlement_date": "2026-01-06", "sequence": 10, "execution_id": "e1", "order_id": "o1", "side": "BUY", "ticker": "ABCD3", "shares": 10, "price": 10, "source_document": "doc_a.bin", "source_sha256": hash_a}],
            )
            self._csv(
                cash,
                ["value_date", "sequence", "event_id", "kind", "amount", "ticker", "source_document", "source_sha256"],
                [{"value_date": "2026-01-06", "sequence": 20, "event_id": "fee", "kind": "B3_FEE", "amount": -0.10, "ticker": "ABCD3", "source_document": "doc_a.bin", "source_sha256": hash_a}],
            )
            opening.write_text(
                json.dumps({"schema_version": 1, "value_date": "2026-01-01", "boundary": "START_OF_DAY", "cash_balance": 1000.0, "positions": {}, "source_document": "doc_b.bin", "source_sha256": hash_b}),
                encoding="utf-8",
            )
            closing.write_text(
                json.dumps({"schema_version": 1, "value_date": "2026-01-06", "boundary": "END_OF_DAY", "cash_balance": 899.90, "positions": {"ABCD3": 10}, "source_document": "doc_b.bin", "source_sha256": hash_b}),
                encoding="utf-8",
            )
            coverage.write_text(
                json.dumps({
                    "schema_version": 1,
                    "coverage_start": "2026-01-01",
                    "coverage_end": "2026-01-06",
                    "coverage_complete": True,
                    "reviewed_by": "test",
                    "reviewed_at_utc": "2026-01-07T12:00:00+00:00",
                    "documents": [
                        {"path": "doc_a.bin", "sha256": hash_a, "kind": "source"},
                        {"path": "doc_b.bin", "sha256": hash_b, "kind": "source"}
                    ]
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

            doc_a.write_bytes(b"changed")
            self.assertEqual(main(args), 5)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(payload["exact"])
            self.assertIn("source_document_hash_mismatch:doc_a.bin", payload["blockers"])


if __name__ == "__main__":
    unittest.main()
