from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from b3_strategy_lab.candles import (
    DEFAULT_ACTIONS_DIR,
    DEFAULT_YEARLY_DATA_DIR,
    Candle,
    actions_path,
    load_actions,
    load_candles,
    save_candles,
    split_candles_by_year,
    validate_candles,
    yearly_cache_path,
)
from b3_strategy_lab.cotahist import (
    DEFAULT_MANIFESTS_DIR,
    DataVerificationError,
    PRICE_VERIFIED_STATUS,
    load_manifest,
    manifest_path,
    verify_dataset,
)


INTERVAL_LABELS = {"4h": "4h", "1d": "1d", "1wk": "1sem"}
DEFAULT_CANDLES_DIR = Path("data/candles")
DEFAULT_HEIKIN_ASHI_DIR = Path("data/heikin_ashi")
DEFAULT_REPORTS_DIR = Path("reports")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Organiza inventario de dados e gera Heikin Ashi derivado.")
    parser.add_argument("--candles-dir", default=str(DEFAULT_CANDLES_DIR))
    parser.add_argument("--heikin-ashi-dir", default=str(DEFAULT_HEIKIN_ASHI_DIR))
    parser.add_argument("--yearly-dir", default=str(DEFAULT_YEARLY_DATA_DIR))
    parser.add_argument("--actions-dir", default=str(DEFAULT_ACTIONS_DIR))
    parser.add_argument("--manifests-dir", default=str(DEFAULT_MANIFESTS_DIR))
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR))
    parser.add_argument(
        "--quarantine-unverified",
        action="store_true",
        help="Move fontes e derivados sem manifesto valido para data/legacy.",
    )
    parser.add_argument("--legacy-dir", default="data/legacy")
    args = parser.parse_args(argv)

    candles_dir = Path(args.candles_dir)
    heikin_ashi_dir = Path(args.heikin_ashi_dir)
    yearly_dir = Path(args.yearly_dir)
    actions_dir = Path(args.actions_dir)
    manifests_dir = Path(args.manifests_dir)
    legacy_dir = Path(args.legacy_dir)
    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    verified_sources, rejected_sources = verified_candle_files(
        candles_dir,
        actions_dir,
        manifests_dir,
    )
    quarantined = 0
    if args.quarantine_unverified:
        quarantined += quarantine_files(
            rejected_sources,
            candles_dir,
            legacy_dir / "candles",
        )

    generated, heikin_files = generate_heikin_ashi_files(verified_sources, heikin_ashi_dir)
    if args.quarantine_unverified:
        unexpected_heikin = set(heikin_ashi_dir.glob("*.csv")) - set(heikin_files)
        quarantined += quarantine_files(
            unexpected_heikin,
            heikin_ashi_dir,
            legacy_dir / "heikin_ashi",
        )

    yearly_generated, yearly_files = generate_yearly_files(
        verified_sources,
        heikin_files,
        yearly_dir,
    )
    if args.quarantine_unverified:
        unexpected_yearly = set(yearly_dir.glob("*/*/*/*.csv")) - set(yearly_files)
        quarantined += quarantine_files(
            unexpected_yearly,
            yearly_dir,
            legacy_dir / "yearly",
        )
    inventory = build_inventory(
        candles_dir,
        heikin_ashi_dir,
        actions_dir,
        manifests_dir,
    )
    yearly_inventory = build_yearly_inventory(yearly_dir, manifests_dir)
    write_inventory_csv(inventory, reports_dir / "data_status.csv")
    write_inventory_markdown(inventory, reports_dir / "data_status.md")
    write_yearly_inventory_csv(yearly_inventory, reports_dir / "yearly_data_status.csv")
    write_yearly_inventory_markdown(yearly_inventory, reports_dir / "yearly_data_status.md")

    print(f"Heikin Ashi gerado: {generated} arquivos em {heikin_ashi_dir}")
    print(f"Arquivos anuais gerados: {yearly_generated} arquivos em {yearly_dir}")
    print(f"Arquivos sem proveniencia movidos para quarentena: {quarantined}")
    print(f"Inventario CSV: {reports_dir / 'data_status.csv'}")
    print(f"Inventario Markdown: {reports_dir / 'data_status.md'}")
    print(f"Inventario anual CSV: {reports_dir / 'yearly_data_status.csv'}")
    print(f"Inventario anual Markdown: {reports_dir / 'yearly_data_status.md'}")
    return 0


