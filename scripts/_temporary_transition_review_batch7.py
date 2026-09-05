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
        "effective_date": "2026-01-14",
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
        "evidence_summary": "AZUL54 deixa de negociar em 13/01/2026, mas as 75 AZUL53 ON por PN são creditadas na Central Depositária em 14/01/2026. O evento da posição é aplicado apenas no crédito; uma carteira que precise marcar AZUL54 em 13/01 continua fail-closed em vez de antecipar a disponibilidade das novas ações. O fator de cotação muda de 10.000 para 1.000.000 sem representar split adicional.",
    },
    {
        "effective_date": "2026-04-20",
        "cutoff_date": "2026-04-17",
        "first_successor_trade_date": "2026-04-20",
        "old_ticker": "AZUL53",
        "new_ticker": "AZUL3",
        "old_isin": "BRAZULA01OR8",
        "new_isin": "BRAZULACNOR7",
        "share_ratio": 0.000006666666666666667,
        "old_quotation_factor": 1000000,
        "new_quotation_factor": 1,
        "cash_per_old_share": 0.0,
        "event_type": "reorganization",
        "fractional_treatment": "cash_in_lieu",
        "tax_basis_treatment": "carry_total_basis",
        "certification_status": "certified",
        "source_authority": "B3",
        "source_url": "https://www.b3.com.br/data/files/07/94/CE/8F/6839D9107DD5C8D9AC094EA8/OC%20023-2026-VNC%20GRUPAMENTO_%20AZUL%20SA_PT.pdf",
        "source_reference": "B3 Ofício Circular 023/2026-VNC, 15/04/2026; COTAHIST/BDI B3 confirma AZUL53 até 17/04 e AZUL3 após o grupamento",
        "evidence_summary": "A B3 documenta grupamento das ON da Azul na proporção de 150.000 para 1 com efeitos em 20/04/2026. A série anterior AZUL53 encerra negociação em 17/04 e a ação agrupada passa a AZUL3. Quantidades que não gerem número inteiro de AZUL3 exigem tratamento de frações/cash-in-lieu e permanecem fail-closed no motor atual.",
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
    addition = '''\n\n    def test_final_chained_successors_are_source_bound(self) -> None:\n        reviews = load_transition_reviews(\n            Path("data/corporate_actions/instrument_transition_reviews.json")\n        )\n        by_old = {item.old_ticker: item for item in reviews}\n        self.assertEqual(by_old["ALSO3"].new_ticker, "ALOS3")\n        self.assertEqual(by_old["ALSO3"].share_ratio, 1.0)\n        self.assertEqual(by_old["AZUL54"].new_ticker, "AZUL53")\n        self.assertEqual(by_old["AZUL54"].share_ratio, 75.0)\n        self.assertEqual(by_old["AZUL54"].old_quotation_factor, 10000)\n        self.assertEqual(by_old["AZUL54"].new_quotation_factor, 1000000)\n        self.assertEqual(by_old["AZUL54"].effective_date, "2026-01-14")\n        self.assertEqual(by_old["AZUL54"].first_successor_trade_date, "2026-01-13")\n        self.assertEqual(by_old["AZUL53"].new_ticker, "AZUL3")\n        self.assertAlmostEqual(by_old["AZUL53"].share_ratio, 1.0 / 150000.0)\n        self.assertEqual(by_old["AZUL53"].old_isin, "BRAZULA01OR8")\n        self.assertEqual(by_old["AZUL53"].new_isin, "BRAZULACNOR7")\n        self.assertEqual(by_old["AZUL53"].first_successor_trade_date, "2026-04-20")\n\n    def test_azul54_to_azul53_preserves_total_basis(self) -> None:\n        account = self._account(shares=2, average_cost=75.0)\n        transition = self._certified(\n            effective_date="2026-01-14",\n            old_ticker="OLD4",\n            new_ticker="NEW54",\n            share_ratio=75.0,\n            old_quotation_factor=10000,\n            new_quotation_factor=1000000,\n            fractional_treatment="require_integer",\n            event_type="class_change",\n        )\n        _apply_ticker_transitions(account, [transition])\n        self.assertEqual(account.shares("NEW54"), 150)\n        self.assertAlmostEqual(account.positions["NEW54"].average_cost, 1.0)\n        self.assertAlmostEqual(\n            account.positions["NEW54"].shares * account.positions["NEW54"].average_cost,\n            150.0,\n        )\n\n    def test_azul53_grouping_preserves_basis_only_for_exact_multiple(self) -> None:\n        account = self._account(shares=300000, average_cost=0.001)\n        transition = self._certified(\n            effective_date="2026-04-20",\n            old_ticker="OLD4",\n            new_ticker="NEW3",\n            share_ratio=1.0 / 150000.0,\n            old_quotation_factor=1000000,\n            new_quotation_factor=1,\n            fractional_treatment="cash_in_lieu",\n            event_type="reorganization",\n        )\n        _apply_ticker_transitions(account, [transition])\n        self.assertEqual(account.shares("NEW3"), 2)\n        self.assertAlmostEqual(account.positions["NEW3"].average_cost, 150.0)\n        self.assertAlmostEqual(\n            account.positions["NEW3"].shares * account.positions["NEW3"].average_cost,\n            300.0,\n        )\n\n    def test_azul53_grouping_fraction_remains_fail_closed(self) -> None:\n        account = self._account(shares=100000, average_cost=0.001)\n        transition = self._certified(\n            effective_date="2026-04-20",\n            old_ticker="OLD4",\n            new_ticker="NEW3",\n            share_ratio=1.0 / 150000.0,\n            fractional_treatment="cash_in_lieu",\n            event_type="reorganization",\n        )\n        with self.assertRaisesRegex(ValueError, "cash-in-lieu"):\n            _apply_ticker_transitions(account, [transition])\n'''
    if anchor not in text:
        raise SystemExit("instrument transition test anchor missing")
    TESTS.write_text(text.replace(anchor, addition + anchor, 1), encoding="utf-8")


update_registry()
patch_tests()
