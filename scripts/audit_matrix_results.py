from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_RESULTS = Path(
    "reports/strategy_management_combinations_40_adjusted_no_dividends_1d.csv.gz"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _report_base(path: Path) -> Path:
    if path.suffixes[-2:] == [".csv", ".gz"]:
        return path.with_suffix("").with_suffix("")
    return path.with_suffix("")


def _open_results(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, mode="rt", encoding="utf-8", newline="")
    return path.open(encoding="utf-8", newline="")


def _real_money_blockers(manifest: dict[str, object]) -> list[str]:
    blockers: list[str] = []
    if manifest.get("result_classification") != "REALISTIC_POINT_IN_TIME_VALIDATED":
        blockers.append("matrix_result_is_research_not_realistic_point_in_time_validation")
    if manifest.get("real_money_claim_allowed") is not True:
        blockers.append("manifest_forbids_real_money_claim")
    if manifest.get("evaluation_scope") == "full_period":
        blockers.append("strategy_and_management_selected_on_full_period")
    universe = manifest.get("universe")
    if not isinstance(universe, dict) or universe.get("survivorship_safe") is not True:
        blockers.append("universe_is_not_survivorship_safe")
    if manifest.get("dividends_jcp") != "included_with_certified_cash_events":
        blockers.append("dividends_and_jcp_are_not_certified_in_matrix")
    limitations = {str(item) for item in (manifest.get("limitations") or [])}
    if "taxes_excluded" in limitations:
        blockers.append("taxes_are_excluded")
    if "standard_market_open_used_for_integer_share_research_execution" in limitations:
        blockers.append("fractional_market_execution_is_not_modeled")
    return sorted(set(blockers))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audita cardinalidade, ordenacao, metricas e hashes da matriz completa."
    )
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--annual-report", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    report_base = _report_base(args.results)
    manifest_path = args.manifest or report_base.with_suffix(".manifest.json")
    annual_path = args.annual_report or report_base.with_name(
        f"{report_base.name}_top5_annual.md"
    )
    output_path = args.output or report_base.with_suffix(".audit.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_strategies = set(manifest["strategies"])
    expected_managements = {
        config["name"] for config in manifest["management_configs"]
    }
    expected_rows = int(manifest["combinations"])
    float_fields = (
        "exposure",
        "avg_positions",
        "initial_equity",
        "final_equity",
        "total_return",
        "cagr",
        "average_annual_return",
        "max_drawdown",
        "annual_volatility",
        "sharpe",
        "turnover",
    )

    seen_pairs: set[tuple[str, str]] = set()
    observed_strategies: set[str] = set()
    observed_managements: set[str] = set()
    ranked_pairs: list[tuple[str, str]] = []
    row_count = 0
    ranks_are_sequential = True
    metrics_are_finite = True
    returns_match_equity = True
    dates_and_candles_match = True
    sorted_as_declared = True
    previous_sort_key: tuple[float, float, str, str] | None = None
    with _open_results(args.results) as source:
        for row_count, row in enumerate(csv.DictReader(source), start=1):
            try:
                rank = int(row["rank"])
                candles = int(row["candles"])
                values = {field: float(row[field]) for field in float_fields}
            except (KeyError, TypeError, ValueError):
                ranks_are_sequential = False
                metrics_are_finite = False
                continue
            ranks_are_sequential &= rank == row_count
            metrics_are_finite &= all(math.isfinite(value) for value in values.values())
            returns_match_equity &= math.isclose(
                values["total_return"],
                values["final_equity"] / values["initial_equity"] - 1.0,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            dates_and_candles_match &= (
                row["start"] == manifest["start"]
                and row["end"] == manifest["end"]
                and candles > 0
            )
            sort_key = (
                -values["total_return"],
                -values["cagr"],
                row["trading_strategy"],
                row["management_strategy"],
            )
            if previous_sort_key is not None:
                sorted_as_declared &= previous_sort_key <= sort_key
            previous_sort_key = sort_key
            pair = (row["trading_strategy"], row["management_strategy"])
            seen_pairs.add(pair)
            observed_strategies.add(pair[0])
            observed_managements.add(pair[1])
            ranked_pairs.append(pair)

    annual_text = annual_path.read_text(encoding="utf-8")
    annual_pairs = [
        (match.group(1), match.group(2))
        for match in re.finditer(
            r"^## \d+\. ([a-z0-9_]+) \+ ([a-z0-9_]+)$",
            annual_text,
            flags=re.MULTILINE,
        )
    ]
    annual_top_n = len(annual_pairs)
    annual_report_top_matches_csv = (
        annual_top_n > 0 and annual_pairs == ranked_pairs[:annual_top_n]
    )

    source_hashes_match = all(
        Path(path).exists() and _sha256(Path(path)) == expected_hash
        for path, expected_hash in manifest["source_sha256"].items()
    )
    required_source_hashes = {
        "b3_strategy_lab/backtest.py",
        "b3_strategy_lab/candles.py",
        "b3_strategy_lab/cli.py",
        "b3_strategy_lab/cotahist.py",
        "b3_strategy_lab/strategies.py",
        "b3_strategy_lab/extensions.py",
        "b3_strategy_lab/user_extensions.py",
        "b3_strategy_lab/additional_strategies.py",
        "b3_strategy_lab/researched_strategies.py",
        "b3_strategy_lab/extended_strategies.py",
        "b3_strategy_lab/research_indicators.py",
        "b3_strategy_lab/indicator_strategies.py",
        "b3_strategy_lab/trend_strategies.py",
        "b3_strategy_lab/portfolio_risk.py",
        "scripts/backtest_strategy_management_combinations.py",
        "scripts/research_portfolio_allocation.py",
        "scripts/research_portfolio_allocation_core.py",
    }
    if manifest.get("sharded_execution") is True:
        required_source_hashes.add("scripts/merge_matrix_shards.py")
    universe_path = Path(manifest["universe"]["manifest"])
    universe_hash_matches = (
        universe_path.exists()
        and _sha256(universe_path) == manifest["universe"]["sha256"]
    )
    dataset_hashes_match = all(
        (Path("data/candles") / f"{ticker.lower()}_{manifest['interval']}.csv").exists()
        and _sha256(
            Path("data/candles")
            / f"{ticker.lower()}_{manifest['interval']}.csv"
        )
        == values["candle_sha256"]
        for ticker, values in manifest["datasets"].items()
    )
    split_evidence_hashes = {
        values["split_evidence_sha256"] for values in manifest["datasets"].values()
    }
    split_evidence_hash_matches = (
        len(split_evidence_hashes) == 1
        and Path("data/corporate_actions/split_evidence.json").exists()
        and _sha256(Path("data/corporate_actions/split_evidence.json"))
        == next(iter(split_evidence_hashes))
    )

    checks = {
        "row_count_matches_manifest": row_count == expected_rows,
        "rank_is_sequential": ranks_are_sequential,
        "strategy_management_pairs_are_unique": len(seen_pairs) == row_count,
        "full_cartesian_product_is_present": (
            row_count == len(expected_strategies) * len(expected_managements)
            and observed_strategies == expected_strategies
            and observed_managements == expected_managements
        ),
        "manifest_counts_match_declared_catalogs": (
            int(manifest.get("strategy_count", -1)) == len(expected_strategies)
            and int(manifest.get("management_count", -1))
            == len(expected_managements)
            and expected_rows
            == len(expected_strategies) * len(expected_managements)
        ),
        "full_catalog_really_exceeds_100k": (
            manifest.get("catalog_complete") is True
            and (
                expected_rows > 100_000
                and expected_rows
                == int(manifest.get("catalog_combination_count", -1))
                and len(expected_strategies)
                == int(manifest.get("catalog_strategy_count", -1))
                and len(expected_managements)
                == int(manifest.get("catalog_management_count", -1))
            )
        ),
        "ranking_is_deterministic_total_return_cagr_names": sorted_as_declared,
        "execution_policy_is_fail_closed": (
            manifest.get("execution_missing_price_policy")
            == "fail_closed_fresh_open_and_close_required"
        ),
        "signal_changes_execute_at_next_open": (
            manifest.get("signal_execution_policy")
            == "designated_basket_binary_signal_changes_execute_next_open_"
            "without_intraperiod_reranking"
        ),
        "initial_rebalance_boundary_uses_prior_close": (
            manifest.get("initial_entry_policy")
            == "prior_close_decision_executes_at_first_open_when_start_is_"
            "rebalance_boundary"
        ),
        "buy_allocation_policy_is_declared": (
            manifest.get("buy_allocation_policy")
            == "target_shares_at_market_open_then_common_scale_for_costs"
        ),
        "retrospective_research_is_not_labeled_real_money": (
            manifest.get("result_classification")
            == "RETROSPECTIVE_PRICE_ONLY_RESEARCH"
            and manifest.get("real_money_claim_allowed") is False
        ),
        "full_period_selection_bias_is_declared": (
            manifest.get("evaluation_scope") == "full_period"
            and manifest.get("train_ratio_applied") is False
            and "strategy_and_management_selected_on_the_same_full_period"
            in (manifest.get("limitations") or [])
        ),
        "final_mark_to_market_is_not_mislabeled_as_liquidation": (
            manifest.get("final_valuation")
            == "mark_to_market_at_last_verified_close_not_liquidated"
        ),
        "transaction_assumptions_are_finite_and_nonnegative": all(
            math.isfinite(float(manifest.get(field, math.nan)))
            and float(manifest.get(field, -1)) >= 0
            for field in ("cost_bps", "slippage_bps")
        ),
        "all_numeric_metrics_are_finite": metrics_are_finite,
        "total_return_matches_equity_ratio": returns_match_equity,
        "all_rows_match_manifest_window": dates_and_candles_match,
        "annual_report_top_matches_csv": annual_report_top_matches_csv,
        "source_hashes_match": source_hashes_match,
        "all_critical_sources_are_hashed": required_source_hashes.issubset(
            manifest["source_sha256"]
        ),
        "calculation_worktree_was_clean": manifest.get("git_dirty") is False,
        "calculation_worktree_scope_is_explicit": (
            manifest.get("git_dirty_scope")
            == "calculation_sources_and_workflows_excluding_hashed_market_data"
        ),
        "universe_hash_matches": universe_hash_matches,
        "dataset_hashes_match": dataset_hashes_match,
        "split_evidence_hash_matches": split_evidence_hash_matches,
    }
    research_ready = all(checks.values())
    real_money_blockers = _real_money_blockers(manifest)
    real_money_ready = research_ready and not real_money_blockers
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "results": str(args.results),
        "results_sha256": _sha256(args.results),
        "manifest": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "annual_report": str(annual_path),
        "annual_report_sha256": _sha256(annual_path),
        "annual_report_top_n": annual_top_n,
        "rows": row_count,
        "strategy_count": len(observed_strategies),
        "management_count": len(observed_managements),
        "result_classification": manifest.get("result_classification"),
        "checks": checks,
        "ready": research_ready,
        "ready_for_research_ranking": research_ready,
        "ready_for_real_money": real_money_ready,
        "real_money_claim_allowed": bool(
            real_money_ready and manifest.get("real_money_claim_allowed") is True
        ),
        "real_money_blockers": real_money_blockers,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output_path)
    print(
        f"{output_path}: research_ready={payload['ready_for_research_ranking']}, "
        f"real_money_ready={payload['ready_for_real_money']}, linhas={row_count}, "
        f"estrategias={len(observed_strategies)}, gestoes={len(observed_managements)}, "
        f"top_n={annual_top_n}"
    )
    return 0 if payload["ready_for_research_ranking"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
