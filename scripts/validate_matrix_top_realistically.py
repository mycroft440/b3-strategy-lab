from __future__ import annotations

import argparse
import csv
import gzip
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_MATRIX = Path(
    "reports/strategy_management_combinations_40_adjusted_no_dividends_1d.csv.gz"
)
DEFAULT_OUTPUT_DIR = Path("reports/realistic_gate")


def _open_rows(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", newline="", encoding="utf-8")
    return path.open("r", newline="", encoding="utf-8")


def _top_rows(path: Path, top: int) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Matriz nao encontrada: {path}")
    with _open_rows(path) as file:
        rows = list(csv.DictReader(file))
    if not rows:
        raise ValueError(f"Matriz vazia: {path}")

    def ranking(row: dict[str, str]) -> tuple[int, float, float]:
        rank_text = str(row.get("rank", "")).strip()
        rank = int(rank_text) if rank_text.isdigit() else 10**9
        total_return = float(row.get("total_return", 0.0) or 0.0)
        cagr = float(row.get("cagr", 0.0) or 0.0)
        return (rank, -total_return, -cagr)

    rows.sort(key=ranking)
    selected: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (
            str(row.get("trading_strategy", "")).strip(),
            str(row.get("management_strategy", "")).strip(),
        )
        if not all(key) or key in seen:
            continue
        seen.add(key)
        selected.append(row)
        if len(selected) >= top:
            break
    return selected


def _run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def _safe_name(value: str) -> str:
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    return "".join(char if char in allowed else "_" for char in value)[:120]


def _write_markdown(rows: list[dict[str, object]], path: Path) -> None:
    lines = [
        "# Gate realista dos vencedores da matriz",
        "",
        "A matriz rapida e usada apenas para triagem. A classificacao abaixo vem da ",
        "reexecucao dos mesmos pares estrategia/gerenciamento no motor economico, ",
        "com universo point-in-time, proventos, taxas, tributacao e slippage sensivel ",
        "a participacao no volume. Leia o campo `validity`: ele preserva qualquer ",
        "limitacao ainda existente nos insumos.",
        "",
        "| rank rapido | estrategia | gerenciamento | CAGR rapido | CAGR realista | retorno realista | MDD realista | validade |",
        "|---:|---|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| {fast_rank} | `{strategy}` | `{management}` | {fast_cagr:.2%} | "
            "{realistic_cagr:.2%} | {realistic_total_return:.2%} | "
            "{realistic_max_drawdown:.2%} | `{validity}` |".format(**row)
        )
    lines.append("")
    lines.append(
        "**Regra:** nenhum CAGR da matriz rapida deve ser apresentado como retorno "
        "economico final sem este gate."
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reexecuta o Top N da matriz de screening no motor realista e compara "
            "o resultado rapido com o resultado economicamente modelado."
        )
    )
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--initial-cash", type=float, default=1_000.0)
    parser.add_argument("--start", default="2018-01-02")
    parser.add_argument("--end")
    parser.add_argument("--base-slippage-bps", type=float, default=10.0)
    parser.add_argument("--participation-bps-at-1pct", type=float, default=5.0)
    parser.add_argument("--max-slippage-bps", type=float, default=100.0)
    parser.add_argument(
        "--skip-input-audit",
        action="store_true",
        help="Somente para diagnostico; por padrao os insumos realistas sao auditados antes.",
    )
    args = parser.parse_args(argv)

    if args.top <= 0:
        parser.error("--top precisa ser maior que zero.")
    if args.initial_cash <= 0:
        parser.error("--initial-cash precisa ser maior que zero.")
    if min(args.base_slippage_bps, args.participation_bps_at_1pct, args.max_slippage_bps) < 0:
        parser.error("Parametros de slippage nao podem ser negativos.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    if not args.skip_input_audit:
        _run([sys.executable, "scripts/audit_realistic_backtest_inputs.py"])

    selected = _top_rows(args.matrix, args.top)
    comparison: list[dict[str, object]] = []
    for index, row in enumerate(selected, start=1):
        strategy = str(row["trading_strategy"])
        management = str(row["management_strategy"])
        prefix = f"{index:02d}_{_safe_name(strategy)}__{_safe_name(management)}"
        summary_path = args.output_dir / f"{prefix}.json"
        curve_path = args.output_dir / f"{prefix}_curve.csv"
        trades_path = args.output_dir / f"{prefix}_trades.csv"
        cash_path = args.output_dir / f"{prefix}_cash.csv"
        tax_path = args.output_dir / f"{prefix}_tax.csv"

        command = [
            sys.executable,
            "scripts/backtest_strategy_management_realistic.py",
            "--strategy",
            strategy,
            "--management",
            management,
            "--start",
            args.start,
            "--initial-cash",
            str(args.initial_cash),
            "--base-slippage-bps",
            str(args.base_slippage_bps),
            "--participation-bps-at-1pct",
            str(args.participation_bps_at_1pct),
            "--max-slippage-bps",
            str(args.max_slippage_bps),
            "--economic-gap-adjustment",
            "--output",
            str(summary_path),
            "--curve-output",
            str(curve_path),
            "--trades-output",
            str(trades_path),
            "--cash-ledger-output",
            str(cash_path),
            "--tax-output",
            str(tax_path),
        ]
        if args.end:
            command.extend(["--end", args.end])
        _run(command)

        realistic = json.loads(summary_path.read_text(encoding="utf-8"))
        comparison.append(
            {
                "fast_rank": int(row.get("rank", index) or index),
                "strategy": strategy,
                "management": management,
                "fast_total_return": float(row.get("total_return", 0.0) or 0.0),
                "fast_cagr": float(row.get("cagr", 0.0) or 0.0),
                "realistic_total_return": float(realistic["total_return"]),
                "realistic_cagr": float(realistic["cagr"]),
                "realistic_max_drawdown": float(realistic["max_drawdown"]),
                "realistic_sharpe": float(realistic["sharpe"]),
                "fees_paid": float(realistic["fees_paid"]),
                "ordinary_income_tax_paid": float(realistic["ordinary_income_tax_paid"]),
                "distribution_tax_paid": float(realistic["distribution_tax_paid"]),
                "distributions_net": float(realistic["distributions_net"]),
                "validity": str(realistic["validity"]),
                "summary": str(summary_path),
            }
        )

    comparison.sort(
        key=lambda item: (
            -float(item["realistic_cagr"]),
            -float(item["realistic_total_return"]),
            int(item["fast_rank"]),
        )
    )
    json_path = args.output_dir / "comparison.json"
    md_path = args.output_dir / "TOP_REALISTIC.md"
    json_path.write_text(
        json.dumps(comparison, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _write_markdown(comparison, md_path)
    print(f"Gate realista concluido: {json_path}")
    print(f"Ranking realista: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
