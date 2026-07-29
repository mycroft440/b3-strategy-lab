from __future__ import annotations

import argparse
from pathlib import Path


KEEP = {
    "data_status.csv",
    "data_status.md",
    "market_data_audit.md",
    "market_data_source_comparison.csv",
    "strategy_inventory.csv",
    "strategy_inventory.md",
    "yearly_data_status.csv",
    "yearly_data_status.md",
}
QUARANTINE_NAME = "legacy_unverified"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Move resultados antigos para uma quarentena recuperavel."
    )
    parser.add_argument("--reports-dir", default="reports")
    args = parser.parse_args(argv)

    reports_dir = Path(args.reports_dir)
    quarantine_dir = reports_dir / QUARANTINE_NAME
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    moved = 0
    for path in sorted(reports_dir.iterdir()):
        if path.name in KEEP or path.name == QUARANTINE_NAME:
            continue
        destination = quarantine_dir / path.name
        if destination.exists():
            raise FileExistsError(
                f"Quarentena ja contem {destination}; nenhuma sobrescrita foi feita."
            )
        path.replace(destination)
        moved += 1
    print(f"Relatorios movidos para {quarantine_dir}: {moved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