def verified_candle_files(
    candles_dir: Path,
    actions_dir: Path,
    manifests_dir: Path,
) -> tuple[list[Path], list[Path]]:
    verified: list[Path] = []
    rejected: list[Path] = []
    for path in sorted(candles_dir.glob("*.csv")):
        ticker, interval = _ticker_interval_from_path(path)
        try:
            verify_dataset(
                path,
                actions_path(ticker, actions_dir),
                manifest_path(ticker, interval, manifests_dir),
                ticker=ticker,
                interval=interval,
            )
        except (DataVerificationError, FileNotFoundError, ValueError):
            rejected.append(path)
        else:
            verified.append(path)
    return verified, rejected


def generate_heikin_ashi_files(paths: list[Path], output_dir: Path) -> tuple[int, list[Path]]:
    count = 0
    outputs: list[Path] = []
    for path in paths:
        candles = load_candles(path)
        if not candles:
            continue
        output = output_dir / path.name
        save_candles(to_heikin_ashi(candles), output)
        outputs.append(output)
        count += 1
    return count, outputs


def generate_yearly_files(
    candle_files: list[Path],
    heikin_ashi_files: list[Path],
    output_dir: Path,
) -> tuple[int, list[Path]]:
    count = 0
    outputs: list[Path] = []
    for chart_type, paths in (("candles", candle_files), ("heikin_ashi", heikin_ashi_files)):
        for path in paths:
            ticker, interval = _ticker_interval_from_path(path)
            for year, candles in split_candles_by_year(load_candles(path)).items():
                output = yearly_cache_path(ticker, interval, year, chart_type, output_dir)
                save_candles(candles, output)
                outputs.append(output)
                count += 1
    return count, outputs


