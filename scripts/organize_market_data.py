from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from b3_strategy_lab.candles import Candle, actions_path, load_actions, load_candles, save_candles, validate_candles


INTERVAL_LABELS = {"4h": "4h", "1d": "1d", "1wk": "1sem"}
DEFAULT_CANDLES_DIR = Path("data/candles")
DEFAULT_HEIKIN_ASHI_DIR = Path("data/heikin_ashi")
DEFAULT_REPORTS_DIR = Path("reports")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Organiza inventario de dados e gera Heikin Ashi derivado.")
    parser.add_argument("--candles-dir", default=str(DEFAULT_CANDLES_DIR))
    parser.add_argument("--heikin-ashi-dir", default=str(DEFAULT_HEIKIN_ASHI_DIR))
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR))
    args = parser.parse_args(argv)

    candles_dir = Path(args.candles_dir)
    heikin_ashi_dir = Path(args.heikin_ashi_dir)
    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    generated = generate_heikin_ashi_files(candles_dir, heikin_ashi_dir)
    inventory = build_inventory(candles_dir, heikin_ashi_dir)
    write_inventory_csv(inventory, reports_dir / "data_status.csv")
    write_inventory_markdown(inventory, reports_dir / "data_status.md")

    print(f"Heikin Ashi gerado: {generated} arquivos em {heikin_ashi_dir}")
    print(f"Inventario CSV: {reports_dir / 'data_status.csv'}")
    print(f"Inventario Markdown: {reports_dir / 'data_status.md'}")
    return 0


def generate_heikin_ashi_files(candles_dir: Path, output_dir: Path) -> int:
    count = 0
    for path in sorted(candles_dir.glob("*.csv")):
        candles = load_candles(path)
        if not candles:
            continue
        output = output_dir / path.name
        save_candles(to_heikin_ashi(candles), output)
        count += 1
    return count


def to_heikin_ashi(candles: list[Candle]) -> list[Candle]:
    result: list[Candle] = []
    previous_open: float | None = None
    previous_close: float | None = None

    for candle in candles:
        ha_close = (candle.open + candle.high + candle.low + candle.close) / 4

        if previous_open is None or previous_close is None:
            ha_open = (candle.open + candle.close) / 2
        else:
            ha_open = (previous_open + previous_close) / 2

        ha_high = max(candle.high, ha_open, ha_close)
        ha_low = min(candle.low, ha_open, ha_close)

        result.append(
            replace(
                candle,
                open=ha_open,
                high=ha_high,
                low=ha_low,
                close=ha_close,
                adj_close=ha_close,
                raw_open=ha_open,
                raw_high=ha_high,
                raw_low=ha_low,
                raw_close=ha_close,
                adjustment_factor=1.0,
                source_high=ha_high,
                source_low=ha_low,
                ohlc_repaired=0,
            )
        )
        previous_open = ha_open
        previous_close = ha_close

    return result


def build_inventory(candles_dir: Path, heikin_ashi_dir: Path) -> list[dict[str, str]]:
    tickers = sorted({path.stem.rsplit("_", 1)[0].upper() for path in candles_dir.glob("*.csv")})
    rows: list[dict[str, str]] = []
    for ticker in tickers:
        actions = load_actions(actions_path(ticker))
        for chart_type, directory in (("candles", candles_dir), ("heikin_ashi", heikin_ashi_dir)):
            for interval in ("4h", "1d", "1wk"):
                path = directory / f"{ticker.lower()}_{interval}.csv"
                rows.append(_inventory_row(ticker, chart_type, interval, path, len(actions)))
    return rows


def _inventory_row(ticker: str, chart_type: str, interval: str, path: Path, action_count: int) -> dict[str, str]:
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
            "issues": "arquivo inexistente",
        }

    candles = load_candles(path)
    issues = validate_candles(candles)
    ready = bool(candles) and not issues
    return {
        "ticker": ticker,
        "chart_type": chart_type,
        "interval": INTERVAL_LABELS[interval],
        "file": str(path),
        "status": "ok" if ready else "revisar",
        "ready_for_backtest": "sim" if ready else "nao",
        "rows": str(len(candles)),
        "start": candles[0].date if candles else "",
        "end": candles[-1].date if candles else "",
        "corporate_actions": str(action_count),
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
        "file",
        "issues",
    ]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fields} for row in rows])


def write_inventory_markdown(rows: list[dict[str, str]], path: Path) -> None:
    tickers = sorted({row["ticker"] for row in rows})
    lines = [
        "# Inventario de dados",
        "",
        "Status gerado a partir de `data/candles`, `data/heikin_ashi` e `data/corporate_actions`.",
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
            lines.append("| Tempo | Status | Backtest | Linhas | Inicio | Fim | Arquivo |")
            lines.append("|---|---|---|---:|---|---|---|")
            for interval in ("4h", "1d", "1sem"):
                row = next(
                    item for item in rows
                    if item["ticker"] == ticker and item["chart_type"] == chart_type and item["interval"] == interval
                )
                lines.append(
                    f"| {interval} | {row['status']} | {row['ready_for_backtest']} | "
                    f"{row['rows']} | {row['start']} | {row['end']} | `{row['file']}` |"
                )
            actions = next(item["corporate_actions"] for item in rows if item["ticker"] == ticker)
        lines.append("")
        lines.append(f"Eventos corporativos baixados: {actions}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
