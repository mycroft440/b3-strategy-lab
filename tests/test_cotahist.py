from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from b3_strategy_lab.candles import CorporateAction, save_actions, validate_candles
from b3_strategy_lab.cotahist import (
    CotahistError,
    DataVerificationError,
    OfficialQuote,
    build_verified_daily_candles,
    create_manifest,
    parse_cotahist_lines,
    resample_daily_to_weekly,
    save_verified_candles,
    source_archive,
    verify_split_evidence,
    verify_dataset,
    write_manifest,
)
from scripts.sync_official_universe import _read_official_quotes, _with_fractional_volume


def cotahist_line(
    *,
    ticker: str = "TEST3",
    quote_date: str = "20240102",
    open_: float = 10.0,
    high: float = 12.0,
    low: float = 9.0,
    close: float = 11.0,
    volume: int = 1_000,
    trades: int = 42,
    financial_volume: float = 10_500.0,
    quotation_factor: int = 1,
) -> str:
    chars = [" "] * 245

    def put(start: int, end: int, value: str) -> None:
        if len(value) != end - start:
            raise AssertionError((start, end, value))
        chars[start:end] = value

    def integer(start: int, end: int, value: int) -> None:
        put(start, end, f"{value:0{end - start}d}")

    put(0, 2, "01")
    put(2, 10, quote_date)
    put(10, 12, "02")
    put(12, 24, ticker.ljust(12))
    put(24, 27, "010")
    put(27, 39, "EMPRESA TEST".ljust(12))
    put(39, 49, "ON      NM".ljust(10))
    for start, end, value in (
        (56, 69, open_),
        (69, 82, high),
        (82, 95, low),
        (108, 121, close),
    ):
        integer(start, end, round(value * 100 * quotation_factor))
    integer(147, 152, trades)
    integer(152, 170, volume)
    integer(170, 188, round(financial_volume * 100))
    integer(210, 217, quotation_factor)
    put(230, 242, "BRTESTACNOR0")
    integer(242, 245, 123)
    return "".join(chars)


def cotahist_envelope(detail_lines: list[str], *, declared_count: int | None = None) -> list[str]:
    header = "00" + " " * 243
    trailer_chars = [" "] * 245
    trailer_chars[0:2] = "99"
    count = len(detail_lines) if declared_count is None else declared_count
    trailer_chars[31:42] = f"{count:011d}"
    return [header, *detail_lines, "".join(trailer_chars)]


def quote(
    day: str,
    *,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: int,
) -> OfficialQuote:
    return OfficialQuote(
        date=day,
        ticker="TEST3",
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        trades=10,
        financial_volume=volume * close,
        quotation_factor=1,
        bdi_code="02",
        market_type="010",
    )


class CotahistParsingTests(unittest.TestCase):
    def test_historical_cutoff_filters_later_fractional_anomaly_before_validation(self) -> None:
        standard = quote(
            "2024-01-02",
            open_=10.0,
            high=11.0,
            low=9.0,
            close=10.0,
            volume=1_000,
        )
        fractional_after_cutoff = OfficialQuote(
            date="2024-01-03",
            ticker="TEST3F",
            open=10.0,
            high=10.0,
            low=10.0,
            close=10.0,
            volume=100,
            trades=1,
            financial_volume=1_000.0,
            quotation_factor=1,
            bdi_code="02",
            market_type="020",
        )
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "COTAHIST_A2024.ZIP"
            archive.write_bytes(b"fixture")
            with (
                patch(
                    "scripts.sync_official_universe.read_cotahist",
                    return_value=[standard],
                ),
                patch(
                    "scripts.sync_official_universe.read_fractional_cotahist",
                    return_value=[fractional_after_cutoff],
                ),
            ):
                quotes, _sources = _read_official_quotes(
                    [(2024, archive)],
                    ["TEST3"],
                    exclude_date="2024-01-10",
                    end_date="2024-01-02",
                    require_standard_for_fractional_from="2024-01-01",
                )

        self.assertEqual([item.date for item in quotes["TEST3"]], ["2024-01-02"])

    def test_parses_fixed_width_prices_using_quotation_factor(self) -> None:
        parsed = parse_cotahist_lines(
            [
                cotahist_line(
                    quotation_factor=1_000,
                    open_=0.01349,
                    high=0.014,
                    low=0.0124,
                    close=0.013,
                    volume=7_800_000,
                    financial_volume=98_379.0,
                )
            ]
        )

        self.assertEqual(len(parsed), 1)
        self.assertAlmostEqual(parsed[0].open, 0.01349)
        self.assertAlmostEqual(parsed[0].close, 0.013)
        self.assertEqual(parsed[0].quotation_factor, 1_000)
        self.assertEqual(parsed[0].volume, 7_800_000)
        self.assertEqual(parsed[0].issuer_name, "EMPRESA TEST")
        self.assertEqual(parsed[0].specification, "ON      NM")
        self.assertEqual(parsed[0].isin, "BRTESTACNOR0")
        self.assertEqual(parsed[0].distribution_number, 123)

    def test_rejects_truncated_rows(self) -> None:
        with self.assertRaises(CotahistError):
            parse_cotahist_lines(["01short"])

    def test_validates_official_header_trailer_and_record_count(self) -> None:
        parsed = parse_cotahist_lines(
            cotahist_envelope([cotahist_line()]),
            require_envelope=True,
        )

        self.assertEqual(len(parsed), 1)

    def test_rejects_trailer_count_that_does_not_match_file(self) -> None:
        with self.assertRaises(CotahistError):
            parse_cotahist_lines(
                cotahist_envelope([cotahist_line()], declared_count=99),
                require_envelope=True,
            )


