from __future__ import annotations

import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from b3_strategy_lab.strategies import strategies_by_family, strategy_parameters


DEFAULT_REPORTS_DIR = Path("reports")


def main(argv: list[str] | None = None) -> int:
    reports_dir = Path(argv[0]) if argv else DEFAULT_REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)
    rows = strategy_rows()
    write_strategy_csv(rows, reports_dir / "strategy_inventory.csv")
    write_strategy_markdown(rows, reports_dir / "strategy_inventory.md")
    print(f"Inventario de estrategias CSV: {reports_dir / 'strategy_inventory.csv'}")
    print(f"Inventario de estrategias Markdown: {reports_dir / 'strategy_inventory.md'}")
    return 0


def strategy_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for family, strategies in strategies_by_family().items():
        for info in strategies:
            params = strategy_parameters(info.name)
            rows.append(
                {
                    "family": family,
                    "strategy": info.name,
                    "sweepable": "sim" if info.sweepable else "nao",
                    "default_params": ";".join(f"{key}={value}" for key, value in params.items()) if params else "",
                    "description": info.description,
                }
            )
    return rows


def write_strategy_csv(rows: list[dict[str, str]], path: Path) -> None:
    fields = ["family", "strategy", "sweepable", "default_params", "description"]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fields} for row in rows])


def write_strategy_markdown(rows: list[dict[str, str]], path: Path) -> None:
    lines = [
        "# Inventario de estrategias",
        "",
        "Catalogo gerado a partir de `b3_strategy_lab/strategies.py`.",
        "",
    ]
    for family in sorted({row["family"] for row in rows}):
        lines.append(f"## {family}")
        lines.append("")
        lines.append("| Estrategia | Sweep | Parametros padrao | Descricao |")
        lines.append("|---|---|---|---|")
        for row in [item for item in rows if item["family"] == family]:
            lines.append(
                f"| {row['strategy']} | {row['sweepable']} | `{row['default_params'] or '-'}` | {row['description']} |"
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
