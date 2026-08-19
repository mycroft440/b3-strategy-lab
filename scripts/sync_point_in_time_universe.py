from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.b3_official import (  # noqa: E402
    audit_share_count_markers,
    extract_official_split_events,
    merge_official_split_events,
    parse_supplemental_split_events,
)
from b3_strategy_lab.cash_distributions import build_cash_events  # noqa: E402
from b3_strategy_lab.candles import actions_path, cache_path, load_actions, save_actions  # noqa: E402
from b3_strategy_lab.cotahist import (  # noqa: E402
    DEFAULT_MANIFESTS_DIR,
    build_verified_daily_candles,
    create_manifest,
    manifest_path,
    resample_daily_to_weekly,
    save_verified_candles,
    verify_dataset,
    write_manifest,
)
from scripts.sync_official_universe import (  # noqa: E402
    _event_continuity_audit,
    _historical_quotes,
    _load_quality_reviews,
    _load_supplements,
    _merge_official_splits,
    _merge_sources,
    _parse_years,
    _prepare_archives,
    _prior_sources,
    _read_official_quotes,
    _write_json_atomic,
)


DEFAULT_UNIVERSE = Path("data/universes/point_in_time_union.json")
DEFAULT_SPLIT_EVIDENCE = Path("data/corporate_actions/point_in_time_split_evidence.json")
DEFAULT_CASH = Path("data/corporate_actions/point_in_time_cash_distributions.csv")
DEFAULT_CASH_MANIFEST = Path("data/corporate_actions/point_in_time_cash_distributions.manifest.json")
DEFAULT_MISSING_SPLITS = Path("reports/point_in_time_missing_split_evidence.json")
DEFAULT_SUPPLEMENTAL_SPLITS = Path("data/corporate_actions/supplemental_split_events.json")


