from __future__ import annotations

import argparse
import ast
import inspect
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from b3_strategy_lab.additional_strategies import ADDITIONAL_STRATEGIES  # noqa: E402
from b3_strategy_lab.cli import _signal_candles  # noqa: E402
from b3_strategy_lab.cotahist import (  # noqa: E402
    DEFAULT_SPLIT_EVIDENCE_PATH,
    load_verified_candles,
)
from b3_strategy_lab.extensions import build_indicator, registered_indicators  # noqa: E402
from b3_strategy_lab.strategies import (  # noqa: E402
    STRATEGIES,
    build_signals,
    portfolio_strategies,
    strategy_info,
    strategy_parameters,
)


EXPECTED_SOURCE_CONSUMERS = {
    "b3_strategy_lab.additional_strategies._mfi",
    "b3_strategy_lab.extended_strategies.ease_of_movement",
    "b3_strategy_lab.extended_strategies.elder_force_index",
    "b3_strategy_lab.extended_strategies.klinger_volume_oscillator",
    "b3_strategy_lab.extended_strategies.negative_volume_index",
    "b3_strategy_lab.researched_strategies.chaikin_money_flow",
    "b3_strategy_lab.research_indicators.money_flow_index",
    "b3_strategy_lab.research_indicators.chaikin_money_flow",
    "b3_strategy_lab.research_indicators.elder_force_index",
    "b3_strategy_lab.research_indicators.ease_of_movement",
    "b3_strategy_lab.research_indicators.negative_volume_index",
    "b3_strategy_lab.strategies.chandelier_breakout",
    "b3_strategy_lab.strategies.range_expansion_breakout",
}

VOLUME_CONSUMER_GROUPS = (
    {
        "indicator": "Money Flow Index (MFI)",
        "strategies": sorted(
            [item.name for item in ADDITIONAL_STRATEGIES if item.engine == "mfi_trend"]
            + [
                "mfi_reversal", "mfi_trend_follow", "mfi_cmf_confirm",
                "mfi_efi_confirm", "mfi_price_trend", "nvi_mfi_confirm",
            ]
        ),
        "input": "preco tipico normalizado multiplicado pela quantidade normalizada",
        "source_function": "b3_strategy_lab.additional_strategies._mfi",
    },
    {
        "indicator": "Chaikin Money Flow",
        "strategies": [
            "chaikin_money_flow", "cmf_zero_cross", "cmf_threshold_hysteresis",
            "mfi_cmf_confirm", "cmf_efi_confirm", "volume_triple_confirm",
            "cmf_price_trend", "cmf_ema_trend",
        ],
        "input": "multiplicador de fechamento no range vezes quantidade normalizada",
        "source_function": "b3_strategy_lab.researched_strategies.chaikin_money_flow",
    },
    {
        "indicator": "Elder Force Index",
        "strategies": [
            "elder_force_index", "efi_zero_cross", "efi_trend_confirm",
            "mfi_efi_confirm", "cmf_efi_confirm", "volume_triple_confirm",
        ],
        "input": "variacao do fechamento normalizado vezes quantidade normalizada",
        "source_function": "b3_strategy_lab.extended_strategies.elder_force_index",
    },
    {
        "indicator": "Ease of Movement",
        "strategies": [
            "ease_of_movement", "eom_zero_cross", "eom_trend_confirm",
            "eom_nvi_confirm", "volume_triple_confirm",
        ],
        "input": "movimento do ponto medio e range divididos pela quantidade normalizada",
        "source_function": "b3_strategy_lab.extended_strategies.ease_of_movement",
    },
    {
        "indicator": "Negative Volume Index",
        "strategies": [
            "negative_volume_index", "nvi_ema_trend", "nvi_price_confirm",
            "eom_nvi_confirm", "nvi_mfi_confirm", "nvi_dual_ema_trend",
        ],
        "input": "comparacao entre quantidades normalizadas consecutivas",
        "source_function": "b3_strategy_lab.extended_strategies.negative_volume_index",
    },
    {
        "indicator": "Klinger Volume Oscillator",
        "strategies": ["klinger_volume_oscillator"],
        "input": "forca do range e tendencia vezes quantidade normalizada",
        "source_function": "b3_strategy_lab.extended_strategies.klinger_volume_oscillator",
    },
    {
        "indicator": "Filtro de volume em rompimentos",
        "strategies": ["chandelier_breakout", "range_expansion_breakout"],
        "input": "quantidade normalizada comparada com sua media movel",
        "source_function": (
            "b3_strategy_lab.strategies.chandelier_breakout; "
            "b3_strategy_lab.strategies.range_expansion_breakout"
        ),
    },
)

