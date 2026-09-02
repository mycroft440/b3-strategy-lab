from __future__ import annotations

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

from b3_strategy_lab.cotahist import CotahistError
from b3_strategy_lab.point_in_time import (
    KNOWN_COTAHIST_OHLC_ENVELOPE_REPAIRS,
    read_fractional_cotahist,
    read_standard_company_equity_cotahist,
)


EALT3_20200608_RAW = (
    "012020060802EALT3       010ACO ALTONA  ON  EDJ      R$  "
    "000000000202100000000025100000000001843000000000217300000000018400"
    "000000001840000000000197800257000000000000045700000000000099348100"
    "000000000000009999123100000010000000000000BREALTACNOR4133"
)


def cotahist_line(
    *,
    ticker: str,
    specification: str,
    bdi_code: str,
    market_type: str,
    open_: float,
    high: float,
    low: float,
    close: float,
) -> str:
    chars = [" "] * 245

    def put(start: int, end: int, value: str) -> None:
        if len(value) != end - start:
            raise AssertionError((start, end, value))
        chars[start:end] = value

    def integer(start: int, end: int, value: int) -> None:
        put(start, end, f"{value:0{end - start}d}")

    put(0, 2, "01")
    put(2, 10, "20200608")
    put(10, 12, bdi_code)
    put(12, 24, ticker.ljust(12))
    put(24, 27, market_type)
    put(27, 39, "EMPRESA TEST".ljust(12))
    put(39, 49, specification.ljust(10))
    for start, end, value in (
        (56, 69, open_),
        (69, 82, high),
        (82, 95, low),
        (108, 121, close),
    ):
        integer(start, end, round(value * 100))
    integer(147, 152, 10)
    integer(152, 170, 1_000)
    integer(170, 188, 1_000_000)
    integer(210, 217, 1)
    put(230, 242, "BRTESTACNOR0")
    integer(242, 245, 1)
    return "".join(chars)


def envelope(details: list[str]) -> str:
    header = "00" + " " * 243
    trailer = [" "] * 245
    trailer[0:2] = "99"
    trailer[31:42] = f"{len(details):011d}"
    return "\n".join([header, *details, "".join(trailer)]) + "\n"


class PointInTimeCotahistFilterTests(unittest.TestCase):
    def _write(self, content: str) -> Path:
        directory = Path(tempfile.mkdtemp())
        path = directory / "COTAHIST_TEST.TXT"
        path.write_text(content, encoding="latin-1")
        self.addCleanup(lambda: shutil.rmtree(directory, ignore_errors=True))
        return path

    def test_non_equity_bad_ohlc_cannot_break_standard_stock_reader(self) -> None:
        bad_non_equity = cotahist_line(
            ticker="BOAC34",
            specification="DRN",
            bdi_code="02",
            market_type="010",
            open_=10.0,
            high=9.0,
            low=8.0,
            close=9.0,
        )
        good_equity = cotahist_line(
            ticker="PETR4",
            specification="PN N2",
            bdi_code="02",
            market_type="010",
            open_=30.0,
            high=31.0,
            low=29.0,
            close=30.5,
        )

        quotes = read_standard_company_equity_cotahist(
            self._write(envelope([bad_non_equity, good_equity]))
        )

        self.assertEqual([quote.ticker for quote in quotes], ["PETR4"])

    def test_standard_reader_keeps_recovery_extrajudicial_equity(self) -> None:
        recovered = cotahist_line(
            ticker="BRKM5",
            specification="PNA N1",
            bdi_code="07",
            market_type="010",
            open_=4.56,
            high=4.70,
            low=4.10,
            close=4.11,
        )

        quotes = read_standard_company_equity_cotahist(
            self._write(envelope([recovered]))
        )

        self.assertEqual(len(quotes), 1)
        self.assertEqual(quotes[0].ticker, "BRKM5")
        self.assertEqual(quotes[0].bdi_code, "07")

    def test_unknown_positive_company_equity_bad_ohlc_still_fails_closed(self) -> None:
        bad_equity = cotahist_line(
            ticker="PETR4",
            specification="PN N2",
            bdi_code="02",
            market_type="010",
            open_=30.0,
            high=29.0,
            low=28.0,
            close=29.0,
        )

        with self.assertRaises(CotahistError):
            read_standard_company_equity_cotahist(
                self._write(envelope([bad_equity]))
            )

    def test_all_zero_standard_ohlc_is_unavailable_not_synthetic(self) -> None:
        zero_price = cotahist_line(
            ticker="BGIP4",
            specification="PN",
            bdi_code="02",
            market_type="010",
            open_=0.0,
            high=0.0,
            low=0.0,
            close=0.0,
        )
        good_equity = cotahist_line(
            ticker="PETR4",
            specification="PN N2",
            bdi_code="02",
            market_type="010",
            open_=30.0,
            high=31.0,
            low=29.0,
            close=30.5,
        )

        quotes = read_standard_company_equity_cotahist(
            self._write(envelope([zero_price, good_equity]))
        )

        self.assertEqual([quote.ticker for quote in quotes], ["PETR4"])

    def test_all_zero_fractional_ohlc_is_unavailable_not_synthetic(self) -> None:
        zero_price = cotahist_line(
            ticker="HETA4F",
            specification="PN",
            bdi_code="96",
            market_type="020",
            open_=0.0,
            high=0.0,
            low=0.0,
            close=0.0,
        )
        good_equity = cotahist_line(
            ticker="PETR4F",
            specification="PN N2",
            bdi_code="96",
            market_type="020",
            open_=30.0,
            high=31.0,
            low=29.0,
            close=30.5,
        )

        quotes = read_fractional_cotahist(
            self._write(envelope([zero_price, good_equity]))
        )

        self.assertEqual([quote.ticker for quote in quotes], ["PETR4F"])

    def test_hash_pinned_ealt3_envelope_repair_preserves_open_and_close(self) -> None:
        raw_hash = hashlib.sha256(EALT3_20200608_RAW.encode("latin-1")).hexdigest()
        self.assertIn(raw_hash, KNOWN_COTAHIST_OHLC_ENVELOPE_REPAIRS)

        quotes = read_standard_company_equity_cotahist(
            self._write(envelope([EALT3_20200608_RAW]))
        )

        self.assertEqual(len(quotes), 1)
        quote = quotes[0]
        self.assertEqual(quote.ticker, "EALT3")
        self.assertAlmostEqual(quote.open, 20.21)
        self.assertAlmostEqual(quote.high, 25.10)
        self.assertAlmostEqual(quote.low, 18.40)
        self.assertAlmostEqual(quote.close, 18.40)
        self.assertEqual(quote.trades, 257)
        self.assertEqual(quote.volume, 45_700)
        self.assertAlmostEqual(quote.financial_volume, 993_481.0)

    def test_fractional_reader_filters_non_equities_before_validation(self) -> None:
        bad_non_equity = cotahist_line(
            ticker="BOAC34F",
            specification="DRN",
            bdi_code="96",
            market_type="020",
            open_=10.0,
            high=9.0,
            low=8.0,
            close=9.0,
        )
        good_equity = cotahist_line(
            ticker="PETR4F",
            specification="PN N2",
            bdi_code="96",
            market_type="020",
            open_=30.0,
            high=31.0,
            low=29.0,
            close=30.5,
        )

        quotes = read_fractional_cotahist(
            self._write(envelope([bad_non_equity, good_equity]))
        )

        self.assertEqual([quote.ticker for quote in quotes], ["PETR4F"])


if __name__ == "__main__":
    unittest.main()
