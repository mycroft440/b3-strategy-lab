from __future__ import annotations

from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    if text.count(old) != 1:
        raise RuntimeError(f"{path}: expected one anchor, found {text.count(old)}")
    write(path, text.replace(old, new, 1))


def replace_between(path: str, start_marker: str, end_marker: str, replacement: str) -> None:
    text = read(path)
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"{path}: start marker missing: {start_marker!r}")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"{path}: end marker missing: {end_marker!r}")
    write(path, text[:start] + replacement + text[end:])


def patch_validator() -> None:
    path = "scripts/validate_matrix_top_realistic.py"
    replace_once(
        path,
        'DEFAULT_MARKDOWN = Path("reports/REALISTIC_TOP_10.md")\n',
        'DEFAULT_MARKDOWN = Path("reports/REALISTIC_TOP_10.md")\n'
        'DEFAULT_EXECUTION_PRICES = ROOT / "data/execution/b3_standard_fractional_open.csv"\n'
        'DEFAULT_FEE_SCHEDULE = ROOT / "data/fees/b3_equity_fee_schedule.json"\n'
        'DEFAULT_BASE_SLIPPAGE_BPS = 10.0\n'
        'DEFAULT_PARTICIPATION_BPS_AT_1PCT = 5.0\n'
        'DEFAULT_MAX_SLIPPAGE_BPS = 100.0\n',
    )

    anchor = '''def _csv_rows(path: Path) -> list[dict[str, str]]:\n    with path.open(newline="", encoding="utf-8") as file:\n        return list(csv.DictReader(file))\n\n\n'''
    helpers = r'''def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _base_execution_ticker(ticker: str, market_type: str) -> str:
    value = ticker.strip().upper()
    if (
        market_type == "020"
        and value.endswith("F")
        and len(value) >= 3
        and value[-2].isdigit()
    ):
        return value[:-1]
    return value


def _execution_source(
    path: Path,
) -> dict[tuple[str, str, str], tuple[float, float]]:
    result: dict[tuple[str, str, str], tuple[float, float]] = {}
    for row in _csv_rows(path):
        value_date = str(row.get("date", ""))[:10]
        market_type = str(row.get("market_type", ""))
        ticker = _base_execution_ticker(str(row.get("ticker", "")), market_type)
        source_open = float(row.get("open", "nan"))
        financial_volume = float(row.get("financial_volume", "nan"))
        if (
            not value_date
            or not ticker
            or market_type not in {"010", "020"}
            or not math.isfinite(source_open)
            or source_open <= 0
            or not math.isfinite(financial_volume)
            or financial_volume <= 0
        ):
            raise ValueError("invalid certified execution-price row")
        key = (value_date, ticker, market_type)
        if key in result:
            raise ValueError(f"duplicate certified execution-price row: {key}")
        result[key] = (source_open, financial_volume)
    if not result:
        raise ValueError("certified execution-price source is empty")
    return result


def _fee_rules(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_rules = payload.get("rules")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise ValueError("fee schedule must contain non-empty rules")
    result: list[dict[str, object]] = []
    for raw in raw_rules:
        if not isinstance(raw, dict):
            raise ValueError("invalid fee rule")
        start = str(raw.get("start", ""))[:10]
        end = str(raw.get("end", ""))[:10]
        datetime.fromisoformat(start)
        datetime.fromisoformat(end)
        b3_bps = float(raw.get("b3_bps", "nan"))
        brokerage_fixed = float(raw.get("brokerage_fixed", 0.0))
        if (
            start > end
            or not math.isfinite(b3_bps)
            or b3_bps < 0
            or not math.isfinite(brokerage_fixed)
            or brokerage_fixed < 0
        ):
            raise ValueError("invalid fee rule economics")
        result.append(
            {
                "start": start,
                "end": end,
                "b3_bps": b3_bps,
                "brokerage_fixed": brokerage_fixed,
                "quality": str(raw.get("quality", "")),
            }
        )
    return result


def _expected_fee(
    rules: list[dict[str, object]], value_date: str, notional: float
) -> tuple[float, str]:
    matches = [
        rule
        for rule in rules
        if str(rule["start"]) <= value_date <= str(rule["end"])
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one fee rule for {value_date}; found {len(matches)}"
        )
    rule = matches[0]
    return (
        notional * float(rule["b3_bps"]) / 10_000
        + float(rule["brokerage_fixed"]),
        str(rule["quality"]),
    )


'''
    replace_once(path, anchor, helpers)

    old_signature = '''def _artifact_binding_issues(\n    payload: dict[str, object],\n    *,\n    curve_path: Path,\n    trades_path: Path,\n    cash_path: Path,\n    tax_path: Path | None = None,\n) -> list[str]:\n'''
    new_signature = '''def _artifact_binding_issues(\n    payload: dict[str, object],\n    *,\n    curve_path: Path,\n    trades_path: Path,\n    cash_path: Path,\n    tax_path: Path | None = None,\n    execution_prices_path: Path | None = None,\n    fee_schedule_path: Path | None = None,\n    base_slippage_bps: float = DEFAULT_BASE_SLIPPAGE_BPS,\n    participation_bps_at_1pct: float = DEFAULT_PARTICIPATION_BPS_AT_1PCT,\n    max_slippage_bps: float = DEFAULT_MAX_SLIPPAGE_BPS,\n) -> list[str]:\n'''
    replace_once(path, old_signature, new_signature)

    trade_start = '''    try:\n        if len(trades) != int(payload["trades"]):\n'''
    cash_start = '''    try:\n        ledger_distributions = sum(float(row["net"]) for row in cash)\n'''
    new_trade = r'''    execution_source: dict[tuple[str, str, str], tuple[float, float]] = {}
    if execution_prices_path is not None:
        try:
            execution_source = _execution_source(execution_prices_path)
        except (OSError, csv.Error, UnicodeError, ValueError, json.JSONDecodeError):
            issues.append("invalid_execution_price_source")

    fee_rules: list[dict[str, object]] = []
    if fee_schedule_path is not None:
        try:
            fee_rules = _fee_rules(fee_schedule_path)
        except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
            issues.append("invalid_fee_schedule_source")

    try:
        if len(trades) != int(payload["trades"]):
            issues.append("trade_ledger_count_mismatch")
        trade_start_date = datetime.fromisoformat(str(payload["start"])[:10]).date()
        trade_end_date = datetime.fromisoformat(str(payload["end"])[:10]).date()
        previous_trade_date = None
        for row in trades:
            ticker = str(row.get("ticker", "")).strip().upper()
            side = str(row.get("side", "")).upper()
            market_type = str(row.get("market_type", ""))
            try:
                value_date = datetime.fromisoformat(
                    str(row.get("date", ""))[:10]
                ).date()
                raw_shares = float(row.get("shares", "nan"))
                if not math.isfinite(raw_shares) or not raw_shares.is_integer():
                    raise ValueError("shares must be an integer")
                shares = int(raw_shares)
                raw_open = float(row.get("raw_open", "nan"))
                execution_price = float(row.get("execution_price", "nan"))
                notional = float(row.get("notional", "nan"))
                fee = float(row.get("fee", "nan"))
                slippage = float(row.get("slippage_bps", "nan"))
                realized_gain = float(row.get("realized_gain", "nan"))
            except (TypeError, ValueError, OverflowError):
                issues.append("invalid_trade_execution_leg")
                continue

            if not ticker:
                issues.append("trade_ticker_missing")
            if value_date < trade_start_date or value_date > trade_end_date:
                issues.append("trade_date_outside_candidate_period")
            if previous_trade_date is not None and value_date < previous_trade_date:
                issues.append("trade_ledger_date_order_mismatch")
            previous_trade_date = value_date

            if (
                side not in {"BUY", "SELL"}
                or market_type not in {"010", "020"}
                or shares <= 0
                or not all(
                    math.isfinite(value)
                    for value in (
                        raw_open,
                        execution_price,
                        notional,
                        fee,
                        slippage,
                        realized_gain,
                    )
                )
                or raw_open <= 0
                or execution_price <= 0
                or notional <= 0
                or fee < 0
                or not (0 <= slippage < 10_000)
            ):
                issues.append("invalid_trade_execution_leg")
                continue

            if market_type == "010" and shares % 100 != 0:
                issues.append("invalid_standard_market_lot")
            if market_type == "020" and not 1 <= shares < 100:
                issues.append("invalid_fractional_market_lot")
            if side == "BUY" and not math.isclose(
                realized_gain, 0.0, rel_tol=0.0, abs_tol=1e-10
            ):
                issues.append("buy_realized_gain_nonzero")

            recorded_expected_execution = raw_open * (
                1.0 + slippage / 10_000
                if side == "BUY"
                else 1.0 - slippage / 10_000
            )
            if not math.isclose(
                execution_price,
                recorded_expected_execution,
                rel_tol=1e-9,
                abs_tol=1e-8,
            ):
                issues.append("trade_slippage_execution_price_mismatch")
            if not math.isclose(
                notional,
                shares * execution_price,
                rel_tol=1e-9,
                abs_tol=1e-6,
            ):
                issues.append("trade_notional_mismatch")

            if execution_prices_path is not None and execution_source:
                key = (value_date.isoformat(), ticker, market_type)
                source_quote = execution_source.get(key)
                if source_quote is None:
                    issues.append("trade_execution_source_missing")
                else:
                    source_open, financial_volume = source_quote
                    if not math.isclose(
                        raw_open, source_open, rel_tol=1e-10, abs_tol=1e-8
                    ):
                        issues.append("trade_raw_open_source_mismatch")
                    raw_notional = shares * source_open
                    participation = raw_notional / financial_volume
                    expected_slippage = min(
                        max_slippage_bps,
                        base_slippage_bps
                        + max(
                            0.0,
                            participation_bps_at_1pct * (participation / 0.01),
                        ),
                    )
                    if not math.isclose(
                        slippage,
                        expected_slippage,
                        rel_tol=1e-9,
                        abs_tol=1e-8,
                    ):
                        issues.append("trade_slippage_model_mismatch")
                    source_expected_execution = source_open * (
                        1.0 + expected_slippage / 10_000
                        if side == "BUY"
                        else 1.0 - expected_slippage / 10_000
                    )
                    if not math.isclose(
                        execution_price,
                        source_expected_execution,
                        rel_tol=1e-9,
                        abs_tol=1e-8,
                    ):
                        issues.append("trade_execution_source_model_mismatch")

            if fee_schedule_path is not None and fee_rules:
                try:
                    expected_fee, fee_quality = _expected_fee(
                        fee_rules, value_date.isoformat(), notional
                    )
                    if fee_quality != "official":
                        issues.append("trade_fee_rule_not_official")
                    if not math.isclose(
                        fee, expected_fee, rel_tol=1e-9, abs_tol=1e-8
                    ):
                        issues.append("trade_fee_schedule_mismatch")
                except (KeyError, TypeError, ValueError):
                    issues.append("trade_fee_rule_missing_or_ambiguous")

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
    except (KeyError, TypeError, ValueError, OverflowError):
        issues.append("invalid_trade_ledger")
'''
    replace_between(path, trade_start, cash_start, new_trade)

    cash_end = '''\n    if tax_path is None:\n        return sorted(set(issues))\n'''
    new_cash = r'''    try:
        cash_start_date = datetime.fromisoformat(str(payload["start"])[:10]).date()
        cash_end_date = datetime.fromisoformat(str(payload["end"])[:10]).date()
        previous_cash_date = None
        for row in cash:
            value_date = datetime.fromisoformat(str(row.get("date", ""))[:10]).date()
            ticker = str(row.get("ticker", "")).strip().upper()
            label = str(row.get("label", "")).strip().upper()
            raw_shares = float(row.get("shares_entitled", "nan"))
            gross = float(row.get("gross", "nan"))
            tax_value = float(row.get("tax", "nan"))
            net = float(row.get("net", "nan"))
            if (
                not math.isfinite(raw_shares)
                or not raw_shares.is_integer()
                or raw_shares <= 0
                or not ticker
                or label not in {"DIVIDENDO", "DIVIDEND", "JCP", "JSCP"}
                or not all(math.isfinite(value) for value in (gross, tax_value, net))
                or gross < 0
                or tax_value < 0
                or net < 0
            ):
                issues.append("invalid_cash_ledger_row")
                continue
            if value_date < cash_start_date or value_date > cash_end_date:
                issues.append("cash_ledger_date_outside_candidate_period")
            if previous_cash_date is not None and value_date < previous_cash_date:
                issues.append("cash_ledger_date_order_mismatch")
            previous_cash_date = value_date
            if not math.isclose(
                net, gross - tax_value, rel_tol=1e-9, abs_tol=1e-8
            ):
                issues.append("cash_ledger_net_identity_mismatch")
            expected_tax = 0.0
            if label in {"JCP", "JSCP"}:
                expected_tax = gross * (
                    0.175 if value_date.isoformat() >= "2026-01-01" else 0.15
                )
            if not math.isclose(
                tax_value, expected_tax, rel_tol=1e-9, abs_tol=1e-8
            ):
                issues.append("cash_ledger_withholding_mismatch")

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
    except (KeyError, TypeError, ValueError, OverflowError):
        issues.append("invalid_cash_ledger")
'''
    replace_between(path, cash_start, cash_end, new_cash)

    replace_once(
        path,
        '    required_tax_columns = {"month", "tax_due", "irrf_withheld_month"}\n',
        '    required_tax_columns = {\n'
        '        "month",\n'
        '        "sales",\n'
        '        "realized_gain",\n'
        '        "tax_due",\n'
        '        "irrf_withheld_month",\n'
        '    }\n',
    )

    tax_anchor = '''        try:\n            tax_months = [str(row["month"]) for row in tax]\n'''
    tax_insert = r'''        try:
            sell_sales_by_month: dict[str, float] = {}
            sell_gain_by_month: dict[str, float] = {}
            for row in trades:
                if str(row.get("side", "")).upper() != "SELL":
                    continue
                month = str(row.get("date", ""))[:7]
                sell_sales_by_month[month] = sell_sales_by_month.get(month, 0.0) + float(
                    row["notional"]
                )
                sell_gain_by_month[month] = sell_gain_by_month.get(month, 0.0) + float(
                    row["realized_gain"]
                )
            for row in tax:
                month = str(row["month"])
                sales = float(row["sales"])
                realized_gain = float(row["realized_gain"])
                tax_due = float(row["tax_due"])
                irrf = float(row["irrf_withheld_month"])
                if (
                    len(month) != 7
                    or month[4:5] != "-"
                    or not all(
                        math.isfinite(value)
                        for value in (sales, realized_gain, tax_due, irrf)
                    )
                    or sales < 0
                    or tax_due < 0
                    or irrf < 0
                ):
                    issues.append("invalid_tax_ledger_values")
                    continue
                if not math.isclose(
                    sales,
                    sell_sales_by_month.get(month, 0.0),
                    rel_tol=1e-9,
                    abs_tol=1e-8,
                ):
                    issues.append("tax_ledger_sales_trade_mismatch")
                if not math.isclose(
                    realized_gain,
                    sell_gain_by_month.get(month, 0.0),
                    rel_tol=1e-9,
                    abs_tol=1e-8,
                ):
                    issues.append("tax_ledger_realized_gain_trade_mismatch")
        except (KeyError, TypeError, ValueError, OverflowError):
            issues.append("invalid_tax_ledger_values")

        try:
            tax_months = [str(row["month"]) for row in tax]
'''
    replace_once(path, tax_anchor, tax_insert)

    run_start = '''def _run_candidate(\n'''
    validation_start = '''\ndef _validation_issues(\n'''
    old_run = read(path)
    start = old_run.index(run_start)
    end = old_run.index(validation_start, start)
    new_run = r'''def _run_candidate(
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
    # Rank is already required to be unique. Keeping untrusted strategy/management
    # strings out of the filesystem prevents candidate metadata from becoming a path.
    stem = f"candidate_{rank:02d}"
    summary = output_dir / f"{stem}.json"
    curve = output_dir / f"{stem}_curve.csv"
    trades = output_dir / f"{stem}_trades.csv"
    cash = output_dir / f"{stem}_cash.csv"
    tax = output_dir / f"{stem}_tax.csv"
    for artifact in (summary, curve, trades, cash, tax):
        artifact.unlink(missing_ok=True)
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
        "--base-slippage-bps",
        str(DEFAULT_BASE_SLIPPAGE_BPS),
        "--participation-bps-at-1pct",
        str(DEFAULT_PARTICIPATION_BPS_AT_1PCT),
        "--max-slippage-bps",
        str(DEFAULT_MAX_SLIPPAGE_BPS),
        "--execution-prices",
        str(DEFAULT_EXECUTION_PRICES),
        "--fee-schedule",
        str(DEFAULT_FEE_SCHEDULE),
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
    try:
        subprocess.run(command, cwd=ROOT, check=True)
    except subprocess.CalledProcessError as error:
        return {
            "_candidate_execution_error": f"exit_code={error.returncode}",
            "research_rank": rank,
            "research_strategy": strategy,
            "research_management": management,
        }
    try:
        payload = json.loads(summary.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return {
            "_candidate_artifact_error": error.__class__.__name__,
            "research_rank": rank,
            "research_strategy": strategy,
            "research_management": management,
        }
    if not isinstance(payload, dict):
        return {
            "_candidate_artifact_error": "summary_not_object",
            "research_rank": rank,
            "research_strategy": strategy,
            "research_management": management,
        }
    payload["_artifact_binding_issues"] = _artifact_binding_issues(
        payload,
        curve_path=curve,
        trades_path=trades,
        cash_path=cash,
        tax_path=tax,
        execution_prices_path=DEFAULT_EXECUTION_PRICES,
        fee_schedule_path=DEFAULT_FEE_SCHEDULE,
        base_slippage_bps=DEFAULT_BASE_SLIPPAGE_BPS,
        participation_bps_at_1pct=DEFAULT_PARTICIPATION_BPS_AT_1PCT,
        max_slippage_bps=DEFAULT_MAX_SLIPPAGE_BPS,
    )
    payload["research_rank"] = rank
    payload["research_strategy"] = strategy
    payload["research_management"] = management
    return payload

'''
    text = read(path)
    write(path, text[:start] + new_run + text[end + 1 :])

    replace_once(
        path,
        '''    if payload.get("_candidate_execution_error"):\n        return ["candidate_execution_failed:" + str(payload["_candidate_execution_error"])]\n''',
        '''    if payload.get("_candidate_execution_error"):\n        return ["candidate_execution_failed:" + str(payload["_candidate_execution_error"])]\n    if payload.get("_candidate_artifact_error"):\n        return ["candidate_artifact_invalid:" + str(payload["_candidate_artifact_error"])]\n''',
    )

    main_marker = '\ndef main(argv: list[str] | None = None) -> int:\n'
    helper = r'''
def _validated_finalists(
    candidates: object, limit: int
) -> list[tuple[int, str, str]]:
    if not isinstance(candidates, list):
        raise ValueError("Candidate file top_10 must be a list.")
    if len(candidates) < limit:
        raise ValueError(
            f"Candidate file contains only {len(candidates)} finalists; requested {limit}."
        )
    result: list[tuple[int, str, str]] = []
    pairs: set[tuple[str, str]] = set()
    for expected_rank, raw in enumerate(candidates[:limit], start=1):
        if not isinstance(raw, dict):
            raise ValueError("Invalid candidate row.")
        raw_rank = raw.get("rank")
        if isinstance(raw_rank, bool):
            raise ValueError("Candidate rank must be a positive integer.")
        try:
            rank_value = float(raw_rank)
        except (TypeError, ValueError):
            raise ValueError("Candidate rank must be a positive integer.") from None
        if not math.isfinite(rank_value) or not rank_value.is_integer():
            raise ValueError("Candidate rank must be a positive integer.")
        rank = int(rank_value)
        if rank != expected_rank:
            raise ValueError(
                f"Finalist ranks must be exactly 1..{limit} in order; "
                f"expected {expected_rank}, found {rank}."
            )
        strategy = str(raw.get("trading_strategy", "")).strip()
        management = str(raw.get("management_strategy", "")).strip()
        if not strategy or not management:
            raise ValueError("Candidate strategy and management must be non-empty.")
        pair = (strategy.casefold(), management.casefold())
        if pair in pairs:
            raise ValueError(
                f"Duplicate finalist strategy/management pair: {strategy} + {management}"
            )
        pairs.add(pair)
        result.append((rank, strategy, management))
    return result


def _clear_previous_validation_outputs(
    output: Path, markdown_output: Path, work_dir: Path
) -> tuple[Path, Path]:
    rejected_output = output.with_name(f"{output.stem}_REJECTED{output.suffix}")
    rejected_markdown = markdown_output.with_name(
        f"{markdown_output.stem}_REJECTED{markdown_output.suffix}"
    )
    for artifact in (output, markdown_output, rejected_output, rejected_markdown):
        artifact.unlink(missing_ok=True)
    if work_dir.exists():
        for artifact in work_dir.iterdir():
            if artifact.is_file() and artifact.name.startswith("candidate_"):
                artifact.unlink()
    return rejected_output, rejected_markdown

'''
    text = read(path)
    if text.count(main_marker) != 1:
        raise RuntimeError("validator main marker changed")
    write(path, text.replace(main_marker, helper + main_marker, 1))

    old_source_block = '''    source = json.loads(args.candidates.read_text(encoding="utf-8"))\n    period = source.get("period") or {}\n    start = str(period.get("start", ""))\n    end = str(period.get("end", ""))\n    initial_cash = float(source.get("initial_cash", 0.0))\n    candidates = source.get("top_10")\n    if (\n        not start\n        or not end\n        or not math.isfinite(initial_cash)\n        or initial_cash <= 0\n        or not isinstance(candidates, list)\n    ):\n        raise ValueError("Candidate file is missing period, initial_cash or top_10.")\n\n    validated: list[dict[str, object]] = []\n    excluded: list[dict[str, object]] = []\n    for raw in candidates[: args.limit]:\n        if not isinstance(raw, dict):\n            raise ValueError("Invalid candidate row.")\n        rank = int(raw["rank"])\n        strategy = str(raw["trading_strategy"])\n        management = str(raw["management_strategy"])\n'''
    new_source_block = '''    rejected_output, rejected_markdown = _clear_previous_validation_outputs(\n        args.output, args.markdown_output, args.work_dir\n    )\n    source = json.loads(args.candidates.read_text(encoding="utf-8"))\n    period = source.get("period") or {}\n    start = str(period.get("start", ""))\n    end = str(period.get("end", ""))\n    try:\n        initial_cash = float(source.get("initial_cash", 0.0))\n        start_date = datetime.fromisoformat(start)\n        end_date = datetime.fromisoformat(end)\n    except (TypeError, ValueError):\n        raise ValueError("Candidate file has an invalid period or initial_cash.") from None\n    candidates = source.get("top_10")\n    if (\n        not math.isfinite(initial_cash)\n        or initial_cash <= 0\n        or end_date < start_date\n    ):\n        raise ValueError("Candidate file has an invalid period or initial_cash.")\n    required_valid = _required_valid_count(args.limit, args.require_valid)\n    finalists = _validated_finalists(candidates, required_valid)\n\n    validated: list[dict[str, object]] = []\n    excluded: list[dict[str, object]] = []\n    for rank, strategy, management in finalists:\n'''
    replace_once(path, old_source_block, new_source_block)

    replace_once(
        path,
        '''    required_valid = _required_valid_count(args.limit, args.require_valid)\n    if len(candidates) < required_valid:\n        raise ValueError(\n            f"Candidate file contains only {len(candidates)} finalists; "\n            f"requested {required_valid}."\n        )\n    if len(ranking) < required_valid:\n''',
        '''    if len(ranking) < required_valid:\n''',
    )
    replace_once(
        path,
        '''        rejected_output = args.output.with_name(\n            f"{args.output.stem}_REJECTED{args.output.suffix}"\n        )\n        rejected_markdown = args.markdown_output.with_name(\n            f"{args.markdown_output.stem}_REJECTED{args.markdown_output.suffix}"\n        )\n''',
        '',
    )


