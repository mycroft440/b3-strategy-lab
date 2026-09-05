from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data/corporate_actions/instrument_transition_reviews.json"
TESTS = ROOT / "tests/test_instrument_transition_layer.py"

NEW_REVIEWS = [
    {
        "effective_date": "2023-10-25",
        "cutoff_date": "2023-10-24",
        "first_successor_trade_date": "2023-10-25",
        "old_ticker": "ALSO3",
        "new_ticker": "ALOS3",
        "share_ratio": 1.0,
        "old_quotation_factor": 1,
        "new_quotation_factor": 1,
        "cash_per_old_share": 0.0,
        "event_type": "ticker_change",
        "fractional_treatment": "preserve_units",
        "tax_basis_treatment": "carry_total_basis",
        "certification_status": "certified",
        "source_authority": "issuer",
        "source_url": "https://allos.co/",
        "source_reference": "ALLOS Comunicado ao Mercado de 17/10/2023; novo ticker ALOS3 a partir de 25/10/2023",
        "evidence_summary": "ALSO3 passou a negociar como ALOS3 a partir de 25/10/2023 após mudança de denominação, sem conversão econômica de quantidade.",
    },
    {
        "effective_date": "2026-01-13",
        "cutoff_date": "2026-01-12",
        "first_successor_trade_date": "2026-01-13",
        "old_ticker": "AZUL54",
        "new_ticker": "AZUL53",
        "old_isin": "BRAZULA02PR3",
        "new_isin": "BRAZULA01OR8",
        "share_ratio": 75.0,
        "old_quotation_factor": 10000,
        "new_quotation_factor": 1000000,
        "cash_per_old_share": 0.0,
        "event_type": "class_change",
        "fractional_treatment": "require_integer",
        "tax_basis_treatment": "carry_total_basis",
        "certification_status": "certified",
        "source_authority": "B3",
        "source_url": "https://www.b3.com.br/data/files/09/40/28/A8/EB5AB9109B5E99B9AC094EA8/OC%20004-2026-VNC%20AZUL_Conversao%20PN%20ON_090126_PT.pdf",
        "source_reference": "B3 Ofício Circular 004/2026-VNC, 09/01/2026",
        "evidence_summary": "Após aprovação em 12/01/2026, AZUL54 deixa de negociar em 13/01/2026 e cada PN é convertida em 75 AZUL53 ON; o fator de cotação muda de 10.000 para 1.000.000 sem representar split adicional.",
    },
]


def update_registry() -> None:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    reviews = payload.get("reviews")
    if payload.get("schema_version") != 1 or not isinstance(reviews, list):
        raise SystemExit("unexpected transition review registry schema")
    keys = {
        (str(row.get("effective_date")), str(row.get("old_ticker")), str(row.get("new_ticker", "")))
        for row in reviews
        if isinstance(row, dict)
    }
    for row in NEW_REVIEWS:
        key = (row["effective_date"], row["old_ticker"], row["new_ticker"])
        if key not in keys:
            reviews.append(row)
            keys.add(key)
    reviews.sort(key=lambda row: (str(row["effective_date"]), str(row["old_ticker"]), str(row.get("new_ticker", ""))))
    REGISTRY.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def patch_tests() -> None:
    text = TESTS.read_text(encoding="utf-8")
    if "test_final_chained_successors_are_source_bound" in text:
        return
    anchor = '\n\nif __name__ == "__main__":\n    unittest.main()\n'
    addition = '''\n\n    def test_final_chained_successors_are_source_bound(self) -> None:\n        reviews = load_transition_reviews(\n            Path("data/corporate_actions/instrument_transition_reviews.json")\n        )\n        by_old = {item.old_ticker: item for item in reviews}\n        self.assertEqual(by_old["ALSO3"].new_ticker, "ALOS3")\n        self.assertEqual(by_old["ALSO3"].share_ratio, 1.0)\n        self.assertEqual(by_old["AZUL54"].new_ticker, "AZUL53")\n        self.assertEqual(by_old["AZUL54"].share_ratio, 75.0)\n        self.assertEqual(by_old["AZUL54"].old_quotation_factor, 10000)\n        self.assertEqual(by_old["AZUL54"].new_quotation_factor, 1000000)\n        self.assertEqual(by_old["AZUL54"].first_successor_trade_date, "2026-01-13")\n\n    def test_azul54_to_azul53_preserves_total_basis(self) -> None:\n        account = self._account(shares=2, average_cost=75.0)\n        transition = self._certified(\n            effective_date="2026-01-13",\n            old_ticker="OLD4",\n            new_ticker="NEW54",\n            share_ratio=75.0,\n            old_quotation_factor=10000,\n            new_quotation_factor=1000000,\n            fractional_treatment="require_integer",\n            event_type="class_change",\n        )\n        _apply_ticker_transitions(account, [transition])\n        self.assertEqual(account.shares("NEW54"), 150)\n        self.assertAlmostEqual(account.positions["NEW54"].average_cost, 1.0)\n        self.assertAlmostEqual(\n            account.positions["NEW54"].shares * account.positions["NEW54"].average_cost,\n            150.0,\n        )\n'''
    if anchor not in text:
        raise SystemExit("instrument transition test anchor missing")
    TESTS.write_text(text.replace(anchor, addition + anchor, 1), encoding="utf-8")


update_registry()
patch_tests()
