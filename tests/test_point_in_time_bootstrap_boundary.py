from __future__ import annotations

import unittest

from b3_strategy_lab.point_in_time import weekly_decision_dates


class PointInTimeBootstrapBoundaryTests(unittest.TestCase):
    def test_first_in_range_session_is_seeded_before_weekly_close(self) -> None:
        dates = [
            "2017-12-29",
            "2018-01-02",
            "2018-01-03",
            "2018-01-04",
            "2018-01-05",
            "2018-01-08",
            "2018-01-12",
        ]

        self.assertEqual(
            weekly_decision_dates(dates, "2018-01-02", "2018-01-12"),
            ["2018-01-02", "2018-01-05", "2018-01-12"],
        )

    def test_bootstrap_uses_first_actual_session_not_calendar_start(self) -> None:
        dates = ["2018-01-05", "2018-01-08", "2018-01-09", "2018-01-12"]

        self.assertEqual(
            weekly_decision_dates(dates, "2018-01-06", "2018-01-12"),
            ["2018-01-08", "2018-01-12"],
        )


if __name__ == "__main__":
    unittest.main()
