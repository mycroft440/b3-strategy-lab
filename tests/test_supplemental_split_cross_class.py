from __future__ import annotations

import json
import unittest
from pathlib import Path


REGISTRY = Path("data/corporate_actions/supplemental_split_events.json")


class SupplementalSplitCrossClassTests(unittest.TestCase):
    def test_companywide_bonus_events_cover_both_share_classes(self) -> None:
        payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
        events = {
            (str(row["ticker"]), str(row["ex_date"])): row
            for row in payload["events"]
        }

        paired_classes = (
            ("BBDC3", "BBDC4"),
            ("CMIG4", "CMIG3"),
            ("GGBR3", "GGBR4"),
            ("ITSA4", "ITSA3"),
        )
        expected_mirrored_events = 0
        for source_ticker, paired_ticker in paired_classes:
            source_rows = [
                row for (ticker, _date), row in events.items() if ticker == source_ticker
            ]
            self.assertTrue(source_rows, source_ticker)
            expected_mirrored_events += len(source_rows)
            for source in source_rows:
                paired = events.get((paired_ticker, str(source["ex_date"])))
                self.assertIsNotNone(
                    paired,
                    f"{paired_ticker} missing primary-source evidence for {source['ex_date']}",
                )
                assert paired is not None
                for field in (
                    "last_date_prior",
                    "split_ratio",
                    "event",
                    "source_authority",
                    "source_url",
                ):
                    self.assertEqual(paired[field], source[field])

        self.assertEqual(expected_mirrored_events, 14)


if __name__ == "__main__":
    unittest.main()
