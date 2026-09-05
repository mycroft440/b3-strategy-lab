from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path

from b3_strategy_lab.ex_ante_validation import (
    ValidationError,
    build_frozen_candidate,
    build_holdout_validation_report,
    latest_complete_calendar_year,
    point_in_time_contract_issues,
)


class HoldoutBoundaryTests(unittest.TestCase):
    def test_latest_complete_year_never_uses_current_partial_year(self) -> None:
        dates = [
            *(f"2024-{month:02d}-{day:02d}" for month in range(1, 13) for day in range(1, 22)),
            *(f"2025-{month:02d}-{day:02d}" for month in range(1, 13) for day in range(1, 22)),
            *(f"2026-{month:02d}-{day:02d}" for month in range(1, 9) for day in range(1, 22)),
        ]
        self.assertEqual(
            latest_complete_calendar_year(dates, as_of=date(2026, 9, 5)),
            2025,
        )

    def _pit_audit(self) -> dict[str, object]:
        return {
            "status": "PASS",
            "report_sha256": "abc",
            "cash_announcement_timing_certified": True,
        }

    def _matrix(self, end: str = "2024-12-30") -> dict[str, object]:
        return {
            "start": "2018-01-02",
            "end": end,
            "catalog_complete": True,
            "universe": {"point_in_time": True, "survivorship_safe": True},
        }

    def _top(self, end: str = "2024-12-30") -> dict[str, object]:
        return {
            "period": {"start": "2018-01-02", "end": end},
            "top_10": [
                {
                    "rank": 1,
                    "trading_strategy": "gap_momentum",
                    "management_strategy": "top1_test_adjusted",
                },
                {
                    "rank": 2,
                    "trading_strategy": "ema_pullback_trend",
                    "management_strategy": "top1_other_adjusted",
                },
            ],
        }

    def test_freeze_rejects_training_overlap_with_holdout(self) -> None:
        with self.assertRaisesRegex(ValidationError, "overlaps"):
            build_frozen_candidate(
                candidates=self._top(end="2025-01-03"),
                matrix_manifest=self._matrix(end="2025-01-03"),
                pit_audit=self._pit_audit(),
                holdout_start="2025-01-02",
                holdout_end="2025-12-30",
                source_bindings={},
            )

    def test_holdout_result_cannot_switch_to_second_candidate(self) -> None:
        frozen = build_frozen_candidate(
            candidates=self._top(),
            matrix_manifest=self._matrix(),
            pit_audit=self._pit_audit(),
            holdout_start="2025-01-02",
            holdout_end="2025-12-30",
            source_bindings={},
        )
        summary = {
            "strategy": "ema_pullback_trend",
            "management": "top1_other_adjusted",
            "start": "2025-01-02",
            "end": "2025-12-30",
            "selection_status": "prospective_frozen",
            "point_in_time_universe": True,
            "survivorship_safe": True,
            "cash_events_complete": True,
            "fractional_execution": True,
            "fee_quality": "official",
            "economic_gap_adjustment": False,
            "validity": "REALISTIC_POINT_IN_TIME",
        }
        report = build_holdout_validation_report(
            frozen=frozen,
            realistic_summary=summary,
            pit_audit=self._pit_audit(),
            source_bindings={},
        )
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("holdout_strategy_differs_from_frozen", report["issues"])
        self.assertFalse(frozen["fallback_candidate_allowed"])

    def test_exact_frozen_candidate_passes_without_reranking(self) -> None:
        frozen = build_frozen_candidate(
            candidates=self._top(),
            matrix_manifest=self._matrix(),
            pit_audit=self._pit_audit(),
            holdout_start="2025-01-02",
            holdout_end="2025-12-30",
            source_bindings={},
        )
        summary = {
            "strategy": "gap_momentum",
            "management": "top1_test_adjusted",
            "start": "2025-01-02",
            "end": "2025-12-30",
            "selection_status": "prospective_frozen",
            "point_in_time_universe": True,
            "survivorship_safe": True,
            "cash_events_complete": True,
            "fractional_execution": True,
            "fee_quality": "official",
            "economic_gap_adjustment": True,
            "validity": "REALISTIC_POINT_IN_TIME",
            "total_return": -0.10,
        }
        report = build_holdout_validation_report(
            frozen=frozen,
            realistic_summary=summary,
            pit_audit=self._pit_audit(),
            source_bindings={},
        )
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(
            report["selection_classification"],
            "EX_ANTE_FROZEN_SINGLE_HOLDOUT_VALIDATED",
        )
        self.assertEqual(report["holdout_metrics"]["total_return"], -0.10)
        self.assertFalse(report["formal_multiple_testing_significance_claim_allowed"])


