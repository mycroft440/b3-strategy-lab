from scripts.audit_matrix_results import _real_money_blockers


def _base_manifest() -> dict[str, object]:
    return {
        "result_classification": "REALISTIC_POINT_IN_TIME_VALIDATED",
        "real_money_claim_allowed": True,
        "evaluation_scope": "holdout",
        "universe": {"survivorship_safe": True},
        "dividends_jcp": "excluded",
        "limitations": [],
    }


def test_explicit_price_only_scope_does_not_require_dividend_certification() -> None:
    blockers = _real_money_blockers(_base_manifest())
    assert blockers == []
    assert "dividends_and_jcp_are_not_certified_in_matrix" not in blockers


def test_non_excluded_dividend_scope_is_rejected() -> None:
    manifest = _base_manifest()
    manifest["dividends_jcp"] = "included_with_certified_cash_events"
    assert "dividends_and_jcp_scope_is_not_explicitly_excluded" in _real_money_blockers(manifest)
