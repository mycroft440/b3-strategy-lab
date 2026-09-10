from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"expected patch anchor missing in {path}: {old[:120]!r}")
    if text.count(old) != 1:
        raise SystemExit(f"patch anchor is not unique in {path}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# Map only source-certified complex transition failures to an explicit research-invalid reason.
replace_once(
    "scripts/research_portfolio_allocation.py",
    "import json\nimport sys\n",
    "import json\nimport re\nimport sys\n",
)
anchor = """def _applicable_unit_transitions(current_date: str):
    day = str(current_date)[:10]
    for effective in sorted(_certified_unit_transitions()):
        if effective > day:
            break
        for transition in _certified_unit_transitions()[effective]:
            yield transition


"""
addition = anchor + """@lru_cache(maxsize=1)
def _certified_unsupported_transition_boundaries() -> tuple[tuple[str, str, str, str], ...]:
    \"\"\"Return certified events the price-only research engine must not fabricate.\"\"\"
    if not _TRANSITION_REVIEWS.exists():
        return ()
    payload = json.loads(_TRANSITION_REVIEWS.read_text(encoding=\"utf-8\"))
    reviews = payload.get(\"reviews\", []) if isinstance(payload, dict) else []
    boundaries: list[tuple[str, str, str, str]] = []
    for raw in reviews:
        if not isinstance(raw, dict) or raw.get(\"certification_status\") != \"certified\":
            continue
        old = str(raw.get(\"old_ticker\", \"\")).strip().upper()
        new = str(raw.get(\"new_ticker\", \"\")).strip().upper()
        effective = str(raw.get(\"effective_date\", \"\")).strip()[:10]
        event_type = str(raw.get(\"event_type\", \"unknown\")).strip() or \"unknown\"
        try:
            ratio = float(raw.get(\"share_ratio\", 0.0))
            cash = float(raw.get(\"cash_per_old_share\", 0.0))
        except (TypeError, ValueError):
            ratio = 0.0
            cash = 0.0
        unit_preserving = (
            bool(new)
            and abs(ratio - 1.0) <= 1e-12
            and abs(cash) <= 1e-12
            and raw.get(\"fractional_treatment\") == \"preserve_units\"
            and raw.get(\"tax_basis_treatment\") == \"carry_total_basis\"
        )
        if old and effective and not unit_preserving:
            boundaries.append((effective, old, new, event_type))
    return tuple(sorted(boundaries))


def _research_invalid_transition_reason(message: str) -> str | None:
    \"\"\"Classify only fresh-price failures explained by a certified complex event.\"\"\"
    match = re.match(
        r\"^(?P<date>\\d{4}-\\d{2}-\\d{2}): (?:abertura|fechamento) fresca obrigatoria \"
        r\"ausente para (?P<tickers>.+)$\",
        message.strip(),
    )
    if match is None:
        return None
    value_date = match.group(\"date\")
    missing = {item.strip().upper() for item in match.group(\"tickers\").split(\",\")}
    for effective, old, new, event_type in _certified_unsupported_transition_boundaries():
        if effective <= value_date and old in missing:
            successor = new or \"TERMINAL\"
            return (
                f\"{value_date}:{old}->{successor}:{event_type}:\"
                \"CERTIFIED_COMPLEX_TRANSITION_UNSUPPORTED_IN_PRICE_ONLY_RESEARCH\"
            )
    return None


"""
replace_once("scripts/research_portfolio_allocation.py", anchor, addition)

# Keep full Cartesian cardinality but mark only certified-complex-transition crossings invalid.
replace_once(
    "scripts/backtest_strategy_management_combinations.py",
    """    _configs,
    run_portfolio,
)
""",
    """    _configs,
    _research_invalid_transition_reason,
    run_portfolio,
)
""",
)
replace_once(
    "scripts/backtest_strategy_management_combinations.py",
    """def _ranking_key(row: dict[str, object]) -> tuple[float, float, str, str]:
    return (
        -float(row[\"total_return\"]),
        -float(row[\"cagr\"]),
        str(row[\"trading_strategy\"]),
        str(row[\"management_strategy\"]),
    )
""",
    """def _ranking_key(row: dict[str, object]) -> tuple[int, float, float, str, str]:
    if str(row.get(\"validity\", \"VALID\")) != \"VALID\":
        return (1, 0.0, 0.0, str(row[\"trading_strategy\"]), str(row[\"management_strategy\"]))
    return (
        0,
        -float(row[\"total_return\"]),
        -float(row[\"cagr\"]),
        str(row[\"trading_strategy\"]),
        str(row[\"management_strategy\"]),
    )
""",
)
old_strategy = """    for config in configs:
        summary, _ = run_portfolio(
            data,
            config,
            start=start,
            end=end,
            initial_cash=initial_cash,
            cost_bps=cost_bps,
            slippage_bps=slippage_bps,
            lot_size=lot_size,
            eligibility=eligibility,
            universe_membership=universe_membership,
            collect_curve=False,
        )
        rows.append(
            {
                \"trading_strategy\": strategy,
                \"strategy_params\": params_text,
                \"management_strategy\": config.name,
                \"start\": summary.start,
                \"end\": summary.end,
                \"candles\": summary.candles,
                \"trades\": summary.trades,
                \"exposure\": summary.exposure,
                \"avg_positions\": summary.avg_positions,
                \"initial_equity\": initial_cash,
                \"final_equity\": summary.final_equity,
                \"total_return\": summary.total_return,
                \"cagr\": summary.cagr,
                \"average_annual_return\": summary.average_annual_return,
                \"max_drawdown\": summary.max_drawdown,
                \"annual_volatility\": summary.annual_volatility,
                \"sharpe\": summary.sharpe,
                \"turnover\": summary.turnover,
            }
        )
"""
new_strategy = """    for config in configs:
        try:
            summary, _ = run_portfolio(
                data,
                config,
                start=start,
                end=end,
                initial_cash=initial_cash,
                cost_bps=cost_bps,
                slippage_bps=slippage_bps,
                lot_size=lot_size,
                eligibility=eligibility,
                universe_membership=universe_membership,
                collect_curve=False,
            )
        except ValueError as error:
            invalid_reason = _research_invalid_transition_reason(str(error))
            if invalid_reason is None:
                raise
            rows.append(
                {
                    \"trading_strategy\": strategy,
                    \"strategy_params\": params_text,
                    \"management_strategy\": config.name,
                    \"validity\": \"INVALID_UNSUPPORTED_CERTIFIED_CORPORATE_TRANSITION\",
                    \"invalid_reason\": invalid_reason,
                    \"start\": start,
                    \"end\": end,
                    \"candles\": sum(start <= value <= end for value in data.dates),
                    \"initial_equity\": initial_cash,
                }
            )
            continue
        rows.append(
            {
                \"trading_strategy\": strategy,
                \"strategy_params\": params_text,
                \"management_strategy\": config.name,
                \"validity\": \"VALID\",
                \"invalid_reason\": \"\",
                \"start\": summary.start,
                \"end\": summary.end,
                \"candles\": summary.candles,
                \"trades\": summary.trades,
                \"exposure\": summary.exposure,
                \"avg_positions\": summary.avg_positions,
                \"initial_equity\": initial_cash,
                \"final_equity\": summary.final_equity,
                \"total_return\": summary.total_return,
                \"cagr\": summary.cagr,
                \"average_annual_return\": summary.average_annual_return,
                \"max_drawdown\": summary.max_drawdown,
                \"annual_volatility\": summary.annual_volatility,
                \"sharpe\": summary.sharpe,
                \"turnover\": summary.turnover,
            }
        )
"""
replace_once("scripts/backtest_strategy_management_combinations.py", old_strategy, new_strategy)
replace_once(
    "scripts/backtest_strategy_management_combinations.py",
    """    rows.sort(key=_ranking_key)
    for rank, row in enumerate(rows, start=1):
        row[\"rank\"] = rank

    config_by_name = {config.name: config for config in configs}
    annual_sections = _top_annual_sections(
        rows[: args.top],
""",
    """    rows.sort(key=_ranking_key)
    for rank, row in enumerate(rows, start=1):
        row[\"rank\"] = rank
    valid_rows = [row for row in rows if row.get(\"validity\") == \"VALID\"]
    if len(valid_rows) < args.top:
        raise ValueError(f\"Somente {len(valid_rows)} combinacoes validas; Top {args.top} indisponivel.\")

    config_by_name = {config.name: config for config in configs}
    annual_sections = _top_annual_sections(
        valid_rows[: args.top],
""",
)
replace_once(
    "scripts/backtest_strategy_management_combinations.py",
    """    _print_top(rows[: args.top])
    return 0
""",
    """    _print_top(valid_rows[: args.top])
    return 0
""",
)
replace_once(
    "scripts/backtest_strategy_management_combinations.py",
    """        \"management_strategy\",
        \"start\",
""",
    """        \"management_strategy\",
        \"validity\",
        \"invalid_reason\",
        \"start\",
""",
)
replace_once(
    "scripts/backtest_strategy_management_combinations.py",
    '        "ranking": "total_return_desc_then_cagr_desc_then_strategy_management_asc",\n',
    '        "ranking": "valid_only_then_total_return_desc_then_cagr_desc_then_strategy_management_asc",\n',
)
replace_once(
    "scripts/backtest_strategy_management_combinations.py",
    """            \"standard_market_open_used_for_integer_share_research_execution\",
        ],
""",
    """            \"standard_market_open_used_for_integer_share_research_execution\",
            \"certified_complex_corporate_transition_crossings_excluded_from_ranking\",
        ],
""",
)

# Merge ranks only valid simulations while preserving attempted cardinality.
replace_once(
    "scripts/merge_matrix_shards.py",
    """    top_rows = all_rows[: args.top]
""",
    """    valid_rows = [row for row in all_rows if str(row.get(\"validity\", \"VALID\")) == \"VALID\"]
    invalid_rows = [row for row in all_rows if str(row.get(\"validity\", \"VALID\")) != \"VALID\"]
    if len(valid_rows) < args.top:
        raise ValueError(f\"Somente {len(valid_rows)} combinacoes validas no merge; Top {args.top} indisponivel.\")
    manifest[\"valid_combination_count\"] = len(valid_rows)
    manifest[\"invalid_combination_count\"] = len(invalid_rows)
    top_rows = valid_rows[: args.top]
""",
)

# Audit invalid rows separately; absent performance metrics are never treated as returns.
audit = Path("scripts/audit_matrix_results.py")
text = audit.read_text(encoding="utf-8")
old = 'previous_sort_key: tuple[float, float, str, str] | None = None\n'
new = (
    'previous_sort_key: tuple[int, float, float, str, str] | None = None\n'
    'invalid_rows_are_explicit = True\n'
    'valid_rows_precede_invalid_rows = True\n'
    'seen_invalid = False\n'
    'valid_row_count = 0\n'
    'invalid_row_count = 0\n'
)
if old not in text:
    raise SystemExit("audit initialization anchor missing")
text = text.replace(old, new, 1)
old_loop = """            try:
                rank = int(row[\"rank\"])
                candles = int(row[\"candles\"])
                values = {field: float(row[field]) for field in float_fields}
            except (KeyError, TypeError, ValueError):
                ranks_are_sequential = False
                metrics_are_finite = False
                continue
            ranks_are_sequential &= rank == row_count
            metrics_are_finite &= all(math.isfinite(value) for value in values.values())
            returns_match_equity &= math.isclose(
                values[\"total_return\"],
                values[\"final_equity\"] / values[\"initial_equity\"] - 1.0,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            dates_and_candles_match &= (
                row[\"start\"] == manifest[\"start\"]
                and row[\"end\"] == manifest[\"end\"]
                and candles > 0
            )
            sort_key = (
                -values[\"total_return\"],
                -values[\"cagr\"],
                row[\"trading_strategy\"],
                row[\"management_strategy\"],
            )
            if previous_sort_key is not None:
                sorted_as_declared &= previous_sort_key <= sort_key
            previous_sort_key = sort_key
            pair = (row[\"trading_strategy\"], row[\"management_strategy\"])
            seen_pairs.add(pair)
            observed_strategies.add(pair[0])
            observed_managements.add(pair[1])
            ranked_pairs.append(pair)
"""
new_loop = """            try:
                rank = int(row[\"rank\"])
                candles = int(row[\"candles\"])
            except (KeyError, TypeError, ValueError):
                ranks_are_sequential = False
                dates_and_candles_match = False
                continue
            ranks_are_sequential &= rank == row_count
            pair = (row[\"trading_strategy\"], row[\"management_strategy\"])
            seen_pairs.add(pair)
            observed_strategies.add(pair[0])
            observed_managements.add(pair[1])
            validity = str(row.get(\"validity\", \"VALID\"))
            if validity != \"VALID\":
                invalid_row_count += 1
                seen_invalid = True
                invalid_rows_are_explicit &= (
                    validity == \"INVALID_UNSUPPORTED_CERTIFIED_CORPORATE_TRANSITION\"
                    and bool(str(row.get(\"invalid_reason\", \"\")).strip())
                )
                dates_and_candles_match &= (
                    row[\"start\"] == manifest[\"start\"]
                    and row[\"end\"] == manifest[\"end\"]
                    and candles > 0
                )
                sort_key = (1, 0.0, 0.0, pair[0], pair[1])
                if previous_sort_key is not None:
                    sorted_as_declared &= previous_sort_key <= sort_key
                previous_sort_key = sort_key
                continue
            valid_row_count += 1
            valid_rows_precede_invalid_rows &= not seen_invalid
            try:
                values = {field: float(row[field]) for field in float_fields}
            except (KeyError, TypeError, ValueError):
                metrics_are_finite = False
                continue
            metrics_are_finite &= all(math.isfinite(value) for value in values.values())
            returns_match_equity &= math.isclose(
                values[\"total_return\"],
                values[\"final_equity\"] / values[\"initial_equity\"] - 1.0,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            dates_and_candles_match &= (
                row[\"start\"] == manifest[\"start\"]
                and row[\"end\"] == manifest[\"end\"]
                and candles > 0
            )
            sort_key = (
                0,
                -values[\"total_return\"],
                -values[\"cagr\"],
                pair[0],
                pair[1],
            )
            if previous_sort_key is not None:
                sorted_as_declared &= previous_sort_key <= sort_key
            previous_sort_key = sort_key
            ranked_pairs.append(pair)
"""
if old_loop not in text:
    raise SystemExit("audit row-loop anchor missing")
text = text.replace(old_loop, new_loop, 1)
checks_anchor = '        "ranking_is_deterministic_total_return_cagr_names": sorted_as_declared,\n'
checks_new = """        \"ranking_is_deterministic_total_return_cagr_names\": sorted_as_declared,
        \"certified_complex_transition_invalid_rows_are_explicit\": invalid_rows_are_explicit,
        \"valid_rows_precede_invalid_rows\": valid_rows_precede_invalid_rows,
        \"ranking_contains_valid_rows\": valid_row_count > 0,
        \"manifest_declares_complex_transition_ranking_exclusion\": (
            \"certified_complex_corporate_transition_crossings_excluded_from_ranking\"
            in (manifest.get(\"limitations\") or [])
        ),
"""
if checks_anchor not in text:
    raise SystemExit("audit checks anchor missing")
text = text.replace(checks_anchor, checks_new, 1)
text = text.replace(
    '        "rows": row_count,\n',
    '        "rows": row_count,\n        "valid_rows": valid_row_count,\n        "invalid_rows": invalid_row_count,\n',
    1,
)
audit.write_text(text, encoding="utf-8")

# Regression coverage.
Path("tests/test_matrix_complex_transition_invalid.py").write_text(
    """from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts import backtest_strategy_management_combinations as matrix
from scripts import research_portfolio_allocation as research


class ComplexTransitionInvalidationTests(unittest.TestCase):
    def test_gndi3_certified_complex_transition_is_classified(self) -> None:
        reason = research._research_invalid_transition_reason(
            \"2022-02-14: abertura fresca obrigatoria ausente para GNDI3\"
        )
        self.assertIsNotNone(reason)
        self.assertIn(\"GNDI3->HAPV3\", reason)
        self.assertIn(\"CERTIFIED_COMPLEX_TRANSITION\", reason)

    def test_unrelated_missing_price_remains_fatal(self) -> None:
        self.assertIsNone(
            research._research_invalid_transition_reason(
                \"2022-02-14: abertura fresca obrigatoria ausente para PETR4\"
            )
        )

    def test_strategy_rows_marks_only_certified_complex_transition_invalid(self) -> None:
        class Data:
            dates = [\"2022-02-11\", \"2022-02-14\"]
        config = type(\"Config\", (), {\"name\": \"management\"})()
        with patch.object(
            matrix,
            \"run_portfolio\",
            side_effect=ValueError(\"2022-02-14: abertura fresca obrigatoria ausente para GNDI3\"),
        ):
            rows = matrix._strategy_rows(
                Data(), [config], \"strategy\", {}, {},
                universe_membership={}, start=\"2022-02-11\", end=\"2022-02-14\",
                initial_cash=1000.0, cost_bps=3.2, slippage_bps=10.0, lot_size=1,
            )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][\"validity\"], \"INVALID_UNSUPPORTED_CERTIFIED_CORPORATE_TRANSITION\")

    def test_strategy_rows_does_not_swallow_ordinary_value_error(self) -> None:
        class Data:
            dates = [\"2022-02-11\", \"2022-02-14\"]
        config = type(\"Config\", (), {\"name\": \"management\"})()
        with patch.object(matrix, \"run_portfolio\", side_effect=ValueError(\"ordinary bug\")):
            with self.assertRaisesRegex(ValueError, \"ordinary bug\"):
                matrix._strategy_rows(
                    Data(), [config], \"strategy\", {}, {},
                    universe_membership={}, start=\"2022-02-11\", end=\"2022-02-14\",
                    initial_cash=1000.0, cost_bps=3.2, slippage_bps=10.0, lot_size=1,
                )


if __name__ == \"__main__\":
    unittest.main()
""",
    encoding="utf-8",
)
