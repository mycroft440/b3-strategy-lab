from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from b3_strategy_lab.cotahist import COMPANY_EQUITY_BDI_CODES
from b3_strategy_lab.point_in_time import read_standard_company_equity_cotahist


def _record(*, day: str, bdi: str, ticker: str, spec: str, close: float, isin: str, market: str = "010", factor: int = 1) -> str:
    line = [" "] * 245

    def put(start: int, end: int, value: str) -> None:
        width = end - start
        line[start:end] = list(value[:width].ljust(width))

    def num(start: int, end: int, value: int) -> None:
        width = end - start
        line[start:end] = list(f"{value:0{width}d}")

    put(0, 2, "01")
    put(2, 10, day.replace("-", ""))
    put(10, 12, bdi)
    put(12, 24, ticker)
    put(24, 27, market)
    put(27, 39, "GOL")
    put(39, 49, spec)
    raw = int(round(close * 100 * factor))
    for start, end in ((56, 69), (69, 82), (82, 95), (95, 108), (108, 121)):
        num(start, end, raw)
    num(147, 152, 10)
    num(152, 170, 1000)
    num(170, 188, raw * 1000)
    num(210, 217, factor)
    put(230, 242, isin)
    num(242, 245, 1)
    return "".join(line)


def _archive(rows: list[str], root: Path) -> Path:
    header = "00" + " " * 243
    trailer = [" "] * 245
    trailer[0:2] = list("99")
    trailer[31:42] = list(f"{len(rows):011d}")
    payload = "\n".join([header, *rows, "".join(trailer)]) + "\n"
    path = root / "COTAHIST_A2025.ZIP"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("COTAHIST_A2025.TXT", payload.encode("latin-1"))
    return path


class Bdi58Goll4RegressionTests(unittest.TestCase):
    def test_company_equity_candidate_codes_include_58_explicitly(self) -> None:
        self.assertIn("58", COMPANY_EQUITY_BDI_CODES)
        self.assertNotIn("10", COMPANY_EQUITY_BDI_CODES)

    def test_goll4_keeps_bdi58_history_between_standard_status_rows(self) -> None:
        rows = [
            _record(day="2024-01-29", bdi="02", ticker="GOLL4", spec="PN N2", close=3.93, isin="BRGOLLACNPR4"),
            _record(day="2024-01-30", bdi="58", ticker="GOLL4", spec="PN N2", close=2.87, isin="BRGOLLACNPR4"),
            _record(day="2024-06-07", bdi="58", ticker="GOLL4", spec="PN N2", close=1.10, isin="BRGOLLACNPR4"),
            _record(day="2025-06-06", bdi="58", ticker="GOLL4", spec="PN N2", close=1.10, isin="BRGOLLACNPR4"),
            _record(day="2025-06-09", bdi="02", ticker="GOLL4", spec="PN N2", close=1.23, isin="BRGOLLACNPR4"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            quotes = read_standard_company_equity_cotahist(_archive(rows, Path(directory)))
        self.assertEqual([q.bdi_code for q in quotes], ["02", "58", "58", "58", "02"])
        self.assertEqual(quotes[-2].date, "2025-06-06")
        self.assertAlmostEqual(quotes[-2].close, 1.10)
        self.assertAlmostEqual(quotes[-1].close, 1.23)
        self.assertGreater(quotes[-1].close / quotes[-2].close - 1.0, 0.0)
        adjacent_dates = [(a.date, b.date) for a, b in zip(quotes, quotes[1:])]
        self.assertNotIn(("2024-01-29", "2025-06-09"), adjacent_dates)

    def test_bdi58_is_not_a_blanket_acceptance_rule(self) -> None:
        rows = [
            _record(day="2025-01-02", bdi="58", ticker="GOOD4", spec="PN", close=10.0, isin="BRGOODACNPR4"),
            _record(day="2025-01-02", bdi="58", ticker="UNIT11", spec="UNT", close=10.0, isin="BRUNITCDAM18"),
            _record(day="2025-01-03", bdi="58", ticker="BADX", spec="PN", close=10.0, isin="BRBADXACNPR0"),
            _record(day="2025-01-04", bdi="58", ticker="GOOD4", spec="PN", close=10.0, isin="BRGOODACNPR4", market="020"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            quotes = read_standard_company_equity_cotahist(_archive(rows, Path(directory)))
        self.assertEqual(
            [(q.ticker, q.market_type, q.specification.strip()) for q in quotes],
            [("GOOD4", "010", "PN")],
        )


    def test_bdi58_keeps_alphanumeric_company_share_root(self) -> None:
        rows = [
            _record(
                day="2025-01-02",
                bdi="58",
                ticker="B3SA3",
                spec="ON NM",
                close=12.34,
                isin="BRB3SAACNOR6",
            ),
        ]
        with tempfile.TemporaryDirectory() as directory:
            quotes = read_standard_company_equity_cotahist(_archive(rows, Path(directory)))
        self.assertEqual([(q.ticker, q.bdi_code) for q in quotes], [("B3SA3", "58")])


if __name__ == "__main__":
    unittest.main()
