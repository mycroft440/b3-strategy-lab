from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from b3_strategy_lab.strategies import portfolio_strategies
from scripts.backtest_strategy_management_combinations import _ranking_key, _write_results


DEFAULT_INPUT_DIR = Path("reports/shards")
DEFAULT_OUTPUT = Path(
    "reports/strategy_management_combinations_40_adjusted_no_dividends_1d.csv.gz"
)


def _report_base(path: Path) -> Path:
    if path.suffixes[-2:] == [".csv", ".gz"]:
        return path.with_suffix("").with_suffix("")
    return path.with_suffix("")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_rows(path: Path) -> list[dict[str, object]]:
    opener = gzip.open if path.suffix == ".gz" else open
    kwargs = {"mode": "rt", "encoding": "utf-8", "newline": ""}
    with opener(path, **kwargs) as source:
        return [dict(row) for row in csv.DictReader(source)]


def _read_annual_sections(path: Path) -> dict[tuple[str, str], str]:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"^## \d+\. ([a-z0-9_]+) \+ ([a-z0-9_]+)\n(.*?)(?=^## \d+\.|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    sections: dict[tuple[str, str], str] = {}
    for match in pattern.finditer(text):
        sections[(match.group(1), match.group(2))] = match.group(3).strip()
    return sections


def _validate_manifests(manifests: list[dict[str, object]]) -> None:
    if not manifests:
        raise ValueError("Nenhum manifesto de shard encontrado.")
    reference = manifests[0]
    keys = (
        "git_commit",
        "git_dirty",
        "git_dirty_scope",
        "source_sha256",
        "universe",
        "market_data_paths",
        "universe_selection_policy",
        "datasets",
        "tickers",
        "management_count",
        "management_configs",
        "interval",
        "start",
        "end",
        "signal_mode",
        "signal_history_start",
        "management_history_start",
        "allow_unverified_data",
        "execution_price_mode",
        "mark_price_mode",
        "dividends_jcp",
        "initial_cash",
        "cost_bps",
        "slippage_bps",
        "lot_size",
        "ranking",
        "signal_execution_policy",
        "signal_calendar_policy",
        "initial_entry_policy",
        "execution_missing_price_policy",
        "buy_allocation_policy",
        "evaluation_scope",
        "train_ratio_applied",
        "result_classification",
        "real_money_claim_allowed",
        "limitations",
        "final_valuation",
    )
    if reference.get("git_dirty") is not False:
        raise ValueError("Shard 0 foi calculado com fontes ou dados versionados modificados.")
    for index, manifest in enumerate(manifests[1:], start=1):
        if manifest.get("git_dirty") is not False:
            raise ValueError(
                f"Shard {index} foi calculado com fontes ou dados versionados modificados."
            )
        for key in keys:
            if manifest.get(key) != reference.get(key):
                raise ValueError(f"Shard {index}: campo incompatível no manifesto: {key}.")


def _build_manifest(
    manifests: list[dict[str, object]],
    *,
    strategies: list[str],
    combinations: int,
) -> dict[str, object]:
    reference = dict(manifests[0])
    source_hashes = dict(reference.get("source_sha256", {}))
    source_hashes["scripts/merge_matrix_shards.py"] = _sha256(Path(__file__))
    reference.update(
        {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_sha256": source_hashes,
            "strategy_count": len(strategies),
            "strategies": strategies,
            "combinations": combinations,
            "catalog_complete": set(strategies) == set(portfolio_strategies()),
            "sharded_execution": True,
            "shard_count": len(manifests),
            "workers_per_shard": manifests[0].get("workers"),
            "elapsed_seconds": max(
                float(manifest.get("elapsed_seconds", 0.0)) for manifest in manifests
            ),
            "shard_elapsed_seconds": [
                float(manifest.get("elapsed_seconds", 0.0)) for manifest in manifests
            ],
        }
    )
    return reference


