from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from b3_strategy_lab.personal_account import (
    load_actual_fills,
    load_cash_events,
    load_position_events,
    load_snapshot,
    reconcile_actual_account,
)


DIGEST = "a" * 64


class PersonalAccountReconciliationTests(unittest.TestCase):
    def _csv(self, path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def _snapshot(
        self,
        path: Path,
        *,
        value_date: str,
        boundary: str,
        cash: float,
        positions: dict[str, int],
    ) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "value_date": value_date,
                    "boundary": boundary,
                    "cash_balance": cash,
                    "positions": positions,
                    "source_document": f"snapshot-{value_date}",
                    "source_sha256": DIGEST,
                }
            ),
            encoding="utf-8",
        )

    def test_ledger_reconciles_when_cash_and_positions_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fills = root / "fills.csv"
            cash = root / "cash.csv"
            positions = root / "position_events.csv"
            opening = root / "opening.json"
            closing = root / "closing.json"
            self._csv(
                fills,
                ["trade_date", "settlement_date", "sequence", "execution_id", "order_id", "side", "ticker", "shares", "price", "source_document", "source_sha256"],
                [
                    {"trade_date": "2026-01-02", "settlement_date": "2026-01-06", "sequence": 10, "execution_id": "e1", "order_id": "o1", "side": "BUY", "ticker": "ABCD3", "shares": 10, "price": 10, "source_document": "doc-1", "source_sha256": DIGEST},
                    {"trade_date": "2026-02-02", "settlement_date": "2026-02-04", "sequence": 10, "execution_id": "e2", "order_id": "o2", "side": "SELL", "ticker": "ABCD3", "shares": 4, "price": 12, "source_document": "doc-2", "source_sha256": DIGEST},
                ],
            )
            self._csv(
                cash,
                ["value_date", "sequence", "event_id", "kind", "amount", "ticker", "source_document", "source_sha256"],
                [
                    {"value_date": "2026-01-06", "sequence": 20, "event_id": "f1", "kind": "B3_FEE", "amount": -0.10, "ticker": "ABCD3", "source_document": "doc-1", "source_sha256": DIGEST},
                    {"value_date": "2026-02-04", "sequence": 20, "event_id": "f2", "kind": "B3_FEE", "amount": -0.05, "ticker": "ABCD3", "source_document": "doc-2", "source_sha256": DIGEST},
                    {"value_date": "2026-03-01", "sequence": 10, "event_id": "d1", "kind": "DIVIDEND", "amount": 6.00, "ticker": "ABCD3", "source_document": "doc-3", "source_sha256": DIGEST},
                ],
            )
            self._csv(
                positions,
                ["value_date", "sequence", "event_id", "ticker", "share_delta", "source_document", "source_sha256"],
                [],
            )
            self._snapshot(opening, value_date="2026-01-01", boundary="START_OF_DAY", cash=1000, positions={})
            self._snapshot(closing, value_date="2026-03-01", boundary="END_OF_DAY", cash=953.85, positions={"ABCD3": 6})
            result = reconcile_actual_account(
                opening_snapshot=load_snapshot(opening),
                closing_snapshot=load_snapshot(closing),
                fills=load_actual_fills(fills),
                cash_events=load_cash_events(cash),
                position_events=load_position_events(positions),
            )
            self.assertTrue(result.ledger_reconciles)
            self.assertEqual(result.blockers, ())
            payload = result.as_dict()
            self.assertEqual(payload["classification"], "PERSONAL_ACCOUNT_LEDGER_RECONCILED")
            self.assertNotIn("exact", payload)

    def test_missing_cent_blocks_ledger_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fills = root / "fills.csv"
            cash = root / "cash.csv"
            opening = root / "opening.json"
            closing = root / "closing.json"
            self._csv(
                fills,
                ["trade_date", "settlement_date", "sequence", "execution_id", "order_id", "side", "ticker", "shares", "price", "source_document", "source_sha256"],
                [{"trade_date": "2026-01-02", "settlement_date": "2026-01-06", "sequence": 0, "execution_id": "e1", "order_id": "o1", "side": "BUY", "ticker": "ABCD3", "shares": 10, "price": 10, "source_document": "doc-1", "source_sha256": DIGEST}],
            )
            self._csv(cash, ["value_date", "sequence", "event_id", "kind", "amount", "ticker", "source_document", "source_sha256"], [])
            self._snapshot(opening, value_date="2026-01-01", boundary="START_OF_DAY", cash=1000, positions={})
            self._snapshot(closing, value_date="2026-01-06", boundary="END_OF_DAY", cash=899.99, positions={"ABCD3": 10})
            result = reconcile_actual_account(
                opening_snapshot=load_snapshot(opening),
                closing_snapshot=load_snapshot(closing),
                fills=load_actual_fills(fills),
                cash_events=load_cash_events(cash),
                position_events=[],
            )
            self.assertFalse(result.ledger_reconciles)
            self.assertIn("cash_does_not_reconcile_to_cent", result.blockers)

    def test_duplicate_execution_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fills.csv"
            rows = [
                {"trade_date": "2026-01-02", "settlement_date": "2026-01-06", "sequence": 0, "execution_id": "same", "order_id": "o1", "side": "BUY", "ticker": "ABCD3", "shares": 1, "price": 10, "source_document": "doc", "source_sha256": DIGEST},
                {"trade_date": "2026-01-02", "settlement_date": "2026-01-06", "sequence": 1, "execution_id": "same", "order_id": "o1", "side": "BUY", "ticker": "ABCD3", "shares": 1, "price": 10, "source_document": "doc", "source_sha256": DIGEST},
            ]
            self._csv(path, list(rows[0]), rows)
            with self.assertRaisesRegex(ValueError, "duplicate execution_id"):
                load_actual_fills(path)

    def test_settlement_before_trade_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fills.csv"
            row = {"trade_date": "2026-01-06", "settlement_date": "2026-01-02", "sequence": 0, "execution_id": "e1", "order_id": "o1", "side": "BUY", "ticker": "ABCD3", "shares": 1, "price": 10, "source_document": "doc", "source_sha256": DIGEST}
            self._csv(path, list(row), [row])
            with self.assertRaisesRegex(ValueError, "settlement_date precedes trade_date"):
                load_actual_fills(path)

    def test_invalid_source_hash_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fills.csv"
            row = {"trade_date": "2026-01-02", "settlement_date": "2026-01-06", "sequence": 0, "execution_id": "e1", "order_id": "o1", "side": "BUY", "ticker": "ABCD3", "shares": 1, "price": 10, "source_document": "doc", "source_sha256": "not-a-hash"}
            self._csv(path, list(row), [row])
            with self.assertRaisesRegex(ValueError, "source_sha256"):
                load_actual_fills(path)

    def test_snapshot_boundary_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshot.json"
            path.write_text(
                json.dumps({"schema_version": 1, "value_date": "2026-01-01", "cash_balance": 100, "positions": {}, "source_document": "doc", "source_sha256": DIGEST}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "boundary"):
                load_snapshot(path)

    def test_opening_and_closing_boundary_roles_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            opening = root / "opening.json"
            closing = root / "closing.json"
            self._snapshot(opening, value_date="2026-01-01", boundary="END_OF_DAY", cash=100, positions={})
            self._snapshot(closing, value_date="2026-01-02", boundary="START_OF_DAY", cash=100, positions={})
            with self.assertRaisesRegex(ValueError, "opening snapshot must use boundary=START_OF_DAY"):
                reconcile_actual_account(
                    opening_snapshot=load_snapshot(opening),
                    closing_snapshot=load_snapshot(closing),
                    fills=[],
                    cash_events=[],
                    position_events=[],
                )

    def test_ticker_change_can_reconcile_with_position_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            opening = root / "opening.json"
            closing = root / "closing.json"
            positions = root / "positions.csv"
            self._snapshot(opening, value_date="2026-01-01", boundary="START_OF_DAY", cash=100, positions={"OLD3": 5})
            self._snapshot(closing, value_date="2026-01-02", boundary="END_OF_DAY", cash=100, positions={"NEW3": 5})
            self._csv(
                positions,
                ["value_date", "sequence", "event_id", "ticker", "share_delta", "source_document", "source_sha256"],
                [
                    {"value_date": "2026-01-02", "sequence": 1, "event_id": "rename-out", "ticker": "OLD3", "share_delta": -5, "source_document": "doc", "source_sha256": DIGEST},
                    {"value_date": "2026-01-02", "sequence": 2, "event_id": "rename-in", "ticker": "NEW3", "share_delta": 5, "source_document": "doc", "source_sha256": DIGEST},
                ],
            )
            result = reconcile_actual_account(
                opening_snapshot=load_snapshot(opening),
                closing_snapshot=load_snapshot(closing),
                fills=[],
                cash_events=[],
                position_events=load_position_events(positions),
            )
            self.assertTrue(result.ledger_reconciles)


if __name__ == "__main__":
    unittest.main()