def patch_realistic_runner_policy() -> None:
    path = "scripts/backtest_strategy_management_realistic.py"
    old = '''    payload["bonus_tax_basis_policy"] = (\n        "Receita Federal distinguishes stock bonuses from ordinary splits for acquisition "\n        "cost. The current engine does not yet apply issuer-specific bonus cost to weighted "\n        "average tax basis. Therefore any sale on/after a bonus date, including after a "\n        "source-backed ticker rename, is tax-basis-uncertain and cannot support a certified "\n        "deterministic replay."\n    )\n'''
    new = '''    payload["bonus_tax_basis_policy"] = (\n        "Receita Federal distinguishes stock bonuses from ordinary splits for acquisition "\n        "cost. The current engine does not yet apply issuer-specific bonus cost to weighted "\n        "average tax basis. Certification is therefore blocked only when the simulated "\n        "account actually held the affected position across the bonus date and later sells "\n        "those shares, following source-backed 1:1 ticker renames. A bonus before the replay "\n        "or before the first simulated purchase does not taint later-acquired shares."\n    )\n    payload["execution_model"] = {\n        "execution_prices": str(args.execution_prices),\n        "fee_schedule": str(args.fee_schedule),\n        "base_slippage_bps": float(args.base_slippage_bps),\n        "participation_bps_at_1pct": float(args.participation_bps_at_1pct),\n        "max_slippage_bps": float(args.max_slippage_bps),\n    }\n'''
    replace_once(path, old, new)