def _write_annual_report(
    top_rows: list[dict[str, object]],
    sections: dict[tuple[str, str], str],
    output: Path,
) -> None:
    lines = ["# Resultados anuais das melhores combinacoes", ""]
    for rank, row in enumerate(top_rows, start=1):
        pair = (str(row["trading_strategy"]), str(row["management_strategy"]))
        body = sections.get(pair)
        if body is None:
            raise ValueError(
                "A combinacao global Top N nao foi encontrada nos relatórios anuais "
                f"dos shards: {pair[0]} + {pair[1]}."
            )
        lines.extend([f"## {rank}. {pair[0]} + {pair[1]}", "", body, ""])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_summary(
    top_rows: list[dict[str, object]],
    *,
    manifest: dict[str, object],
    markdown_output: Path,
    json_output: Path,
) -> None:
    lines = [
        "# TOP 10 — B3 Strategy Lab",
        "",
        f"Período: **{manifest['start']} a {manifest['end']}**  ",
        f"Capital inicial: **R$ {float(manifest['initial_cash']):,.2f}**  ",
        f"Combinações avaliadas: **{int(manifest['combinations']):,}**  ",
        f"Custos: **{float(manifest['cost_bps']):g} bps** | Slippage: **{float(manifest['slippage_bps']):g} bps**",
        "",
        "> Pesquisa retrospectiva price-only: não inclui proventos nem impostos e não representa retorno real.",
        "",
        "| # | Estratégia | Gerenciamento | Patrimônio final | Retorno total | CAGR | Média anual | Drawdown máx. | Trades | Sharpe |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    payload_rows: list[dict[str, object]] = []
    for row in top_rows:
        rank = int(row["rank"])
        final_equity = float(row["final_equity"])
        total_return = float(row["total_return"])
        cagr = float(row["cagr"])
        average = float(row["average_annual_return"])
        max_drawdown = float(row["max_drawdown"])
        trades = int(float(row["trades"]))
        sharpe = float(row["sharpe"])
        lines.append(
            f"| {rank} | {row['trading_strategy']} | {row['management_strategy']} | "
            f"R$ {final_equity:,.2f} | {total_return:.2%} | {cagr:.2%} | "
            f"{average:.2%} | {max_drawdown:.2%} | {trades} | {sharpe:.3f} |"
        )
        payload_rows.append(
            {
                "rank": rank,
                "trading_strategy": row["trading_strategy"],
                "management_strategy": row["management_strategy"],
                "initial_equity": float(row["initial_equity"]),
                "final_equity": final_equity,
                "total_return": total_return,
                "cagr": cagr,
                "average_annual_return": average,
                "max_drawdown": max_drawdown,
                "trades": trades,
                "sharpe": sharpe,
            }
        )
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_output.write_text(
        json.dumps(
            {
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "period": {"start": manifest["start"], "end": manifest["end"]},
                "initial_cash": manifest["initial_cash"],
                "combinations": manifest["combinations"],
                "cost_bps": manifest["cost_bps"],
                "slippage_bps": manifest["slippage_bps"],
                "result_classification": manifest["result_classification"],
                "real_money_claim_allowed": manifest["real_money_claim_allowed"],
                "limitations": manifest["limitations"],
                "top_10": payload_rows,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Junta shards da matriz, reordena globalmente e gera o Top N final."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--summary-output", type=Path, default=Path("reports/TOP_10.md"))
    parser.add_argument("--json-output", type=Path, default=Path("reports/TOP_10.json"))
    args = parser.parse_args(argv)
    if args.top <= 0:
        parser.error("--top precisa ser maior que zero.")

    result_paths = sorted(args.input_dir.glob("shard_*.csv.gz"))
    if not result_paths:
        raise FileNotFoundError(f"Nenhum shard encontrado em {args.input_dir}.")

    manifests: list[dict[str, object]] = []
    all_rows: list[dict[str, object]] = []
    annual_sections: dict[tuple[str, str], str] = {}
    seen_pairs: set[tuple[str, str]] = set()
    shard_strategies: set[str] = set()

    for result_path in result_paths:
        base = _report_base(result_path)
        manifest_path = base.with_suffix(".manifest.json")
        annual_path = base.with_name(f"{base.name}_top{args.top}_annual.md")
        if not manifest_path.exists() or not annual_path.exists():
            raise FileNotFoundError(f"Artefatos incompletos para {result_path.name}.")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifests.append(manifest)
        shard_strategies.update(str(value) for value in manifest["strategies"])
        annual_sections.update(_read_annual_sections(annual_path))
        for row in _read_rows(result_path):
            pair = (str(row["trading_strategy"]), str(row["management_strategy"]))
            if pair in seen_pairs:
                raise ValueError(f"Combinação duplicada entre shards: {pair}.")
            seen_pairs.add(pair)
            all_rows.append(row)

    _validate_manifests(manifests)
    catalog = list(portfolio_strategies())
    expected_strategies = [strategy for strategy in catalog if strategy in shard_strategies]
    if set(expected_strategies) != shard_strategies:
        unknown = sorted(shard_strategies - set(catalog))
        raise ValueError(f"Estratégias fora do catálogo: {unknown}.")
    if set(expected_strategies) != set(catalog):
        missing = sorted(set(catalog) - set(expected_strategies))
        raise ValueError(f"Shards não cobrem o catálogo completo. Faltando: {missing}.")

    all_rows.sort(key=_ranking_key)
    for rank, row in enumerate(all_rows, start=1):
        row["rank"] = rank

    management_count = int(manifests[0]["management_count"])
    expected_combinations = len(expected_strategies) * management_count
    if len(all_rows) != expected_combinations:
        raise ValueError(
            f"Cardinalidade global inválida: {len(all_rows)} != {expected_combinations}."
        )

    _write_results(all_rows, args.output)
    report_base = _report_base(args.output)
    manifest = _build_manifest(
        manifests,
        strategies=expected_strategies,
        combinations=len(all_rows),
    )
    manifest_path = report_base.with_suffix(".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    top_rows = all_rows[: args.top]
    annual_output = report_base.with_name(f"{report_base.name}_top{args.top}_annual.md")
    _write_annual_report(top_rows, annual_sections, annual_output)
    _write_summary(
        top_rows,
        manifest=manifest,
        markdown_output=args.summary_output,
        json_output=args.json_output,
    )
    print(f"Matriz global: {args.output} ({len(all_rows)} combinações)")
    print(f"Manifesto global: {manifest_path}")
    print(f"Top {args.top}: {args.summary_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
