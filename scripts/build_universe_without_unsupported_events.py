"""Universo point-in-time sem ações cujos eventos os motores não sabem valorar.

Remove, sem substituição, as ações selecionáveis que:

- têm evento certificado que a matriz de pesquisa não valora (incorporação, cisão,
  reorganização ou cancelamento de registro), ou
- saíram da bolsa sem sucessor documentado (`reports/unresolved_historical_delistings.csv`).

Saber hoje quais empresas passariam por esses eventos é informação futura: o filtro é
retrospectivo e fica marcado em `control_panel.selection_is_retrospective_user_filter`.

Saídas em `--output-dir`:

- `universo_matriz.json`: `--universe-manifest` de `backtest_strategy_management_combinations.py`;
- `universo_realista.json` e `snapshots_filtrados.csv`: `--universe-manifest` e `--snapshots`
  de `backtest_strategy_management_realistic.py`;
- `acoes_removidas.json`: ação removida e motivo.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import research_portfolio_allocation as research  # noqa: E402
from scripts.realistic_combination_backtest_control_panel import _selected_payload  # noqa: E402

DEFAULT_UNIVERSE = Path("data/universes/point_in_time_union.json")
DEFAULT_DELISTINGS = Path("reports/unresolved_historical_delistings.csv")
DEFAULT_OUTPUT_DIR = Path(".cache/universo_sem_problematicas")


def unsupported_tickers(
    boundaries: Iterable[tuple[str, str, str, str]],
    delistings: Iterable[Mapping[str, str]],
    selectable: Iterable[str],
) -> dict[str, str]:
    """Selectable tickers with an event the engines cannot value, and why."""
    allowed = {str(ticker).upper() for ticker in selectable}
    reasons: dict[str, str] = {}
    for effective, old, new, event in sorted(boundaries):
        successor = f"{old}->{new}" if new else "sem sucessor"
        reasons.setdefault(old.upper(), f"{event} em {effective} ({successor})")
    for row in delistings:
        ticker = str(row["ticker"]).upper()
        reasons.setdefault(
            ticker, f"saiu da bolsa em {row['last_quote_date']} sem sucessor documentado"
        )
    return {ticker: reason for ticker, reason in sorted(reasons.items()) if ticker in allowed}


def _relative(path: Path) -> str:
    resolved = path if path.is_absolute() else ROOT / path
    try:
        return resolved.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--universe-manifest", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--delistings", type=Path, default=DEFAULT_DELISTINGS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    base = json.loads(args.universe_manifest.read_text(encoding="utf-8"))
    selectable = sorted(str(ticker).upper() for ticker in base["tickers"])
    with args.delistings.open(encoding="utf-8", newline="") as source:
        delistings = list(csv.DictReader(source))
    excluded = unsupported_tickers(
        research._certified_unsupported_transition_boundaries(), delistings, selectable
    )
    kept = [ticker for ticker in selectable if ticker not in excluded]

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    matrix_manifest = _selected_payload(kept, args.universe_manifest)
    matrix_manifest["snapshot_file"] = _relative(Path(str(matrix_manifest["snapshot_file"])))
    (output / "universo_matriz.json").write_text(
        json.dumps(matrix_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    snapshots = Path(str(base["snapshot_file"]))
    snapshots = snapshots if snapshots.is_absolute() else ROOT / snapshots
    with snapshots.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        fields = list(reader.fieldnames or [])
        rows = [row for row in reader if row["ticker"].upper() not in excluded]
    filtered = output / "snapshots_filtrados.csv"
    with filtered.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    realistic_manifest = dict(base)
    realistic_manifest["tickers"] = sorted({row["ticker"].upper() for row in rows})
    realistic_manifest["snapshot_file"] = _relative(filtered)
    realistic_manifest["control_panel"] = matrix_manifest["control_panel"]
    (output / "universo_realista.json").write_text(
        json.dumps(realistic_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output / "acoes_removidas.json").write_text(
        json.dumps(excluded, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    per_week: dict[str, int] = {}
    for row in rows:
        per_week[row["effective_date"]] = per_week.get(row["effective_date"], 0) + 1
    print(f"Selecionaveis: {len(selectable)}; removidas: {len(excluded)}; mantidas: {len(kept)}")
    print(f"Acoes por semana: {min(per_week.values())} a {max(per_week.values())}")
    for ticker, reason in excluded.items():
        print(f"- {ticker}: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