def _write_cash(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "ticker",
        "label",
        "last_date_prior",
        "ex_date",
        "payment_date",
        "gross_per_share",
        "isin",
        "source_authority",
        "source_url",
    ]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Sync all symbols required by the realistic account, including same-ISIN "
            "continuity-only tickers. Splits are fail-closed: uncovered COTAHIST "
            "share-count markers stop the build."
        )
    )
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--archives-dir", type=Path, default=Path(".cache/cotahist"))
    parser.add_argument("--supplements-dir", type=Path, default=Path(".cache/b3_supplements"))
    parser.add_argument("--data-dir", type=Path, default=Path("data/candles"))
    parser.add_argument("--actions-dir", type=Path, default=Path("data/corporate_actions"))
    parser.add_argument("--manifests-dir", type=Path, default=DEFAULT_MANIFESTS_DIR)
    parser.add_argument("--split-evidence", type=Path, default=DEFAULT_SPLIT_EVIDENCE)
    parser.add_argument("--cash-output", type=Path, default=DEFAULT_CASH)
    parser.add_argument("--cash-manifest", type=Path, default=DEFAULT_CASH_MANIFEST)
    parser.add_argument("--missing-splits-report", type=Path, default=DEFAULT_MISSING_SPLITS)
    parser.add_argument("--supplemental-splits", type=Path, default=DEFAULT_SUPPLEMENTAL_SPLITS)
    parser.add_argument("--quality-reviews", type=Path, default=Path("data/quality_reviews.json"))
    parser.add_argument("--years", nargs="+", default=[f"2017:{date.today().year}"])
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--refresh-current", action="store_true")
    parser.add_argument("--refresh-actions", action="store_true")
    parser.add_argument("--action-workers", type=int, default=2)
    parser.add_argument("--allow-incomplete-cash-ledger", action="store_true")
    args = parser.parse_args(argv)

    universe = json.loads(args.universe.read_text(encoding="utf-8"))
    if universe.get("point_in_time") is not True:
        parser.error("--universe must provide point-in-time historical snapshots.")
    survivorship_safe = universe.get("survivorship_safe") is True
    retrospective_fixed = not survivorship_safe
    if retrospective_fixed and universe.get("no_replacements") is not True:
        parser.error(
            "A non-survivorship-safe universe is accepted only for the explicitly "
            "retrospective fixed-universe/no-replacements replay."
        )

    selected_tickers = [str(ticker).strip().upper() for ticker in universe["tickers"]]
    tickers = [
        str(ticker).strip().upper()
        for ticker in universe.get("market_data_tickers", selected_tickers)
    ]
    if not set(selected_tickers).issubset(tickers):
        parser.error("market_data_tickers must contain every selectable ticker.")
    coverage_start = str(universe["warmup_start"])
    issuer_by_ticker = {
        str(ticker).upper(): str(issuer).upper()
        for ticker, issuer in universe["issuing_company_by_ticker"].items()
    }
    missing_issuer_codes = sorted(set(tickers) - set(issuer_by_ticker))
    if missing_issuer_codes:
        parser.error(f"Missing issuing-company codes for: {missing_issuer_codes}")

    years = _parse_years(args.years)
    archives = _prepare_archives(
        years,
        args.archives_dir,
        download=args.download,
        refresh_current=args.refresh_current,
    )
    quotes_by_ticker, sources = _read_official_quotes(
        archives,
        tickers,
        exclude_date=date.today().isoformat(),
    )
    payloads = _load_supplements(
        sorted(set(issuer_by_ticker[ticker] for ticker in tickers)),
        args.supplements_dir,
        refresh=args.refresh_actions,
        workers=args.action_workers,
    )

    supplemental_by_ticker: dict[str, list] = defaultdict(list)
    if args.supplemental_splits.exists():
        payload = json.loads(args.supplemental_splits.read_text(encoding="utf-8"))
        filtered = dict(payload)
        filtered["events"] = [
            event
            for event in payload.get("events", [])
            if str(event.get("ticker", "")).upper() in set(tickers)
        ]
        parsed = parse_supplemental_split_events(
            filtered,
            tickers=tickers,
            quote_dates_by_ticker={
                ticker: (quote.date for quote in quotes_by_ticker[ticker])
                for ticker in tickers
            },
            coverage_start=coverage_start,
        )
        for event in parsed:
            supplemental_by_ticker[event.ticker].append(event)

    events_by_ticker = {}
    marker_rows: list[dict[str, object]] = []
    missing_markers: list[dict[str, object]] = []
    evidence_events: list[dict[str, object]] = []
    for ticker in tickers:
        issuer = issuer_by_ticker[ticker]
        quotes = quotes_by_ticker[ticker]
        current = extract_official_split_events(
            payloads[issuer],
            ticker=ticker,
            issuing_company=issuer,
            quote_dates=(quote.date for quote in quotes),
            quote_isins=(quote.isin for quote in quotes),
            coverage_start=coverage_start,
        )
        events = merge_official_split_events(current, supplemental_by_ticker[ticker])
        events_by_ticker[ticker] = events
        markers = audit_share_count_markers(
            quotes,
            events,
            coverage_start=coverage_start,
        )
        for marker in markers:
            row = {"ticker": ticker, **marker}
            marker_rows.append(row)
            if not marker["covered"]:
                missing_markers.append(row)
        continuity = _event_continuity_audit(quotes, events)
        excessive = [
            item
            for item in continuity
            if abs(float(item["split_neutral_raw_close_return"])) > 0.35
        ]
        if excessive:
            raise ValueError(f"{ticker}: split-neutral discontinuity exceeds 35%: {excessive}")
        evidence_events.extend(event.evidence() for event in events)

    if missing_markers:
        _write_json_atomic(
            args.missing_splits_report,
            {
                "schema_version": 1,
                "ready": False,
                "reason": "uncovered_share_count_markers",
                "markers": missing_markers,
            },
        )
        raise ValueError(
            f"{len(missing_markers)} share-count markers lack primary-source split evidence. "
            f"See {args.missing_splits_report}; realistic build stopped."
        )

    evidence_payload = {
        "schema_version": 3,
        "coverage_start": coverage_start,
        "survivorship_safe_universe": survivorship_safe,
        "selection_validity": (
            "SURVIVORSHIP_SAFE_POINT_IN_TIME"
            if survivorship_safe
            else "RETROSPECTIVE_FIXED_UNIVERSE_ONLY"
        ),
        "no_replacements": universe.get("no_replacements") is True,
        "point_in_time_universe": str(args.universe),
        "selectable_ticker_count": len(selected_tickers),
        "market_data_ticker_count": len(tickers),
        "marker_count": len(marker_rows),
        "uncovered_count": 0,
        "events": sorted(evidence_events, key=lambda row: (row["ex_date"], row["ticker"])),
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    _write_json_atomic(args.split_evidence, evidence_payload)

    quality_reviews = _load_quality_reviews(args.quality_reviews)
    for ticker in tickers:
        action_file = actions_path(ticker, args.actions_dir)
        actions = _merge_official_splits(
            load_actions(action_file),
            [event.action() for event in events_by_ticker[ticker]],
            ticker=ticker,
            coverage_start=coverage_start,
        )
        existing_file = cache_path(ticker, "1d", args.data_dir)
        quotes = _historical_quotes(existing_file, coverage_start) + quotes_by_ticker[ticker]
        daily, warnings = build_verified_daily_candles(ticker, quotes, actions)
        weekly = resample_daily_to_weekly(daily)
        prior_sources = _prior_sources(ticker, args.manifests_dir, before_year=min(years))
        all_sources = _merge_sources(prior_sources, sources)
        save_actions(actions, action_file)
        for interval, candles in (("1d", daily), ("1wk", weekly)):
            candle_file = cache_path(ticker, interval, args.data_dir)
            save_verified_candles(candles, candle_file)
            manifest = create_manifest(
                ticker=ticker,
                interval=interval,
                candles_path=candle_file,
                actions_path=action_file,
                source_archives=all_sources,
                corporate_action_source=(
                    "B3 Listed Companies for share-count events; cash distributions "
                    "stored in a separate official ledger for realistic accounting"
                ),
                split_evidence_path=args.split_evidence,
                warnings=warnings,
                warning_reviews=quality_reviews,
            )
            manifest_file = manifest_path(ticker, interval, args.manifests_dir)
            write_manifest(manifest, manifest_file)
            verify_dataset(
                candle_file,
                action_file,
                manifest_file,
                ticker=ticker,
                interval=interval,
                require_verified_splits_from=coverage_start,
                split_evidence_path=args.split_evidence,
            )
        print(f"{ticker}: verified through {daily[-1].date}", flush=True)

    cash_rows, cash_issues = build_cash_events(
        tickers,
        issuer_by_ticker,
        payloads,
        quotes_by_ticker,
    )
    _write_cash(args.cash_output, cash_rows)
    cash_manifest = {
        "schema_version": 3,
        "source": "B3 GetListedSupplementCompany.cashDividends",
        "source_authority": "B3",
        "universe": str(args.universe),
        "selection_validity": (
            "SURVIVORSHIP_SAFE_POINT_IN_TIME"
            if survivorship_safe
            else "RETROSPECTIVE_FIXED_UNIVERSE_ONLY"
        ),
        "no_replacements": universe.get("no_replacements") is True,
        "selectable_ticker_count": len(selected_tickers),
        "market_data_ticker_count": len(tickers),
        "event_identity": "ticker+isin+last_date_prior+payment_date+label+rate",
        "event_count": len(cash_rows),
        "issues": cash_issues,
        "complete": not cash_issues,
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    _write_json_atomic(args.cash_manifest, cash_manifest)
    if cash_issues and not args.allow_incomplete_cash_ledger:
        raise ValueError(
            f"Cash distribution ledger has {len(cash_issues)} unresolved issue(s); "
            f"see {args.cash_manifest}. Refusing a real-money claim."
        )

    print(f"Cash events: {args.cash_output} ({len(cash_rows)} events)")
    print(
        f"Realistic account data synchronized: {len(selected_tickers)} selectable + "
        f"{len(set(tickers) - set(selected_tickers))} continuity-only tickers; "
        f"selection validity={'survivorship-safe' if survivorship_safe else 'retrospective-fixed'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
