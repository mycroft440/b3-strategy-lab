from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, replace
from datetime import date, datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from b3_strategy_lab.b3_official import (  # noqa: E402
    audit_share_count_markers,
    b3_supplement_url,
    download_b3_supplement,
    extract_official_split_events,
    merge_official_split_events,
    parse_supplemental_split_events,
    payload_sha256,
)
from b3_strategy_lab.candles import (  # noqa: E402
    CorporateAction,
    actions_path,
    cache_path,
    load_actions,
    load_candles,
    save_actions,
)
from b3_strategy_lab.cotahist import (  # noqa: E402
    DEFAULT_MANIFESTS_DIR,
    DEFAULT_SPLIT_EVIDENCE_PATH,
    OfficialQuote,
    SourceArchive,
    build_verified_daily_candles,
    create_manifest,
    download_cotahist,
    load_manifest,
    manifest_path,
    read_cotahist,
    resample_daily_to_weekly,
    save_verified_candles,
    source_archive,
    verify_dataset,
    write_manifest,
)
from b3_strategy_lab.point_in_time import (  # noqa: E402
    base_fractional_ticker,
    read_fractional_cotahist,
)


DEFAULT_UNIVERSE = Path("data/universes/fixed_40_2018.json")
DEFAULT_QUALITY_REVIEWS = Path("data/quality_reviews.json")
DEFAULT_SELECTION_REPORT = Path("reports/universe_40_selection_2018.csv")
DEFAULT_SUPPLEMENTAL_SPLITS = Path(
    "data/corporate_actions/supplemental_split_events.json"
)
SPLIT_NEUTRAL_OPEN_GAP_LIMIT = 0.35


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Sincroniza o universo de 40 acoes com COTAHIST e eventos de "
            "quantidade de acoes oficiais da B3, da CVM e dos emissores."
        )
    )
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--archives-dir", type=Path, default=Path(".cache/cotahist"))
    parser.add_argument("--supplements-dir", type=Path, default=Path(".cache/b3_supplements"))
    parser.add_argument("--data-dir", type=Path, default=Path("data/candles"))
    parser.add_argument("--actions-dir", type=Path, default=Path("data/corporate_actions"))
    parser.add_argument("--manifests-dir", type=Path, default=DEFAULT_MANIFESTS_DIR)
    parser.add_argument("--split-evidence", type=Path, default=DEFAULT_SPLIT_EVIDENCE_PATH)
    parser.add_argument("--supplemental-splits", type=Path, default=DEFAULT_SUPPLEMENTAL_SPLITS)
    parser.add_argument("--quality-reviews", type=Path, default=DEFAULT_QUALITY_REVIEWS)
    parser.add_argument("--selection-report", type=Path, default=DEFAULT_SELECTION_REPORT)
    parser.add_argument("--years", nargs="+", default=[f"2017:{date.today().year}"])
    parser.add_argument("--end")
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--refresh-current", action="store_true")
    parser.add_argument("--refresh-actions", action="store_true")
    parser.add_argument("--refresh-selection", action="store_true")
    parser.add_argument("--action-workers", type=int, default=2)
    args = parser.parse_args(argv)

    if args.action_workers <= 0:
        parser.error("--action-workers precisa ser positivo.")
    try:
        end_date = date.fromisoformat(args.end).isoformat() if args.end else None
    except ValueError:
        parser.error("--end precisa estar no formato YYYY-MM-DD.")
    if end_date is not None and end_date >= date.today().isoformat():
        parser.error("--end precisa ser anterior ao dia corrente.")
    universe = json.loads(args.universe.read_text(encoding="utf-8"))
    tickers = [str(ticker).strip().upper() for ticker in universe["tickers"]]
    coverage_start = str(universe["warmup_start"])
    years = _parse_years(args.years)
    if min(years) > int(coverage_start[:4]):
        parser.error("Os anos precisam incluir o inicio do warm-up do universo.")

    archives = _prepare_archives(years, args.archives_dir, download=args.download, refresh_current=args.refresh_current)
    quotes_by_ticker, sources = _read_official_quotes(archives, tickers, exclude_date=date.today().isoformat(), end_date=end_date)
    if args.selection_report:
        if args.selection_report.exists() and not args.refresh_selection:
            selected = _selected_from_report(args.selection_report)
        else:
            selected = _write_selection_report(universe, archives, args.selection_report)
        expected_added = [str(ticker).upper() for ticker in universe["added_tickers"]]
        if selected != expected_added:
            raise ValueError(f"As 30 adicoes do manifesto nao reproduzem o ranking oficial: esperado={expected_added}, calculado={selected}.")

    issuer_by_ticker = {str(ticker).upper(): str(issuer).upper() for ticker, issuer in universe["issuing_company_by_ticker"].items()}
    payloads = _load_supplements(sorted(set(issuer_by_ticker.values())), args.supplements_dir, refresh=args.refresh_actions, workers=args.action_workers)

    supplemental_payload = json.loads(args.supplemental_splits.read_text(encoding="utf-8"))
    supplemental_events = parse_supplemental_split_events(
        supplemental_payload,
        tickers=tickers,
        quote_dates_by_ticker={ticker: (quote.date for quote in quotes_by_ticker[ticker]) for ticker in tickers},
        coverage_start=coverage_start,
    )
    supplemental_by_ticker = defaultdict(list)
    for event in supplemental_events:
        supplemental_by_ticker[event.ticker].append(event)

    events_by_ticker = {}
    evidence_reviews = []
    evidence_events = []
    marker_audit = []
    continuity_audit = []
    for ticker in tickers:
        quotes = quotes_by_ticker[ticker]
        issuer = issuer_by_ticker[ticker]
        payload = payloads[issuer]
        b3_events = extract_official_split_events(
            payload,
            ticker=ticker,
            issuing_company=issuer,
            quote_dates=(quote.date for quote in quotes),
            quote_isins=(quote.isin for quote in quotes),
            coverage_start=coverage_start,
        )
        historical_events = supplemental_by_ticker[ticker]
        events = merge_official_split_events(b3_events, historical_events)
        events_by_ticker[ticker] = events
        markers = audit_share_count_markers(quotes, events, coverage_start=coverage_start)
        uncovered_markers = [marker for marker in markers if not marker["covered"]]
        if uncovered_markers:
            raise ValueError(f"{ticker}: marcador(es) EB/EG sem evento oficial: {uncovered_markers}.")
        marker_audit.extend({"ticker": ticker, **marker} for marker in markers)
        continuity = _event_continuity_audit(quotes, events)
        continuity_audit.extend(continuity)
        excessive = _excessive_event_continuity(continuity)
        if excessive:
            raise ValueError(
                f"{ticker}: descontinuidade de abertura superior a 35% apos aplicar evento oficial: {excessive}."
            )
        evidence_reviews.append(
            {
                "ticker": ticker,
                "issuing_company": issuer,
                "source_authority": "B3",
                "source_url": b3_supplement_url(issuer),
                "source_payload_sha256": payload_sha256(payload),
                "result": (
                    f"{len(events)} evento(s) de quantidade de acoes desde {coverage_start}: "
                    f"{len(b3_events)} na consulta corrente da B3 e {len(historical_events)} "
                    "no registro historico oficial; eventos em dinheiro ignorados."
                ),
            }
        )
        evidence_events.extend(event.evidence() for event in events)

    evidence_payload = {
        "schema_version": 1,
        "coverage_start": coverage_start,
        "retrieved_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "scope": "Grupamentos, desdobramentos e bonificacoes que alteram a quantidade de acoes. Dividendos e JCP sao excluidos do backtest.",
        "method": (
            "Eventos consultados no cadastro oficial de companhias listadas da B3. "
            "Omissoes historicas da resposta corrente foram preenchidas somente com documentos primarios dos emissores ou da CVM. "
            "O ex_date e o primeiro pregao COTAHIST do ativo posterior a ultima data com direito. ISINs foram cruzados com o COTAHIST do ticker e todos os inicios de marcador EB/EG foram reconciliados."
        ),
        "supplemental_registry": {
            "path": str(args.supplemental_splits),
            "payload_sha256": payload_sha256(supplemental_payload),
            "event_count": len(supplemental_events),
            "allowed_authorities": ["CVM", "issuer"],
        },
        "share_count_marker_audit": {
            "marker_count": len(marker_audit),
            "uncovered_count": 0,
            "maximum_lag_calendar_days": 10,
            "markers": sorted(marker_audit, key=lambda row: (row["marker_date"], row["ticker"])),
        },
        "event_continuity_audit": {
            "event_count": len(continuity_audit),
            "maximum_absolute_split_neutral_raw_open_gap": max(
                (abs(float(item["split_neutral_raw_open_gap"])) for item in continuity_audit),
                default=0.0,
            ),
            "maximum_absolute_split_neutral_raw_close_return": max(
                (abs(float(item["split_neutral_raw_close_return"])) for item in continuity_audit),
                default=0.0,
            ),
            "gate_limit_absolute_open_gap": SPLIT_NEUTRAL_OPEN_GAP_LIMIT,
            "events": sorted(continuity_audit, key=lambda row: (row["ex_date"], row["ticker"])),
        },
        "ticker_reviews": sorted(evidence_reviews, key=lambda row: row["ticker"]),
        "events": sorted(evidence_events, key=lambda row: (row["ex_date"], row["ticker"])),
    }
    _write_json_atomic(args.split_evidence, evidence_payload)

    built = {}
    for ticker in tickers:
        action_file = actions_path(ticker, args.actions_dir)
        actions = _merge_official_splits(load_actions(action_file), [event.action() for event in events_by_ticker[ticker]], ticker=ticker, coverage_start=coverage_start)
        existing_file = cache_path(ticker, "1d", args.data_dir)
        historical_quotes = _historical_quotes(existing_file, coverage_start)
        quotes = historical_quotes + quotes_by_ticker[ticker]
        daily, warnings = build_verified_daily_candles(ticker, quotes, actions)
        weekly = resample_daily_to_weekly(daily)
        prior_sources = _prior_sources(ticker, args.manifests_dir, before_year=min(years))
        all_sources = _merge_sources(prior_sources, sources)
        built[ticker] = {"actions": actions, "daily": daily, "weekly": weekly, "warnings": warnings, "sources": all_sources}

    quality_reviews = _load_quality_reviews(args.quality_reviews)
    archive_by_year = {archive.year: archive for archive in sources}
    for ticker, values in built.items():
        candles = values["daily"]
        by_date = {candle.date: index for index, candle in enumerate(candles)}
        for warning in values["warnings"]:
            warning_date = warning.split()[1].rstrip(":")
            index = by_date[warning_date]
            current = candles[index]
            previous = candles[index - 1]
            archive = archive_by_year.get(int(warning_date[:4]))
            archive_note = f"{archive.filename} (SHA-256 {archive.sha256})" if archive is not None else "arquivo COTAHIST oficial registrado no manifesto"
            quality_reviews[warning] = (
                f"Confirmado em {archive_note}: fechamento bruto anterior R$ {previous.raw_close:.8g}, "
                f"fechamento bruto atual R$ {current.raw_close:.8g}, {current.trades} negocios e volume financeiro R$ {current.financial_volume:.2f}. "
                "Registro oficial mantido sem reparo sintetico."
            )
    _write_json_atomic(args.quality_reviews, {"schema_version": 1, "warning_reviews": dict(sorted(quality_reviews.items()))})

    for ticker in tickers:
        values = built[ticker]
        action_file = actions_path(ticker, args.actions_dir)
        save_actions(values["actions"], action_file)
        for interval, candles in (("1d", values["daily"]), ("1wk", values["weekly"])):
            candle_file = cache_path(ticker, interval, args.data_dir)
            save_verified_candles(candles, candle_file)
            manifest = create_manifest(
                ticker=ticker,
                interval=interval,
                candles_path=candle_file,
                actions_path=action_file,
                source_archives=values["sources"],
                corporate_action_source="B3 Listed Companies plus issuer/CVM historical share-count events; cash distributions excluded or retained only as unverified legacy evidence",
                split_evidence_path=args.split_evidence,
                warnings=values["warnings"],
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
        print(
            f"{ticker}: {len(values['daily'])} diarios, {values['daily'][0].date} a {values['daily'][-1].date}, "
            f"splits={len(events_by_ticker[ticker])}, historicos={len(supplemental_by_ticker[ticker])}, avisos={len(values['warnings'])}",
            flush=True,
        )
    return 0


def _prepare_archives(years: list[int], directory: Path, *, download: bool, refresh_current: bool) -> list[tuple[int, Path]]:
    result = []
    for year in years:
        archive = directory / f"COTAHIST_A{year}.ZIP"
        if download:
            archive = download_cotahist(year, directory, refresh=refresh_current and year == date.today().year)
        elif not archive.exists():
            raise FileNotFoundError(f"{archive} ausente; use --download.")
        result.append((year, archive))
    return result


def _read_official_quotes(
    archives: list[tuple[int, Path]], tickers: list[str], *, exclude_date: str, end_date: str | None = None
) -> tuple[dict[str, list[OfficialQuote]], list[SourceArchive]]:
    by_ticker: dict[str, list[OfficialQuote]] = defaultdict(list)
    sources = []
    for year, archive in archives:
        quotes = [quote for quote in read_cotahist(archive, tickers=tickers) if quote.date < exclude_date and (end_date is None or quote.date <= end_date)]
        fractional = [quote for quote in read_fractional_cotahist(archive) if base_fractional_ticker(quote.ticker) in tickers and quote.date < exclude_date and (end_date is None or quote.date <= end_date)]
        fractional_by_base_date = {(base_fractional_ticker(quote.ticker), quote.date): quote for quote in fractional}
        if len(fractional_by_base_date) != len(fractional):
            raise ValueError(f"{year}: cotacoes fracionarias duplicadas por ativo/data.")
        standard_keys = {(quote.ticker, quote.date) for quote in quotes}
        fractional_only = sorted(set(fractional_by_base_date) - standard_keys)
        if fractional_only:
            print(f"{year}: {len(fractional_only)} registro(s) fracionario(s) sem OHLC padrao; nao foi sintetizado candle", flush=True)
        quotes = [_with_fractional_volume(quote, fractional_by_base_date.get((quote.ticker, quote.date))) for quote in quotes]
        for quote in quotes:
            by_ticker[quote.ticker].append(quote)
        sources.append(source_archive(archive, year))
        print(f"{year}: {len(quotes)} cotacoes do universo; {len(fractional)} registros fracionarios consolidados", flush=True)
    missing = [ticker for ticker in tickers if not by_ticker[ticker]]
    if missing:
        raise ValueError(f"Tickers sem cotacao oficial: {missing}.")
    return {ticker: sorted(by_ticker[ticker], key=lambda quote: quote.date) for ticker in tickers}, sources


def _with_fractional_volume(standard: OfficialQuote, fractional: OfficialQuote | None) -> OfficialQuote:
    fractional_volume = fractional.volume if fractional is not None else 0
    fractional_trades = fractional.trades if fractional is not None else 0
    fractional_financial = fractional.financial_volume if fractional is not None else 0.0
    return replace(
        standard,
        volume=standard.volume + fractional_volume,
        trades=standard.trades + fractional_trades,
        financial_volume=standard.financial_volume + fractional_financial,
        fractional_volume=fractional_volume,
        fractional_trades=fractional_trades,
        fractional_financial_volume=fractional_financial,
        volume_scope="consolidated_010_020",
    )


def _load_supplements(issuers: list[str], directory: Path, *, refresh: bool, workers: int) -> dict[str, list[dict[str, object]]]:
    directory.mkdir(parents=True, exist_ok=True)
    result = {}
    pending = []
    for issuer in issuers:
        path = directory / f"{issuer.lower()}.json"
        if path.exists() and not refresh:
            result[issuer] = json.loads(path.read_text(encoding="utf-8"))
        else:
            pending.append(issuer)
    if pending:
        failed = []
        with ThreadPoolExecutor(max_workers=min(workers, len(pending))) as executor:
            futures = {executor.submit(download_b3_supplement, issuer): issuer for issuer in pending}
            for future in as_completed(futures):
                issuer = futures[future]
                try:
                    payload = future.result()
                except Exception as error:
                    failed.append((issuer, error))
                    print(f"Nova tentativa necessaria: {issuer} ({error})", flush=True)
                    continue
                result[issuer] = payload
                _write_json_atomic(directory / f"{issuer.lower()}.json", payload)
                print(f"Eventos oficiais: {issuer}", flush=True)
        for issuer, _error in failed:
            payload = download_b3_supplement(issuer, attempts=8)
            result[issuer] = payload
            _write_json_atomic(directory / f"{issuer.lower()}.json", payload)
            print(f"Eventos oficiais (nova tentativa): {issuer}", flush=True)
    return result


def _merge_official_splits(legacy: list[CorporateAction], official: list[CorporateAction], *, ticker: str, coverage_start: str) -> list[CorporateAction]:
    retained = []
    for action in legacy:
        if action.date < coverage_start:
            retained.append(action)
        elif action.dividend != 0.0:
            retained.append(CorporateAction(action.date, ticker, action.source_symbol, action.dividend, 1.0))
    by_date: dict[str, CorporateAction] = {}
    for action in sorted([*retained, *official], key=lambda item: item.date):
        previous = by_date.get(action.date)
        if previous is None:
            by_date[action.date] = action
        else:
            by_date[action.date] = CorporateAction(
                action.date,
                ticker,
                action.source_symbol if action.split_ratio != 1.0 else previous.source_symbol,
                previous.dividend + action.dividend,
                previous.split_ratio * action.split_ratio,
            )
    return [by_date[value] for value in sorted(by_date)]


def _event_continuity_audit(quotes: list[OfficialQuote], events: list) -> list[dict[str, object]]:
    by_date = {quote.date: index for index, quote in enumerate(quotes)}
    result = []
    for event in events:
        index = by_date.get(event.ex_date)
        if index is None or index == 0:
            raise ValueError(f"{event.ticker} {event.ex_date}: evento sem par COTAHIST anterior.")
        previous = quotes[index - 1]
        current = quotes[index]
        open_gap = current.open * event.split_ratio / previous.close - 1.0
        close_return = current.close * event.split_ratio / previous.close - 1.0
        result.append(
            {
                "ticker": event.ticker,
                "ex_date": event.ex_date,
                "last_quote_date_prior": previous.date,
                "raw_close_prior": previous.close,
                "raw_open_ex_date": current.open,
                "raw_close_ex_date": current.close,
                "split_ratio": event.split_ratio,
                "split_neutral_raw_open_gap": open_gap,
                "split_neutral_raw_close_return": close_return,
                "source_authority": event.source_authority,
                "source_url": event.source_url,
            }
        )
    return result


def _excessive_event_continuity(continuity: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        item
        for item in continuity
        if abs(float(item["split_neutral_raw_open_gap"])) > SPLIT_NEUTRAL_OPEN_GAP_LIMIT
    ]


def _historical_quotes(path: Path, coverage_start: str) -> list[OfficialQuote]:
    if not path.exists():
        return []
    result = []
    for candle in load_candles(path):
        if candle.date >= coverage_start:
            continue
        result.append(
            OfficialQuote(
                date=candle.date,
                ticker=candle.ticker,
                open=candle.raw_open,
                high=candle.raw_high,
                low=candle.raw_low,
                close=candle.raw_close,
                volume=candle.raw_volume,
                trades=candle.trades,
                financial_volume=candle.financial_volume,
                quotation_factor=candle.quotation_factor,
                bdi_code=candle.bdi_code,
                market_type=candle.market_type,
                isin=candle.isin,
                distribution_number=candle.distribution_number,
                specification=candle.specification,
                issuer_name=candle.issuer_name,
                fractional_volume=candle.fractional_raw_volume,
                fractional_trades=candle.fractional_trades,
                fractional_financial_volume=candle.fractional_financial_volume,
                volume_scope=candle.volume_scope,
            )
        )
    return result


def _prior_sources(ticker: str, manifests_dir: Path, *, before_year: int) -> list[SourceArchive]:
    path = manifest_path(ticker, "1d", manifests_dir)
    if not path.exists():
        return []
    return [source for source in load_manifest(path).source_archives if source.year < before_year]


def _merge_sources(prior: list[SourceArchive], refreshed: list[SourceArchive]) -> list[SourceArchive]:
    by_year = {source.year: source for source in [*prior, *refreshed]}
    return [by_year[year] for year in sorted(by_year)]


def _load_quality_reviews(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(warning): str(evidence) for warning, evidence in (payload.get("warning_reviews") or {}).items()}


def _write_selection_report(universe: dict[str, object], archives: list[tuple[int, Path]], output: Path) -> list[str]:
    archive_by_year = {year: path for year, path in archives}
    if 2018 not in archive_by_year:
        raise ValueError("O relatorio de selecao exige COTAHIST_A2018.ZIP.")
    quotes_2018 = read_cotahist(archive_by_year[2018])
    by_ticker: dict[str, list[OfficialQuote]] = defaultdict(list)
    for quote in quotes_2018:
        by_ticker[quote.ticker].append(quote)
    original = {str(ticker).upper() for ticker in universe["original_tickers"]}
    original_issuers = {ticker[:4] for ticker in original}
    ranked = [ticker for ticker, _quotes in sorted(by_ticker.items(), key=lambda item: sum(quote.financial_volume for quote in item[1]), reverse=True) if ticker not in original]
    candidates = ranked[:140]
    presence = {ticker: {} for ticker in candidates}
    for year, archive in archives:
        if year < 2018:
            continue
        quotes = read_cotahist(archive, tickers=[*candidates, "PETR4"])
        sessions = {quote.date for quote in quotes if quote.ticker == "PETR4"}
        counts: dict[str, int] = defaultdict(int)
        for quote in quotes:
            if quote.ticker in presence:
                counts[quote.ticker] += 1
        for ticker in candidates:
            presence[ticker][year] = counts[ticker] / len(sessions)
    rows = []
    eligible_rank = 0
    selected = []
    for liquidity_rank, ticker in enumerate(ranked, start=1):
        if ticker not in presence:
            continue
        minimum_presence = min(presence[ticker].values())
        same_issuer = ticker[:4] in original_issuers
        eligible = minimum_presence >= 0.95 and not same_issuer
        if eligible:
            eligible_rank += 1
            if len(selected) < 30:
                selected.append(ticker)
        rows.append(
            {
                "ticker": ticker,
                "liquidity_rank_2018": liquidity_rank,
                "eligible_rank": eligible_rank if eligible else "",
                "financial_volume_2018": sum(quote.financial_volume for quote in by_ticker[ticker]),
                "minimum_annual_presence_2018_latest": minimum_presence,
                "same_issuing_company_as_original": int(same_issuer),
                "eligible": int(eligible),
                "selected": int(ticker in selected),
            }
        )
        if len(selected) >= 30 and liquidity_rank >= max(row["liquidity_rank_2018"] for row in rows if row["selected"]):
            break
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(output)
    return selected


def _selected_from_report(path: Path) -> list[str]:
    with path.open("r", newline="", encoding="utf-8") as file:
        return [str(row["ticker"]).upper() for row in csv.DictReader(file) if int(row["selected"]) == 1]


def _parse_years(values: list[str]) -> list[int]:
    years = set()
    for value in values:
        if ":" in value:
            start, end = (int(part) for part in value.split(":", 1))
            if end < start:
                raise ValueError(f"Intervalo invertido: {value}.")
            years.update(range(start, end + 1))
        else:
            years.add(int(value))
    return sorted(years)


def _write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
