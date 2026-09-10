from scripts.research_portfolio_allocation import _research_invalid_transition_reason


def test_terminal_transition_classifies_missing_close_with_masculine_message() -> None:
    reason = _research_invalid_transition_reason(
        "2024-08-27: fechamento fresco obrigatorio ausente para CIEL3"
    )
    assert reason == (
        "2024-08-27:CIEL3->TERMINAL:registration_cancelled:"
        "CERTIFIED_COMPLEX_TRANSITION_UNSUPPORTED_IN_PRICE_ONLY_RESEARCH"
    )


def test_complex_transition_classifies_missing_open_with_feminine_message() -> None:
    reason = _research_invalid_transition_reason(
        "2022-02-14: abertura fresca obrigatoria ausente para GNDI3"
    )
    assert reason == (
        "2022-02-14:GNDI3->HAPV3:incorporation:"
        "CERTIFIED_COMPLEX_TRANSITION_UNSUPPORTED_IN_PRICE_ONLY_RESEARCH"
    )


def test_unexplained_missing_price_remains_fail_closed() -> None:
    assert _research_invalid_transition_reason(
        "2024-08-27: fechamento fresco obrigatorio ausente para PETR4"
    ) is None
