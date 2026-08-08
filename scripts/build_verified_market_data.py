from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from b3_strategy_lab.candles import (  # noqa: E402
    DEFAULT_ACTIONS_DIR,
    DEFAULT_DATA_DIR,
    DEFAULT_TICKERS,
    actions_path,
    cache_path,
    load_actions,
)
from b3_strategy_lab.cotahist import (  # noqa: E402
    DEFAULT_MANIFESTS_DIR,
    DEFAULT_SPLIT_EVIDENCE_PATH,
    build_verified_daily_candles,
    create_manifest,
    download_cotahist,
    manifest_path,
    read_cotahist,
    resample_daily_to_weekly,
    save_verified_candles,
    source_archive,
    verify_dataset,
    write_manifest,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Constroi candles verificados usando cotacoes oficiais COTAHIST da B3."
    )
    parser.add_argument("--tickers", nargs="+", default=list(DEFAULT_TICKERS))
    parser.add_argument(
        "--years",
        nargs="+",
        required=True,
        help="Anos ou intervalos, exemplo: --years 2000:2026 ou --years 2024 2025 2026.",
    )
    parser.add_argument("--archives-dir", default=".cache/cotahist")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--actions-dir", default=str(DEFAULT_ACTIONS_DIR))
    parser.add_argument("--manifests-dir", default=str(DEFAULT_MANIFESTS_DIR))
    parser.add_argument(
        "--split-evidence",
        default=str(DEFAULT_SPLIT_EVIDENCE_PATH),
        help="Registro local das razoes de split conferidas em fontes oficiais.",
    )
    parser.add_argument(
        "--warning-reviews",
        default="data/quality_reviews.json",
        help="Arquivo JSON com evidencias para anomalias de preco revisadas.",
    )
    parser.add_argument("--download", action="store_true", help="Baixa os ZIPs anuais ausentes da B3.")
    args = parser.parse_args(argv)

    tickers = sorted({ticker.strip().upper() for ticker in args.tickers})
    years = _parse_years(args.years)
    archives_dir = Path(args.archives_dir)
    data_dir = Path(args.data_dir)
    actions_dir = Path(args.actions_dir)
    manifests_dir = Path(args.manifests_dir)
    split_evidence = Path(args.split_evidence)
    warning_reviews = _load_warning_reviews(Path(args.warning_reviews))

    quotes_by_ticker: dict[str, list] = defaultdict(list)
    sources = []
    for year in years:
        archive = archives_dir / f"COTAHIST_A{year}.ZIP"
        if args.download:
            archive = download_cotahist(
                year,
                archives_dir,
                refresh=year == date.today().year,
            )
        elif not archive.exists():
            raise FileNotFoundError(
                f"{archive} nao existe. Use --download ou forneca o arquivo oficial."
            )
        quotes = read_cotahist(archive, tickers=tickers)
        for quote in quotes:
            quotes_by_ticker[quote.ticker].append(quote)
        sources.append(source_archive(archive, year))
        print(f"{year}: {len(quotes)} cotacoes oficiais carregadas", flush=True)

    for ticker in tickers:
        action_file = actions_path(ticker, actions_dir)
        if not action_file.exists():
            raise FileNotFoundError(
                f"Eventos corporativos ausentes para {ticker}: {action_file}. "
                "As razoes de split sao necessarias para normalizar a serie."
            )
        actions = load_actions(action_file)
        daily, warnings = build_verified_daily_candles(ticker, quotes_by_ticker[ticker], actions)
        weekly = resample_daily_to_weekly(daily)

        for interval, candles in (("1d", daily), ("1wk", weekly)):
            candle_file = cache_path(ticker, interval, data_dir)
            save_verified_candles(candles, candle_file)
            manifest = create_manifest(
                ticker=ticker,
                interval=interval,
                candles_path=candle_file,
                actions_path=action_file,
                source_archives=sources,
                split_evidence_path=split_evidence,
                warnings=warnings,
                warning_reviews=warning_reviews,
            )
            manifest_file = manifest_path(ticker, interval, manifests_dir)
            write_manifest(manifest, manifest_file)
            verify_dataset(
                candle_file,
                action_file,
                manifest_file,
                ticker=ticker,
                interval=interval,
                require_verified_splits_from=manifest.split_verified_from,
                split_evidence_path=split_evidence,
            )
            print(
                f"{ticker} {interval}: {len(candles)} candles verificados "
                f"({candles[0].date} a {candles[-1].date}); avisos={len(warnings)}",
                flush=True,
            )
    return 0


def _parse_years(values: list[str]) -> list[int]:
    years: set[int] = set()
    for value in values:
        if ":" in value:
            start_text, end_text = value.split(":", 1)
            start = int(start_text)
            end = int(end_text)
            if end < start:
                raise ValueError(f"Intervalo de anos invertido: {value}.")
            years.update(range(start, end + 1))
        else:
            years.add(int(value))
    if not years:
        raise ValueError("Informe pelo menos um ano.")
    return sorted(years)


def _load_warning_reviews(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    reviews = payload.get("warning_reviews", {})
    if not isinstance(reviews, dict) or not all(
        isinstance(warning, str) and isinstance(evidence, str)
        for warning, evidence in reviews.items()
    ):
        raise ValueError(f"Formato invalido em {path}: warning_reviews precisa ser um objeto de strings.")
    return reviews


if __name__ == "__main__":
    raise SystemExit(main())
