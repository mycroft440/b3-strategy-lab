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
REQUIRED_EXECUTION_FIELDS = (
    "signal",
    "execution",
    "cost_bps_per_side",
    "slippage_bps_per_side",
    "lot_size",
    "dividends_jcp",
    "income_tax",
)


def audit_freeze(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    strategy = payload.get("strategy") or {}
    management = payload.get("management") or {}
    execution = payload.get("execution_assumptions") or {}
    name = str(strategy.get("name") or "")
    params = strategy.get("parameters") or {}
    signal_mode = str(management.get("signal_mode") or "adjusted")

    registered = set(portfolio_strategies())
    runtime_params = strategy_parameters(name) if name in registered else None
    configs = {config.name: config for config in _configs(signal_mode, "all")}
    management_name = str(management.get("name") or "")
    runtime_management = configs.get(management_name)

    checks: dict[str, bool] = {
        "strategy_exists": name in registered,
        "strategy_parameters_match_runtime_defaults": runtime_params == params,
        "management_exists": runtime_management is not None,
        "no_reoptimization_after_freeze": payload.get("no_reoptimization_after_freeze") is True,
        "execution_fields_complete": all(field in execution for field in REQUIRED_EXECUTION_FIELDS),
        "execution_is_next_session_open": (
            execution.get("signal") == "fechamento confirmado da sessao de decisao"
            and execution.get("execution") == "abertura da sessao seguinte de rebalanceamento"
        ),
    }

    management_mismatches: dict[str, dict[str, object]] = {}
    if runtime_management is not None:
        for field in MANAGEMENT_FIELDS:
            expected = management.get(field)
            actual = getattr(runtime_management, field)
            if actual != expected:
                management_mismatches[field] = {"expected": expected, "actual": actual}
    checks["management_fields_match_runtime"] = not management_mismatches

    numeric_execution_valid = True
    for field in ("cost_bps_per_side", "slippage_bps_per_side"):
        try:
            value = float(execution[field])
            numeric_execution_valid &= math.isfinite(value) and value >= 0
        except (KeyError, TypeError, ValueError):
            numeric_execution_valid = False
    try:
        numeric_execution_valid &= int(execution["lot_size"]) >= 0
    except (KeyError, TypeError, ValueError):
        numeric_execution_valid = False
    checks["execution_numeric_assumptions_are_valid"] = numeric_execution_valid

    return {
        "path": str(path),
        "strategy": name,
        "strategy_parameters": params,
        "runtime_strategy_parameters": runtime_params,
        "management": management_name,
        "management_mismatches": management_mismatches,
        "execution_assumptions": execution,
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