def patch_existing_test_fixtures() -> None:
    path = "tests/test_realistic_ranking_gate.py"
    replace_once(
        path,
        '            "distribution_tax_paid": 1.0,\n',
        '            "distribution_tax_paid": 0.0,\n',
    )
    replace_once(
        path,
        '''                "date,side,ticker,shares,market_type,raw_open,execution_price,notional,fee,slippage_bps\\n"\n                "2018-01-02,BUY,AAA3,10,020,10,10.01,100.1,1,10\\n"\n                "2018-01-03,SELL,AAA3,10,020,11,10.989,109.89,2,10\\n",\n''',
        '''                "date,side,ticker,shares,market_type,raw_open,execution_price,notional,fee,slippage_bps,realized_gain\\n"\n                "2018-01-02,BUY,AAA3,10,020,10,10.01,100.1,1,10,0\\n"\n                "2018-01-03,SELL,AAA3,10,020,11,10.989,109.89,2,10,7.89\\n",\n''',
    )
    replace_once(
        path,
        '            cash.write_text("date,net,tax\\n2018-01-03,5,1\\n", encoding="utf-8")\n',
        '            cash.write_text(\n'
        '                "date,ticker,label,shares_entitled,gross,tax,net\\n"\n'
        '                "2018-01-03,AAA3,DIVIDENDO,10,5,0,5\\n",\n'
        '                encoding="utf-8",\n'
        '            )\n',
    )

    path = "tests/test_realistic_artifact_reconciliation.py"
    replace_once(
        path,
        '        trades.write_text("date,fee\\n", encoding="utf-8")\n',
        '        trades.write_text(\n'
        '            "date,side,ticker,shares,market_type,raw_open,execution_price,"\n'
        '            "notional,fee,slippage_bps,realized_gain\\n",\n'
        '            encoding="utf-8",\n'
        '        )\n',
    )
    replace_once(
        path,
        '''            "month,tax_due,irrf_withheld_month\\n"\n            "2023-12,10,1\\n"\n            "2024-01,5,0\\n",\n''',
        '''            "month,sales,realized_gain,tax_due,irrf_withheld_month\\n"\n            "2023-12,0,0,10,1\\n"\n            "2024-01,0,0,5,0\\n",\n''',
    )
    replace_once(
        path,
        '            tax.write_text("month,tax_due,irrf_withheld_month\\n", encoding="utf-8")\n',
        '            tax.write_text(\n'
        '                "month,sales,realized_gain,tax_due,irrf_withheld_month\\n",\n'
        '                encoding="utf-8",\n'
        '            )\n',
    )
    replace_once(
        path,
        '                "month,tax_due\\n2023-12,10\\n2024-01,5\\n",\n',
        '                "month,sales,realized_gain,tax_due\\n"\n'
        '                "2023-12,0,0,10\\n2024-01,0,0,5\\n",\n',
    )
    replace_once(
        path,
        '''                "month,tax_due,irrf_withheld_month\\n"\n                "2023-12,10,1\\n"\n                "2023-12,5,0\\n",\n''',
        '''                "month,sales,realized_gain,tax_due,irrf_withheld_month\\n"\n                "2023-12,0,0,10,1\\n"\n                "2023-12,0,0,5,0\\n",\n''',
    )


