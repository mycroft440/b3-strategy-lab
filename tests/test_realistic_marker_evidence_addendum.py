from __future__ import annotations

import unittest

from b3_strategy_lab.b3_official import B3CorporateActionError
from b3_strategy_lab.cotahist import OfficialQuote
from scripts import sync_point_in_time_universe as base
from scripts import sync_point_in_time_universe_realistic as realistic


class RealisticMarkerEvidenceAddendumTests(unittest.TestCase):
    def test_registry_requires_exact_primary_https_binding(self) -> None:
        payload = {
            "schema_version": 1,
            "events": [],
            "marker_evidence": [
                {
                    "ticker": "AAA3",
                    "marker_date": "2025-01-03",
                    "specification": "ON EB NM",
                    "event": "BONIFICACAO",
                    "source_authority": "issuer",
                    "source_url": "http://example.com/evidence",
                }
            ],
        }
        with self.assertRaisesRegex(B3CorporateActionError, "URL primaria"):
            realistic._validated_marker_evidence(payload)

    def test_cvm_marker_evidence_must_stay_on_cvm_domain(self) -> None:
        payload = {
            "schema_version": 1,
            "events": [],
            "marker_evidence": [
                {
                    "ticker": "AAA3",
                    "marker_date": "2025-01-03",
                    "specification": "ON EB NM",
                    "event": "BONIFICACAO",
                    "source_authority": "CVM",
                    "source_url": "https://example.com/evidence",
                }
            ],
        }
        with self.assertRaisesRegex(B3CorporateActionError, "fora de dominio cvm.gov.br"):
            realistic._validated_marker_evidence(payload)

    def test_exact_marker_can_be_covered_without_fabricating_economic_action(self) -> None:
        payload = {
            "schema_version": 1,
            "coverage_start": "2017-01-01",
            "events": [],
            "marker_evidence": [
                {
                    "ticker": "TIMS3",
                    "marker_date": "2025-07-03",
                    "specification": "ON EBG NM",
                    "event": "GRUPAMENTO 100 PARA 1 E DESDOBRAMENTO 1 PARA 100",
                    "source_authority": "issuer",
                    "source_url": "https://ri.tim.com.br/informacoes-ao-mercado/grupamento-e-desdobramento-de-acoes/",
                }
            ],
        }
        original_parse = base.parse_supplemental_split_events
        original_audit = base.audit_share_count_markers
        try:
            realistic._install_evidence_addendum(payload)
            quotes = [
                OfficialQuote(
                    date="2025-07-02",
                    ticker="TIMS3",
                    open=10,
                    high=10,
                    low=10,
                    close=10,
                    volume=100,
                    trades=1,
                    financial_volume=1000,
                    quotation_factor=1,
                    bdi_code="02",
                    market_type="010",
                    specification="ON NM",
                ),
                OfficialQuote(
                    date="2025-07-03",
                    ticker="TIMS3",
                    open=10,
                    high=10,
                    low=10,
                    close=10,
                    volume=100,
                    trades=1,
                    financial_volume=1000,
                    quotation_factor=1,
                    bdi_code="02",
                    market_type="010",
                    specification="ON EBG NM",
                ),
            ]
            rows = base.audit_share_count_markers(
                quotes, [], coverage_start="2017-01-01"
            )
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0]["covered"])
            self.assertEqual(
                rows[0]["coverage_method"], "explicit_primary_marker_evidence"
            )
            self.assertEqual(rows[0]["covered_by_ex_date"], "")
            self.assertIsNone(rows[0]["lag_calendar_days"])
        finally:
            base.parse_supplemental_split_events = original_parse
            base.audit_share_count_markers = original_audit

    def test_marker_binding_is_exact_on_date_and_specification(self) -> None:
        evidence = realistic._validated_marker_evidence(
            {
                "schema_version": 1,
                "events": [],
                "marker_evidence": [
                    {
                        "ticker": "AAA3",
                        "marker_date": "2025-01-03",
                        "specification": "ON EB NM",
                        "event": "BONIFICACAO",
                        "source_authority": "issuer",
                        "source_url": "https://issuer.example/evidence",
                    }
                ],
            }
        )
        self.assertIn(("AAA3", "2025-01-03", "ON EB NM"), evidence)
        self.assertNotIn(("AAA3", "2025-01-04", "ON EB NM"), evidence)
        self.assertNotIn(("AAA3", "2025-01-03", "ON EG NM"), evidence)


if __name__ == "__main__":
    unittest.main()