class PointInTimeContractTests(unittest.TestCase):
    def _universe(self) -> dict[str, object]:
        return {
            "schema_version": 8,
            "selected_as_of": "2024-01-02",
            "selection_end": "2024-12-30",
            "point_in_time": True,
            "survivorship_safe": True,
            "tickers": ["AAA3", "BBB4"],
            "selection_rules": {
                "weekly_candidates": 2,
                "future_continuity_filter": False,
                "future_return_filter": False,
            },
        }

    def _snapshots(self) -> list[dict[str, object]]:
        return [
            {"effective_date": "2024-01-02", "ticker": "AAA3", "rank": 1},
            {"effective_date": "2024-01-02", "ticker": "BBB4", "rank": 2},
            {"effective_date": "2024-01-09", "ticker": "BBB4", "rank": 1},
            {"effective_date": "2024-01-09", "ticker": "AAA3", "rank": 2},
        ]

    def test_strict_pit_contract_passes_only_with_timing_certification(self) -> None:
        issues = point_in_time_contract_issues(
            universe=self._universe(),
            snapshots=self._snapshots(),
            data_dir=Path("data/candles_point_in_time"),
            actions_dir=Path("data/actions_point_in_time"),
            manifests_dir=Path("data/manifests_point_in_time"),
            split_evidence=Path("data/corporate_actions/point_in_time_split_evidence.json"),
            cash_certification={
                "coverage_certified": True,
                "announcement_timing_certified": True,
            },
        )
        self.assertEqual(issues, [])

    def test_future_filter_and_uncertified_timing_are_blockers(self) -> None:
        universe = self._universe()
        universe["selection_rules"] = dict(universe["selection_rules"])
        universe["selection_rules"]["future_return_filter"] = True
        issues = point_in_time_contract_issues(
            universe=universe,
            snapshots=self._snapshots(),
            data_dir=Path("data/candles_point_in_time"),
            actions_dir=Path("data/actions_point_in_time"),
            manifests_dir=Path("data/manifests_point_in_time"),
            split_evidence=Path("data/corporate_actions/point_in_time_split_evidence.json"),
            cash_certification={"coverage_certified": True},
        )
        self.assertIn("future_return_filter_not_false", issues)
        self.assertIn("cash_announcement_timing_not_certified", issues)

    def test_legacy_storage_is_rejected_even_with_good_snapshots(self) -> None:
        issues = point_in_time_contract_issues(
            universe=self._universe(),
            snapshots=self._snapshots(),
            data_dir=Path("data/candles"),
            actions_dir=Path("data/corporate_actions"),
            manifests_dir=Path("data/manifests"),
            split_evidence=Path("data/corporate_actions/split_evidence.json"),
            cash_certification={
                "coverage_certified": True,
                "announcement_timing_certified": True,
            },
        )
        self.assertIn("legacy_or_unexpected_data_dir", issues)
        self.assertIn("legacy_or_unexpected_actions_dir", issues)
        self.assertIn("legacy_or_unexpected_manifests_dir", issues)
        self.assertIn("legacy_or_unexpected_split_evidence", issues)


if __name__ == "__main__":
    unittest.main()
