from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATES = Path("reports/TOP_10.json")
DEFAULT_OUTPUT = Path("reports/REALISTIC_TOP_10.json")
DEFAULT_MARKDOWN = Path("reports/REALISTIC_TOP_10.md")


BLOCKING_VALIDITY_TAGS = (
    "RETROSPECTIVE_UNIVERSE",
    "UNCERTIFIED_CASH_EVENTS",
    "UNBOUND_TICKER_TRANSITIONS",
    "BONUS_TAX_BASIS_UNCERTIFIED",
)


def _run_candidate(
    *,
    rank: int,
    strategy: str,
    management: str,
    start: str,
    end: str,
    initial_cash: float,
    output_dir: Path,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"candidate_{rank:02d}_{strategy}_{management}"
    summary = output_dir / f"{stem}.json"
    curve = output_dir / f"{stem}_curve.csv"
    trades = output_dir / f"{stem}_trades.csv"
    cash = output_dir / f"{stem}_cash.csv"
    tax = output_dir / f"{stem}_tax.csv"
    command = [
        sys.executable,
        "scripts/backtest_strategy_management_realistic.py",
        "--strategy",
        strategy,
        "--management",
        management,
        "--start",
        start,
        "--end",
        end,
        "--initial-cash",
        str(initial_cash),
        "--selection-status",
        "retrospective_hypothesis_replay",
        "--output",
        str(summary),
        "--curve-output",
        str(curve),
        "--trades-output",
        str(trades),
        "--cash-ledger-output",
        str(cash),
        "--tax-output",
        str(tax),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    payload = json.loads(summary.read_text(encoding="utf-8"))
    payload["research_rank"] = rank
    payload["research_strategy"] = strategy
    payload["research_management"] = management
    return payload


def _validation_issues(payload: dict[str, object]) -> list[str]:
    issues: list[str] = []
    validity = str(payload.get("validity", ""))
    for tag in BLOCKING_VALIDITY_TAGS:
        if tag in validity:
            issues.append(f"validity:{tag}")
    if payload.get("survivorship_safe") is not True:
        issues.append("survivorship_safe=false")
    if payload.get("cash_events_complete") is not True:
        issues.append("cash_events_complete=false")
    if payload.get("ticker_transition_binding_verified") is not True:
        issues.append("ticker_transition_binding_verified=false")
    if payload.get("bonus_tax_basis_affects_realized_gain") is True:
        issues.append("bonus_tax_basis_affects_realized_gain=true")
    if str(payload.get("fee_quality", "")) != "official":
        issues.append(f"fee_quality={payload.get('fee_quality')}")
    if payload.get("selection_status") != "retrospective_hypothesis_replay":
        issues.append("unexpected_selection_status")
    try:
        if float(payload.get("final_equity", 0.0)) <= 0:
            issues.append("nonpositive_final_equity")
    except (TypeError, ValueError):
        issues.append("invalid_final_equity")
    return sorted(set(issues))


def _write_markdown(result: dict[str, object], path: Path) -> None:
    rows = result["realistic_ranking"]
    assert isinstance(rows, list)
    lines = [
        "# Top 10 — validação realista dos candidatos da matriz",
        "",
        "> A matriz original é apenas triagem retrospectiva. Esta tabela reexecuta os candidatos com o motor point-in-time e não transforma a escolha retrospectiva em uma decisão ex-ante.",
        "",
        "| Rank realista | Rank pesquisa | Estratégia | Gerenciamento | Patrimônio final | Retorno | CAGR | Drawdown | Trades |",
        "|---:|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        assert isinstance(row, dict)
        lines.append(
            f"| {row['realistic_rank']} | {row['research_rank']} | {row['strategy']} | "
            f"{row['management']} | R$ {float(row['final_equity']):,.2f} | "
            f"{float(row['total_return']):.2%} | {float(row['cagr']):.2%} | "
            f"{float(row['max_drawdown']):.2%} | {int(row['trades'])} |"
        )
    excluded = result.get("excluded_candidates") or []
    if excluded:
        lines.extend(["", "## Candidatos excluídos pelo gate fail-closed", ""])
        for item in excluded:
            lines.append(
                f"- #{item['research_rank']} {item['strategy']} + {item['management']}: "
                + ", ".join(item["issues"])
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reexecuta o Top N da matriz retrospectiva no motor realista. "
            "Resultados com insumos/certificações incompletos são excluídos fail-closed."
        )
    )
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--work-dir", type=Path, default=Path("reports/realistic_candidates"))
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--require-valid", type=int, default=1)
    args = parser.parse_args(argv)
    if args.limit <= 0 or args.require_valid <= 0:
        parser.error("--limit and --require-valid must be positive.")

    source = json.loads(args.candidates.read_text(encoding="utf-8"))
    period = source.get("period") or {}
    start = str(period.get("start", ""))
    end = str(period.get("end", ""))
    initial_cash = float(source.get("initial_cash", 0.0))
    candidates = source.get("top_10")
    if not start or not end or initial_cash <= 0 or not isinstance(candidates, list):
        raise ValueError("Candidate file is missing period, initial_cash or top_10.")

    validated: list[dict[str, object]] = []
    excluded: list[dict[str, object]] = []
    for raw in candidates[: args.limit]:
        if not isinstance(raw, dict):
            raise ValueError("Invalid candidate row.")
        rank = int(raw["rank"])
        strategy = str(raw["trading_strategy"])
        management = str(raw["management_strategy"])
        payload = _run_candidate(
            rank=rank,
            strategy=strategy,
            management=management,
            start=start,
            end=end,
            initial_cash=initial_cash,
            output_dir=args.work_dir,
        )
        issues = _validation_issues(payload)
        if issues:
            excluded.append(
                {
                    "research_rank": rank,
                    "strategy": strategy,
                    "management": management,
                    "issues": issues,
                }
            )
            continue
        validated.append(payload)

    validated.sort(
        key=lambda item: (
            -float(item["total_return"]),
            -float(item["cagr"]),
            str(item["strategy"]),
            str(item["management"]),
        )
    )
    ranking: list[dict[str, object]] = []
    for realistic_rank, item in enumerate(validated, start=1):
        ranking.append(
            {
                "realistic_rank": realistic_rank,
                "research_rank": int(item["research_rank"]),
                "strategy": item["strategy"],
                "management": item["management"],
                "final_equity": float(item["final_equity"]),
                "total_return": float(item["total_return"]),
                "cagr": float(item["cagr"]),
                "max_drawdown": float(item["max_drawdown"]),
                "trades": int(item["trades"]),
                "fees_paid": float(item["fees_paid"]),
                "ordinary_income_tax_paid": float(item["ordinary_income_tax_paid"]),
                "distribution_tax_paid": float(item["distribution_tax_paid"]),
                "distributions_net": float(item["distributions_net"]),
                "validity": item["validity"],
                "selection_status": item["selection_status"],
            }
        )

    result = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_candidates": str(args.candidates),
        "source_classification": source.get("result_classification"),
        "start": start,
        "end": end,
        "initial_cash": initial_cash,
        "validated_candidate_count": len(ranking),
        "excluded_candidate_count": len(excluded),
        "result_classification": "REALISTIC_POINT_IN_TIME_RETROSPECTIVE_FINALIST_REPLAY",
        "real_money_claim_allowed": False,
        "ex_ante_selection_claim_allowed": False,
        "counterfactual_execution_exact": False,
        "interpretation": (
            "This reranks hindsight-generated finalists using the realistic account engine. "
            "It improves execution/account fidelity but does not remove strategy-selection "
            "hindsight. Use full-catalog walk-forward for out-of-sample selection validation."
        ),
        "realistic_ranking": ranking,
        "excluded_candidates": excluded,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _write_markdown(result, args.markdown_output)
    if len(ranking) < args.require_valid:
        raise SystemExit(
            f"Only {len(ranking)} candidates passed realistic certification; "
            f"required {args.require_valid}."
        )
    print(
        f"Realistic finalist validation: valid={len(ranking)}, excluded={len(excluded)}, "
        f"output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
