from __future__ import annotations

import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import validate_matrix_top_realistic as validator


class ParallelRealisticValidationTests(unittest.TestCase):
    def test_finalists_execute_concurrently_and_return_by_rank(self) -> None:
        barrier = threading.Barrier(2, timeout=3.0)
        calls: list[int] = []
        calls_lock = threading.Lock()

        def fake_run_candidate(**kwargs):
            rank = int(kwargs["rank"])
            with calls_lock:
                calls.append(rank)
            barrier.wait()
            return {"research_rank": rank, "marker": f"rank-{rank}"}

        finalists = [
            (1, "strategy_a", "management_a"),
            (2, "strategy_b", "management_b"),
        ]
        with patch.object(validator, "_run_candidate", side_effect=fake_run_candidate):
            result = validator._run_finalists_parallel(
                finalists,
                start="2020-01-02",
                end="2020-12-30",
                initial_cash=1000.0,
                output_dir=Path("reports/test_parallel_realistic"),
                workers=2,
            )

        self.assertEqual(set(calls), {1, 2})
        self.assertEqual(result[1]["marker"], "rank-1")
        self.assertEqual(result[2]["marker"], "rank-2")

    def test_single_worker_keeps_same_candidate_contract(self) -> None:
        finalists = [
            (1, "strategy_a", "management_a"),
            (2, "strategy_b", "management_b"),
        ]

        def fake_run_candidate(**kwargs):
            return {
                "research_rank": int(kwargs["rank"]),
                "research_strategy": kwargs["strategy"],
                "research_management": kwargs["management"],
            }

        with patch.object(validator, "_run_candidate", side_effect=fake_run_candidate):
            result = validator._run_finalists_parallel(
                finalists,
                start="2020-01-02",
                end="2020-12-30",
                initial_cash=1000.0,
                output_dir=Path("reports/test_parallel_realistic"),
                workers=1,
            )

        self.assertEqual(result[1]["research_strategy"], "strategy_a")
        self.assertEqual(result[2]["research_management"], "management_b")

    def test_invalid_worker_count_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "workers must be positive"):
            validator._run_finalists_parallel(
                [(1, "strategy_a", "management_a")],
                start="2020-01-02",
                end="2020-12-30",
                initial_cash=1000.0,
                output_dir=Path("reports/test_parallel_realistic"),
                workers=0,
            )

    def test_core_validator_helpers_remain_publicly_available(self) -> None:
        self.assertIs(validator._validation_issues, validator._base._validation_issues)
        self.assertIs(validator._artifact_binding_issues, validator._base._artifact_binding_issues)
        self.assertIs(validator._validated_finalists, validator._base._validated_finalists)


if __name__ == "__main__":
    unittest.main()
