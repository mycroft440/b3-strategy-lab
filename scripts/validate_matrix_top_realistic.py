from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
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

FINITE_METRICS = (
    "final_equity",
    "total_return",
    "cagr",
    "max_drawdown",
    "annual_volatility",
    "sharpe",
    "average_annual_return",
    "fees_paid",
    "ordinary_income_tax_paid",
    "distribution_tax_paid",
    "distributions_net",
)

NONNEGATIVE_METRICS = (
    "annual_volatility",
    "fees_paid",
    "ordinary_income_tax_paid",
    "distribution_tax_paid",
    "distributions_net",
)


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _curve_recalculated_metrics(
    curve: list[dict[str, str]],
    *,
    initial_cash: float,
) -> dict[str, float]:
    if not math.isfinite(initial_cash) or initial_cash <= 0:
        raise ValueError("initial cash must be finite and positive")
    if len(curve) < 2:
        raise ValueError("curve must contain at least two sessions")

    dates: list[datetime] = []
    equities: list[float] = []
    for row in curve:
        current = datetime.fromisoformat(str(row["date"]))
        equity = float(row["equity"])
        if not math.isfinite(equity) or equity <= 0:
            raise ValueError("curve equity must be finite and positive")
        if dates and current <= dates[-1]:
            raise ValueError("curve dates must be strictly increasing")
        dates.append(current)
        equities.append(equity)

    returns = [
        equities[index] / equities[index - 1] - 1.0
        for index in range(1, len(equities))
    ]
    years = max(
        (dates[-1] - dates[0]).total_seconds() / 31_557_600.0,
        1 / 365.25,
    )
    periods_per_year = (len(equities) - 1) / years
    if len(returns) >= 2:
        return_std = statistics.stdev(returns)
        annual_volatility = return_std * math.sqrt(periods_per_year)
        sharpe = (
            statistics.mean(returns) / return_std * math.sqrt(periods_per_year)
            if return_std > 0
            else 0.0
        )
    else:
        annual_volatility = 0.0
        sharpe = 0.0

    year_ends: dict[int, float] = {}
    for current, equity in zip(dates, equities):
        year_ends[current.year] = equity
    prior_equity = initial_cash
    yearly_returns: list[float] = []
    for end_equity in year_ends.values():
        yearly_returns.append(end_equity / prior_equity - 1.0)
        prior_equity = end_equity

    return {
        "annual_volatility": annual_volatility,
        "sharpe": sharpe,
        "average_annual_return": (
            statistics.mean(yearly_returns) if yearly_returns else 0.0
        ),
    }