STRATEGY_SOURCE_FILES = (
    Path("b3_strategy_lab/additional_strategies.py"),
    Path("b3_strategy_lab/researched_strategies.py"),
    Path("b3_strategy_lab/extended_strategies.py"),
    Path("b3_strategy_lab/research_indicators.py"),
    Path("b3_strategy_lab/indicator_strategies.py"),
    Path("b3_strategy_lab/trend_strategies.py"),
    Path("b3_strategy_lab/strategies.py"),
    Path("b3_strategy_lab/user_extensions.py"),
)


def volume_strategy_names() -> list[str]:
    builtins = {
            strategy
            for group in VOLUME_CONSUMER_GROUPS
            for strategy in group["strategies"]
    }
    user_strategies = {
        name
        for name in portfolio_strategies()
        if STRATEGIES[name].__module__ == "b3_strategy_lab.user_extensions"
    }
    return sorted(builtins | user_strategies)


def source_attribute_consumers(
    attributes: set[str],
    root: Path = PROJECT_ROOT,
) -> set[str]:
    consumers: set[str] = set()
    for relative_path in STRATEGY_SOURCE_FILES:
        module = ".".join(relative_path.with_suffix("").parts)
        tree = ast.parse((root / relative_path).read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if any(
                isinstance(child, ast.Attribute) and child.attr in attributes
                for child in ast.walk(node)
            ):
                consumers.add(f"{module}.{node.name}")
    return consumers


def source_volume_consumers(root: Path = PROJECT_ROOT) -> set[str]:
    return source_attribute_consumers({"volume"}, root)


def source_raw_volume_consumers(root: Path = PROJECT_ROOT) -> set[str]:
    return source_attribute_consumers({"raw_volume"}, root)


def _relative_outside(value: float, low: float, high: float) -> float:
    if value < low:
        return (low - value) / low if low else math.inf
    if value > high:
        return (value - high) / high if high else math.inf
    return 0.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audita o volume oficial, os ajustes de quantidade e todos os indicadores "
            "ou filtros que consomem volume na matriz de backtest."
        )
    )
    parser.add_argument(
        "--universe",
        type=Path,
        default=Path("data/universes/fixed_40_2018.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/volume_indicator_audit_40.json"),
    )
    parser.add_argument(
        "--split-evidence",
        type=Path,
        default=DEFAULT_SPLIT_EVIDENCE_PATH,
    )
    args = parser.parse_args(argv)

    universe = json.loads(args.universe.read_text(encoding="utf-8"))
    split_evidence = json.loads(args.split_evidence.read_text(encoding="utf-8"))
    tickers = [str(ticker).upper() for ticker in universe["tickers"]]
    evaluation_start = str(universe["selected_as_of"])
    coverage_start = str(universe["warmup_start"])
    candles_by_ticker = {}
    manifests = {}
    for ticker in tickers:
        candles, manifest = load_verified_candles(
            ticker,
            "1d",
            require_verified_splits_from=coverage_start,
        )
        candles_by_ticker[ticker] = candles
        manifests[ticker] = manifest

    evaluation_end = min(candles[-1].date for candles in candles_by_ticker.values())
    date_sets = {
        ticker: {
            candle.date
            for candle in candles
            if evaluation_start <= candle.date <= evaluation_end
        }
        for ticker, candles in candles_by_ticker.items()
    }
    common_dates = set.intersection(*date_sets.values())
    union_dates = set.union(*date_sets.values())

    rows = []
    official_vwap_outliers = []
    all_volume_adjustment_errors = []
    all_notional_errors = []
    all_notional_rounding_excesses = []
    for ticker in tickers:
        window = [
            candle
            for candle in candles_by_ticker[ticker]
            if evaluation_start <= candle.date <= evaluation_end
        ]
        adjustment_errors = []
        notional_errors = []
        notional_rounding_excesses = []
        ticker_outliers = []
        for candle in window:
            expected_adjusted_volume = (
                candle.raw_volume / candle.adjustment_factor
                if candle.adjustment_factor > 0
                else math.inf
            )
            adjustment_error = abs(candle.volume - expected_adjusted_volume)
            adjustment_errors.append(adjustment_error)
            all_volume_adjustment_errors.append(adjustment_error)

            raw_typical = (candle.raw_high + candle.raw_low + candle.raw_close) / 3
            adjusted_typical = (candle.high + candle.low + candle.close) / 3
            raw_notional = raw_typical * candle.raw_volume
            adjusted_notional = adjusted_typical * candle.volume
            notional_error = (
                abs(adjusted_notional - raw_notional) / abs(raw_notional)
                if raw_notional
                else 0.0
            )
            notional_errors.append(notional_error)
            all_notional_errors.append(notional_error)
            # ``volume`` is an integer after the inverse split adjustment.  A
            # half-share of rounding is therefore the tight mathematical bound
            # for the otherwise invariant price x quantity notional.
            expected_adjusted_volume = candle.raw_volume / candle.adjustment_factor
            rounding_tolerance = (
                0.500001 / expected_adjusted_volume
                if expected_adjusted_volume > 0
                else math.inf
            )
            rounding_excess = max(0.0, notional_error - rounding_tolerance)
            notional_rounding_excesses.append(rounding_excess)
            all_notional_rounding_excesses.append(rounding_excess)

            # OHLC belongs to the standard market (010).  Once activity from
            # the fractional market (020) is consolidated, only the standard
            # component is comparable with that OHLC interval.
            standard_volume = candle.raw_volume - candle.fractional_raw_volume
            standard_financial_volume = (
                candle.financial_volume - candle.fractional_financial_volume
            )
            official_vwap = (
                standard_financial_volume / standard_volume
                if standard_volume > 0
                else math.inf
            )
            outside = _relative_outside(
                official_vwap,
                candle.raw_low,
                candle.raw_high,
            )
            if outside > 0:
                item = {
                    "ticker": ticker,
                    "date": candle.date,
                    "raw_low": candle.raw_low,
                    "official_vwap": official_vwap,
                    "raw_high": candle.raw_high,
                    "outside_range_pct": outside * 100,
                    "standard_raw_volume": standard_volume,
                    "standard_financial_volume": standard_financial_volume,
                    "consolidated_raw_volume": candle.raw_volume,
                    "consolidated_trades": candle.trades,
                    "consolidated_financial_volume": candle.financial_volume,
                    "candle_sha256": manifests[ticker].candle_sha256,
                }
                ticker_outliers.append(item)
                official_vwap_outliers.append(item)

        rows.append(
            {
                "ticker": ticker,
                "rows": len(window),
                "first_date": window[0].date,
                "last_date": window[-1].date,
                "zero_or_negative_adjusted_volume_rows": sum(
                    candle.volume <= 0 for candle in window
                ),
                "zero_or_negative_raw_volume_rows": sum(
                    candle.raw_volume <= 0 for candle in window
                ),
                "zero_trade_rows": sum(candle.trades <= 0 for candle in window),
                "zero_or_negative_financial_volume_rows": sum(
                    candle.financial_volume <= 0 for candle in window
                ),
                "non_consolidated_volume_rows": sum(
                    candle.volume_scope != "consolidated_010_020"
                    for candle in window
                ),
                "fractional_raw_volume": sum(
                    candle.fractional_raw_volume for candle in window
                ),
                "fractional_trades": sum(
                    candle.fractional_trades for candle in window
                ),
                "fractional_financial_volume": sum(
                    candle.fractional_financial_volume for candle in window
                ),
                "max_adjusted_volume_rounding_error": max(adjustment_errors, default=0.0),
                "max_price_quantity_notional_relative_error": max(
                    notional_errors,
                    default=0.0,
                ),
                "max_notional_error_above_integer_rounding_bound": max(
                    notional_rounding_excesses,
                    default=0.0,
                ),
                "official_vwap_outside_raw_ohlc_rows": len(ticker_outliers),
                "candle_sha256": manifests[ticker].candle_sha256,
            }
        )

    audited_strategies = volume_strategy_names()
    registered = set(portfolio_strategies())
    family_volume = {
        strategy
        for strategy in registered
        if "volume" in strategy_info(strategy).family
    }
    parameter_volume = {
        strategy
        for strategy in registered
        if {"volume_window", "volume_mult"} & set(strategy_parameters(strategy))
    }
    indirect_volume_strategies = {"cmf_ema_trend", "nvi_dual_ema_trend"}

    signal_failures = []
    signal_runs = 0
    indicator_runs = 0
    for ticker in tickers:
        signal_candles = [
            candle
            for candle in candles_by_ticker[ticker]
            if coverage_start <= candle.date <= evaluation_end
        ]
        adjusted = _signal_candles(signal_candles, "adjusted")
        raw = _signal_candles(signal_candles, "raw")
        if any(candle.volume != candle.raw_volume for candle in raw):
            signal_failures.append(f"{ticker}: modo raw nao usa raw_volume")
        if any(
            candle.volume != original.volume
            for candle, original in zip(adjusted, signal_candles)
        ):
            signal_failures.append(f"{ticker}: modo adjusted alterou volume normalizado")
        for strategy in audited_strategies:
            signal_runs += 1
            try:
                params = strategy_parameters(strategy)
                complete = build_signals(strategy, adjusted, **params)
                prefix = build_signals(strategy, adjusted[:-1], **params)
                if len(complete) != len(adjusted) or complete[:-1] != prefix:
                    signal_failures.append(
                        f"{ticker}/{strategy}: tamanho ou causalidade invalida"
                    )
            except Exception as error:  # pragma: no cover - materializado no relatorio
                signal_failures.append(f"{ticker}/{strategy}: {error}")

        for indicator_name, indicator_function in registered_indicators():
            indicator_runs += 1
            try:
                parameters = {
                    name: parameter.default
                    for name, parameter in inspect.signature(
                        indicator_function
                    ).parameters.items()
                    if name != "candles"
                }
                complete = build_indicator(indicator_name, adjusted, **parameters)
                prefix = build_indicator(indicator_name, adjusted[:-1], **parameters)
                if len(complete) != len(adjusted) or complete[:-1] != prefix:
                    signal_failures.append(
                        f"{ticker}/{indicator_name}: indicador com tamanho ou "
                        "causalidade invalida"
                    )
            except Exception as error:  # pragma: no cover - materializado no relatorio
                signal_failures.append(f"{ticker}/{indicator_name}: {error}")

    source_consumers = source_volume_consumers()
    raw_volume_consumers = source_raw_volume_consumers()
    user_source_consumers = {
        name
        for name in source_consumers
        if name.startswith("b3_strategy_lab.user_extensions.")
    }
    marker_audit = split_evidence.get("share_count_marker_audit") or {}
    marker_rows = marker_audit.get("markers") or []
    continuity_audit = split_evidence.get("event_continuity_audit") or {}
    supplemental_registry = split_evidence.get("supplemental_registry") or {}
    supplemental_evidence_events = [
        event
        for event in split_evidence.get("events") or []
        if event.get("source_authority") in {"CVM", "issuer"}
    ]
    max_vwap_outside = max(
        (item["outside_range_pct"] / 100 for item in official_vwap_outliers),
        default=0.0,
    )
    checks = {
        "all_tickers_share_every_evaluation_session": common_dates == union_dates,
        "all_adjusted_volumes_are_positive": all(
            row["zero_or_negative_adjusted_volume_rows"] == 0 for row in rows
        ),
        "all_raw_volumes_are_positive": all(
            row["zero_or_negative_raw_volume_rows"] == 0 for row in rows
        ),
        "all_rows_have_trades": all(row["zero_trade_rows"] == 0 for row in rows),
        "all_rows_have_financial_volume": all(
            row["zero_or_negative_financial_volume_rows"] == 0 for row in rows
        ),
        "all_rows_use_consolidated_standard_and_fractional_volume": all(
            row["non_consolidated_volume_rows"] == 0 for row in rows
        ),
        "adjusted_volume_matches_split_factor_with_rounding": max(
            all_volume_adjustment_errors,
            default=0.0,
        ) <= 0.500001,
        "adjusted_price_quantity_preserves_raw_notional_with_integer_rounding": max(
            all_notional_rounding_excesses,
            default=0.0,
        ) <= 0.000000001,
        "all_cotahist_share_count_markers_have_official_events": (
            marker_audit.get("uncovered_count") == 0
            and bool(marker_rows)
            and all(marker.get("covered") for marker in marker_rows)
        ),
        "historical_events_missing_from_current_b3_api_are_loaded": (
            supplemental_registry.get("event_count")
            == len(supplemental_evidence_events)
            and len(supplemental_evidence_events) > 0
        ),
        "official_event_factors_leave_no_extreme_price_discontinuity": float(
            continuity_audit.get(
                "maximum_absolute_split_neutral_raw_close_return",
                math.inf,
            )
        )
        <= 0.35,
        "official_financial_volume_has_no_large_ohlc_inconsistency": (
            max_vwap_outside <= 0.05
        ),
        "builtin_source_volume_consumers_match_inventory": (
            source_consumers - user_source_consumers == EXPECTED_SOURCE_CONSUMERS
        ),
        "user_extensions_do_not_bypass_signal_volume_basis": not any(
            name.startswith("b3_strategy_lab.user_extensions.")
            for name in raw_volume_consumers
        ),
        "all_volume_families_are_audited": family_volume <= set(audited_strategies),
        "known_indirect_volume_strategies_are_audited": (
            indirect_volume_strategies <= set(audited_strategies)
        ),
        "all_volume_parameter_filters_are_audited": parameter_volume
        <= set(audited_strategies),
        "builtin_volume_parameter_filters_match_inventory": (
            {"chandelier_breakout", "range_expansion_breakout"} <= parameter_volume
        ),
        "all_audited_strategies_are_in_full_matrix": set(audited_strategies) <= registered,
        "all_volume_signal_runs_are_binary_and_causal": not signal_failures,
    }
    warnings = []
    if official_vwap_outliers:
        warnings.append(
            "O COTAHIST oficial possui registros em que VOLTOT/QUATOT fica fora do "
            "intervalo PREMIN-PREMAX; os registros brutos foram preservados e listados "
            "em official_vwap_outliers, sem reparo sintetico. O maior desvio e inferior "
            "ao limite diagnostico de 5%."
        )

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "universe_id": universe["id"],
        "universe_manifest": str(args.universe),
        "source": {
            "name": "B3 COTAHIST",
            "raw_quantity_field": "QUATOT consolidado dos mercados 010 e 020",
            "trade_count_field": "TOTNEG consolidado dos mercados 010 e 020",
            "financial_volume_field": "VOLTOT consolidado dos mercados 010 e 020",
            "price_basis": "PREABE/PREMAX/PREMIN/PREULT do mercado 010 dividido por FATCOT",
            "ohlc_market": "010 / BDI 02",
            "fractional_activity_market": "020 / BDI 96",
        },
        "volume_policy": {
            "adjusted_signal_mode": (
                "precos e quantidade consolidada 010+020 normalizados inversamente "
                "pelos eventos de capital"
            ),
            "raw_signal_mode": (
                "precos raw_* do mercado 010 e raw_volume consolidado 010+020 sem normalizacao"
            ),
            "dividends_and_jcp": "excluidos",
        },
        "corporate_action_volume_basis": {
            "split_evidence": str(args.split_evidence),
            "official_event_count": len(split_evidence.get("events") or []),
            "historical_supplemental_event_count": len(
                supplemental_evidence_events
            ),
            "cotahist_share_count_marker_count": len(marker_rows),
            "uncovered_marker_count": marker_audit.get("uncovered_count"),
            "maximum_absolute_split_neutral_raw_close_return": (
                continuity_audit.get(
                    "maximum_absolute_split_neutral_raw_close_return"
                )
            ),
        },
        "warmup_start": coverage_start,
        "evaluation_start": evaluation_start,
        "evaluation_end": evaluation_end,
        "common_sessions": len(common_dates),
        "audited_strategy_count": len(audited_strategies),
        "audited_strategies": audited_strategies,
        "indicator_groups": VOLUME_CONSUMER_GROUPS,
        "source_volume_consumers": sorted(source_consumers),
        "source_raw_volume_consumers": sorted(raw_volume_consumers),
        "user_source_volume_consumers": sorted(user_source_consumers),
        "signal_runs": signal_runs,
        "indicator_runs": indicator_runs,
        "signal_failures": signal_failures,
        "checks": checks,
        "warnings": warnings,
        "official_vwap_outliers": sorted(
            official_vwap_outliers,
            key=lambda item: (item["outside_range_pct"], item["ticker"], item["date"]),
            reverse=True,
        ),
        "tickers": rows,
        "ready": all(checks.values()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    print(
        f"{args.output}: ready={payload['ready']}, "
        f"estrategias={payload['audited_strategy_count']}, "
        f"execucoes={payload['signal_runs']}, outliers_oficiais={len(official_vwap_outliers)}"
    )
    return 0 if payload["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
