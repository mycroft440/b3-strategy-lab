from __future__ import annotations

import csv
import tempfile
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

    def test_fee_rule_lookup_cache_preserves_canonical_fee_math(self) -> None:
        rules = [
            {
                "start": "2020-01-01",
                "end": "2025-12-31",
                "b3_bps": 3.2,
                "brokerage_fixed": 0.0,
                "quality": "official",
            },
            {
                "start": "2026-01-01",
                "end": "2030-12-31",
                "b3_bps": 2.7,
                "brokerage_fixed": 0.25,
                "quality": "official",
            },
        ]
        validator._fee_rule_by_date_cache.clear()
        expected_first = validator._original_expected_fee(rules, "2026-02-03", 1234.56)
        expected_second = validator._original_expected_fee(rules, "2026-02-03", 9876.54)
        actual_first = validator._expected_fee(rules, "2026-02-03", 1234.56)
        actual_second = validator._expected_fee(rules, "2026-02-03", 9876.54)
        self.assertEqual(actual_first, expected_first)
        self.assertEqual(actual_second, expected_second)
        self.assertEqual(len(validator._fee_rule_by_date_cache), 1)

    def test_execution_source_is_parsed_once_per_certified_file(self) -> None:
        validator._execution_source.cache_clear()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "execution.csv"
            with path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=[
                        "date",
                        "ticker",
                        "market_type",
                        "open",
                        "financial_volume",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "date": "2026-01-02",
                        "ticker": "AAA3",
                        "market_type": "010",
                        "open": "10.0",
                        "financial_volume": "1000000",
                    }
                )
            first = validator._execution_source(path)
            second = validator._execution_source(path)
        self.assertIs(first, second)
        self.assertEqual(first[("2026-01-02", "AAA3", "010")], (10.0, 1_000_000.0))
        self.assertGreaterEqual(validator._execution_source.cache_info().hits, 1)


if __name__ == "__main__":
    unittest.main()
