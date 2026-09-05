from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data/corporate_actions/instrument_transition_reviews.json"
PORTFOLIO = ROOT / "b3_strategy_lab/realistic_portfolio.py"
TESTS = ROOT / "tests/test_instrument_transition_layer.py"


def source_review(
    *,
    effective_date: str,
    cutoff_date: str,
    old_ticker: str,
    new_ticker: str = "",
    share_ratio: float = 1.0,
    cash_per_old_share: float = 0.0,
    event_type: str,
    fractional_treatment: str,
    tax_basis_treatment: str,
    source_authority: str,
    source_url: str,
    source_reference: str,
    evidence_summary: str,
    first_successor_trade_date: str = "",
    old_isin: str = "",
    new_isin: str = "",
    old_quotation_factor: int = 1,
    new_quotation_factor: int = 1,
) -> dict[str, object]:
    row: dict[str, object] = {
        "effective_date": effective_date,
        "cutoff_date": cutoff_date,
        "first_successor_trade_date": first_successor_trade_date,
        "old_ticker": old_ticker,
        "new_ticker": new_ticker,
        "share_ratio": share_ratio,
        "old_quotation_factor": old_quotation_factor,
        "new_quotation_factor": new_quotation_factor,
        "cash_per_old_share": cash_per_old_share,
        "event_type": event_type,
        "fractional_treatment": fractional_treatment,
        "tax_basis_treatment": tax_basis_treatment,
        "certification_status": "certified",
        "source_authority": source_authority,
        "source_url": source_url,
        "source_reference": source_reference,
        "evidence_summary": evidence_summary,
    }
    if old_isin:
        row["old_isin"] = old_isin
    if new_isin:
        row["new_isin"] = new_isin
    return row