def quarantine_files(paths, source_root: Path, destination_root: Path) -> int:
    count = 0
    for path in sorted(paths):
        destination = destination_root / path.relative_to(source_root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if path.read_bytes() != destination.read_bytes():
                raise FileExistsError(
                    f"Quarentena contem conteudo diferente em {destination}; "
                    "nenhuma sobrescrita foi feita."
                )
            path.unlink()
        else:
            path.replace(destination)
        count += 1
    return count


def to_heikin_ashi(candles: list[Candle]) -> list[Candle]:
    result: list[Candle] = []
    previous_open: float | None = None
    previous_close: float | None = None
    previous_raw_open: float | None = None
    previous_raw_close: float | None = None

    for candle in candles:
        ha_close = (
            candle.open
            + candle.high
            + candle.low
            + candle.close
        ) / 4
        raw_ha_close = (
            candle.raw_open
            + candle.raw_high
            + candle.raw_low
            + candle.raw_close
        ) / 4

        if previous_open is None or previous_close is None:
            ha_open = (candle.open + candle.close) / 2
        else:
            ha_open = (previous_open + previous_close) / 2
        if previous_raw_open is None or previous_raw_close is None:
            raw_ha_open = (candle.raw_open + candle.raw_close) / 2
        else:
            raw_ha_open = (previous_raw_open + previous_raw_close) / 2

        ha_high = max(candle.high, ha_open, ha_close)
        ha_low = min(candle.low, ha_open, ha_close)
        raw_ha_high = max(candle.raw_high, raw_ha_open, raw_ha_close)
        raw_ha_low = min(candle.raw_low, raw_ha_open, raw_ha_close)
        factor = ha_close / raw_ha_close if raw_ha_close else 1.0

        result.append(
            replace(
                candle,
                open=ha_open,
                high=ha_high,
                low=ha_low,
                close=ha_close,
                adj_close=ha_close,
                raw_open=raw_ha_open,
                raw_high=raw_ha_high,
                raw_low=raw_ha_low,
                raw_close=raw_ha_close,
                adjustment_factor=factor,
                source_high=raw_ha_high,
                source_low=raw_ha_low,
                ohlc_repaired=0,
            )
        )
        previous_open = ha_open
        previous_close = ha_close
        previous_raw_open = raw_ha_open
        previous_raw_close = raw_ha_close

    return result


def _ticker_interval_from_path(path: Path) -> tuple[str, str]:
    ticker, interval = path.stem.rsplit("_", 1)
    return ticker.upper(), interval


def build_inventory(
    candles_dir: Path,
    heikin_ashi_dir: Path,
    actions_dir: Path,
    manifests_dir: Path,
) -> list[dict[str, str]]:
    tickers = sorted({path.stem.rsplit("_", 1)[0].upper() for path in candles_dir.glob("*.csv")})
    rows: list[dict[str, str]] = []
    for ticker in tickers:
        actions = load_actions(actions_path(ticker, actions_dir))
        for chart_type, directory in (("candles", candles_dir), ("heikin_ashi", heikin_ashi_dir)):
            for interval in ("4h", "1d", "1wk"):
                path = directory / f"{ticker.lower()}_{interval}.csv"
                rows.append(
                    _inventory_row(
                        ticker,
                        chart_type,
                        interval,
                        path,
                        len(actions),
                        manifests_dir,
                    )
                )
    return rows


def _inventory_row(
    ticker: str,
    chart_type: str,
    interval: str,
    path: Path,
    action_count: int,
    manifests_dir: Path,
) -> dict[str, str]:
    manifest_file = manifest_path(ticker, interval, manifests_dir)
    manifest = load_manifest(manifest_file) if manifest_file.exists() else None
    price_status = manifest.status if manifest else "unverified"
    if chart_type == "heikin_ashi" and price_status == PRICE_VERIFIED_STATUS:
        price_status = "derived_from_price_verified"
    action_status = manifest.corporate_action_status if manifest else "unverified"
    split_status = manifest.split_action_status if manifest else "unverified"
    split_verified_from = manifest.split_verified_from if manifest else ""
    if not path.exists():
        return {
            "ticker": ticker,
            "chart_type": chart_type,
            "interval": INTERVAL_LABELS[interval],
            "file": str(path),
            "status": "faltando",
            "ready_for_backtest": "nao",
            "rows": "0",
            "start": "",
            "end": "",
            "corporate_actions": str(action_count),
            "price_status": price_status,
            "action_status": action_status,
            "split_status": split_status,
            "split_verified_from": split_verified_from,
            "issues": "arquivo inexistente",
        }

    candles = load_candles(path)
    issues = validate_candles(candles)
    price_ready = price_status in {
        PRICE_VERIFIED_STATUS,
        "derived_from_price_verified",
    }
    split_ready = bool(
        candles
        and split_status == "verified"
        and split_verified_from
        and candles[-1].date >= split_verified_from
    )
    fully_split_covered = bool(
        split_ready and candles[0].date >= split_verified_from
    )
    ready = (
        bool(candles)
        and not issues
        and price_ready
        and split_ready
        and chart_type == "candles"
    )
    status = (
        "ok_retorno_preco"
        if ready and fully_split_covered
        else "ok_retorno_preco_desde_split_coverage"
        if ready
        else "derivado_verificado"
        if candles and price_ready and chart_type == "heikin_ashi"
        else "revisar"
    )
    return {
        "ticker": ticker,
        "chart_type": chart_type,
        "interval": INTERVAL_LABELS[interval],
        "file": str(path),
        "status": status,
        "ready_for_backtest": (
            "sim"
            if ready and fully_split_covered
            else f"sim_desde_{split_verified_from}"
            if ready
            else "nao"
        ),
        "rows": str(len(candles)),
        "start": candles[0].date if candles else "",
        "end": candles[-1].date if candles else "",
        "corporate_actions": str(action_count),
        "price_status": price_status,
        "action_status": action_status,
        "split_status": split_status,
        "split_verified_from": split_verified_from,
        "issues": "; ".join(issues[:5]),
    }


def build_yearly_inventory(yearly_dir: Path, manifests_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(yearly_dir.glob("*/*/*/*.csv")):
        year, chart_type, interval = path.parts[-4:-1]
        ticker, _path_interval = _ticker_interval_from_path(path)
        rows.append(
            _yearly_inventory_row(
                year,
                ticker,
                chart_type,
                interval,
                path,
                manifests_dir,
            )
        )
    return rows


def _yearly_inventory_row(
    year: str,
    ticker: str,
    chart_type: str,
    interval: str,
    path: Path,
    manifests_dir: Path,
) -> dict[str, str]:
    candles = load_candles(path)
    issues = validate_candles(candles)
    manifest_file = manifest_path(ticker, interval, manifests_dir)
    manifest = load_manifest(manifest_file) if manifest_file.exists() else None
    price_status = manifest.status if manifest else "unverified"
    if chart_type == "heikin_ashi" and price_status == PRICE_VERIFIED_STATUS:
        price_status = "derived_from_price_verified"
    action_status = manifest.corporate_action_status if manifest else "unverified"
    split_status = manifest.split_action_status if manifest else "unverified"
    split_verified_from = manifest.split_verified_from if manifest else ""
    if len(candles) < 2:
        issues = [*issues, "menos de 2 candles para backtest"]
    price_ready = price_status in {
        PRICE_VERIFIED_STATUS,
        "derived_from_price_verified",
    }
    split_ready = bool(
        candles
        and split_status == "verified"
        and split_verified_from
        and candles[-1].date >= split_verified_from
    )
    fully_split_covered = bool(
        split_ready and candles[0].date >= split_verified_from
    )
    ready = (
        len(candles) >= 2
        and not issues
        and price_ready
        and split_ready
        and chart_type == "candles"
    )
    status = (
        "ok_retorno_preco"
        if ready and fully_split_covered
        else "ok_retorno_preco_desde_split_coverage"
        if ready
        else "derivado_verificado"
        if candles and price_ready and chart_type == "heikin_ashi"
        else "revisar"
    )
    return {
        "year": year,
        "ticker": ticker,
        "chart_type": chart_type,
        "interval": INTERVAL_LABELS.get(interval, interval),
        "status": status,
        "ready_for_backtest": (
            "sim"
            if ready and fully_split_covered
            else f"sim_desde_{split_verified_from}"
            if ready
            else "nao"
        ),
        "rows": str(len(candles)),
        "start": candles[0].date if candles else "",
        "end": candles[-1].date if candles else "",
        "price_status": price_status,
        "action_status": action_status,
        "split_status": split_status,
        "split_verified_from": split_verified_from,
        "file": str(path),
        "issues": "; ".join(issues[:5]),
    }


def write_inventory_csv(rows: list[dict[str, str]], path: Path) -> None:
    fields = [
        "ticker",
        "chart_type",
        "interval",
        "status",
        "ready_for_backtest",
        "rows",
        "start",
        "end",
        "corporate_actions",
        "price_status",
        "split_status",
        "split_verified_from",
        "action_status",
        "file",
        "issues",
    ]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fields} for row in rows])


