import pytest

from scripts.walk_forward_realistic import _training_end, main


def test_holdout_never_becomes_training_in_later_years():
    days = ["2020-12-30", "2021-12-30", "2022-01-03", "2022-12-30", "2023-01-02"]
    assert _training_end(days, "2022-01-03", "2022-01-01") == "2021-12-30"
    assert _training_end(days, "2023-01-02", "2022-01-01") == "2021-12-30"
    assert _training_end(days, "2023-01-02") == "2022-12-30"


def test_excess_sharpe_requires_a_dated_benchmark():
    with pytest.raises(SystemExit) as caught:
        main(["--objective", "excess_sharpe"])
    assert caught.value.code == 2


def test_holdout_boundary_must_align_with_annual_folds():
    with pytest.raises(SystemExit) as caught:
        main(["--holdout-start", "2025-06-01"])
    assert caught.value.code == 2
