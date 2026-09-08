from datetime import date

import pytest

from b3_strategy_lab.benchmarks import benchmark_comparison, load_daily_benchmark
from scripts.sync_cdi_benchmark import normalize_payload


def test_cdi_units_are_daily_percent_not_annual():
    result = normalize_payload([{"data": "02/01/2024", "valor": "0.043739"}],
                               date(2024, 1, 1), date(2024, 1, 31))
    assert result == {"2024-01-02": 0.00043739}


def test_return_matching_benchmark_has_zero_excess():
    dates = ["2024-01-02", "2024-01-03", "2024-01-04"]
    reference = dict(zip(dates, [0.01, 0.02, 0.03]))
    result = benchmark_comparison(dates, [101, 103.02, 106.1106], 100, reference)
    assert result["benchmark_total_return"] == pytest.approx(0.061106)
    assert result["excess_total_return"] == pytest.approx(0)
    assert result["excess_sharpe"] == 0


def test_idle_cash_has_negative_excess():
    days = ["2024-01-02", "2024-01-03"]
    result = benchmark_comparison(days, [100, 100], 100, dict(zip(days, [0.01, 0.02])))
    assert result["excess_total_return"] < 0
    assert result["excess_sharpe"] < 0


def test_exchange_holiday_benchmark_accrual_is_preserved():
    result = benchmark_comparison(["2024-12-23", "2024-12-26"], [100, 100], 100,
                                  {"2024-12-23": 0.01, "2024-12-24": 0.02, "2024-12-26": 0.03})
    assert result["benchmark_total_return"] == pytest.approx(1.01 * 1.02 * 1.03 - 1)


def test_missing_session_cannot_silently_become_zero():
    with pytest.raises(ValueError, match="does not cover"):
        benchmark_comparison(["2024-01-02"], [100], 100, {})


@pytest.mark.parametrize("rows", ["2024-01-02,nan\n", "2024-01-02,0.01\n2024-01-02,0.02\n"])
def test_invalid_or_duplicate_csv_rejected(tmp_path, rows):
    path = tmp_path / "benchmark.csv"
    path.write_text("date,return\n" + rows, encoding="utf-8")
    with pytest.raises(ValueError):
        load_daily_benchmark(path)
