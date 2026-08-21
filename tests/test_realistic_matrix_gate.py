from __future__ import annotations

import csv
import gzip
from pathlib import Path

from scripts.validate_matrix_top_realistically import _top_rows, _write_markdown


def test_top_rows_prefers_explicit_matrix_rank(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.csv.gz"
    fields = [
        "rank",
        "trading_strategy",
        "management_strategy",
        "total_return",
        "cagr",
    ]
    with gzip.open(matrix, "wt", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "rank": 2,
                "trading_strategy": "second",
                "management_strategy": "m2",
                "total_return": 10,
                "cagr": 0.4,
            }
        )
        writer.writerow(
            {
                "rank": 1,
                "trading_strategy": "first",
                "management_strategy": "m1",
                "total_return": 9,
                "cagr": 0.3,
            }
        )

    rows = _top_rows(matrix, 1)
    assert len(rows) == 1
    assert rows[0]["trading_strategy"] == "first"


def test_top_rows_deduplicates_strategy_management_pairs(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.csv"
    fields = [
        "rank",
        "trading_strategy",
        "management_strategy",
        "total_return",
        "cagr",
    ]
    with matrix.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "rank": 1,
                "trading_strategy": "a",
                "management_strategy": "m",
                "total_return": 3,
                "cagr": 0.3,
            }
        )
        writer.writerow(
            {
                "rank": 2,
                "trading_strategy": "a",
                "management_strategy": "m",
                "total_return": 2,
                "cagr": 0.2,
            }
        )
        writer.writerow(
            {
                "rank": 3,
                "trading_strategy": "b",
                "management_strategy": "n",
                "total_return": 1,
                "cagr": 0.1,
            }
        )

    rows = _top_rows(matrix, 2)
    assert [(row["trading_strategy"], row["management_strategy"]) for row in rows] == [
        ("a", "m"),
        ("b", "n"),
    ]


def test_markdown_preserves_realistic_validity_flags(tmp_path: Path) -> None:
    path = tmp_path / "TOP_REALISTIC.md"
    _write_markdown(
        [
            {
                "fast_rank": 1,
                "strategy": "demo",
                "management": "manager",
                "fast_cagr": 0.5,
                "realistic_cagr": 0.2,
                "realistic_total_return": 1.0,
                "realistic_max_drawdown": -0.3,
                "validity": "REALISTIC_POINT_IN_TIME__UNCERTIFIED_CASH_EVENTS",
            }
        ],
        path,
    )
    text = path.read_text(encoding="utf-8")
    assert "UNCERTIFIED_CASH_EVENTS" in text
    assert "nenhum CAGR da matriz rapida" in text