def write_yearly_inventory_csv(rows: list[dict[str, str]], path: Path) -> None:
    fields = [
        "year",
        "ticker",
        "chart_type",
        "interval",
        "status",
        "ready_for_backtest",
        "rows",
        "start",
        "end",
        "price_status",
        "split_status",
        "split_verified_from",
        "action_status",
        "file",
        "issues",
    ]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fields} for row in rows])


def write_inventory_markdown(rows: list[dict[str, str]], path: Path) -> None:
    tickers = sorted({row["ticker"] for row in rows})
    lines = [
        "# Inventario de dados",
        "",
        "Status gerado a partir de `data/candles`, `data/heikin_ashi` e `data/corporate_actions`.",
        "",
        "`Backtest = sim` exige preco e splits verificados; dividendos/JCP permanecem "
        "fora do modo retorno de preco.",
        "",
        "Observacao: `VALE4` nao existe nos dados atuais; o ticker disponivel e `VALE3`.",
        "",
    ]
    for ticker in tickers:
        lines.append(f"## {ticker}")
        for chart_type, label in (("candles", "Grafico de candles"), ("heikin_ashi", "Grafico Heikin Ashi")):
            lines.append("")
            lines.append(f"### {label}")
            lines.append("")
            lines.append("| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |")
            lines.append("|---|---|---|---|---|---|---|---:|---|---|---|")
            for interval in ("4h", "1d", "1sem"):
                row = next(
                    item for item in rows
                    if item["ticker"] == ticker and item["chart_type"] == chart_type and item["interval"] == interval
                )
                lines.append(
                    f"| {interval} | {row['status']} | {row['price_status']} | "
                    f"{row['split_status']} | {row['split_verified_from']} | "
                    f"{row['action_status']} | {row['ready_for_backtest']} | "
                    f"{row['rows']} | {row['start']} | {row['end']} | `{row['file']}` |"
                )
            actions = next(item["corporate_actions"] for item in rows if item["ticker"] == ticker)
        lines.append("")
        lines.append(f"Eventos corporativos baixados: {actions}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_yearly_inventory_markdown(rows: list[dict[str, str]], path: Path) -> None:
    lines = [
        "# Inventario anual de dados",
        "",
        "Arquivos gerados a partir dos historicos completos em `data/candles` e `data/heikin_ashi`.",
        "",
        "| Ano | Ticker | Grafico | Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |",
        "|---:|---|---|---|---|---|---|---|---|---|---:|---|---|---|",
    ]
    for row in sorted(rows, key=lambda item: (item["year"], item["ticker"], item["chart_type"], item["interval"])):
        lines.append(
            f"| {row['year']} | {row['ticker']} | {row['chart_type']} | {row['interval']} | "
            f"{row['status']} | {row['price_status']} | {row['split_status']} | "
            f"{row['split_verified_from']} | {row['action_status']} | "
            f"{row['ready_for_backtest']} | {row['rows']} | "
            f"{row['start']} | {row['end']} | `{row['file']}` |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