class VerifiedCandleTests(unittest.TestCase):
    def test_consolidates_fractional_activity_without_mixing_ohlc(self) -> None:
        standard = quote(
            "2024-01-02",
            open_=10.0,
            high=11.0,
            low=9.0,
            close=10.5,
            volume=1_000,
        )
        fractional = OfficialQuote(
            date="2024-01-02",
            ticker="TEST3F",
            open=10.1,
            high=10.8,
            low=9.2,
            close=10.4,
            volume=37,
            trades=12,
            financial_volume=380.0,
            quotation_factor=1,
            bdi_code="96",
            market_type="020",
        )

        consolidated = _with_fractional_volume(standard, fractional)
        candles, _warnings = build_verified_daily_candles(
            "TEST3",
            [consolidated],
            [],
        )

        self.assertEqual(consolidated.open, standard.open)
        self.assertEqual(consolidated.volume, 1_037)
        self.assertEqual(candles[0].raw_volume, 1_037)
        self.assertEqual(candles[0].fractional_raw_volume, 37)
        self.assertEqual(candles[0].fractional_trades, 12)
        self.assertEqual(candles[0].volume_scope, "consolidated_010_020")
        self.assertEqual(validate_candles(candles), [])

    def test_normalizes_prices_and_volume_but_ignores_cash_distributions(self) -> None:
        quotes = [
            quote("2024-01-01", open_=0.100, high=0.102, low=0.099, close=0.100, volume=1_000_000),
            quote("2024-01-02", open_=100.0, high=102.0, low=99.0, close=100.0, volume=1_000),
            quote("2024-01-03", open_=98.0, high=99.0, low=97.0, close=98.0, volume=1_200),
        ]
        actions = [
            CorporateAction("2024-01-02", "TEST3", "TEST3.SA", dividend=0.0, split_ratio=0.001),
            CorporateAction("2024-01-03", "TEST3", "TEST3.SA", dividend=2.0, split_ratio=1.0),
        ]

        candles, warnings = build_verified_daily_candles("TEST3", quotes, actions)

        self.assertEqual(warnings, [])
        self.assertAlmostEqual(candles[0].raw_close, 0.1)
        self.assertEqual(candles[0].raw_volume, 1_000_000)
        self.assertEqual(candles[0].volume, 1_000)
        self.assertAlmostEqual(candles[0].close, 100.0)
        self.assertAlmostEqual(candles[1].close, 100.0)
        self.assertAlmostEqual(candles[2].close, 98.0)
        self.assertEqual(
            [candle.adjustment_factor for candle in candles],
            [1_000.0, 1.0, 1.0],
        )
        self.assertEqual(validate_candles(candles), [])

    def test_same_day_cash_events_do_not_change_price_series(self) -> None:
        quotes = [
            quote("2024-01-01", open_=100.0, high=100.0, low=100.0, close=100.0, volume=100),
            quote("2024-01-02", open_=97.0, high=97.0, low=97.0, close=97.0, volume=100),
        ]
        actions = [
            CorporateAction("2024-01-02", "TEST3", "TEST3.SA", dividend=1.0, split_ratio=1.0),
            CorporateAction("2024-01-02", "TEST3", "TEST3.SA", dividend=2.0, split_ratio=1.0),
        ]

        candles, _warnings = build_verified_daily_candles("TEST3", quotes, actions)

        self.assertAlmostEqual(candles[0].adjustment_factor, 1.0)
        self.assertAlmostEqual(candles[0].close, 100.0)
        self.assertAlmostEqual(candles[1].close, 97.0)

    def test_ignores_actions_after_last_official_quote(self) -> None:
        quotes = [
            quote("2024-01-01", open_=100.0, high=100.0, low=100.0, close=100.0, volume=100),
            quote("2024-01-02", open_=100.0, high=100.0, low=100.0, close=100.0, volume=100),
        ]
        actions = [
            CorporateAction("2024-02-01", "TEST3", "TEST3.SA", dividend=10.0, split_ratio=2.0)
        ]

        candles, _warnings = build_verified_daily_candles("TEST3", quotes, actions)

        self.assertEqual([candle.adjustment_factor for candle in candles], [1.0, 1.0])
        self.assertEqual([candle.raw_close for candle in candles], [100.0, 100.0])

    def test_warns_when_split_normalization_leaves_a_large_price_jump(self) -> None:
        quotes = [
            quote("2024-01-01", open_=100.0, high=100.0, low=100.0, close=100.0, volume=100),
            quote("2024-01-02", open_=30.0, high=30.0, low=30.0, close=30.0, volume=300),
        ]
        actions = [
            CorporateAction("2024-01-02", "TEST3", "TEST3.SA", dividend=0.0, split_ratio=2.0)
        ]

        _candles, warnings = build_verified_daily_candles("TEST3", quotes, actions)

        self.assertEqual(
            warnings,
            [
                "TEST3 2024-01-02: variacao de fechamento apos "
                "normalizacao de split de -40.00%."
            ],
        )

    def test_weekly_ohlc_uses_split_normalized_price_only_basis(self) -> None:
        quotes = [
            quote("2024-01-01", open_=100.0, high=102.0, low=99.0, close=100.0, volume=100),
            quote("2024-01-02", open_=98.0, high=99.0, low=97.0, close=98.0, volume=200),
        ]
        actions = [
            CorporateAction("2024-01-02", "TEST3", "TEST3.SA", dividend=2.0, split_ratio=1.0)
        ]
        daily, _warnings = build_verified_daily_candles("TEST3", quotes, actions)

        weekly = resample_daily_to_weekly(daily)

        self.assertEqual(len(weekly), 1)
        self.assertAlmostEqual(weekly[0].open, 100.0)
        self.assertAlmostEqual(weekly[0].high, 102.0)
        self.assertAlmostEqual(weekly[0].raw_open, 100.0)
        self.assertAlmostEqual(weekly[0].raw_high, 102.0)
        self.assertAlmostEqual(weekly[0].close, 98.0)
        self.assertEqual(weekly[0].volume, 300)
        self.assertEqual(validate_candles(weekly), [])

    def test_weekly_raw_ohlc_preserves_scale_change_inside_split_week(self) -> None:
        quotes = [
            quote("2024-01-01", open_=100.0, high=102.0, low=99.0, close=100.0, volume=100),
            quote("2024-01-02", open_=10.0, high=10.2, low=9.9, close=10.0, volume=1_000),
        ]
        actions = [
            CorporateAction("2024-01-02", "TEST3", "B3", dividend=0.0, split_ratio=10.0)
        ]

        daily, _warnings = build_verified_daily_candles("TEST3", quotes, actions)
        weekly = resample_daily_to_weekly(daily)

        self.assertAlmostEqual(weekly[0].open, 10.0)
        self.assertAlmostEqual(weekly[0].close, 10.0)
        self.assertAlmostEqual(weekly[0].raw_high, 102.0)
        self.assertAlmostEqual(weekly[0].raw_low, 9.9)
        self.assertEqual(validate_candles(weekly), [])


