from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass

from b3_strategy_lab.candles import DEFAULT_TICKERS, Candle
from b3_strategy_lab.cotahist import load_verified_candles


@dataclass(frozen=True)
class AuditFinding:
    ticker: str
    severity: str
    code: str
    date: str
    message: str


def _audit_candle(candle: Candle) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    values = (candle.open, candle.high, candle.low, candle.close)
    raw_values = (candle.raw_open, candle.raw_high, candle.raw_low, candle.raw_close)
    if any(not math.isfinite(value) or value <= 0 for value in values):
        findings.append(AuditFinding(candle.ticker, "error", "invalid_adjusted_ohlc", candle.date, "OHLC normalizado nao positivo/finito."))
    if any(not math.isfinite(value) or value <= 0 for value in raw_values):
        findings.append(AuditFinding(candle.ticker, "error", "invalid_raw_ohlc", candle.date, "OHLC bruto nao positivo/finito."))
    if candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close) or candle.high < candle.low:
        findings.append(AuditFinding(candle.ticker, "error", "adjusted_ohlc_order", candle.date, "OHLC normalizado inconsistente."))
    if candle.raw_high < max(candle.raw_open, candle.raw_close) or candle.raw_low > min(candle.raw_open, candle.raw_close) or candle.raw_high < candle.raw_low:
        findings.append(AuditFinding(candle.ticker, "error", "raw_ohlc_order", candle.date, "OHLC bruto inconsistente."))
    if not math.isfinite(candle.adjustment_factor) or candle.adjustment_factor <= 0:
        findings.append(AuditFinding(candle.ticker, "error", "invalid_adjustment_factor", candle.date, "Fator de ajuste invalido."))
    else:
        pairs = (
            (candle.open, candle.raw_open),
            (candle.high, candle.raw_high),
            (candle.low, candle.raw_low),
            (candle.close, candle.raw_close),
        )
        for adjusted, raw in pairs:
            expected = raw * candle.adjustment_factor
            if not math.isclose(adjusted, expected, rel_tol=1e-8, abs_tol=1e-8):
                findings.append(AuditFinding(candle.ticker, "error", "price_adjustment_mismatch", candle.date, "OHLC normalizado diverge de raw_* x adjustment_factor."))
                break
    if candle.raw_volume < 0 or candle.volume < 0 or candle.trades < 0 or candle.financial_volume < 0:
        findings.append(AuditFinding(candle.ticker, "error", "negative_volume_fields", candle.date, "Volume, negocios ou volume financeiro negativo."))
    if candle.raw_volume > 0 and candle.adjustment_factor > 0:
        expected_volume = int(round(candle.raw_volume / candle.adjustment_factor))
        if abs(candle.volume - expected_volume) > 1:
            findings.append(AuditFinding(candle.ticker, "error", "volume_adjustment_mismatch", candle.date, "Volume normalizado nao corresponde ao raw_volume / adjustment_factor."))
    if candle.raw_volume == 0 and candle.trades > 0:
        findings.append(AuditFinding(candle.ticker, "warning", "trades_without_volume", candle.date, "Ha negocios registrados com raw_volume zero."))
    if candle.raw_volume > 0 and candle.trades == 0:
        findings.append(AuditFinding(candle.ticker, "warning", "volume_without_trades", candle.date, "Ha raw_volume positivo com zero negocios."))
    if candle.financial_volume > 0 and candle.raw_volume > 0:
        vwap_proxy = candle.financial_volume / candle.raw_volume
        if vwap_proxy < candle.raw_low * 0.95 or vwap_proxy > candle.raw_high * 1.05:
            findings.append(AuditFinding(candle.ticker, "warning", "financial_volume_price_range", candle.date, "VOLTOT/QUATOT fica fora da faixa OHLC bruta com tolerancia de 5%."))
    return findings


def audit_series(ticker: str, candles: list[Candle]) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    seen: set[str] = set()
    previous: Candle | None = None
    for candle in candles:
        findings.extend(_audit_candle(candle))
        if candle.date in seen:
            findings.append(AuditFinding(ticker, "error", "duplicate_date", candle.date, "Data duplicada na serie."))
        seen.add(candle.date)
        if previous is not None:
            if candle.date <= previous.date:
                findings.append(AuditFinding(ticker, "error", "date_order", candle.date, "Datas fora de ordem estritamente crescente."))
            if previous.close > 0:
                move = candle.close / previous.close - 1.0
                if abs(move) > 0.50:
                    findings.append(AuditFinding(ticker, "warning", "extreme_adjusted_move", candle.date, f"Variacao de fechamento normalizado de {move:.2%}."))
        previous = candle
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audita OHLC, ajustes, volume e continuidade antes do backtest.")
    parser.add_argument("--tickers", nargs="+", default=list(DEFAULT_TICKERS))
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    findings: list[AuditFinding] = []
    summary: dict[str, dict[str, object]] = {}
    for ticker in [value.upper() for value in args.tickers]:
        candles, manifest = load_verified_candles(ticker, args.interval, start=args.start)
        ticker_findings = audit_series(ticker, candles)
        findings.extend(ticker_findings)
        summary[ticker] = {
            "rows": len(candles),
            "start": candles[0].date if candles else "",
            "end": candles[-1].date if candles else "",
            "manifest_status": manifest.status,
            "volume_source": manifest.volume_source,
            "errors": sum(item.severity == "error" for item in ticker_findings),
            "warnings": sum(item.severity == "warning" for item in ticker_findings),
        }

    payload = {
        "summary": summary,
        "errors": [asdict(item) for item in findings if item.severity == "error"],
        "warnings": [asdict(item) for item in findings if item.severity == "warning"],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for ticker, row in summary.items():
            print(f"{ticker}: {row['rows']} candles | {row['start']}..{row['end']} | erros={row['errors']} avisos={row['warnings']}")
        if payload["errors"]:
            print("\nERROS:")
            for item in payload["errors"][:100]:
                print(f"- {item['ticker']} {item['date']} {item['code']}: {item['message']}")
        if payload["warnings"]:
            print("\nAVISOS:")
            for item in payload["warnings"][:100]:
                print(f"- {item['ticker']} {item['date']} {item['code']}: {item['message']}")

    return 1 if payload["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
