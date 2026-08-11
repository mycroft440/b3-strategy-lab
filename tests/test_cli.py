from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

from b3_strategy_lab.cli import (
    _actions_for_candles,
    _load_or_fetch_for_backtest,
    _signal_candles,
)
from b3_strategy_lab.candles import (
    DEFAULT_ACTIONS_DIR,
    DEFAULT_DATA_DIR,
    Candle,
    CorporateAction,
    save_actions,
)
from b3_strategy_lab.cotahist import (
    DataVerificationError,
    create_manifest,
    manifest_path,
    save_verified_candles,
    source_archive,
    write_manifest,
)


def candle(day: str, open_: float, close: float) -> Candle:
    return Candle(
        date=day,
        ticker="TEST3",
        source_symbol="TEST3.SA",
        open=open_,
        high=max(open_, close),
        low=min(open_, close),
        close=close,
        adj_close=close,
        volume=1000,
        raw_open=open_,
        raw_high=max(open_, close),
        raw_low=min(open_, close),
        raw_close=close,
        adjustment_factor=1.0,
        source_high=max(open_, close),
        source_low=min(open_, close),
    )


class CliWindowTests(unittest.TestCase):
    def test_signal_modes_keep_price_and_volume_on_the_same_basis(self) -> None:
        original = Candle(
            date="2024-01-02",
            ticker="TEST3",
            source_symbol="TEST3",
            open=10.0,
            high=11.0,
            low=9.0,
            close=10.5,
            adj_close=10.5,
            volume=3_000,
            raw_open=30.0,
            raw_high=33.0,
            raw_low=27.0,
            raw_close=31.5,
            adjustment_factor=1 / 3,
            raw_volume=1_000,
        )

        adjusted = _signal_candles([original], "adjusted")[0]
        raw = _signal_candles([original], "raw")[0]

        self.assertIs(adjusted, original)
        self.assertEqual((adjusted.close, adjusted.volume), (10.5, 3_000))
        self.assertEqual((raw.close, raw.volume), (31.5, 1_000))
        self.assertEqual(raw.adjustment_factor, 1.0)

    def test_weekly_action_filter_keeps_actions_inside_last_weekly_candle(self) -> None:
        candles = [
            candle("2024-01-01", 100.0, 100.0),
            candle("2024-01-08", 100.0, 100.0),
        ]
        actions = [
            CorporateAction("2024-01-10", "TEST3", "TEST3.SA", dividend=1.0, split_ratio=1.0),
            CorporateAction("2024-01-15", "TEST3", "TEST3.SA", dividend=2.0, split_ratio=1.0),
        ]

        filtered = _actions_for_candles(actions, candles, "1wk")

        self.assertEqual([action.date for action in filtered], ["2024-01-10"])

    def test_daily_action_filter_stops_on_last_daily_candle(self) -> None:
        candles = [
            candle("2024-01-01", 100.0, 100.0),
            candle("2024-01-02", 100.0, 100.0),
        ]
        actions = [
            CorporateAction("2024-01-02", "TEST3", "TEST3.SA", dividend=1.0, split_ratio=1.0),
            CorporateAction("2024-01-03", "TEST3", "TEST3.SA", dividend=2.0, split_ratio=1.0),
        ]

        filtered = _actions_for_candles(actions, candles, "1d")

        self.assertEqual([action.date for action in filtered], ["2024-01-02"])


class SafeDataLoadingTests(unittest.TestCase):
    def test_price_only_accepts_verified_prices_and_raw_events_stays_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            data_dir = root / "candles"
            actions_dir = root / "actions"
            manifests_dir = root / "manifests"
            candle_file = save_verified_candles(
                [
                    candle("2024-01-01", 10.0, 10.0),
                    candle("2024-01-02", 11.0, 11.0),
                ],
                data_dir / "test3_1d.csv",
            )
            action_file = save_actions([], actions_dir / "test3_actions.csv")
            archive_file = root / "COTAHIST_A2024.ZIP"
            archive_file.write_bytes(b"official fixture")
            write_manifest(
                create_manifest(
                    ticker="TEST3",
                    interval="1d",
                    candles_path=candle_file,
                    actions_path=action_file,
                    source_archives=[source_archive(archive_file, 2024)],
                ),
                manifest_path("TEST3", "1d", manifests_dir),
            )
            args = argparse.Namespace(
                interval="1d",
                data_dir=str(data_dir),
                actions_dir=str(actions_dir),
                manifests_dir=str(manifests_dir),
                start=None,
                end=None,
                refresh_data=False,
                allow_unverified_data=False,
                allow_unverified_actions=False,
                price_mode="price_only",
            )

            loaded = _load_or_fetch_for_backtest("TEST3", args)
            self.assertEqual(len(loaded), 2)

            args.price_mode = "raw_events"
            with self.assertRaises(DataVerificationError):
                _load_or_fetch_for_backtest("TEST3", args)

            args.allow_unverified_actions = True
            loaded = _load_or_fetch_for_backtest("TEST3", args)
            self.assertEqual(len(loaded), 2)

    def test_legacy_refresh_cannot_overwrite_canonical_directories(self) -> None:
        args = argparse.Namespace(
            interval="1d",
            data_dir=str(DEFAULT_DATA_DIR),
            actions_dir=str(DEFAULT_ACTIONS_DIR),
            manifests_dir="data/manifests",
            start=None,
            end=None,
            refresh_data=True,
            allow_unverified_data=True,
            allow_unverified_actions=True,
            price_mode="price_only",
        )

        with self.assertRaises(DataVerificationError):
            _load_or_fetch_for_backtest("PETR4", args)


if __name__ == "__main__":
    unittest.main()
