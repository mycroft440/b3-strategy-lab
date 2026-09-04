from __future__ import annotations

import json
from pathlib import Path

from scripts import sync_point_in_time_universe_realistic as realistic


FAILED_RUN_33868398460_TICKERS = {
    "BTOW3",
    "BVMF3",
    "CCRO3",
    "CRFB3",
    "ELET3",
    "EMBR3",
    "ESTC3",
    "FIBR3",
    "GNDI3",
    "GOLL4",
    "JBSS3",
    "KROT3",
    "LAME4",
    "MRFG3",
    "NTCO3",
    "PETZ3",
    "RRRP3",
    "SMLS3",
    "VIIA3",
    "VVAR3",
}


def test_realistic_addendum_covers_historical_tickers_from_failed_rebuild() -> None:
    path = Path("data/corporate_actions/realistic_split_evidence_addendum.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    validated = realistic._validated_ticker_reviews(payload)

    assert FAILED_RUN_33868398460_TICKERS <= validated.keys()
    for ticker in FAILED_RUN_33868398460_TICKERS:
        review = validated[ticker]
        assert review["source_authority"] in {"issuer", "CVM"}
        assert review["source_url"].startswith("https://")
        assert review["review"].strip()


def test_failed_historical_rows_are_bound_before_manifest_write(tmp_path, monkeypatch) -> None:
    payload = realistic._load_evidence_addendum()
    captured: dict[str, object] = {}

    def capture_write(path: Path, value: object) -> None:
        captured["value"] = value

    monkeypatch.setattr(realistic, "_BASE_WRITE_JSON_ATOMIC", capture_write)
    realistic._install_evidence_addendum(payload)

    generated = {
        "schema_version": 3,
        "ticker_reviews": [
            {
                "ticker": ticker,
                "source_authority": "historical_primary_registry",
                "source_url": "",
                "result": "Revisao gerada fail-closed.",
            }
            for ticker in sorted(FAILED_RUN_33868398460_TICKERS)
        ],
    }

    realistic.base._write_json_atomic(tmp_path / "evidence.json", generated)
    written = captured["value"]
    assert isinstance(written, dict)
    rows = written["ticker_reviews"]
    assert isinstance(rows, list)
    assert {row["ticker"] for row in rows} == FAILED_RUN_33868398460_TICKERS
    assert all(row["source_authority"] in {"issuer", "CVM"} for row in rows)
    assert all(row["source_url"].startswith("https://") for row in rows)
