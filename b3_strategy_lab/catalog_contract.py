from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from b3_strategy_lab.strategies import portfolio_strategies, strategy_parameters


CATALOG_SCHEMA_VERSION = 1
DEFAULT_CATALOG_CONTRACT = Path(
    "data/research_catalogs/portfolio_adjusted_all.json"
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def runtime_catalog_contract(
    *,
    signal_mode: str = "adjusted",
    config_set: str = "all",
) -> dict[str, Any]:
    """Return a deterministic, content-addressed strategy/configuration catalog."""

    # Import lazily to avoid making the core strategy registry depend on a CLI module.
    from scripts.research_portfolio_allocation import _configs

    strategies = [
        {
            "name": name,
            "parameters": strategy_parameters(name),
        }
        for name in sorted(portfolio_strategies())
    ]
    managements = [asdict(config) for config in _configs(signal_mode, config_set)]
    managements.sort(key=lambda item: str(item["name"]))
    content = {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "signal_mode": signal_mode,
        "config_set": config_set,
        "strategies": strategies,
        "managements": managements,
    }
    digest = hashlib.sha256(_canonical_json(content).encode("utf-8")).hexdigest()
    return {
        **content,
        "strategy_count": len(strategies),
        "management_count": len(managements),
        "candidate_count": len(strategies) * len(managements),
        "catalog_sha256": digest,
    }


def validate_catalog_contract(
    path: Path | str = DEFAULT_CATALOG_CONTRACT,
    *,
    signal_mode: str = "adjusted",
    config_set: str = "all",
) -> dict[str, Any]:
    """Fail closed when the checked-in declaration differs from runtime code."""

    source = Path(path)
    declared = json.loads(source.read_text(encoding="utf-8"))
    runtime = runtime_catalog_contract(signal_mode=signal_mode, config_set=config_set)
    binding_fields = (
        "schema_version",
        "signal_mode",
        "config_set",
        "strategy_count",
        "management_count",
        "candidate_count",
        "catalog_sha256",
    )
    expected_binding = {field: runtime[field] for field in binding_fields}
    if declared != expected_binding:
        declared_hash = str(declared.get("catalog_sha256", "missing"))
        raise ValueError(
            "Runtime research catalog differs from its checked-in contract: "
            f"declared={declared_hash}, runtime={runtime['catalog_sha256']}. "
            "Review the strategy/configuration change and regenerate the contract."
        )
    return runtime


def write_catalog_contract(
    path: Path | str = DEFAULT_CATALOG_CONTRACT,
    *,
    signal_mode: str = "adjusted",
    config_set: str = "all",
) -> dict[str, Any]:
    payload = runtime_catalog_contract(signal_mode=signal_mode, config_set=config_set)
    binding_fields = (
        "schema_version",
        "signal_mode",
        "config_set",
        "strategy_count",
        "management_count",
        "candidate_count",
        "catalog_sha256",
    )
    binding = {field: payload[field] for field in binding_fields}
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(binding, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def write_runtime_catalog(path: Path | str, payload: dict[str, Any]) -> Path:
    """Persist the complete ordered names, parameters and configurations used."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
