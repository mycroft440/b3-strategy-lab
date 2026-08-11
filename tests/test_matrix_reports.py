from __future__ import annotations

import csv
import gzip
import tempfile
import unittest
from pathlib import Path

from scripts.audit_matrix_results import _open_results, _report_base as audit_report_base
from scripts.backtest_strategy_management_combinations import (
    _report_base as backtest_report_base,
    _write_results,
)


class MatrixReportTests(unittest.TestCase):
    def test_csv_gzip_uses_the_same_sidecar_base(self) -> None:
        compressed = Path("reports/matrix.csv.gz")

        self.assertEqual(backtest_report_base(compressed), Path("reports/matrix"))
        self.assertEqual(audit_report_base(compressed), Path("reports/matrix"))

    def test_compressed_results_are_readable_and_deterministic(self) -> None:
        rows = [
            {
                "rank": 1,
                "trading_strategy": "money_flow_index",
                "management_strategy": "equal_weight",
                "total_return": 0.25,
            }
        ]
        with tempfile.TemporaryDirectory() as temporary_dir:
            output = Path(temporary_dir) / "matrix.csv.gz"

            _write_results(rows, output)
            first_bytes = output.read_bytes()
            _write_results(rows, output)

            self.assertEqual(output.read_bytes(), first_bytes)
            with gzip.open(output, mode="rt", encoding="utf-8", newline="") as source:
                self.assertEqual(
                    list(csv.DictReader(source))[0]["trading_strategy"],
                    "money_flow_index",
                )
            with _open_results(output) as source:
                self.assertEqual(len(list(csv.DictReader(source))), 1)


if __name__ == "__main__":
    unittest.main()
