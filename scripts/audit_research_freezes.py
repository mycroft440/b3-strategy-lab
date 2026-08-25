from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from b3_strategy_lab.strategies import portfolio_strategies, strategy_parameters  # noqa: E402
from scripts.research_portfolio_allocation import _configs  # noqa: E402


DEFAULT_FREEZE_DIR = Path("data/research_freezes")
DEFAULT_OUTPUT = Path("reports/research_freeze_audit.json")
MANAGEMENT_FIELDS = (
    "lookback",
    "skip",
    "trend_window",
    "vol_window",
    "top_n",
    "rebalance",
    "score",
    "weighting",
    "absolute_momentum",
    "max_weight",
    "signal_mode",
)
RETROSPECTIVE_EXECUTION_FIELDS = (
    "signal",
    "execution",
    "cost_bps_per_side",
    "slippage_bps_per_side",
    "lot_size",
    "dividends_jcp",
    "income_tax",
)
REALISTIC_EXECUTION_FIELDS = (
    "decision",
    "fill",
    "standard_market",
    "fractional_market",
    "standard_lot",
    "base_slippage_bps",
    "participation_bps_at_1pct",
    "max_slippage_bps",
    "max_participation_rate",
)
REALISTIC_ACCOUNTING_FIELDS = (
    "initial_cash_brl",
    "integer_shares",
    "cash_distributions",
    "monthly_tax_ledger",
    "fresh_close_required",
    "stale_price_fallback",
)


def _nonnegative_finite(mapping: dict[str, object], fields: tuple[str, ...]) -> bool:
    for field in fields:
        try:
            value = float(mapping[field])
        except (KeyError, TypeError, ValueError):
            return False
        if not math.isfinite(value) or value < 0:
            return False
    return True


def audit_freeze(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    strategy = payload.get("strategy") or {}
    management = payload.get("management") or {}
    name = str(strategy.get("name") or "")
    params = strategy.get("parameters") or {}
    signal_mode = str(management.get("signal_mode") or "adjusted")

    registered = set(portfolio_strategies())
    runtime_params = strategy_parameters(name) if name in registered else None
    configs = {config.name: config for config in _configs(signal_mode, "all")}
    management_name = str(management.get("name") or "")
    runtime_management = configs.get(management_name)

    checks: dict[str, bool] = {
        "schema_version_supported": payload.get("schema_version") == 1,
        "strategy_exists": name in registered,
        "strategy_parameters_match_runtime_defaults": runtime_params == params,
        "management_exists": runtime_management is not None,
        "no_reoptimization_after_freeze": payload.get("no_reoptimization_after_freeze") is True,
    }

    management_mismatches: dict[str, dict[str, object]] = {}
    if runtime_management is not None:
        for field in MANAGEMENT_FIELDS:
            if field not in management:
                continue
            expected = management[field]
            actual = getattr(runtime_management, field)
            if actual != expected:
                management_mismatches[field] = {"expected": expected, "actual": actual}
    checks["declared_management_fields_match_runtime"] = not management_mismatches

    contract_type = "unknown"
    execution_details: dict[str, object] = {}
    if "execution_assumptions" in payload:
        contract_type = "retrospective_price_only"
        execution = payload.get("execution_assumptions") or {}
        execution_details = execution
        checks["execution_fields_complete"] = all(
            field in execution for field in RETROSPECTIVE_EXECUTION_FIELDS
        )
        checks["execution_is_next_session_open"] = (
            execution.get("signal") == "fechamento confirmado da sessao de decisao"
            and execution.get("execution") == "abertura da sessao seguinte de rebalanceamento"
        )
        checks["execution_numeric_assumptions_are_valid"] = (
            _nonnegative_finite(execution, ("cost_bps_per_side", "slippage_bps_per_side"))
            and isinstance(execution.get("lot_size"), int)
            and int(execution["lot_size"]) >= 0
        )
    elif "execution" in payload and "accounting" in payload:
        contract_type = "realistic_point_in_time"
        execution = payload.get("execution") or {}
        accounting = payload.get("accounting") or {}
        point_in_time = payload.get("point_in_time_universe") or {}
        execution_details = execution
        checks["execution_fields_complete"] = all(
            field in execution for field in REALISTIC_EXECUTION_FIELDS
        )
        checks["accounting_fields_complete"] = all(
            field in accounting for field in REALISTIC_ACCOUNTING_FIELDS
        )
        checks["execution_is_next_session_open"] = (
            execution.get("decision") == "confirmed close at rebalance decision session"
            and execution.get("fill") == "next rebalance session opening"
        )
        checks["execution_market_contract_is_explicit"] = (
            execution.get("standard_market") == "010"
            and execution.get("fractional_market") == "020"
            and int(execution.get("standard_lot", 0)) == 100
        )
        checks["execution_numeric_assumptions_are_valid"] = _nonnegative_finite(
            execution,
            (
                "base_slippage_bps",
                "participation_bps_at_1pct",
                "max_slippage_bps",
                "max_participation_rate",
            ),
        )
        checks["point_in_time_universe_contract_is_present"] = bool(point_in_time)
        checks["accounting_fails_closed_on_stale_prices"] = (
            accounting.get("fresh_close_required") is True
            and accounting.get("stale_price_fallback") is False
        )
    else:
        checks["recognized_execution_contract"] = False

    return {
        "path": str(path),
        "contract_type": contract_type,
        "strategy": name,
        "strategy_parameters": params,
        "runtime_strategy_parameters": runtime_params,
        "management": management_name,
        "management_mismatches": management_mismatches,
        "execution_contract": execution_details,
        "checks": checks,
        "ready": all(checks.values()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audita hipoteses de pesquisa congeladas contra o catalogo executavel atual."
    )
    parser.add_argument("--freeze-dir", type=Path, default=DEFAULT_FREEZE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    freeze_paths = sorted(args.freeze_dir.glob("*.json"))
    rows = [audit_freeze(path) for path in freeze_paths]
    checks = {
        "at_least_one_freeze_exists": bool(rows),
        "all_freezes_match_runtime_contracts": bool(rows) and all(row["ready"] for row in rows),
    }
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "freeze_dir": str(args.freeze_dir),
        "freeze_count": len(rows),
        "checks": checks,
        "freezes": rows,
        "ready": all(checks.values()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    print(f"{args.output}: ready={payload['ready']}, freezes={len(rows)}")
    return 0 if payload["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
