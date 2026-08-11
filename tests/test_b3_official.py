from __future__ import annotations

import unittest
from types import SimpleNamespace

from b3_strategy_lab.b3_official import (
    B3CorporateActionError,
    audit_share_count_markers,
    b3_supplement_url,
    extract_official_split_events,
    merge_official_split_events,
    parse_supplemental_split_events,
)


class OfficialCorporateActionTests(unittest.TestCase):
    def test_extracts_only_matching_isin_and_converts_b3_factors(self) -> None:
        payload = [
            {
                "code": "TEST",
                "stockDividends": [
                    {
                        "isinCode": "BRTESTACNOR0",
                        "label": "DESDOBRAMENTO",
                        "factor": "200,00000000000",
                        "lastDatePrior": "02/01/2024",
                    },
                    {
                        "isinCode": "BRTESTACNPR7",
                        "label": "DESDOBRAMENTO",
                        "factor": "100,00000000000",
                        "lastDatePrior": "02/01/2024",
                    },
                    {
                        "isinCode": "BRTESTACNOR0",
                        "label": "DIVIDENDO",
                        "factor": "10,00000000000",
                        "lastDatePrior": "03/01/2024",
                    },
                    {
                        "isinCode": "BRTESTACNOR0",
                        "label": "GRUPAMENTO",
                        "factor": "0,10000000000",
                        "lastDatePrior": "04/01/2024",
                    },
                ],
            }
        ]

        events = extract_official_split_events(
            payload,
            ticker="TEST3",
            issuing_company="TEST",
            quote_dates=["2024-01-02", "2024-01-03", "2024-01-05"],
            quote_isins=["BRTESTACNOR0"],
            coverage_start="2024-01-01",
        )

        self.assertEqual([event.ex_date for event in events], ["2024-01-03", "2024-01-05"])
        self.assertAlmostEqual(events[0].split_ratio, 3.0)
        self.assertAlmostEqual(events[1].split_ratio, 0.1)
        self.assertEqual(events[0].action().dividend, 0.0)

    def test_combines_same_day_share_count_events(self) -> None:
        payload = [
            {
                "code": "TEST",
                "stockDividends": [
                    {
                        "isinCode": "BRTESTACNOR0",
                        "label": "BONIFICACAO",
                        "factor": "10,00000000000",
                        "lastDatePrior": "02/01/2024",
                    },
                    {
                        "isinCode": "BRTESTACNOR0",
                        "label": "DESDOBRAMENTO",
                        "factor": "100,00000000000",
                        "lastDatePrior": "02/01/2024",
                    },
                ],
            }
        ]

        events = extract_official_split_events(
            payload,
            ticker="TEST3",
            issuing_company="TEST",
            quote_dates=["2024-01-02", "2024-01-03"],
            quote_isins=["BRTESTACNOR0"],
            coverage_start="2024-01-01",
        )

        self.assertEqual(len(events), 1)
        self.assertAlmostEqual(events[0].split_ratio, 2.2)

    def test_builds_official_endpoint_payload(self) -> None:
        url = b3_supplement_url("BBAS")

        self.assertTrue(url.startswith("https://sistemaswebb3-listados.b3.com.br/"))
        self.assertIn("GetListedSupplementCompany/", url)

    def test_validates_supplement_against_cotahist_calendar(self) -> None:
        payload = {
            "schema_version": 1,
            "events": [
                {
                    "ticker": "TEST3",
                    "ex_date": "2024-01-03",
                    "last_date_prior": "2024-01-02",
                    "split_ratio": 1.1,
                    "event": "BONIFICACAO 10%",
                    "source_authority": "issuer",
                    "source_url": "https://ri.example.test/evento",
                }
            ],
        }

        events = parse_supplemental_split_events(
            payload,
            tickers=["TEST3"],
            quote_dates_by_ticker={"TEST3": ["2024-01-02", "2024-01-03"]},
            coverage_start="2024-01-01",
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].source_authority, "issuer")
        self.assertEqual(events[0].action().source_symbol, "ISSUER_RI")

        payload["events"][0]["ex_date"] = "2024-01-04"
        with self.assertRaises(B3CorporateActionError):
            parse_supplemental_split_events(
                payload,
                tickers=["TEST3"],
                quote_dates_by_ticker={"TEST3": ["2024-01-02", "2024-01-03"]},
                coverage_start="2024-01-01",
            )

    def test_merges_duplicate_sources_only_when_they_agree(self) -> None:
        base = extract_official_split_events(
            [
                {
                    "code": "TEST",
                    "stockDividends": [
                        {
                            "isinCode": "BRTESTACNOR0",
                            "label": "BONIFICACAO",
                            "factor": "10,00000000000",
                            "lastDatePrior": "02/01/2024",
                        }
                    ],
                }
            ],
            ticker="TEST3",
            issuing_company="TEST",
            quote_dates=["2024-01-02", "2024-01-03"],
            quote_isins=["BRTESTACNOR0"],
            coverage_start="2024-01-01",
        )
        duplicate = parse_supplemental_split_events(
            {
                "schema_version": 1,
                "events": [
                    {
                        "ticker": "TEST3",
                        "ex_date": "2024-01-03",
                        "last_date_prior": "2024-01-02",
                        "split_ratio": 1.1,
                        "event": "BONIFICACAO 10%",
                        "source_authority": "CVM",
                        "source_url": "https://www.rad.cvm.gov.br/evento",
                    }
                ],
            },
            tickers=["TEST3"],
            quote_dates_by_ticker={"TEST3": ["2024-01-02", "2024-01-03"]},
            coverage_start="2024-01-01",
        )

        merged = merge_official_split_events(base, duplicate)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].source_authority, "B3")

        conflicting = [
            duplicate[0].__class__(
                **{**duplicate[0].__dict__, "split_ratio": 1.2}
            )
        ]
        with self.assertRaises(B3CorporateActionError):
            merge_official_split_events(base, conflicting)

    def test_cotahist_share_marker_must_have_nearby_official_event(self) -> None:
        quotes = [
            SimpleNamespace(date="2024-01-02", specification="ON NM"),
            SimpleNamespace(date="2024-01-03", specification="ON EB NM"),
        ]
        event = parse_supplemental_split_events(
            {
                "schema_version": 1,
                "events": [
                    {
                        "ticker": "TEST3",
                        "ex_date": "2024-01-03",
                        "last_date_prior": "2024-01-02",
                        "split_ratio": 1.1,
                        "event": "BONIFICACAO 10%",
                        "source_authority": "issuer",
                        "source_url": "https://ri.example.test/evento",
                    }
                ],
            },
            tickers=["TEST3"],
            quote_dates_by_ticker={"TEST3": ["2024-01-02", "2024-01-03"]},
            coverage_start="2024-01-01",
        )

        covered = audit_share_count_markers(
            quotes,
            event,
            coverage_start="2024-01-01",
        )
        uncovered = audit_share_count_markers(
            quotes,
            [],
            coverage_start="2024-01-01",
        )

        self.assertTrue(covered[0]["covered"])
        self.assertFalse(uncovered[0]["covered"])


if __name__ == "__main__":
    unittest.main()
