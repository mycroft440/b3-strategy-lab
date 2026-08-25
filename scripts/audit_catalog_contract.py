from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_strategy_lab.catalog_contract import (  # noqa: E402
    DEFAULT_CATALOG_CONTRACT,
    runtime_catalog_contract,
    validate_catalog_contract,
    write_runtime_catalog,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit the content-addressed strategy/management research catalog."
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CATALOG_CONTRACT)
    parser.add_argument("--signal-mode", choices=["raw", "adjusted"], default="adjusted")
    parser.add_argument("--config-set", default="all")
    parser.add_argument(
        "--runtime-output",
        type=Path,
        default=Path("reports/runtime_catalog_adjusted_all.json"),
    )
    parser.add_argument(
        "--print-runtime",
        action="store_true",
        help="Print the runtime payload without accepting or writing it.",
    )
    args = parser.parse_args(argv)

    if args.print_runtime:
        payload = runtime_catalog_contract(
            signal_mode=args.signal_mode,
            config_set=args.config_set,
        )
    else:
        payload = validate_catalog_contract(
            args.contract,
            signal_mode=args.signal_mode,
            config_set=args.config_set,
        )
    write_runtime_catalog(args.runtime_output, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