NEW_REVIEWS = [
    source_review(
        effective_date="2019-01-04",
        cutoff_date="2019-01-03",
        first_successor_trade_date="2019-01-04",
        old_ticker="FIBR3",
        new_ticker="SUZB3",
        share_ratio=0.4613,
        cash_per_old_share=52.50,
        event_type="incorporation",
        fractional_treatment="cash_in_lieu",
        tax_basis_treatment="source_specific",
        source_authority="B3",
        source_url="https://www.b3.com.br/data/files/97/13/62/E8/C651861012FFCD76AC094EA8/OC%20001-2019%20PRE%20Tratamento%20das%20Posi%C3%A7%C3%B5es%20de%20Empr%C3%A9stimo%20de%20Ativos%2C%20Termo%2C%20Op%C3%A7%C3%B5es%20e%20das%20Carteiras%20...Fibria-Suzano.pdf",
        source_reference="B3 Ofício Circular 001/2019-PRE, complementando 099/2018-PRE",
        evidence_summary=(
            "A B3 corrigiu a relação final FIBR3->SUZB3 para 0,4613. A operação também "
            "possui parcela em dinheiro cuja referência contratual parte de R$52,50 e é "
            "ajustada nos termos da reorganização; por isso o replay registra a transição, "
            "mas mantém posições que atravessem o evento em regime fail-closed até existir "
            "motor tributário/source-specific para a parcela em caixa."
        ),
    ),
    source_review(
        effective_date="2019-10-11",
        cutoff_date="2019-10-10",
        first_successor_trade_date="2019-10-11",
        old_ticker="KROT3",
        new_ticker="COGN3",
        event_type="ticker_change",
        fractional_treatment="preserve_units",
        tax_basis_treatment="carry_total_basis",
        source_authority="issuer",
        source_url="https://s3.amazonaws.com/mz-filemanager/e1110a12-6e58-4cb0-be24-ed1d5f18049a/6a99f803-cedd-4ad9-8f0d-19d8b9d95165_Kroton%20-%20Comunicado%20ao%20mercado%20ref.%20mudan%C3%A7a%20de%20ticker_ENG_v2.pdf",
        source_reference="Kroton market notice, 07/10/2019; COGN3 effective 11/10/2019",
        evidence_summary="Mudança de denominação/ticker KROT3 para COGN3 sem conversão econômica de quantidade.",
    ),
    source_review(
        effective_date="2021-06-07",
        cutoff_date="2021-06-04",
        old_ticker="SMLS3",
        share_ratio=1.0,
        event_type="incorporation",
        fractional_treatment="not_applicable",
        tax_basis_treatment="terminal_unresolved",
        source_authority="issuer",
        source_url="https://api.mziq.com/mzfilemanager/v2/d/5670c94c-aa5b-4ed0-ac4d-937b05238c0a/7e0c23c9-41c1-b208-1ef5-231c77fae4ba?origin=1",
        source_reference="GOL/Smiles Aviso aos Acionistas, 04/06/2021",
        evidence_summary=(
            "A data-base foi 04/06/2021 e SMLS3 deixou de negociar a partir de 07/06. "
            "A contraprestação dependia da opção individual do acionista, com relações de "
            "troca e parcelas em dinheiro diferentes. Como um backtest genérico não conhece "
            "essa eleição individual, a saída é source-backed porém terminal_unresolved no "
            "escopo certificado, bloqueando somente uma posição que atravesse o evento."
        ),
    ),
    source_review(
        effective_date="2022-01-24",
        cutoff_date="2022-01-21",
        first_successor_trade_date="2022-01-24",
        old_ticker="LAME4",
        new_ticker="AMER3",
        share_ratio=0.188964,
        event_type="incorporation",
        fractional_treatment="cash_in_lieu",
        tax_basis_treatment="carry_total_basis",
        source_authority="B3",
        source_url="https://www.b3.com.br/data/files/7A/80/06/B5/DF87E7108BD66BD7AC094EA8/OC%20010-2022%20PRE%20Tratamento%20de%20Posi%C3%A7%C3%B5es%20Garantias%20e%20Carteiras%20de%20%C3%8Dndices%20-%20Americanas%20S.A%20e%20Lojas%20Americanas%20%28PT%29.pdf",
        source_reference="B3 Ofício Circular 010/2022-PRE",
        evidence_summary=(
            "Cada LAME4 é convertida em 0,188964 AMER3. Frações são agrupadas e vendidas "
            "em leilão, de modo que o motor pode carregar o custo total quando a quantidade "
            "resultante é inteira e falha fechado quando houver cash-in-lieu não modelado."
        ),
    ),
    source_review(
        effective_date="2022-02-14",
        cutoff_date="2022-02-11",
        first_successor_trade_date="2022-02-14",
        old_ticker="GNDI3",
        new_ticker="HAPV3",
        share_ratio=5.2436,
        cash_per_old_share=5.12601160179,
        event_type="incorporation",
        fractional_treatment="cash_in_lieu",
        tax_basis_treatment="source_specific",
        source_authority="B3",
        source_url="https://www.b3.com.br/data/files/20/F5/CF/9C/777BE71092ECAAE7AC094EA8/OC%20016-2022%20PRE%20Tratamento%20das%20Posi%C3%A7%C3%B5es%20INTERMEDICA%20por%20HAPVIDACo%20%28NCS%29%20%28PT%29.pdf",
        source_reference="B3 Ofício Circular 016/2022-PRE",
        evidence_summary=(
            "Para cada GNDI3 a B3 documenta 5,2436 HAPV3 e R$5,12601160179, além de "
            "tratamento de frações. O componente em dinheiro mantém o evento fail-closed "
            "para posições efetivamente carregadas através da incorporação."
        ),
    ),
    source_review(
        effective_date="2023-01-09",
        cutoff_date="2023-01-06",
        first_successor_trade_date="2023-01-09",
        old_ticker="BRML3",
        new_ticker="ALSO3",
        share_ratio=0.398551577675763,
        cash_per_old_share=1.62899410177968,
        event_type="incorporation",
        fractional_treatment="cash_in_lieu",
        tax_basis_treatment="source_specific",
        source_authority="B3",
        source_url="https://www.b3.com.br/data/files/69/11/4D/06/33975810F534EB48AC094EA8/OC%20001-2023-VNC%20Tratamento%20posi%C3%A7%C3%B5es%20incorpora%C3%A7%C3%A3o%20BRML%20ALSO.pdf",
        source_reference="B3 Ofício Circular 001/2023-VNC",
        evidence_summary=(
            "A incorporação converte BRML3 em 0,398551577675763 ALSO3 e contém parcela "
            "em dinheiro. O histórico deixa de ser classificado como desaparecimento sem "
            "explicação, mas a posição permanece fail-closed até o caixa/tributação ser "
            "reproduzido por regra source-specific."
        ),
    ),
    source_review(
        effective_date="2024-08-27",
        cutoff_date="2024-08-26",
        old_ticker="CIEL3",
        event_type="registration_cancelled",
        fractional_treatment="not_applicable",
        tax_basis_treatment="terminal_unresolved",
        source_authority="B3",
        source_url="https://www.b3.com.br/data/files/09/D5/1E/78/68BE09105FE89209AC094EA8/OC%20011-2024-VNC%20Tratamento%20posi%C3%A7%C3%B5es%20e%20carteiras%20de%20%C3%ADndices%20em%20caso%20de%20convers%C3%A3o%20de%20registro%20de%20cia%20aberta%20e%20sa%C3%ADda%20do%20NM%20da%20Cielo%20_PT.pdf",
        source_reference="B3 Ofício Circular 011/2024-VNC; fronteira de negociação vinculada ao COTAHIST oficial",
        evidence_summary=(
            "A OPA/conversão de registro encerra a negociação de CIEL3 e liquida posições "
            "com preço da OPA sujeito aos ajustes definidos no edital. Sem reproduzir essa "
            "liquidação e a eleição do acionista, o evento é explicitamente terminal_unresolved "
            "e bloqueia apenas carteiras que ainda detenham CIEL3 na fronteira."
        ),
    ),
    source_review(
        effective_date="2024-09-09",
        cutoff_date="2024-09-06",
        first_successor_trade_date="2024-09-09",
        old_ticker="RRRP3",
        new_ticker="BRAV3",
        event_type="ticker_change",
        fractional_treatment="preserve_units",
        tax_basis_treatment="carry_total_basis",
        source_authority="B3",
        source_url="https://www.b3.com.br/pt_br/noticias/fusao.htm",
        source_reference="B3, 3R Petroleum e Enauta celebram fusão; BRAV3 a partir de 09/09/2024",
        evidence_summary="RRRP3 passa a BRAV3 por mudança da denominação/ticker da mesma companhia, preservando quantidade e custo total.",
    ),
    source_review(
        effective_date="2025-06-02",
        cutoff_date="2025-05-30",
        old_ticker="CRFB3",
        event_type="incorporation",
        fractional_treatment="not_applicable",
        tax_basis_treatment="terminal_unresolved",
        source_authority="B3",
        source_url="https://www.b3.com.br/data/files/03/E7/AF/B0/2FBC69106B8BCB69AC094EA8/OC%20005-2025-VNC%20TRATAMENTO%20DAS%20CARTEIRAS%20DE%20%C3%8DNDICES%20DA%20B3_PT.pdf",
        source_reference="B3 Ofício Circular 005/2025-VNC",
        evidence_summary=(
            "CRFB3 é excluída após 30/05/2025 em decorrência da incorporação pela "
            "Brachiosaurus. A sequência econômica envolve instrumentos fora do escopo ON/PN "
            "certificado; portanto a descontinuidade é explicada, mas uma posição carregada "
            "através do evento continua bloqueada em vez de receber um ativo sintético."
        ),
    ),
    source_review(
        effective_date="2025-06-09",
        cutoff_date="2025-06-06",
        old_ticker="JBSS3",
        share_ratio=0.5,
        event_type="reorganization",
        fractional_treatment="not_applicable",
        tax_basis_treatment="terminal_unresolved",
        source_authority="B3",
        source_url="https://sistemasweb.b3.com.br/PlantaoNoticias/Noticias/Detail?agencia=15&dataNoticia=2025-05-29+05%3A36%3A32&idNoticia=2951853",
        source_reference="B3 Plantão de Notícias, incorporação JBSS3 e BDR JBS N.V.",
        evidence_summary=(
            "A B3 documenta a exclusão de JBSS3 após 06/06/2025 e a relação de 0,50 BDR "
            "patrocinado JBS N.V. por ação para os índices aplicáveis. BDR é deliberadamente "
            "fora do escopo tributário certificado ON/PN deste replay; a saída é marcada como "
            "terminal_unresolved para impedir continuidade sintética."
        ),
    ),
    source_review(
        effective_date="2025-07-02",
        cutoff_date="2025-07-01",
        first_successor_trade_date="2025-07-02",
        old_ticker="NTCO3",
        new_ticker="NATU3",
        event_type="incorporation",
        fractional_treatment="preserve_units",
        tax_basis_treatment="carry_total_basis",
        source_authority="issuer",
        source_url="https://ri.natura.com.br/noticias/natura-conclui-incorporacao-da-natura-co-e-voltara-a-ser-negociada-como-natu3/",
        source_reference="Natura RI, conclusão da incorporação; NATU3 a partir de 02/07/2025",
        evidence_summary="Cada NTCO3 é substituída por uma NATU3 na razão 1:1.",
    ),
    source_review(
        effective_date="2025-11-10",
        cutoff_date="2025-11-07",
        first_successor_trade_date="2025-11-10",
        old_ticker="CPLE6",
        new_ticker="CPLE5",
        old_isin="BRCPLEACNPB9",
        new_isin="BRCPLEACNPA1",
        event_type="class_change",
        fractional_treatment="preserve_units",
        tax_basis_treatment="carry_total_basis",
        source_authority="B3",
        source_url="https://www.b3.com.br/data/files/0D/93/90/BB/A455A910F51990A9AC094EA8/OC%20047-2025-VNC%20TRATAMENTO%20NAS%20CARTEIRAS%20DE%20%C3%8DNDICES%20DA%20B3%20EM%20VIRTUDE%20DO%20EVENTO%20DE%20CONVERSAO%20DA%20COMPANHIA%20PARANAENSE%20DE%20ENERGIA%20COPEL_PT.pdf",
        source_reference="B3 Ofício Circular 047/2025-VNC",
        evidence_summary="CPLE6 é convertida em CPLE5 na razão 1:1 a partir de 10/11/2025.",
    ),
    source_review(
        effective_date="2025-12-22",
        cutoff_date="2025-12-19",
        first_successor_trade_date="2025-12-22",
        old_ticker="CPLE5",
        new_ticker="CPLE3",
        old_isin="BRCPLEACNPA1",
        new_isin="BRCPLEACNOR8",
        cash_per_old_share=0.7749,
        event_type="class_change",
        fractional_treatment="preserve_units",
        tax_basis_treatment="source_specific",
        source_authority="B3",
        source_url="https://www.b3.com.br/data/files/50/05/93/F6/AFAEA9105B12E5A9AC094EA8/CL%20055-2025-VNC%20TRATAMENTO%20DAS%20POSICOES%20GARANTIAS%20E%20DAS%20CARTEIRAS%20DE%20%C3%8DNDICES%20EM%20VIRTUDE%20DA%20CONVERSAO_%20EN.pdf",
        source_reference="B3 Circular Letter 055/2025-VNC",
        evidence_summary=(
            "Cada CPLE5 gera uma CPLE3 e uma CPLE7 resgatável automaticamente por R$0,7749. "
            "O equivalente em caixa é preservado no registro, mas a posição cruza o evento "
            "somente quando houver tratamento tributário source-specific para o resgate."
        ),
    ),
    source_review(
        effective_date="2025-12-23",
        cutoff_date="2025-12-22",
        first_successor_trade_date="2025-12-23",
        old_ticker="AZUL4",
        new_ticker="AZUL54",
        old_isin="BRAZULACNPR4",
        new_isin="BRAZULA02PR3",
        old_quotation_factor=1,
        new_quotation_factor=10000,
        event_type="reorganization",
        fractional_treatment="preserve_units",
        tax_basis_treatment="carry_total_basis",
        source_authority="B3",
        source_url="https://sistemasweb.b3.com.br/PlantaoNoticias/Noticias/Detail?agencia=18&dataNoticia=2025-12-22+19%3A54%3A44&idNoticia=3181790",
        source_reference="B3 Plantão de Notícias, Fato Relevante AZUL, 22/12/2025",
        evidence_summary=(
            "A partir de 23/12/2025 AZUL4 passa a AZUL54 com novo ISIN, lote padrão e fator "
            "de cotação de 10.000. O fator de cotação não multiplica a quantidade econômica "
            "de ações, que permanece 1:1."
        ),
    ),
    source_review(
        effective_date="2026-04-01",
        cutoff_date="2026-03-31",
        old_ticker="GOLL54",
        event_type="incorporation",
        fractional_treatment="not_applicable",
        tax_basis_treatment="terminal_unresolved",
        source_authority="issuer",
        source_url="https://ri.voegol.com.br/esg/diretoria-e-conselho-de-administracao/",
        source_reference="GOL RI: GLAI incorporada pela GLA com efeitos em 01/04/2026",
        evidence_summary=(
            "A GLAI foi incorporada pela GLA em 01/04/2026 após a OPA e saiu da B3. A OPA "
            "era opcional e havia período de aquisição remanescente com preço corrigido; sem "
            "a eleição individual do acionista, o replay não inventa liquidação e bloqueia "
            "somente posições GOLL54 que atravessem o evento."
        ),
    ),
]