def _artifact_binding_issues(
    payload: dict[str, object],
    *,
    curve_path: Path,
    trades_path: Path,
    cash_path: Path,
    tax_path: Path | None = None,
) -> list[str]:
    issues: list[str] = []
    try:
        curve = _csv_rows(curve_path)
        trades = _csv_rows(trades_path)
        cash = _csv_rows(cash_path)
        tax = _csv_rows(tax_path) if tax_path is not None else []
    except (OSError, csv.Error, UnicodeError, ValueError):
        return ["invalid_output_artifact"]
    if not curve:
        return ["empty_curve"]
    if curve[0].get("date") != str(payload.get("start", "")):
        issues.append("curve_start_mismatch")
    if curve[-1].get("date") != str(payload.get("end", "")):
        issues.append("curve_end_mismatch")
    try:
        curve_final = float(curve[-1]["equity"])
        summary_final = float(payload["final_equity"])
        if not (
            math.isfinite(curve_final)
            and math.isclose(curve_final, summary_final, rel_tol=1e-10, abs_tol=1e-8)
        ):
            issues.append("curve_final_equity_mismatch")
    except (KeyError, TypeError, ValueError):
        issues.append("invalid_curve_final_equity")
    try:
        if len(trades) != int(payload["trades"]):
            issues.append("trade_ledger_count_mismatch")
        ledger_fees = sum(float(row["fee"]) for row in trades)
        if not (
            math.isfinite(ledger_fees)
            and math.isclose(
                ledger_fees,
                float(payload["fees_paid"]),
                rel_tol=1e-10,
                abs_tol=1e-8,
            )
        ):
            issues.append("trade_ledger_fee_mismatch")
    except (KeyError, TypeError, ValueError):
        issues.append("invalid_trade_ledger")
    try:
        ledger_distributions = sum(float(row["net"]) for row in cash)
        ledger_distribution_tax = sum(float(row["tax"]) for row in cash)
        if not (
            math.isfinite(ledger_distributions)
            and math.isclose(
                ledger_distributions,
                float(payload["distributions_net"]),
                rel_tol=1e-10,
                abs_tol=1e-8,
            )
        ):
            issues.append("cash_ledger_distribution_mismatch")
        if not (
            math.isfinite(ledger_distribution_tax)
            and math.isclose(
                ledger_distribution_tax,
                float(payload["distribution_tax_paid"]),
                rel_tol=1e-10,
                abs_tol=1e-8,
            )
        ):
            issues.append("cash_ledger_tax_mismatch")
    except (KeyError, TypeError, ValueError):
        issues.append("invalid_cash_ledger")

    if tax_path is None:
        return sorted(set(issues))

    required_tax_columns = {"month", "tax_due", "irrf_withheld_month"}
    if not tax:
        issues.append("empty_tax_ledger")
    else:
        missing_tax_columns = required_tax_columns.difference(tax[0])
        if missing_tax_columns:
            issues.append("tax_ledger_missing_columns")
        try:
            tax_months = [str(row["month"]) for row in tax]
            curve_months = sorted({str(row["date"])[:7] for row in curve})
            if len(tax_months) != len(set(tax_months)):
                issues.append("tax_ledger_duplicate_month")
            if tax_months != sorted(tax_months):
                issues.append("tax_ledger_month_order_mismatch")
            if sorted(tax_months) != curve_months:
                issues.append("tax_ledger_month_coverage_mismatch")
        except (KeyError, TypeError, ValueError):
            issues.append("invalid_tax_ledger_months")

    try:
        recomputed = _curve_recalculated_metrics(
            curve,
            initial_cash=float(payload["initial_cash"]),
        )
        metric_issue_names = {
            "annual_volatility": "curve_annual_volatility_mismatch",
            "sharpe": "curve_sharpe_mismatch",
            "average_annual_return": "curve_average_annual_return_mismatch",
        }
        for field, issue_name in metric_issue_names.items():
            actual = float(payload[field])
            expected = float(recomputed[field])
            if not (
                math.isfinite(actual)
                and math.isfinite(expected)
                and math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-10)
            ):
                issues.append(issue_name)
    except (KeyError, TypeError, ValueError, OverflowError, statistics.StatisticsError):
        issues.append("invalid_curve_metrics")

    try:
        ledger_irrf = sum(float(row["irrf_withheld_month"]) for row in tax)
        ledger_tax_due = sum(float(row["tax_due"]) for row in tax)
        outstanding = float(payload["outstanding_accrued_tax_liability"])
        ordinary_paid = float(payload["ordinary_income_tax_paid"])
        if not all(math.isfinite(value) for value in (ledger_irrf, ledger_tax_due, outstanding, ordinary_paid)):
            raise ValueError("non-finite tax reconciliation value")
        expected_darf_paid = ledger_tax_due - outstanding
        if expected_darf_paid < -1e-8:
            issues.append("tax_ledger_outstanding_liability_exceeds_accrual")
        else:
            expected_darf_paid = max(0.0, expected_darf_paid)
            expected_ordinary_paid = ledger_irrf + expected_darf_paid
            if not math.isclose(
                ordinary_paid,
                expected_ordinary_paid,
                rel_tol=1e-9,
                abs_tol=1e-8,
            ):
                issues.append("tax_ledger_ordinary_income_tax_paid_mismatch")
            if "ordinary_irrf_withheld" in payload and not math.isclose(
                float(payload["ordinary_irrf_withheld"]),
                ledger_irrf,
                rel_tol=1e-9,
                abs_tol=1e-8,
            ):
                issues.append("tax_ledger_irrf_withheld_mismatch")
            if "darf_paid" in payload and not math.isclose(
                float(payload["darf_paid"]),
                expected_darf_paid,
                rel_tol=1e-9,
                abs_tol=1e-8,
            ):
                issues.append("tax_ledger_darf_paid_mismatch")
    except (KeyError, TypeError, ValueError):
        issues.append("invalid_tax_ledger")

    return sorted(set(issues))


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
    if strategy == "gap_momentum":
        command.append("--economic-gap-adjustment")
    subprocess.run(command, cwd=ROOT, check=True)
    payload = json.loads(summary.read_text(encoding="utf-8"))
    payload["_artifact_binding_issues"] = _artifact_binding_issues(
        payload,
        curve_path=curve,
        trades_path=trades,
        cash_path=cash,
        tax_path=tax,
    )
    payload["research_rank"] = rank
    payload["research_strategy"] = strategy
    payload["research_management"] = management
    return payload


