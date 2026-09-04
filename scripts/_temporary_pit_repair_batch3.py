from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement, found {count}: {old!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


# Cash-distribution certification schema v2 is required only for a causal/certified
# replay. Legacy schema-v1 coverage validation remains readable for old artifacts and
# unit tests, but cannot satisfy the production certified-input audit.
replace_once(
    "b3_strategy_lab/realistic_core.py",
    '''def cash_coverage_certification_issues(
    certification: dict[str, object],
    *,
    cash_events_path: Path | str,
    cash_manifest_path: Path | str,
    tickers: Iterable[str],
    start: str,
    end: str,
) -> list[str]:
''',
    '''def cash_coverage_certification_issues(
    certification: dict[str, object],
    *,
    cash_events_path: Path | str,
    cash_manifest_path: Path | str,
    tickers: Iterable[str],
    start: str,
    end: str,
    require_announcement_timing: bool = False,
) -> list[str]:
''',
)
replace_once(
    "b3_strategy_lab/realistic_core.py",
    '''    if certification.get("schema_version") != 1:
        issues.append("unsupported certification schema")
    if certification.get("coverage_certified") is not True:
        issues.append("coverage is not certified")
''',
    '''    schema_version = certification.get("schema_version")
    if schema_version not in {1, 2}:
        issues.append("unsupported certification schema")
    if certification.get("coverage_certified") is not True:
        issues.append("coverage is not certified")
    if require_announcement_timing:
        if schema_version != 2:
            issues.append("certified causal replay requires cash certification schema 2")
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

# The public hardening wrapper must expose and forward the new strictness option.
replace_once(
    "b3_strategy_lab/realistic.py",
    '''def cash_coverage_certification_issues(
    certification: dict[str, object],
    *,
    cash_events_path,
    cash_manifest_path,
    tickers,
    start: str,
    end: str,
) -> list[str]:
''',
    '''def cash_coverage_certification_issues(
    certification: dict[str, object],
    *,
    cash_events_path,
    cash_manifest_path,
    tickers,
    start: str,
    end: str,
    require_announcement_timing: bool = False,
) -> list[str]:
''',
)
replace_once(
    "b3_strategy_lab/realistic.py",
    '''            tickers=tickers,
            start=start,
            end=end,
        )
''',
    '''            tickers=tickers,
            start=start,
            end=end,
            require_announcement_timing=require_announcement_timing,
        )
''',
)

replace_once(
    "scripts/audit_realistic_backtest_inputs.py",
    '''            tickers=market_data,
            start=start,
            end=end,
        )
''',
    '''            tickers=market_data,
            start=start,
            end=end,
            require_announcement_timing=True,
        )
''',
)

# Generator always creates the stronger schema-v2 object and refuses to claim causal
# knowledge unless the reviewer explicitly supplies and confirms timing evidence.
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

# Optional audit mode: official/certified execution still raises on the first critical
# dataset verifier error; --audit-all-errors catches independent ticker failures, writes
# one complete report, and then exits non-zero so nothing can be certified/published.
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
                print(
                    f"AUDIT {ticker}/{interval}: {error}",
                    flush=True,
                )
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
