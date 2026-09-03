from __future__ import annotations

import argparse
import json
import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from scripts import validate_matrix_top_realistic_core as _base


# Preserve the historical public module surface. Existing tests and external
# instrumentation can keep importing helpers from this module while the original
# validator implementation remains frozen in the core module.
for _name in dir(_base):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_base, _name)


DEFAULT_CANDIDATE_WORKERS = max(1, min(2, os.cpu_count() or 1))


# These certified inputs are immutable during a finalist-validation process. The
# original validator reparsed the execution CSV and fee JSON once per candidate;
# sharing the exact parsed objects avoids repeated I/O without changing a single
# validation equation.
_original_execution_source = _base._execution_source
_original_fee_rules = _base._fee_rules
_original_expected_fee = _base._expected_fee


@lru_cache(maxsize=4)
def _execution_source(path: Path):
    return _original_execution_source(path)


@lru_cache(maxsize=4)
def _fee_rules(path: Path):
    return _original_fee_rules(path)


_fee_rule_by_date_cache: dict[tuple[int, str], dict[str, object]] = {}


def _expected_fee(rules: list[dict[str, object]], value_date: str, notional: float):
    key = (id(rules), value_date)
    rule = _fee_rule_by_date_cache.get(key)
    if rule is None:
        matches = [
            candidate
            for candidate in rules
            if str(candidate["start"]) <= value_date <= str(candidate["end"])
        ]
        if len(matches) != 1:
            # Delegate the exceptional path to the frozen canonical implementation
            # so its exact error semantics remain authoritative.
            return _original_expected_fee(rules, value_date, notional)
        rule = matches[0]
        _fee_rule_by_date_cache[key] = rule
    return (
        notional * float(rule["b3_bps"]) / 10_000
        + float(rule["brokerage_fixed"]),
        str(rule["quality"]),
    )


_base._execution_source = _execution_source
_base._fee_rules = _fee_rules
_base._expected_fee = _expected_fee


def _split_worker_args(argv: list[str] | None) -> tuple[int, list[str]]:
    raw = list(sys.argv[1:] if argv is None else argv)
    if "-h" in raw or "--help" in raw:
        return DEFAULT_CANDIDATE_WORKERS, raw
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--workers", type=int, default=DEFAULT_CANDIDATE_WORKERS)
    known, remaining = parser.parse_known_args(raw)
    if known.workers <= 0:
        parser.error("--workers must be positive.")
    return int(known.workers), remaining


def _preparse_context(argv: list[str]):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--candidates", type=Path, default=_base.DEFAULT_CANDIDATES)
    parser.add_argument("--output", type=Path, default=_base.DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=_base.DEFAULT_MARKDOWN)
    parser.add_argument(
        "--work-dir", type=Path, default=Path("reports/realistic_candidates")
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--require-valid", type=int, default=1)
    args, _unknown = parser.parse_known_args(argv)
    return args


def _load_parallel_context(args):
    source = json.loads(args.candidates.read_text(encoding="utf-8"))
    period = source.get("period") or {}
    start = str(period.get("start", ""))
    end = str(period.get("end", ""))
    try:
        initial_cash = float(source.get("initial_cash", 0.0))
        start_date = datetime.fromisoformat(start)
        end_date = datetime.fromisoformat(end)
    except (TypeError, ValueError):
        raise ValueError("Candidate file has an invalid period or initial_cash.") from None
    if (
        not math.isfinite(initial_cash)
        or initial_cash <= 0
        or end_date < start_date
    ):
        raise ValueError("Candidate file has an invalid period or initial_cash.")

    required_valid = _base._required_valid_count(args.limit, args.require_valid)
    finalists = _base._validated_finalists(source.get("top_10"), required_valid)
    return start, end, initial_cash, finalists


def _run_finalists_parallel(
    finalists: list[tuple[int, str, str]],
    *,
    start: str,
    end: str,
    initial_cash: float,
    output_dir: Path,
    workers: int,
) -> dict[int, dict[str, object]]:
    """Execute isolated realistic candidates concurrently, keyed by research rank.

    Each candidate still runs through the unchanged subprocess-based realistic engine,
    so account state, tax state and output files remain completely isolated. Only the
    waiting order changes. Results are returned by rank and consumed later in the
    original deterministic finalist order.
    """

    if workers <= 0:
        raise ValueError("workers must be positive")
    if not finalists:
        return {}

    max_workers = min(workers, len(finalists))
    results: dict[int, dict[str, object]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_rank = {
            executor.submit(
                _run_candidate,
                rank=rank,
                strategy=strategy,
                management=management,
                start=start,
                end=end,
                initial_cash=initial_cash,
                output_dir=output_dir,
            ): rank
            for rank, strategy, management in finalists
        }
        for future in as_completed(future_to_rank):
            rank = future_to_rank[future]
            results[rank] = future.result()

    if set(results) != {rank for rank, _strategy, _management in finalists}:
        raise RuntimeError("parallel realistic finalist execution returned incomplete ranks")
    return results


def main(argv: list[str] | None = None) -> int:
    workers, base_argv = _split_worker_args(argv)
    if "-h" in base_argv or "--help" in base_argv:
        # Keep the canonical CLI help and validation behavior. The extra option is
        # intentionally operational rather than part of result semantics.
        return _base.main(base_argv)

    args = _preparse_context(base_argv)
    if args.limit <= 0 or args.require_valid <= 0 or args.require_valid > args.limit:
        # Delegate invalid argument combinations to the canonical parser so error
        # semantics remain unchanged. The canonical parser rejects them before any
        # output cleanup, so do the same.
        return _base.main(base_argv)

    # The frozen validator clears stale outputs before reading/parsing candidates.
    # Preserve that fail-closed ordering exactly: a corrupt candidate file must not
    # leave a prior successful report in place.
    rejected_output, rejected_markdown = _clear_previous_validation_outputs(
        args.output, args.markdown_output, args.work_dir
    )
    start, end, initial_cash, finalists = _load_parallel_context(args)

    payload_by_rank = _run_finalists_parallel(
        finalists,
        start=start,
        end=end,
        initial_cash=initial_cash,
        output_dir=args.work_dir,
        workers=workers,
    )

    original_run_candidate = _base._run_candidate
    original_clear_outputs = _base._clear_previous_validation_outputs

    def cached_run_candidate(**kwargs):
        rank = int(kwargs["rank"])
        try:
            return payload_by_rank[rank]
        except KeyError as error:
            raise RuntimeError(
                f"parallel realistic finalist cache missing research rank {rank}"
            ) from error

    def preserve_parallel_outputs(_output, _markdown_output, _work_dir):
        # The canonical main normally clears candidate files immediately before its
        # sequential execution. They were already cleared and regenerated above.
        return rejected_output, rejected_markdown

    _base._run_candidate = cached_run_candidate
    _base._clear_previous_validation_outputs = preserve_parallel_outputs
    try:
        return _base.main(base_argv)
    finally:
        _base._run_candidate = original_run_candidate
        _base._clear_previous_validation_outputs = original_clear_outputs


if __name__ == "__main__":
    raise SystemExit(main())
