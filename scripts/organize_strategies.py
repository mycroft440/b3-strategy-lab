from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from b3_strategy_lab.strategies import strategies_by_family, strategy_parameters
from scripts.research_portfolio_allocation import PortfolioConfig, _configs


DEFAULT_REPORTS_DIR = Path("reports")
DEFAULT_STRATEGIES_DIR = Path("estrategias_de_trading_que_superam_buy_and_hold")


def main(argv: list[str] | None = None) -> int:
    reports_dir = Path(argv[0]) if argv else DEFAULT_REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)
    rows = strategy_rows()
    write_strategy_csv(rows, reports_dir / "strategy_inventory.csv")
    write_strategy_markdown(rows, reports_dir / "strategy_inventory.md")
    write_trading_strategy_folders(rows, DEFAULT_STRATEGIES_DIR / "estrategias_de_compra")
    managements = _configs("raw", "all")
    write_management_strategy_folders(
        managements,
        DEFAULT_STRATEGIES_DIR / "estrategias_de_gerenciamento",
    )
    write_management_csv(
        managements,
        reports_dir / "portfolio_management_inventory.csv",
    )
    print(f"Inventario de estrategias CSV: {reports_dir / 'strategy_inventory.csv'}")
    print(f"Inventario de estrategias Markdown: {reports_dir / 'strategy_inventory.md'}")
    print(f"Estrategias compradas documentadas: {len(rows) - 1}")
    print(f"Gerenciamentos documentados: {len(managements)}")
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
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
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


def write_trading_strategy_folders(rows: list[dict[str, str]], root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    overview = [
        "# Estrategias de compra",
        "",
        "Catalogo long-only usado pelo executor de combinacoes.",
        "",
        f"Total testavel: {sum(row['sweepable'] == 'sim' for row in rows)} estrategias.",
        "",
        "Convencoes comuns:",
        "",
        "- o sinal usa somente informacoes disponiveis no fechamento;",
        "- a ordem e executada na abertura do candle seguinte;",
        "- sinal 1 significa elegivel para compra e sinal 0 significa fora da carteira;",
        "- dividendos/JCP, custos e slippage ficam excluidos por padrao;",
        "- `buy_and_hold` e benchmark e nao integra as 156 estrategias testaveis.",
        "",
    ]
    _atomic_write(root / "README.md", "\n".join(overview))

    for row in rows:
        if row["strategy"] == "buy_and_hold":
            continue
        strategy_dir = root / row["strategy"]
        strategy_dir.mkdir(parents=True, exist_ok=True)
        content = [
            f"# {row['strategy']}",
            "",
            f"Familia: {row['family']}",
            "",
            "## Como funciona",
            "",
            row["description"],
            "",
            "## Configuracao",
            "",
            "```text",
            row["default_params"] or "sem parametros",
            "```",
            "",
            "## Entrada e saida",
            "",
            "A funcao produz um sinal binario long-only. A condicao descrita acima ativa a "
            "elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. "
            "Estrategias com estado mantem a posicao ate sua regra explicita de saida.",
            "",
            "O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.",
            "",
        ]
        _atomic_write(strategy_dir / "README.md", "\n".join(content))


def write_management_strategy_folders(
    managements: list[PortfolioConfig],
    root: Path,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    overview = [
        "# Estrategias de gerenciamento de carteira",
        "",
        f"Total: {len(managements)} configuracoes.",
        "",
        "Cada gerenciamento recebe somente os ativos elegiveis pela estrategia de compra, "
        "classifica-os, define pesos e rebalanceia na abertura seguinte.",
        "",
    ]
    _atomic_write(root / "README.md", "\n".join(overview))

    for config in managements:
        strategy_dir = root / config.name
        strategy_dir.mkdir(parents=True, exist_ok=True)
        content = [
            f"# {config.name}",
            "",
            "## Como funciona",
            "",
            f"- Selecao: `{config.score}`; conserva no maximo {config.top_n} ativo(s).",
            f"- Janela principal: {config.lookback} candles; defasagem: {config.skip}.",
            f"- Filtro de tendencia: {config.trend_window} candles.",
            f"- Volatilidade: {config.vol_window} candles.",
            f"- Ponderacao: `{config.weighting}`; peso maximo: {config.max_weight:.2%}.",
            f"- Rebalanceamento: `{config.rebalance}`.",
            f"- Momentum absoluto obrigatorio: {'sim' if config.absolute_momentum else 'nao'}.",
            f"- Volatilidade-alvo: {config.target_vol:.2%}.",
            f"- Precos para sinais: `{config.signal_mode}`.",
            "",
            "## Configuracao integral",
            "",
            "```json",
            json.dumps(config.__dict__, indent=2, ensure_ascii=False),
            "```",
            "",
            "O ranking usa apenas informacoes conhecidas no fechamento. As alteracoes de "
            "carteira sao executadas na abertura do candle seguinte.",
            "",
        ]
        _atomic_write(strategy_dir / "README.md", "\n".join(content))


def write_management_csv(managements: list[PortfolioConfig], path: Path) -> None:
    fields = list(PortfolioConfig.__dataclass_fields__)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            [{field: getattr(config, field) for field in fields} for config in managements]
        )
    temporary.replace(path)


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