def update_registry() -> None:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("reviews"), list):
        raise SystemExit("unexpected transition review registry schema")
    reviews = payload["reviews"]
    keys = {
        (str(row.get("effective_date")), str(row.get("old_ticker")), str(row.get("new_ticker", "")))
        for row in reviews
    }
    for row in NEW_REVIEWS:
        key = (str(row["effective_date"]), str(row["old_ticker"]), str(row["new_ticker"]))
        if key not in keys:
            reviews.append(row)
            keys.add(key)
    reviews.sort(key=lambda row: (str(row["effective_date"]), str(row["old_ticker"]), str(row.get("new_ticker", ""))))
    REGISTRY.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def patch_unheld_transition_semantics() -> None:
    text = PORTFOLIO.read_text(encoding="utf-8")
    old = """def _apply_ticker_transitions(account, transitions) -> None:\n    for transition in transitions:\n        if not math.isclose(float(transition.cash_per_old_share), 0.0, abs_tol=1e-12):\n"""
    new = """def _apply_ticker_transitions(account, transitions) -> None:\n    for transition in transitions:\n        # A source-reviewed corporate event is relevant to account economics only\n        # when the account actually carries the disappearing instrument across it.\n        # Unheld terminal/complex events must not poison unrelated portfolios.\n        if account.shares(transition.old_ticker) <= 0:\n            continue\n        if not math.isclose(float(transition.cash_per_old_share), 0.0, abs_tol=1e-12):\n"""
    if new in text:
        return
    if text.count(old) != 1:
        raise SystemExit("unexpected realistic_portfolio transition wrapper shape")
    PORTFOLIO.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_tests() -> None:
    text = TESTS.read_text(encoding="utf-8")
    if "test_unheld_terminal_unresolved_event_does_not_poison_unrelated_account" in text:
        return
    anchor = "\n\nif __name__ == \"__main__\":\n    unittest.main()\n"
    addition = r'''

    def test_unheld_terminal_unresolved_event_does_not_poison_unrelated_account(self) -> None:
        account = self._account()
        account.positions["OLD4"].shares = 0
        account.positions["OLD4"].average_cost = 0.0
        transition = self._certified(
            new_ticker="",
            new_isin="",
            event_type="registration_cancelled",
            fractional_treatment="not_applicable",
            tax_basis_treatment="terminal_unresolved",
            first_successor_trade_date="",
            new_quotation_factor=1,
        )
        cash_before = account.cash
        _apply_ticker_transitions(account, [transition])
        self.assertAlmostEqual(account.cash, cash_before)

    def test_held_terminal_unresolved_event_still_fails_closed(self) -> None:
        account = self._account()
        transition = self._certified(
            new_ticker="",
            new_isin="",
            event_type="registration_cancelled",
            fractional_treatment="not_applicable",
            tax_basis_treatment="terminal_unresolved",
            first_successor_trade_date="",
            new_quotation_factor=1,
        )
        with self.assertRaisesRegex(ValueError, "terminal transition"):
            _apply_ticker_transitions(account, [transition])

    def test_transition_registry_covers_historical_disappearance_set(self) -> None:
        reviews = load_transition_reviews(
            Path("data/corporate_actions/instrument_transition_reviews.json")
        )
        by_old = {item.old_ticker: item for item in reviews}
        required = {
            "AZUL4", "BRML3", "CIEL3", "CPLE6", "CRFB3", "FIBR3", "GNDI3",
            "GOLL54", "JBSS3", "KROT3", "LAME4", "NTCO3", "RRRP3", "SMLS3",
        }
        self.assertEqual(required - set(by_old), set())
        self.assertEqual(by_old["AZUL4"].new_ticker, "AZUL54")
        self.assertEqual(by_old["AZUL4"].new_quotation_factor, 10000)
        self.assertTrue(math.isclose(by_old["FIBR3"].share_ratio, 0.4613))
        self.assertTrue(math.isclose(by_old["GNDI3"].share_ratio, 5.2436))
        self.assertTrue(math.isclose(by_old["LAME4"].share_ratio, 0.188964))
        self.assertEqual(by_old["NTCO3"].new_ticker, "NATU3")
        self.assertEqual(by_old["RRRP3"].new_ticker, "BRAV3")
        for ticker in ("CIEL3", "CRFB3", "GOLL54", "JBSS3", "SMLS3"):
            self.assertEqual(by_old[ticker].new_ticker, "")
            self.assertEqual(by_old[ticker].tax_basis_treatment, "terminal_unresolved")
'''
    if anchor not in text:
        raise SystemExit("instrument transition test anchor missing")
    TESTS.write_text(text.replace(anchor, addition + anchor, 1), encoding="utf-8")


def validate_source_rows() -> None:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = payload["reviews"]
    for row in rows:
        if row.get("certification_status") != "certified":
            continue
        if not str(row.get("source_url", "")).startswith("https://"):
            raise SystemExit(f"missing https source for {row.get('old_ticker')}")
        ratio = float(row.get("share_ratio", 1.0))
        cash = float(row.get("cash_per_old_share", 0.0))
        if not math.isfinite(ratio) or ratio <= 0 or not math.isfinite(cash) or cash < 0:
            raise SystemExit(f"invalid economic values for {row.get('old_ticker')}")


update_registry()
patch_unheld_transition_semantics()
patch_tests()
validate_source_rows()
