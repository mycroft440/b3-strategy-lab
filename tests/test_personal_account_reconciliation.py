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


class PersonalAccountReconciliationTests(unittest.TestCase):
    def _csv(self, path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_exact_reconciliation_requires_cash_and_positions_to_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fills = root / "fills.csv"
            cash = root / "cash.csv"
            positions = root / "position_events.csv"
            snapshot = root / "snapshot.json"
            self._csv(
                fills,
                ["trade_date", "settlement_date", "execution_id", "order_id", "side", "ticker", "shares", "price", "source_document"],
                [
                    {"trade_date": "2026-01-02", "settlement_date": "2026-01-06", "execution_id": "e1", "order_id": "o1", "side": "BUY", "ticker": "ABCD3", "shares": 10, "price": 10, "source_document": "note-1"},
                    {"trade_date": "2026-02-02", "settlement_date": "2026-02-04", "execution_id": "e2", "order_id": "o2", "side": "SELL", "ticker": "ABCD3", "shares": 4, "price": 12, "source_document": "note-2"},
                ],
            )
            self._csv(
                cash,
                ["value_date", "event_id", "kind", "amount", "ticker", "source_document"],
                [
                    {"value_date": "2026-01-06", "event_id": "f1", "kind": "B3_FEE", "amount": -0.10, "ticker": "ABCD3", "source_document": "note-1"},
                    {"value_date": "2026-02-04", "event_id": "f2", "kind": "B3_FEE", "amount": -0.05, "ticker": "ABCD3", "source_document": "note-2"},
                    {"value_date": "2026-03-01", "event_id": "d1", "kind": "DIVIDEND", "amount": 6.00, "ticker": "ABCD3", "source_document": "statement-1"},
                ],
            )
            self._csv(
                positions,
                ["value_date", "event_id", "ticker", "share_delta", "source_document"],
                [],
            )
            # 1000 - 100 - .10 + 48 - .05 + 6 = 953.85; 6 shares remain.
            snapshot.write_text(
                json.dumps({"schema_version": 1, "value_date": "2026-03-01", "cash_balance": 953.85, "positions": {"ABCD3": 6}, "source_document": "broker-snapshot"}),
                encoding="utf-8",
            )
            result = reconcile_actual_account(
                start_cash=1000,
                fills=load_actual_fills(fills),
                cash_events=load_cash_events(cash),
                position_events=load_position_events(positions),
                snapshot=load_snapshot(snapshot),
            )
            self.assertTrue(result.exact)
            self.assertEqual(result.blockers, ())

    def test_missing_fee_cent_blocks_exact_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fills = root / "fills.csv"
            cash = root / "cash.csv"
            snapshot = root / "snapshot.json"
            self._csv(
                fills,
                ["trade_date", "settlement_date", "execution_id", "order_id", "side", "ticker", "shares", "price", "source_document"],
                [{"trade_date": "2026-01-02", "settlement_date": "2026-01-06", "execution_id": "e1", "order_id": "o1", "side": "BUY", "ticker": "ABCD3", "shares": 10, "price": 10, "source_document": "note-1"}],
            )
            self._csv(cash, ["value_date", "event_id", "kind", "amount", "ticker", "source_document"], [])
            snapshot.write_text(
                json.dumps({"schema_version": 1, "value_date": "2026-01-06", "cash_balance": 899.99, "positions": {"ABCD3": 10}, "source_document": "broker-snapshot"}),
                encoding="utf-8",
            )
            result = reconcile_actual_account(
                start_cash=1000,
                fills=load_actual_fills(fills),
                cash_events=load_cash_events(cash),
                position_events=[],
                snapshot=load_snapshot(snapshot),
            )
            self.assertFalse(result.exact)
            self.assertIn("cash_does_not_reconcile_to_cent", result.blockers)

    def test_duplicate_execution_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fills.csv"
            rows = [
                {"trade_date": "2026-01-02", "settlement_date": "2026-01-06", "execution_id": "same", "order_id": "o1", "side": "BUY", "ticker": "ABCD3", "shares": 1, "price": 10, "source_document": "note"},
                {"trade_date": "2026-01-02", "settlement_date": "2026-01-06", "execution_id": "same", "order_id": "o1", "side": "BUY", "ticker": "ABCD3", "shares": 1, "price": 10, "source_document": "note"},
            ]
            self._csv(path, list(rows[0]), rows)
            with self.assertRaisesRegex(ValueError, "duplicate execution_id"):
                load_actual_fills(path)


if __name__ == "__main__":
    unittest.main()