def write_second_review_tests() -> None:
    Path("tests/test_second_review_hardening.py").write_text(
        r'''from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.validate_matrix_top_realistic import (
    _artifact_binding_issues,
    _clear_previous_validation_outputs,
    _run_candidate,
    _validated_finalists,
)


class SecondReviewHardeningTests(unittest.TestCase):
    def _trade_fixture(self, root: Path):
        curve = root / "curve.csv"
        trades = root / "trades.csv"
        cash = root / "cash.csv"
        execution = root / "execution.csv"
        fees = root / "fees.json"
        curve.write_text(
            "date,equity\n2018-01-02,1000\n2018-01-03,1000\n",
            encoding="utf-8",
        )
        cash.write_text("", encoding="utf-8")
        source_open = 10.0
        shares = 10
        financial_volume = 100_000.0
        raw_notional = source_open * shares
        expected_slippage = 10.0 + 5.0 * ((raw_notional / financial_volume) / 0.01)
        execution_price = source_open * (1.0 + expected_slippage / 10_000)
        notional = shares * execution_price
        fee = notional * 3.2 / 10_000
        trades.write_text(
            "date,side,ticker,shares,market_type,raw_open,execution_price,notional,fee,slippage_bps,realized_gain\n"
            f"2018-01-02,BUY,AAA3,{shares},020,{source_open},{execution_price},{notional},{fee},{expected_slippage},0\n",
            encoding="utf-8",
        )
        execution.write_text(
            "date,ticker,market_type,open,close,financial_volume\n"
            f"2018-01-02,AAA3F,020,{source_open},10.1,{financial_volume}\n",
            encoding="utf-8",
        )
        fees.write_text(
            json.dumps(
                {
                    "rules": [
                        {
                            "start": "2018-01-01",
                            "end": "2018-12-31",
                            "b3_bps": 3.2,
                            "brokerage_fixed": 0.0,
                            "quality": "official",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        payload = {
            "start": "2018-01-02",
            "end": "2018-01-03",
            "final_equity": 1000.0,
            "trades": 1,
            "fees_paid": fee,
            "distributions_net": 0.0,
            "distribution_tax_paid": 0.0,
        }
        return payload, curve, trades, cash, execution, fees

    def _issues(self, fixture):
        payload, curve, trades, cash, execution, fees = fixture
        return _artifact_binding_issues(
            payload,
            curve_path=curve,
            trades_path=trades,
            cash_path=cash,
            execution_prices_path=execution,
            fee_schedule_path=fees,
        )

    def test_trade_leg_is_bound_to_source_slippage_notional_and_fee(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self._trade_fixture(Path(temporary))
            self.assertEqual(self._issues(fixture), [])

    def test_consistent_but_wrong_slippage_is_rejected_against_source_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self._trade_fixture(Path(temporary))
            payload, _curve, trades, _cash, _execution, _fees = fixture
            source_open = 10.0
            shares = 10
            bad_slippage = 20.0
            execution_price = source_open * (1 + bad_slippage / 10_000)
            notional = shares * execution_price
            bad_fee = notional * 3.2 / 10_000
            trades.write_text(
                "date,side,ticker,shares,market_type,raw_open,execution_price,notional,fee,slippage_bps,realized_gain\n"
                f"2018-01-02,BUY,AAA3,10,020,10,{execution_price},{notional},{bad_fee},{bad_slippage},0\n",
                encoding="utf-8",
            )
            payload["fees_paid"] = bad_fee
            self.assertIn("trade_slippage_model_mismatch", self._issues(fixture))

    def test_notional_lot_source_open_and_fee_tampering_are_each_blocking(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self._trade_fixture(root)
            payload, _curve, trades, _cash, _execution, _fees = fixture
            original = trades.read_text(encoding="utf-8")

            header, row = original.strip().split("\n")
            parts = row.split(",")
            parts[7] = str(float(parts[7]) + 1.0)
            trades.write_text(header + "\n" + ",".join(parts) + "\n", encoding="utf-8")
            self.assertIn("trade_notional_mismatch", self._issues(fixture))

            trades.write_text(original, encoding="utf-8")
            parts = row.split(",")
            parts[5] = "10.25"
            trades.write_text(header + "\n" + ",".join(parts) + "\n", encoding="utf-8")
            self.assertIn("trade_raw_open_source_mismatch", self._issues(fixture))

            trades.write_text(original, encoding="utf-8")
            parts = row.split(",")
            parts[8] = str(float(parts[8]) + 0.5)
            trades.write_text(header + "\n" + ",".join(parts) + "\n", encoding="utf-8")
            payload["fees_paid"] = float(parts[8])
            self.assertIn("trade_fee_schedule_mismatch", self._issues(fixture))

            standard = row.split(",")
            standard[4] = "010"
            standard[3] = "10"
            trades.write_text(header + "\n" + ",".join(standard) + "\n", encoding="utf-8")
            self.assertIn("invalid_standard_market_lot", self._issues(fixture))

    def test_cash_row_net_and_withholding_are_independently_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            curve = root / "curve.csv"
            trades = root / "trades.csv"
            cash = root / "cash.csv"
            curve.write_text(
                "date,equity\n2025-01-02,1000\n2025-01-03,1000\n",
                encoding="utf-8",
            )
            trades.write_text(
                "date,side,ticker,shares,market_type,raw_open,execution_price,notional,fee,slippage_bps,realized_gain\n",
                encoding="utf-8",
            )
            cash.write_text(
                "date,ticker,label,shares_entitled,gross,tax,net\n"
                "2025-01-03,AAA3,JCP,10,100,14,86\n",
                encoding="utf-8",
            )
            payload = {
                "start": "2025-01-02",
                "end": "2025-01-03",
                "final_equity": 1000.0,
                "trades": 0,
                "fees_paid": 0.0,
                "distributions_net": 86.0,
                "distribution_tax_paid": 14.0,
            }
            issues = _artifact_binding_issues(
                payload,
                curve_path=curve,
                trades_path=trades,
                cash_path=cash,
            )
            self.assertIn("cash_ledger_withholding_mismatch", issues)

    def test_tax_sales_and_realized_gain_are_bound_to_sell_ledger(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            curve = root / "curve.csv"
            trades = root / "trades.csv"
            cash = root / "cash.csv"
            tax = root / "tax.csv"
            curve.write_text(
                "date,equity\n2024-01-02,1000\n2024-01-03,1000\n",
                encoding="utf-8",
            )
            trades.write_text(
                "date,side,ticker,shares,market_type,raw_open,execution_price,notional,fee,slippage_bps,realized_gain\n"
                "2024-01-03,SELL,AAA3,10,020,10,9.99,99.9,0,10,5\n",
                encoding="utf-8",
            )
            cash.write_text("", encoding="utf-8")
            tax.write_text(
                "month,sales,realized_gain,tax_due,irrf_withheld_month\n"
                "2024-01,100,6,0,0\n",
                encoding="utf-8",
            )
            payload = {
                "start": "2024-01-02",
                "end": "2024-01-03",
                "initial_cash": 1000.0,
                "final_equity": 1000.0,
                "max_drawdown": 0.0,
                "annual_volatility": 0.0,
                "sharpe": 0.0,
                "average_annual_return": 0.0,
                "trades": 1,
                "fees_paid": 0.0,
                "distributions_net": 0.0,
                "distribution_tax_paid": 0.0,
                "ordinary_income_tax_paid": 0.0,
                "outstanding_accrued_tax_liability": 0.0,
            }
            issues = _artifact_binding_issues(
                payload,
                curve_path=curve,
                trades_path=trades,
                cash_path=cash,
                tax_path=tax,
            )
            self.assertIn("tax_ledger_sales_trade_mismatch", issues)
            self.assertIn("tax_ledger_realized_gain_trade_mismatch", issues)

    def test_finalist_rows_must_be_exact_unique_top_n(self):
        good = [
            {
                "rank": index,
                "trading_strategy": f"strategy_{index}",
                "management_strategy": f"management_{index}",
            }
            for index in range(1, 4)
        ]
        self.assertEqual(len(_validated_finalists(good, 3)), 3)
        duplicate = [dict(item) for item in good]
        duplicate[2]["trading_strategy"] = duplicate[1]["trading_strategy"]
        duplicate[2]["management_strategy"] = duplicate[1]["management_strategy"]
        with self.assertRaisesRegex(ValueError, "Duplicate finalist"):
            _validated_finalists(duplicate, 3)
        wrong_rank = [dict(item) for item in good]
        wrong_rank[1]["rank"] = 3
        with self.assertRaisesRegex(ValueError, "exactly 1..3"):
            _validated_finalists(wrong_rank, 3)

    def test_stale_candidate_summary_cannot_survive_success_without_new_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            stale = work / "candidate_01.json"
            stale.write_text('{"validity":"STALE"}', encoding="utf-8")
            with patch("scripts.validate_matrix_top_realistic.subprocess.run"):
                payload = _run_candidate(
                    rank=1,
                    strategy="buy_and_hold",
                    management="top1_momentum_lb63_skip0_trend0_vol21_equal_weekly_abs_cap1_adjusted",
                    start="2018-01-02",
                    end="2018-01-03",
                    initial_cash=1000.0,
                    output_dir=work,
                )
            self.assertEqual(payload.get("_candidate_artifact_error"), "FileNotFoundError")
            self.assertFalse(stale.exists())

    def test_canonical_and_rejected_outputs_are_cleared_before_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "REALISTIC_TOP_10.json"
            markdown = root / "REALISTIC_TOP_10.md"
            work = root / "candidates"
            work.mkdir()
            rejected = root / "REALISTIC_TOP_10_REJECTED.json"
            rejected_md = root / "REALISTIC_TOP_10_REJECTED.md"
            for path in (output, markdown, rejected, rejected_md, work / "candidate_old.json"):
                path.write_text("stale", encoding="utf-8")
            actual_rejected, actual_rejected_md = _clear_previous_validation_outputs(
                output, markdown, work
            )
            self.assertEqual(actual_rejected, rejected)
            self.assertEqual(actual_rejected_md, rejected_md)
            self.assertFalse(any(path.exists() for path in (output, markdown, rejected, rejected_md)))
            self.assertFalse((work / "candidate_old.json").exists())

    def test_production_workflow_matches_hardened_contract(self):
        workflow = Path(".github/workflows/full-matrix-backtest-hardened.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn('--require-valid "$TOP_N"', workflow)
        self.assertIn("reports/REALISTIC_TOP_10_REJECTED.json", workflow)
        self.assertIn("reports/REALISTIC_TOP_10_REJECTED.md", workflow)
        for obsolete in (
            ".github/workflows/fix-historical-issuer-refresh-once.yml",
            ".github/workflows/patch-freeze-preflight-once.yml",
            ".github/workflows/patch-pine-warmup-once.yml",
        ):
            self.assertFalse(Path(obsolete).exists(), obsolete)

    def test_bonus_policy_describes_only_held_through_bonus_risk(self):
        source = Path("scripts/backtest_strategy_management_realistic.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("actually held the affected position across the bonus date", source)
        self.assertIn('payload["execution_model"]', source)


if __name__ == "__main__":
    unittest.main()
''',
        encoding="utf-8",
    )


def patch_workflow_locally() -> None:
    path = ".github/workflows/full-matrix-backtest-hardened.yml"
    replace_once(path, '            --require-valid 1\n', '            --require-valid "$TOP_N"\n')
    replace_once(
        path,
        '''          reports/REALISTIC_TOP_10.json\n          reports/REALISTIC_TOP_10.md\n''',
        '''          reports/REALISTIC_TOP_10.json\n          reports/REALISTIC_TOP_10.md\n          reports/REALISTIC_TOP_10_REJECTED.json\n          reports/REALISTIC_TOP_10_REJECTED.md\n''',
    )
    for obsolete in (
        ".github/workflows/fix-historical-issuer-refresh-once.yml",
        ".github/workflows/patch-freeze-preflight-once.yml",
        ".github/workflows/patch-pine-warmup-once.yml",
    ):
        Path(obsolete).unlink(missing_ok=True)


def main() -> None:
    patch_validator()
    patch_realistic_runner_policy()
    patch_existing_test_fixtures()
    write_second_review_tests()
    patch_workflow_locally()
    print("second critical review fixes applied")


if __name__ == "__main__":
    main()
