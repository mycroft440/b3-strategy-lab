from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.realistic import (  # noqa: E402
    PointInTimeUniverse,
    cash_coverage_certification_issues,
)


DEFAULT_EVENTS = Path("data/corporate_actions/point_in_time_cash_distributions.csv")
DEFAULT_MANIFEST = Path("data/corporate_actions/point_in_time_cash_distributions.manifest.json")
DEFAULT_UNIVERSE = Path("data/universes/point_in_time_union.json")
DEFAULT_SNAPSHOTS = Path("data/universes/point_in_time_weekly.csv")
DEFAULT_OUTPUT = Path("data/corporate_actions/cash_distribution_coverage_certification.json")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _load_evidence(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("evidence") if isinstance(payload, dict) else payload
    if not isinstance(items, list) or not items:
        raise ValueError("Evidence file must contain a non-empty evidence list.")
    normalized: list[dict[str, object]] = []
    accepted = {"B3", "CVM", "issuer"}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each evidence item must be an object.")
        authority = str(item.get("source_authority", "")).strip()
        url = str(item.get("source_url", "")).strip()
        scope = str(item.get("scope", "")).strip()
        conclusion = str(item.get("conclusion", "")).strip()
        if authority not in accepted:
            raise ValueError(f"Unsupported evidence authority: {authority}")
        if not url.startswith("https://"):
            raise ValueError("Every coverage evidence item requires an https source_url.")
        if not scope or not conclusion:
            raise ValueError("Every coverage evidence item requires scope and conclusion.")
        normalized.append(
            {
                "source_authority": authority,
                "source_url": url,
                "scope": scope,
                "conclusion": conclusion,
                "source_payload_sha256": str(item.get("source_payload_sha256", "")).strip(),
            }
        )
    return normalized


def _load_announcement_timing_evidence(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("announcement_timing_evidence") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        raise ValueError(
            "Evidence file must contain a non-empty announcement_timing_evidence list."
        )
    normalized: list[dict[str, object]] = []
    accepted = {"B3", "CVM", "issuer"}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each announcement timing evidence item must be an object.")
        authority = str(item.get("source_authority", "")).strip()
        url = str(item.get("source_url", "")).strip()
        scope = str(item.get("scope", "")).strip()
        conclusion = str(item.get("conclusion", "")).strip()
        if authority not in accepted:
            raise ValueError(f"Unsupported announcement evidence authority: {authority}")
        if not url.startswith("https://"):
            raise ValueError("Every announcement evidence item requires an https source_url.")
        if not scope or not conclusion:
            raise ValueError("Every announcement evidence item requires scope and conclusion.")
        normalized.append(
            {
                "source_authority": authority,
                "source_url": url,
                "scope": scope,
                "conclusion": conclusion,
                "source_payload_sha256": str(item.get("source_payload_sha256", "")).strip(),
            }
        )
    return normalized


def _required_cash_tickers(universe_payload: dict[str, object], selectable: set[str]) -> set[str]:
    values = universe_payload.get("market_data_tickers", sorted(selectable))
    if not isinstance(values, list):
        raise ValueError("market_data_tickers must be a list when present.")
    required = {str(item).strip().upper() for item in values if str(item).strip()}
    if not selectable.issubset(required):
        raise ValueError("market_data_tickers must contain every selectable ticker.")
    return required


def _iso_date(value: object, label: str) -> str:
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a valid ISO date.") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Bind a human-reviewed cash-distribution completeness review to the exact "
            "ledger and manifest bytes used by the realistic backtest. This command "
            "does not invent completeness: --confirm-complete-coverage is mandatory."
        )
    )
    parser.add_argument("--evidence-file", type=Path, required=True)
    parser.add_argument("--reviewed-by", required=True)
    parser.add_argument("--confirm-complete-coverage", action="store_true")
    parser.add_argument("--confirm-announcement-timing", action="store_true")
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--cash-manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--snapshots", type=Path, default=DEFAULT_SNAPSHOTS)
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    if not args.confirm_complete_coverage:
        parser.error(
            "Refusing to certify completeness without --confirm-complete-coverage after "
            "a real primary-source review."
        )
    if not args.confirm_announcement_timing:
        parser.error(
            "Refusing schema-v2 certification without --confirm-announcement-timing "
            "after reviewing when each event/rate became publicly knowable."
        )
    for path in (args.events, args.cash_manifest, args.universe, args.snapshots, args.evidence_file):
        if not path.exists():
            parser.error(f"Required input is missing: {path}")

    manifest = json.loads(args.cash_manifest.read_text(encoding="utf-8"))
    if manifest.get("complete") is not True or manifest.get("issues"):
        parser.error("Cash ledger manifest itself is not parse-complete; certification refused.")

    universe_payload = json.loads(args.universe.read_text(encoding="utf-8"))
    universe = PointInTimeUniverse.from_csv(args.snapshots)
    selectable = {str(item).upper() for item in universe_payload.get("tickers", [])}
    if universe.union != selectable:
        parser.error("Snapshot union differs from the universe manifest.")
    try:
        required_cash_tickers = _required_cash_tickers(universe_payload, selectable)
    except ValueError as exc:
        parser.error(str(exc))

    manifest_market_data = {
        str(item).strip().upper()
        for item in manifest.get("market_data_tickers", [])
        if str(item).strip()
    }
    if manifest_market_data != required_cash_tickers:
        parser.error(
            "Cash ledger manifest ticker identity differs from the current market_data_tickers; "
            "rebuild/synchronize the cash ledger before certification."
        )
    if int(manifest.get("market_data_ticker_count", -1)) != len(required_cash_tickers):
        parser.error("Cash ledger manifest market_data_ticker_count is inconsistent with its ticker list.")

    start = args.start or str(
        universe_payload.get("selected_as_of", universe.snapshots[0].effective_date)
    )[:10]
    declared_end = str(
        universe_payload.get(
            "selection_end",
            max(snapshot.effective_date for snapshot in universe.snapshots),
        )
    )[:10]
    end = args.end or declared_end
    try:
        start = _iso_date(start, "start")
        end = _iso_date(end, "end")
        declared_end = _iso_date(declared_end, "universe selection_end")
        manifest_start = _iso_date(manifest.get("coverage_start"), "cash manifest coverage_start")
        manifest_end = _iso_date(manifest.get("coverage_end"), "cash manifest coverage_end")
    except ValueError as exc:
        parser.error(str(exc))
    if end < start:
        parser.error("--end must not precede --start.")
    if end > declared_end:
        parser.error("Cash coverage cannot be certified beyond the universe selection_end.")
    if manifest_start > start or manifest_end < end:
        parser.error(
            "Cash ledger manifest coverage does not contain the requested certification period."
        )

    evidence = _load_evidence(args.evidence_file)
    announcement_timing_evidence = _load_announcement_timing_evidence(args.evidence_file)
    authorities = {str(item["source_authority"]) for item in evidence}
    # Keep the summary authority truthful without claiming sources that were not
    # reviewed. Mixed evidence remains fully visible in the evidence list; the
    # summary uses a validator-supported primary authority actually present.
    if "B3" in authorities:
        source_authority = "B3"
    elif "CVM" in authorities:
        source_authority = "CVM"
    else:
        parser.error(
            "Issuer-only evidence is primary-source evidence but the current certificate "
            "validator does not expose an issuer-only summary authority. Add B3/CVM "
            "coverage or extend the validator before certifying; do not overstate sources."
        )

    payload = {
        "schema_version": 2,
        "coverage_certified": True,
        "announcement_timing_certified": True,
        "announcement_timing_evidence": announcement_timing_evidence,
        "start": start,
        "end": end,
        "tickers": sorted(required_cash_tickers),
        "ticker_scope": "market_data_tickers_including_continuity_history",
        "selectable_ticker_count": len(selectable),
        "market_data_ticker_count": len(required_cash_tickers),
        "continuity_only_ticker_count": len(required_cash_tickers - selectable),
        "source_authority": source_authority,
        "reviewed_by": args.reviewed_by.strip(),
        "reviewed_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "evidence": evidence,
        "cash_events_sha256": _sha256(args.events),
        "cash_manifest_sha256": _sha256(args.cash_manifest),
        "cash_event_count": int(manifest.get("event_count", 0)),
        "cash_manifest_coverage_start": manifest_start,
        "cash_manifest_coverage_end": manifest_end,
        "attestation": (
            "The reviewer attests that primary-source coverage was checked for the "
            "full market-data ticker set used by the replay, including continuity-only "
            "historical symbols, and for the stated replay period; this is not merely a parsing check."
        ),
    }

    issues = cash_coverage_certification_issues(
        payload,
        cash_events_path=args.events,
        cash_manifest_path=args.cash_manifest,
        tickers=required_cash_tickers,
        start=start,
        end=end,
    )
    if issues:
        raise ValueError(f"Generated certification failed self-validation: {issues}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Certified cash-distribution coverage: {args.output}")
    print(f"Bound ledger SHA256: {payload['cash_events_sha256']}")
    print(f"Bound manifest SHA256: {payload['cash_manifest_sha256']}")
    print(
        f"Certified ticker scope: {len(required_cash_tickers)} market-data symbols "
        f"({len(required_cash_tickers - selectable)} continuity-only) through {end}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
