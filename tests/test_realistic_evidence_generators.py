from __future__ import annotations

import unittest

from b3_strategy_lab.b3_official import B3CorporateActionError
from scripts import sync_point_in_time_universe_realistic as realistic


class RealisticEvidenceGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_parse = realistic.base.parse_supplemental_split_events
        self.original_audit = realistic.base.audit_share_count_markers

    def tearDown(self) -> None:
        realistic.base.parse_supplemental_split_events = self.original_parse
        realistic.base.audit_share_count_markers = self.original_audit

    def _payload(self, *, ex_date: str = "2017-05-02") -> dict:
        return {
            "schema_version": 1,
            "coverage_start": "2017-01-01",
            "events": [
                {
                    "ticker": "BRML3",
                    "ex_date": ex_date,
                    "last_date_prior": "2017-04-28",
                    "split_ratio": 1.15,
                    "event": "BONIFICACAO 15%",
                    "source_authority": "issuer",
                    "source_url": "https://ri.allos.co/informacoes-financeiras/central-de-resultados-brmalls/",
                }
            ],
            "marker_evidence": [],
        }

    def test_one_shot_cotahist_calendar_is_reused_for_primary_and_addendum(self) -> None:
        realistic._install_evidence_addendum(self._payload())
        base_registry = {
            "schema_version": 1,
            "coverage_start": "2017-01-01",
            "events": [],
        }
        dates = (value for value in ("2017-04-28", "2017-05-02"))

        events = realistic.base.parse_supplemental_split_events(
            base_registry,
            tickers=["BRML3"],
            quote_dates_by_ticker={"BRML3": dates},
            coverage_start="2017-01-01",
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].ticker, "BRML3")
        self.assertEqual(events[0].ex_date, "2017-05-02")
        self.assertAlmostEqual(events[0].split_ratio, 1.15)

    def test_one_shot_ticker_scope_is_reused_for_primary_and_addendum(self) -> None:
        realistic._install_evidence_addendum(self._payload())
        base_registry = {
            "schema_version": 1,
            "coverage_start": "2017-01-01",
            "events": [],
        }
        tickers = (ticker for ticker in ("BRML3",))

        events = realistic.base.parse_supplemental_split_events(
            base_registry,
            tickers=tickers,
            quote_dates_by_ticker={"BRML3": ["2017-04-28", "2017-05-02"]},
            coverage_start="2017-01-01",
        )

        self.assertEqual([(event.ticker, event.ex_date) for event in events], [("BRML3", "2017-05-02")])

    def test_materialization_does_not_weaken_calendar_reconciliation(self) -> None:
        realistic._install_evidence_addendum(self._payload(ex_date="2017-05-03"))
        base_registry = {
            "schema_version": 1,
            "coverage_start": "2017-01-01",
            "events": [],
        }
        dates = (value for value in ("2017-04-28", "2017-05-02", "2017-05-03"))

        with self.assertRaisesRegex(
            B3CorporateActionError,
            "primeiro pregao posterior.*2017-05-02",
        ):
            realistic.base.parse_supplemental_split_events(
                base_registry,
                tickers=["BRML3"],
                quote_dates_by_ticker={"BRML3": dates},
                coverage_start="2017-01-01",
            )

    def test_corrupt_addendum_event_is_preserved_for_canonical_rejection(self) -> None:
        payload = self._payload()
        payload["events"] = ["corrupt-event"]
        realistic._install_evidence_addendum(payload)
        base_registry = {
            "schema_version": 1,
            "coverage_start": "2017-01-01",
            "events": [],
        }
        with self.assertRaisesRegex(B3CorporateActionError, "Evento suplementar invalido"):
            realistic.base.parse_supplemental_split_events(
                base_registry,
                tickers=["BRML3"],
                quote_dates_by_ticker={"BRML3": ["2017-04-28", "2017-05-02"]},
                coverage_start="2017-01-01",
            )


if __name__ == "__main__":
    unittest.main()