def _validation_issues(
    payload: dict[str, object],
    *,
    expected_strategy: str | None = None,
    expected_management: str | None = None,
    expected_start: str | None = None,
    expected_end: str | None = None,
    expected_initial_cash: float | None = None,
) -> list[str]:
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
    if not validity.startswith("REALISTIC_POINT_IN_TIME"):
        issues.append("unexpected_validity_class")
    if payload.get("point_in_time_universe") is not True:
        issues.append("point_in_time_universe=false")
    if payload.get("fractional_execution") is not True:
        issues.append("fractional_execution=false")
    for field in FINITE_METRICS:
        try:
            value = float(payload[field])
        except (KeyError, TypeError, ValueError):
            issues.append(f"invalid_metric:{field}")
            continue
        if not math.isfinite(value):
            issues.append(f"nonfinite_metric:{field}")
    for field in NONNEGATIVE_METRICS:
        try:
            if float(payload[field]) < 0:
                issues.append(f"negative_metric:{field}")
        except (KeyError, TypeError, ValueError):
            pass
    try:
        if math.isfinite(float(payload["final_equity"])) and float(
            payload["final_equity"]
        ) <= 0:
            issues.append("nonpositive_final_equity")
    except (KeyError, TypeError, ValueError):
        pass
    try:
        initial_cash = float(payload["initial_cash"])
        final_equity = float(payload["final_equity"])
        total_return = float(payload["total_return"])
        if not math.isfinite(initial_cash) or initial_cash <= 0:
            raise ValueError
        implied_return = final_equity / initial_cash - 1.0
        if not math.isclose(
            total_return, implied_return, rel_tol=1e-10, abs_tol=1e-10
        ):
            issues.append("total_return_equity_identity_mismatch")
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        issues.append("invalid_initial_cash")
    try:
        start_date = datetime.fromisoformat(str(payload["start"]))
        end_date = datetime.fromisoformat(str(payload["end"]))
        if end_date < start_date:
            raise ValueError
        initial_cash = float(payload["initial_cash"])
        final_equity = float(payload["final_equity"])
        implied_return = final_equity / initial_cash - 1.0
        years = max((end_date - start_date).total_seconds() / 31_557_600.0, 1 / 365.25)
        implied_cagr = (1.0 + implied_return) ** (1.0 / years) - 1.0
        if not math.isclose(
            float(payload["cagr"]), implied_cagr, rel_tol=1e-10, abs_tol=1e-10
        ):
            issues.append("cagr_equity_period_identity_mismatch")
    except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError):
        issues.append("invalid_cagr_identity")
    try:
        drawdown = float(payload["max_drawdown"])
        if math.isfinite(drawdown) and not (-1.0 <= drawdown <= 0.0):
            issues.append("max_drawdown_out_of_range")
    except (KeyError, TypeError, ValueError):
        pass
    try:
        raw_trades = payload["trades"]
        trades_value = float(raw_trades)
        if (
            isinstance(raw_trades, bool)
            or not math.isfinite(trades_value)
            or not trades_value.is_integer()
            or trades_value < 0
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        issues.append("invalid_trades")
    expected_fields = (
        ("strategy", expected_strategy),
        ("management", expected_management),
        ("start", expected_start),
        ("end", expected_end),
    )
    for field, expected in expected_fields:
        if expected is not None and str(payload.get(field, "")) != expected:
            issues.append(f"candidate_binding_mismatch:{field}")
    if expected_initial_cash is not None:
        try:
            actual_initial_cash = float(payload["initial_cash"])
            if not math.isclose(
                actual_initial_cash,
                expected_initial_cash,
                rel_tol=1e-12,
                abs_tol=1e-9,
            ):
                issues.append("candidate_binding_mismatch:initial_cash")
        except (KeyError, TypeError, ValueError):
            pass
    artifact_issues = payload.get("_artifact_binding_issues", [])
    if not isinstance(artifact_issues, list):
        issues.append("invalid_artifact_binding_issues")
    else:
        issues.extend(str(issue) for issue in artifact_issues)
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
    if (
        not start
        or not end
        or not math.isfinite(initial_cash)
        or initial_cash <= 0
        or not isinstance(candidates, list)
    ):
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
        issues = _validation_issues(
            payload,
            expected_strategy=strategy,
            expected_management=management,
            expected_start=start,
            expected_end=end,
            expected_initial_cash=initial_cash,
        )
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
                "economic_gap_adjustment": bool(item.get("economic_gap_adjustment")),
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
            "hindsight. Gap Momentum is replayed with economic cash-distribution gap "
            "adjustment. Use full-catalog walk-forward for out-of-sample selection validation."
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
