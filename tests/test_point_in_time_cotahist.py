from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from b3_strategy_lab.cotahist import CotahistError
from b3_strategy_lab.point_in_time import (
    read_fractional_cotahist,
    read_standard_company_equity_cotahist,
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

    def test_company_equity_bad_ohlc_still_fails_closed(self) -> None:
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
