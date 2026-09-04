from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement, found {count}: {old!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


# Current certification is schema v2 only. A complete ledger is insufficient unless
# the run also proves when the event/rate became publicly knowable.
replace_once(
    "b3_strategy_lab/realistic_core.py",
    '''    if certification.get("schema_version") != 1:
        issues.append("unsupported certification schema")
    if certification.get("coverage_certified") is not True:
        issues.append("coverage is not certified")
''',
    '''    if certification.get("schema_version") != 2:
        issues.append("unsupported certification schema")
    if certification.get("coverage_certified") is not True:
        issues.append("coverage is not certified")
    if certification.get("announcement_timing_certified") is not True:
        issues.append("announcement timing is not certified")
    timing_evidence = certification.get("announcement_timing_evidence")
    if not isinstance(timing_evidence, list) or not timing_evidence:
        issues.append("announcement timing evidence is missing")
    else:
        for raw in timing_evidence:
            if not isinstance(raw, dict):
                issues.append("announcement timing evidence record is malformed")
                continue
            authority = str(raw.get("source_authority", "")).strip()
            url = str(raw.get("source_url", "")).strip()
            scope = str(raw.get("scope", "")).strip()
            conclusion = str(raw.get("conclusion", "")).strip()
            if authority not in {"B3", "CVM", "issuer"}:
                issues.append("announcement timing evidence authority is not accepted")
            if not url.startswith("https://"):
                issues.append("announcement timing evidence requires https source_url")
            if not scope or not conclusion:
                issues.append("announcement timing evidence requires scope and conclusion")
''',
)

# The generator can only emit schema v2 after two explicit review attestations.
replace_once(
    "scripts/build_cash_distribution_coverage_certification.py",
    "def _required_cash_tickers(universe_payload: dict[str, object], selectable: set[str]) -> set[str]:\n",
    '''def _load_announcement_timing_evidence(path: Path) -> list[dict[str, object]]:
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
''',
)
replace_once(
    "scripts/build_cash_distribution_coverage_certification.py",
    '    parser.add_argument("--confirm-complete-coverage", action="store_true")\n',
    '    parser.add_argument("--confirm-complete-coverage", action="store_true")\n'
    '    parser.add_argument("--confirm-announcement-timing", action="store_true")\n',
)
replace_once(
    "scripts/build_cash_distribution_coverage_certification.py",
    '''    if not args.confirm_complete_coverage:
        parser.error(
            "Refusing to certify completeness without --confirm-complete-coverage after "
            "a real primary-source review."
        )
''',
    '''    if not args.confirm_complete_coverage:
        parser.error(
            "Refusing to certify completeness without --confirm-complete-coverage after "
            "a real primary-source review."
        )
    if not args.confirm_announcement_timing:
        parser.error(
            "Refusing schema-v2 certification without --confirm-announcement-timing "
            "after reviewing when each event/rate became publicly knowable."
        )
''',
)
replace_once(
    "scripts/build_cash_distribution_coverage_certification.py",
    "    evidence = _load_evidence(args.evidence_file)\n",
    "    evidence = _load_evidence(args.evidence_file)\n"
    "    announcement_timing_evidence = _load_announcement_timing_evidence(args.evidence_file)\n",
)
replace_once(
    "scripts/build_cash_distribution_coverage_certification.py",
    '        "schema_version": 1,\n        "coverage_certified": True,\n',
    '        "schema_version": 2,\n'
    '        "coverage_certified": True,\n'
    '        "announcement_timing_certified": True,\n'
    '        "announcement_timing_evidence": announcement_timing_evidence,\n',
)

# Optional diagnostic mode. Default/certified mode remains fail-fast. Audit mode
# collects independent per-ticker verifier failures, writes them all, then exits nonzero.
replace_once(
    "scripts/sync_point_in_time_universe.py",
    "    build_verified_daily_candles,\n",
    "    DataVerificationError,\n    build_verified_daily_candles,\n",
)
replace_once(
    "scripts/sync_point_in_time_universe.py",
    'DEFAULT_SUPPLEMENTAL_SPLITS = Path("data/corporate_actions/supplemental_split_events.json")\n',
    'DEFAULT_SUPPLEMENTAL_SPLITS = Path("data/corporate_actions/supplemental_split_events.json")\n'
    'DEFAULT_DATA_VERIFICATION_REPORT = Path("reports/point_in_time_data_verification.json")\n',
)
replace_once(
    "scripts/sync_point_in_time_universe.py",
    '    parser.add_argument("--supplemental-splits", type=Path, default=DEFAULT_SUPPLEMENTAL_SPLITS)\n',
    '    parser.add_argument("--supplemental-splits", type=Path, default=DEFAULT_SUPPLEMENTAL_SPLITS)\n'
    '    parser.add_argument("--audit-all-errors", action="store_true")\n'
    '    parser.add_argument("--data-verification-report", type=Path, default=DEFAULT_DATA_VERIFICATION_REPORT)\n',
)
replace_once(
    "scripts/sync_point_in_time_universe.py",
    "    quality_reviews = _load_quality_reviews(args.quality_reviews)\n    for ticker in tickers:\n",
    "    quality_reviews = _load_quality_reviews(args.quality_reviews)\n"
    "    verification_failures: list[dict[str, str]] = []\n"
    "    for ticker in tickers:\n",
)
replace_once(
    "scripts/sync_point_in_time_universe.py",
    '''            verify_dataset(
                candle_file,
                action_file,
                manifest_file,
                ticker=ticker,
                interval=interval,
                require_verified_splits_from=coverage_start,
                split_evidence_path=args.dataset_split_evidence,
            )
        print(f"{ticker}: verified through {daily[-1].date}", flush=True)

    cash_rows, cash_issues = build_cash_events(
''',
    '''            try:
                verify_dataset(
                    candle_file,
                    action_file,
                    manifest_file,
                    ticker=ticker,
                    interval=interval,
                    require_verified_splits_from=coverage_start,
                    split_evidence_path=args.dataset_split_evidence,
                )
            except DataVerificationError as error:
                if not args.audit_all_errors:
                    raise
                verification_failures.append(
                    {"ticker": ticker, "interval": interval, "error": str(error)}
                )
                print(f"AUDIT {ticker}/{interval}: {error}", flush=True)
        if not any(row["ticker"] == ticker for row in verification_failures):
            print(f"{ticker}: verified through {daily[-1].date}", flush=True)

    if args.audit_all_errors:
        _write_json_atomic(
            args.data_verification_report,
            {
                "schema_version": 1,
                "mode": "audit_only_no_publication",
                "ready": not verification_failures,
                "failure_count": len(verification_failures),
                "failures": verification_failures,
            },
        )
        if verification_failures:
            raise ValueError(
                f"{len(verification_failures)} point-in-time dataset verification failure(s); "
                f"all independent ticker datasets were audited. See {args.data_verification_report}."
            )

    cash_rows, cash_issues = build_cash_events(
''',
)

# Update the one legacy unit fixture so it tests current schema-v2 hash binding rather
# than relying on a certificate format the repository already declares obsolete.
replace_once(
    "tests/test_realistic_accounting.py",
    '''                "schema_version": 1,
                "coverage_certified": True,
''',
    '''                "schema_version": 2,
                "coverage_certified": True,
                "announcement_timing_certified": True,
                "announcement_timing_evidence": [
                    {
                        "source_authority": "B3",
                        "source_url": "https://example.test/b3/timing",
                        "scope": "AAA3 announcement timing",
                        "conclusion": "Announcement timing reviewed for the certified period.",
                    }
                ],
''',
)
