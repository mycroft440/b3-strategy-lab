from __future__ import annotations

import unittest

from b3_strategy_lab.b3_official import B3CorporateActionError
from scripts import sync_point_in_time_universe as pit


class PointInTimeSupplementalScopingTests(unittest.TestCase):
    def test_drops_only_well_classified_out_of_scope_events(self) -> None:
        payload = {
            "schema_version": 1,
            "coverage_start": "2017-01-01",
            "events": [
                {"ticker": "AAAA3", "marker": "keep"},
                {"ticker": "BBBB3", "marker": "drop"},
            ],
        }
        scoped = pit._scope_supplemental_payload(payload, ["AAAA3"])
        self.assertEqual(scoped["events"], [{"ticker": "AAAA3", "marker": "keep"}])
        self.assertEqual(payload["events"][1]["marker"], "drop")

    def test_preserves_malformed_and_unclassifiable_records_for_canonical_rejection(self) -> None:
        malformed = [
            None,
            ["not", "a", "mapping"],
            {},
            {"ticker": None},
            {"ticker": 123},
            {"ticker": ""},
        ]
        payload = {
            "schema_version": 1,
            "coverage_start": "2017-01-01",
            "events": malformed + [{"ticker": "OUT3"}],
        }
        scoped = pit._scope_supplemental_payload(payload, ["IN3"])
        self.assertEqual(scoped["events"], malformed)

    def test_preserved_corruption_reaches_the_canonical_fail_closed_parser(self) -> None:
        payload = {
            "schema_version": 1,
            "coverage_start": "2017-01-01",
            "events": [None, {"ticker": "OUT3"}],
        }
        scoped = pit._scope_supplemental_payload(payload, ["IN3"])
        with self.assertRaises(B3CorporateActionError):
            pit.parse_supplemental_split_events(
                scoped,
                tickers=["IN3"],
                quote_dates_by_ticker={"IN3": ["2020-01-02"]},
                coverage_start="2017-01-01",
            )

    def test_malformed_payload_shape_is_not_normalized_away(self) -> None:
        payload = ["invalid-root"]
        self.assertIs(pit._scope_supplemental_payload(payload, ["IN3"]), payload)
        payload_without_list = {"schema_version": 1, "events": "invalid"}
        self.assertIs(
            pit._scope_supplemental_payload(payload_without_list, ["IN3"]),
            payload_without_list,
        )


if __name__ == "__main__":
    unittest.main()
