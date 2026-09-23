"""Diagnostico: replay realista que lista frações sem liquidação documentada.

O motor realista falha fechado quando um desdobramento, grupamento ou
bonificação transforma uma posição inteira em fração sem o evento oficial de
venda das frações em `corporate_settlements.json`. Este diagnóstico roda o mesmo
replay, descarta a fração com valor ZERO (hipótese conservadora) e grava:

- `diagnostic_fractional_events`: cada evento que precisa de liquidação documentada;
- `validity` com o sufixo `__DIAGNOSTIC_FRACTIONS_AT_ZERO`.

O resultado nunca é certificável: `--require-certified-inputs` é recusado.
Aceita os mesmos argumentos de `backtest_strategy_management_realistic.py`.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import b3_strategy_lab.realistic_portfolio as realistic_portfolio  # noqa: E402
from scripts import backtest_strategy_management_realistic as realistic_script  # noqa: E402

VALIDITY_SUFFIX = "__DIAGNOSTIC_FRACTIONS_AT_ZERO"


def _fractions_at_zero(events: list[dict[str, object]]):
    def apply(account, data, current: str) -> None:
        for ticker, position in list(account.positions.items()):
            if position.shares <= 0:
                continue
            index = data.index_by_date.get(ticker, {}).get(current)
            if index is None or index <= 0:
                continue
            candle = data.candles[ticker][index]
            previous = data.candles[ticker][index - 1]
            ratio = float(candle.adjustment_factor) / float(previous.adjustment_factor)
            if ratio <= 0 or not math.isfinite(ratio):
                raise ValueError(f"{ticker}/{current}: invalid adjustment factor.")
            if math.isclose(ratio, 1.0, rel_tol=1e-10, abs_tol=1e-12):
                continue
            exact = position.shares * ratio
            whole = math.floor(exact + 1e-9)
            if math.isclose(exact, round(exact), abs_tol=1e-9):
                position.shares = int(round(exact))
                position.average_cost /= ratio
                continue
            if whole <= 0:
                raise ValueError(f"{ticker}/{current}: event leaves no whole share.")
            events.append(
                {
                    "ticker": ticker,
                    "date": current,
                    "shares_before": position.shares,
                    "share_ratio": ratio,
                    "shares_after": whole,
                    "fraction_discarded": exact - whole,
                    "fraction_value_at_official_open": (exact - whole) * float(candle.raw_open),
                }
            )
            # The whole cost basis stays on the whole shares; the fraction earns nothing.
            position.average_cost = position.average_cost * position.shares / whole
            position.shares = int(whole)

    return apply


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--require-certified-inputs" in arguments:
        raise SystemExit("Diagnostico nunca produz resultado certificado; remova --require-certified-inputs.")
    if not any(value == "--output" or value.startswith("--output=") for value in arguments):
        raise SystemExit("Informe --output para nao sobrescrever o resumo realista padrao.")

    events: list[dict[str, object]] = []
    original = realistic_portfolio._original_apply_split_from_adjustment_factors
    realistic_portfolio._original_apply_split_from_adjustment_factors = _fractions_at_zero(events)
    try:
        code = realistic_script.main(arguments)
    finally:
        realistic_portfolio._original_apply_split_from_adjustment_factors = original

    output = Path(next(
        value.split("=", 1)[1] if value.startswith("--output=") else arguments[index + 1]
        for index, value in enumerate(arguments)
        if value == "--output" or value.startswith("--output=")
    ))
    payload = json.loads(output.read_text(encoding="utf-8"))
    if events and VALIDITY_SUFFIX not in str(payload["validity"]):
        payload["validity"] = str(payload["validity"]) + VALIDITY_SUFFIX
    payload["diagnostic_fractional_events"] = events
    payload["diagnostic_fraction_policy"] = (
        "Fractions without a documented fractional_sale settlement are discarded at zero value. "
        "Add the official settlement to corporate_settlements.json and rerun "
        "backtest_strategy_management_realistic.py for a result without this assumption."
    )
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Eventos com fracao descartada: {len(events)}")
    for event in events:
        print(
            f"- {event['ticker']} {event['date']}: {event['fraction_discarded']:.4f} acao "
            f"(~R$ {event['fraction_value_at_official_open']:.2f} na abertura)"
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
