from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from b3_strategy_lab.candles import Candle, save_actions, save_candles
from b3_strategy_lab.cotahist import (
    create_manifest,
    manifest_path,
    source_archive,
    write_manifest,
)
from scripts.organize_market_data import (
    _inventory_row,
    quarantine_files,
    to_heikin_ashi,
)


class HeikinAshiTests(unittest.TestCase):
    def test_preserves_raw_and_split_normalized_heikin_ashi_bases(self) -> None:
        candle = Candle(
            date="2024-01-02",
            ticker="TEST3",
            source_symbol="TEST3",
            open=4.0,
            high=6.0,
            low=3.0,
            close=5.0,
            adj_close=5.0,
            volume=100,
            raw_open=8.0,
            raw_high=12.0,
            raw_low=6.0,
            raw_close=10.0,
            adjustment_factor=0.5,
            source_high=12.0,
            source_low=6.0,
        )

        result = to_heikin_ashi([candle])

        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0].open, 4.5)
        self.assertAlmostEqual(result[0].high, 6.0)
        self.assertAlmostEqual(result[0].low, 3.0)
        self.assertAlmostEqual(result[0].close, 4.5)
        self.assertAlmostEqual(result[0].raw_close, 9.0)
        self.assertEqual(result[0].adjustment_factor, 0.5)


class QuarantineTests(unittest.TestCase):
    def test_removes_source_when_identical_copy_is_already_quarantined(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_root = root / "source"
            destination_root = root / "legacy"
            source = source_root / "nested" / "sample.csv"
            destination = destination_root / "nested" / "sample.csv"
            source.parent.mkdir(parents=True)
            destination.parent.mkdir(parents=True)
            source.write_bytes(b"same bytes\n")
            destination.write_bytes(b"same bytes\n")

            count = quarantine_files([source], source_root, destination_root)

            self.assertEqual(count, 1)
            self.assertFalse(source.exists())
            self.assertEqual(destination.read_bytes(), b"same bytes\n")

    def test_refuses_to_overwrite_different_quarantined_content(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_root = root / "source"
            destination_root = root / "legacy"
            source = source_root / "sample.csv"
            destination = destination_root / "sample.csv"
            source_root.mkdir(parents=True)
            destination_root.mkdir(parents=True)
            source.write_bytes(b"new\n")
            destination.write_bytes(b"old\n")

            with self.assertRaises(FileExistsError):
                quarantine_files([source], source_root, destination_root)

            self.assertEqual(source.read_bytes(), b"new\n")
            self.assertEqual(destination.read_bytes(), b"old\n")


class InventoryTests(unittest.TestCase):
    def test_price_only_is_ready_when_cash_actions_are_unverified(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            candle_file = save_candles(
                [
                    Candle(
                        "2024-01-02",
                        "TEST3",
                        "TEST3",
                        10.0,
                        10.0,
                        10.0,
                        10.0,
                        10.0,
                        100,
                        10.0,
                        10.0,
                        10.0,
                        10.0,
                        1.0,
                        source_high=10.0,
                        source_low=10.0,
                    ),
                    Candle(
                        "2024-01-03",
                        "TEST3",
                        "TEST3",
                        11.0,
                        11.0,
                        11.0,
                        11.0,
                        11.0,
                        100,
                        11.0,
                        11.0,
                        11.0,
                        11.0,
                        1.0,
                        source_high=11.0,
                        source_low=11.0,
                    ),
                ],
                root / "candles" / "test3_1d.csv",
            )
            action_file = save_actions([], root / "actions" / "test3_actions.csv")
            archive_file = root / "COTAHIST_A2024.ZIP"
            archive_file.write_bytes(b"official fixture")
            split_evidence = root / "split_evidence.json"
            split_evidence.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "coverage_start": "2024-01-01",
                        "ticker_reviews": [
                            {
                                "ticker": "TEST3",
                                "source_authority": "B3",
                                "source_url": "https://example.test/b3-official",
                            }
                        ],
                        "events": [],
                    }
                ),
                encoding="utf-8",
            )
            manifests_dir = root / "manifests"
            write_manifest(
                create_manifest(
                    ticker="TEST3",
                    interval="1d",
                    candles_path=candle_file,
                    actions_path=action_file,
                    source_archives=[source_archive(archive_file, 2024)],
                    split_evidence_path=split_evidence,
                ),
                manifest_path("TEST3", "1d", manifests_dir),
            )

            row = _inventory_row(
                "TEST3",
                "candles",
                "1d",
                candle_file,
                0,
                manifests_dir,
            )

            self.assertEqual(row["status"], "ok_retorno_preco")
            self.assertEqual(row["ready_for_backtest"], "sim")
            self.assertEqual(row["action_status"], "unverified")
            self.assertEqual(row["issues"], "")


if __name__ == "__main__":
    unittest.main()
