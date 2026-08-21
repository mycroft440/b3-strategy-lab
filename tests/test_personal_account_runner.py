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

    def test_runner_requires_ledger_and_byte_verified_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            evidence.mkdir()
            note = evidence / "note.pdf"
            statement = evidence / "statement.pdf"
            note.write_bytes(b"actual-note-bytes")
            statement.write_bytes(b"actual-statement-bytes")
            note_hash = hashlib.sha256(note.read_bytes()).hexdigest()
            statement_hash = hashlib.sha256(statement.read_bytes()).hexdigest()

            fills = root / "fills.csv"
            cash = root / "cash.csv"
            opening = root / "opening.json"
            closing = root / "closing.json"
            output = root / "result.json"

            self._csv(
                fills,
                ["trade_date", "settlement_date", "sequence", "execution_id", "order_id", "side", "ticker", "shares", "price", "source_document", "source_sha256"],
                [{"trade_date": "2026-01-02", "settlement_date": "2026-01-06", "sequence": 10, "execution_id": "e1", "order_id": "o1", "side": "BUY", "ticker": "ABCD3", "shares": 10, "price": 10, "source_document": "note.pdf", "source_sha256": note_hash}],
            )
            self._csv(
                cash,
                ["value_date", "sequence", "event_id", "kind", "amount", "ticker", "source_document", "source_sha256"],
                [{"value_date": "2026-01-06", "sequence": 20, "event_id": "fee", "kind": "B3_FEE", "amount": -0.10, "ticker": "ABCD3", "source_document": "note.pdf", "source_sha256": note_hash}],
            )
            opening.write_text(
                json.dumps({"schema_version": 1, "value_date": "2026-01-01", "cash_balance": 1000.0, "positions": {}, "source_document": "statement.pdf", "source_sha256": statement_hash}),
                encoding="utf-8",
            )
            closing.write_text(
                json.dumps({"schema_version": 1, "value_date": "2026-01-06", "cash_balance": 899.90, "positions": {"ABCD3": 10}, "source_document": "statement.pdf", "source_sha256": statement_hash}),
                encoding="utf-8",
            )

            code = main(
                [
                    "--fills", str(fills),
                    "--cash-events", str(cash),
                    "--opening-snapshot", str(opening),
                    "--closing-snapshot", str(closing),
                    "--evidence-root", str(evidence),
                    "--output", str(output),
                ]
            )
            self.assertEqual(code, 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["exact"])
            self.assertEqual(
                payload["classification"],
                "ACTUAL_PERSONAL_ACCOUNT_EXACT_RECONCILIATION",
            )
            self.assertTrue(payload["source_evidence"]["verified"])

            # Mutating a source file after normalization must revoke exactness.
            note.write_bytes(b"tampered")
            code = main(
                [
                    "--fills", str(fills),
                    "--cash-events", str(cash),
                    "--opening-snapshot", str(opening),
                    "--closing-snapshot", str(closing),
                    "--evidence-root", str(evidence),
                    "--output", str(output),
                ]
            )
            self.assertEqual(code, 5)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(payload["exact"])
            self.assertIn("source_document_hash_mismatch:note.pdf", payload["blockers"])


if __name__ == "__main__":
    unittest.main()