class DatasetManifestTests(unittest.TestCase):
    def test_split_evidence_requires_matching_official_ratio(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            action_file = save_actions(
                [CorporateAction("2024-01-02", "TEST3", "B3", 0.0, 2.0)],
                root / "test3_actions.csv",
            )
            evidence_file = root / "split_evidence.json"
            evidence = {
                "schema_version": 1,
                "coverage_start": "2024-01-01",
                "ticker_reviews": [
                    {
                        "ticker": "TEST3",
                        "source_authority": "B3",
                        "source_url": "https://example.test/b3-official",
                    }
                ],
                "events": [
                    {
                        "ticker": "TEST3",
                        "ex_date": "2024-01-02",
                        "split_ratio": 2.0,
                        "source_authority": "B3",
                        "source_url": "https://example.test/b3-official",
                    }
                ],
            }
            evidence_file.write_text(json.dumps(evidence), encoding="utf-8")

            self.assertEqual(
                verify_split_evidence("TEST3", action_file, evidence_file),
                "2024-01-01",
            )
            evidence["events"][0]["split_ratio"] = 3.0
            evidence_file.write_text(json.dumps(evidence), encoding="utf-8")
            with self.assertRaises(DataVerificationError):
                verify_split_evidence("TEST3", action_file, evidence_file)

    def test_split_evidence_rejects_official_event_missing_from_local_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            action_file = save_actions([], root / "test3_actions.csv")
            evidence_file = root / "split_evidence.json"
            evidence_file.write_text(
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
                        "events": [
                            {
                                "ticker": "TEST3",
                                "ex_date": "2024-01-02",
                                "split_ratio": 2.0,
                                "source_authority": "B3",
                                "source_url": "https://example.test/b3-official",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(DataVerificationError):
                verify_split_evidence("TEST3", action_file, evidence_file)

    def test_point_in_time_split_evidence_schema_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            action_file = save_actions([], root / "test3_actions.csv")
            evidence_file = root / "point_in_time_splits.json"
            evidence_file.write_text(
                json.dumps(
                    {
                        "schema_version": 3,
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

            self.assertEqual(
                verify_split_evidence("TEST3", action_file, evidence_file),
                "2024-01-01",
            )

    def test_manifest_ignores_cash_changes_but_rejects_split_changes(self) -> None:
        quotes = [
            quote("2024-01-01", open_=10.0, high=10.0, low=10.0, close=10.0, volume=100),
            quote("2024-01-02", open_=11.0, high=11.0, low=11.0, close=11.0, volume=100),
        ]
        candles, _warnings = build_verified_daily_candles("TEST3", quotes, [])

        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            candle_file = save_verified_candles(candles, root / "test3_1d.csv")
            action_file = root / "test3_actions.csv"
            save_actions(
                [
                    CorporateAction(
                        "2024-01-02",
                        "TEST3",
                        "TEST3",
                        dividend=1.0,
                        split_ratio=2.0,
                    )
                ],
                action_file,
            )
            archive_file = root / "COTAHIST_A2024.ZIP"
            archive_file.write_bytes(b"official archive fixture")
            manifest_file = root / "test3_1d.json"
            write_manifest(
                create_manifest(
                    ticker="TEST3",
                    interval="1d",
                    candles_path=candle_file,
                    actions_path=action_file,
                    source_archives=[source_archive(archive_file, 2024)],
                ),
                manifest_file,
            )

            save_actions(
                [
                    CorporateAction(
                        "2024-01-02",
                        "TEST3",
                        "TEST3",
                        dividend=99.0,
                        split_ratio=2.0,
                    )
                ],
                action_file,
            )
            verify_dataset(candle_file, action_file, manifest_file)

            save_actions(
                [
                    CorporateAction(
                        "2024-01-02",
                        "TEST3",
                        "TEST3",
                        dividend=99.0,
                        split_ratio=3.0,
                    )
                ],
                action_file,
            )
            with self.assertRaises(DataVerificationError):
                verify_dataset(candle_file, action_file, manifest_file)

    def test_manifest_verifies_prices_but_rejects_uncertified_actions_for_backtest(self) -> None:
        quotes = [
            quote("2024-01-01", open_=10.0, high=10.0, low=10.0, close=10.0, volume=100),
            quote("2024-01-02", open_=11.0, high=11.0, low=11.0, close=11.0, volume=100),
        ]
        candles, _warnings = build_verified_daily_candles("TEST3", quotes, [])

        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            candle_file = save_verified_candles(candles, root / "test3_1d.csv")
            action_file = save_actions([], root / "test3_actions.csv")
            archive_file = root / "COTAHIST_A2024.ZIP"
            archive_file.write_bytes(b"official archive fixture")
            manifest_file = root / "test3_1d.json"
            manifest = create_manifest(
                ticker="TEST3",
                interval="1d",
                candles_path=candle_file,
                actions_path=action_file,
                source_archives=[source_archive(archive_file, 2024)],
            )
            write_manifest(manifest, manifest_file)

            verified = verify_dataset(candle_file, action_file, manifest_file)

            self.assertEqual(verified.status, "price_verified")
            self.assertEqual(verified.corporate_action_status, "unverified")
            self.assertIn("cash distributions excluded", verified.price_basis)
            self.assertIn("dividends and JCP ignored", verified.adjustment_method)
            with self.assertRaises(DataVerificationError):
                verify_dataset(
                    candle_file,
                    action_file,
                    manifest_file,
                    require_verified_actions=True,
                )

    def test_manifest_schema_five_remains_compatible(self) -> None:
        quotes = [
            quote("2024-01-01", open_=10.0, high=10.0, low=10.0, close=10.0, volume=100),
            quote("2024-01-02", open_=11.0, high=11.0, low=11.0, close=11.0, volume=100),
        ]
        candles, _warnings = build_verified_daily_candles("TEST3", quotes, [])

        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            candle_file = save_verified_candles(candles, root / "test3_1d.csv")
            action_file = save_actions([], root / "test3_actions.csv")
            archive_file = root / "COTAHIST_A2024.ZIP"
            archive_file.write_bytes(b"official archive fixture")
            manifest_file = root / "test3_1d.json"
            write_manifest(
                create_manifest(
                    ticker="TEST3",
                    interval="1d",
                    candles_path=candle_file,
                    actions_path=action_file,
                    source_archives=[source_archive(archive_file, 2024)],
                ),
                manifest_file,
            )
            payload = json.loads(manifest_file.read_text(encoding="utf-8"))
            self.assertIn("standard market 010", payload["volume_source"])
            self.assertIn("standard market 010 only", payload["volume_basis"])
            payload["schema_version"] = 5
            payload.pop("volume_source")
            payload.pop("volume_basis")
            manifest_file.write_text(json.dumps(payload), encoding="utf-8")

            verified = verify_dataset(candle_file, action_file, manifest_file)

            self.assertEqual(verified.schema_version, 5)
            self.assertEqual(verified.volume_basis, "legacy standard_010")

    def test_manifest_rejects_tampered_candles(self) -> None:
        quotes = [
            quote("2024-01-01", open_=10.0, high=10.0, low=10.0, close=10.0, volume=100),
            quote("2024-01-02", open_=11.0, high=11.0, low=11.0, close=11.0, volume=100),
        ]
        candles, _warnings = build_verified_daily_candles("TEST3", quotes, [])

        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            candle_file = save_verified_candles(candles, root / "test3_1d.csv")
            action_file = save_actions([], root / "test3_actions.csv")
            archive_file = root / "COTAHIST_A2024.ZIP"
            archive_file.write_bytes(b"official archive fixture")
            manifest_file = root / "test3_1d.json"
            write_manifest(
                create_manifest(
                    ticker="TEST3",
                    interval="1d",
                    candles_path=candle_file,
                    actions_path=action_file,
                    source_archives=[source_archive(archive_file, 2024)],
                ),
                manifest_file,
            )
            candle_file.write_text(candle_file.read_text(encoding="utf-8") + "\n", encoding="utf-8")

            with self.assertRaises(DataVerificationError):
                verify_dataset(candle_file, action_file, manifest_file)

    def test_manifest_rejects_unreviewed_price_warning(self) -> None:
        quotes = [
            quote("2024-01-01", open_=10.0, high=10.0, low=10.0, close=10.0, volume=100),
            quote("2024-01-02", open_=16.0, high=16.0, low=16.0, close=16.0, volume=100),
        ]
        candles, warnings = build_verified_daily_candles("TEST3", quotes, [])
        self.assertEqual(len(warnings), 1)

        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            candle_file = save_verified_candles(candles, root / "test3_1d.csv")
            action_file = save_actions([], root / "test3_actions.csv")
            archive_file = root / "COTAHIST_A2024.ZIP"
            archive_file.write_bytes(b"official archive fixture")
            manifest_file = root / "test3_1d.json"
            write_manifest(
                create_manifest(
                    ticker="TEST3",
                    interval="1d",
                    candles_path=candle_file,
                    actions_path=action_file,
                    source_archives=[source_archive(archive_file, 2024)],
                    warnings=warnings,
                ),
                manifest_file,
            )

            with self.assertRaises(DataVerificationError):
                verify_dataset(candle_file, action_file, manifest_file)

            write_manifest(
                create_manifest(
                    ticker="TEST3",
                    interval="1d",
                    candles_path=candle_file,
                    actions_path=action_file,
                    source_archives=[source_archive(archive_file, 2024)],
                    warnings=warnings,
                    warning_reviews={warnings[0]: "Conferido na fonte oficial."},
                ),
                manifest_file,
            )
            verify_dataset(candle_file, action_file, manifest_file)


if __name__ == "__main__":
    unittest.main()
