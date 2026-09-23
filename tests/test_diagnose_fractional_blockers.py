from __future__ import annotations

import unittest
from types import SimpleNamespace

from scripts.diagnose_fractional_blockers import _fractions_at_zero, main


def _data(ratio: float) -> SimpleNamespace:
    previous = SimpleNamespace(adjustment_factor=1 / ratio, raw_open=27.0)
    current = SimpleNamespace(adjustment_factor=1.0, raw_open=28.0)
    return SimpleNamespace(
        index_by_date={"RADL3": {"2023-05-22": 1}},
        candles={"RADL3": [previous, current]},
    )


class DiagnoseFractionalBlockersTests(unittest.TestCase):
    def test_fraction_is_discarded_at_zero_and_reported(self) -> None:
        position = SimpleNamespace(shares=39, average_cost=26.0)
        account = SimpleNamespace(positions={"RADL3": position})
        events: list[dict[str, object]] = []

        _fractions_at_zero(events)(account, _data(1.04), "2023-05-22")

        self.assertEqual(position.shares, 40)
        self.assertAlmostEqual(position.shares * position.average_cost, 39 * 26.0)
        self.assertEqual(len(events), 1)
        self.assertAlmostEqual(events[0]["fraction_discarded"], 0.56)
        self.assertAlmostEqual(events[0]["fraction_value_at_official_open"], 0.56 * 28.0)

    def test_integer_event_matches_engine_without_report(self) -> None:
        position = SimpleNamespace(shares=50, average_cost=26.0)
        account = SimpleNamespace(positions={"RADL3": position})
        events: list[dict[str, object]] = []

        _fractions_at_zero(events)(account, _data(1.04), "2023-05-22")

        self.assertEqual(position.shares, 52)
        self.assertAlmostEqual(position.average_cost, 26.0 / 1.04)
        self.assertEqual(events, [])

    def test_refuses_certified_mode_and_default_output(self) -> None:
        with self.assertRaises(SystemExit):
            main(["--output", "x.json", "--require-certified-inputs"])
        with self.assertRaises(SystemExit):
            main(["--start", "2023-01-02"])


if __name__ == "__main__":
    unittest.main()
