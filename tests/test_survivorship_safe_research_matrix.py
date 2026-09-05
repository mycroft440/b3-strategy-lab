from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

import pytest

from scripts import backtest_strategy_management_combinations as matrix
from scripts import research_portfolio_allocation_core as core


def _pit_fixture(directory: Path) -> tuple[Path, Path]:
    snapshots = directory / "weekly.csv"
    with snapshots.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["effective_date", "ticker", "rank"])
        writer.writeheader()
        writer.writerows(
            [
                {"effective_date": "2020-01-03", "ticker": "AAA3", "rank": 1},
                {"effective_date": "2020-01-03", "ticker": "BBB4", "rank": 2},
                {"effective_date": "2020-01-10", "ticker": "BBB4", "rank": 1},
                {"effective_date": "2020-01-10", "ticker": "CCC3", "rank": 2},
            ]
        )
    manifest = directory / "universe.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 8,
                "id": "test-pit",
                "selection_mode": "full_b3_on_pn_trailing_liquidity_point_in_time",
                "selected_as_of": "2020-01-01",
                "selection_end": "2020-01-31",
                "warmup_start": "2019-01-01",
                "survivorship_safe": True,
                "point_in_time": True,
                "snapshot_file": str(snapshots),
                "bias_disclosure": "test",
                "selection_rules": {
                    "weekly_candidates": 2,
                    "future_continuity_filter": False,
                    "future_return_filter": False,
                },
                "tickers": ["AAA3", "BBB4", "CCC3"],
            }
        ),
        encoding="utf-8",
    )
    return manifest, snapshots


def test_pit_membership_never_backfills_a_future_snapshot() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        manifest_path, _ = _pit_fixture(Path(tmp))
        universe = matrix._load_universe(manifest_path)
        dates = ["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-10", "2020-01-13"]
        membership = matrix._load_point_in_time_membership(universe, dates)

    assert membership["2020-01-02"] == set()
    assert membership["2020-01-03"] == {"AAA3", "BBB4"}
    assert membership["2020-01-06"] == {"AAA3", "BBB4"}
    assert membership["2020-01-10"] == {"BBB4", "CCC3"}
    assert membership["2020-01-13"] == {"BBB4", "CCC3"}


def test_fixed_retrospective_universe_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "fixed.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "id": "legacy",
                    "selection_mode": "legacy",
                    "selected_as_of": "2018-01-02",
                    "warmup_start": "2017-01-01",
                    "survivorship_safe": False,
                    "bias_disclosure": "legacy",
                    "tickers": ["AAA3"],
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="PIT|point_in_time|survivorship"):
            matrix._load_universe(path)


def test_management_decision_intersects_signal_and_pit_universe() -> None:
    class Data:
        tickers = ["AAA3", "BBB4", "CCC3"]
        index_by_date = {
            "AAA3": {"2020-01-03": 0},
            "BBB4": {"2020-01-03": 0},
            "CCC3": {"2020-01-03": 0},
        }

    signals = {"AAA3": [1], "BBB4": [0], "CCC3": [1]}
    universe = {"2020-01-03": {"AAA3", "BBB4"}}
    assert core._decision_eligible_tickers(
        Data(), "2020-01-03", signals, universe
    ) == {"AAA3"}


def test_hardened_matrix_workflow_builds_and_passes_pit_universe() -> None:
    text = Path(".github/workflows/full-matrix-backtest-hardened.yml").read_text(encoding="utf-8")
    assert "build_survivorship_safe_realistic_universe.py" in text
    assert "sync_point_in_time_universe_realistic.py" in text
    assert "--universe-manifest data/universes/point_in_time_union.json" in text
    assert "data/candles_point_in_time" in text
    assert matrix.DEFAULT_UNIVERSE_MANIFEST == Path("data/universes/point_in_time_union.json")
