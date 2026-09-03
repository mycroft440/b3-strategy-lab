from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace(path: str, old: str, new: str, *, count: int = 1) -> None:
    text = read(path)
    actual = text.count(old)
    if actual != count:
        raise RuntimeError(f"{path}: expected {count} patch anchor(s), found {actual}: {old[:120]!r}")
    write(path, text.replace(old, new, count))


def patch_metrics() -> None:
    path = "scripts/research_portfolio_allocation_core.py"
    replace(
        path,
        """    returns = [\n        equities[index] / equities[index - 1] - 1\n        for index in range(1, len(equities))\n        if equities[index - 1] > 0\n    ]\n""",
        """    if not equities or not dates or len(equities) != len(dates):\n        raise ValueError(\"equities/dates must be non-empty and aligned\")\n    if initial_cash <= 0 or not math.isfinite(initial_cash):\n        raise ValueError(\"initial_cash must be finite and positive\")\n    # Include capital-at-risk -> first close. Entry costs/slippage and first-session\n    # P&L are economically real and must contribute to Sharpe/volatility.\n    returns = [equities[0] / initial_cash - 1.0]\n    returns.extend(\n        equities[index] / equities[index - 1] - 1.0\n        for index in range(1, len(equities))\n        if equities[index - 1] > 0\n    )\n""",
    )
    replace(
        path,
        """    periods_per_year = (len(equities) - 1) / years if years > 0 else 252.0\n    peak = equities[0]\n""",
        """    # dates[0] is the first close while initial_cash is capital immediately before\n    # that first session. Add one calendar day only for risk-period annualization.\n    risk_years = years + 1 / 365.25\n    periods_per_year = len(returns) / risk_years if risk_years > 0 else 252.0\n    peak = initial_cash\n""",
    )


def patch_realistic_validator() -> None:
    path = "scripts/validate_matrix_top_realistic.py"
    text = read(path)
    old = """    returns = [\n        equities[index] / equities[index - 1] - 1.0\n        for index in range(1, len(equities))\n    ]\n"""
    new = """    returns = [equities[0] / initial_cash - 1.0]\n    returns.extend(\n        equities[index] / equities[index - 1] - 1.0\n        for index in range(1, len(equities))\n    )\n"""
    if text.count(old) != 1:
        raise RuntimeError("validate realistic: return-series anchor changed")
    text = text.replace(old, new, 1)
    old = """    periods_per_year = (len(equities) - 1) / years\n"""
    if text.count(old) != 1:
        raise RuntimeError("validate realistic: annualization anchor changed")
    text = text.replace(old, """    risk_years = years + 1 / 365.25\n    periods_per_year = len(returns) / risk_years\n""", 1)
    marker = """    if len(returns) >= 2:\n"""
    metric_start = text.index("def _curve_recalculated_metrics")
    metric_end = text.index("def _artifact_binding_issues", metric_start)
    pos = text.index(marker, metric_start, metric_end)
    drawdown = """    peak = initial_cash\n    max_drawdown = 0.0\n    for equity in equities:\n        peak = max(peak, equity)\n        if peak > 0:\n            max_drawdown = min(max_drawdown, equity / peak - 1.0)\n\n"""
    text = text[:pos] + drawdown + text[pos:]
    old = """        \"annual_volatility\": annual_volatility,\n        \"sharpe\": sharpe,\n        \"average_annual_return\": (\n"""
    new = """        \"annual_volatility\": annual_volatility,\n        \"sharpe\": sharpe,\n        \"max_drawdown\": max_drawdown,\n        \"average_annual_return\": (\n"""
    if text.count(old) != 1:
        raise RuntimeError("validate realistic: metric return anchor changed")
    text = text.replace(old, new, 1)
    old = """        metric_issue_names = {\n            \"annual_volatility\": \"curve_annual_volatility_mismatch\",\n            \"sharpe\": \"curve_sharpe_mismatch\",\n            \"average_annual_return\": \"curve_average_annual_return_mismatch\",\n        }\n"""
    new = """        metric_issue_names = {\n            \"annual_volatility\": \"curve_annual_volatility_mismatch\",\n            \"sharpe\": \"curve_sharpe_mismatch\",\n            \"max_drawdown\": \"curve_max_drawdown_mismatch\",\n            \"average_annual_return\": \"curve_average_annual_return_mismatch\",\n        }\n"""
    if text.count(old) != 1:
        raise RuntimeError("validate realistic: metric binding anchor changed")
    text = text.replace(old, new, 1)

    # Actual executed trades must be structurally reconcilable. The engine already
    # fails on missing 010/020 opens; this independent artifact gate proves every
    # recorded fill used an explicit market leg rather than a synthetic fallback.
    anchor = """    try:\n        if len(trades) != int(payload[\"trades\"]):\n            issues.append(\"trade_ledger_count_mismatch\")\n        ledger_fees = sum(float(row[\"fee\"]) for row in trades)\n"""
    replacement = """    try:\n        if len(trades) != int(payload[\"trades\"]):\n            issues.append(\"trade_ledger_count_mismatch\")\n        for row in trades:\n            side = str(row.get(\"side\", \"\")).upper()\n            market_type = str(row.get(\"market_type\", \"\"))\n            shares = int(row.get(\"shares\", \"0\"))\n            raw_open = float(row.get(\"raw_open\", \"nan\"))\n            execution_price = float(row.get(\"execution_price\", \"nan\"))\n            notional = float(row.get(\"notional\", \"nan\"))\n            fee = float(row.get(\"fee\", \"nan\"))\n            slippage = float(row.get(\"slippage_bps\", \"nan\"))\n            if (\n                side not in {\"BUY\", \"SELL\"}\n                or market_type not in {\"010\", \"020\"}\n                or shares <= 0\n                or not all(math.isfinite(value) for value in (raw_open, execution_price, notional, fee, slippage))\n                or raw_open <= 0\n                or execution_price <= 0\n                or notional <= 0\n                or fee < 0\n                or slippage < 0\n            ):\n                issues.append(\"invalid_trade_execution_leg\")\n                break\n        ledger_fees = sum(float(row[\"fee\"]) for row in trades)\n"""
    if text.count(anchor) != 1:
        raise RuntimeError("validate realistic: trade artifact anchor changed")
    text = text.replace(anchor, replacement, 1)

    old = """    subprocess.run(command, cwd=ROOT, check=True)\n    payload = json.loads(summary.read_text(encoding=\"utf-8\"))\n"""
    new = """    try:\n        subprocess.run(command, cwd=ROOT, check=True)\n    except subprocess.CalledProcessError as error:\n        return {\n            \"_candidate_execution_error\": f\"exit_code={error.returncode}\",\n            \"research_rank\": rank,\n            \"research_strategy\": strategy,\n            \"research_management\": management,\n        }\n    payload = json.loads(summary.read_text(encoding=\"utf-8\"))\n"""
    if text.count(old) != 1:
        raise RuntimeError("validate realistic: subprocess anchor changed")
    text = text.replace(old, new, 1)
    old = """    issues: list[str] = []\n    validity = str(payload.get(\"validity\", \"\"))\n"""
    new = """    issues: list[str] = []\n    if payload.get(\"_candidate_execution_error\"):\n        return [\"candidate_execution_failed:\" + str(payload[\"_candidate_execution_error\"])]\n    validity = str(payload.get(\"validity\", \"\"))\n"""
    if text.count(old) != 1:
        raise RuntimeError("validate realistic: validation anchor changed")
    text = text.replace(old, new, 1)

    old = """    if args.limit <= 0 or args.require_valid <= 0:\n        parser.error(\"--limit and --require-valid must be positive.\")\n"""
    new = """    if args.limit <= 0 or args.require_valid <= 0:\n        parser.error(\"--limit and --require-valid must be positive.\")\n    if args.require_valid > args.limit:\n        parser.error(\"--require-valid cannot exceed --limit.\")\n"""
    if text.count(old) != 1:
        raise RuntimeError("validate realistic: parser guard anchor changed")
    text = text.replace(old, new, 1)

    old = """    args.output.parent.mkdir(parents=True, exist_ok=True)\n    args.output.write_text(\n        json.dumps(result, indent=2, ensure_ascii=False) + \"\\n\",\n        encoding=\"utf-8\",\n    )\n    _write_markdown(result, args.markdown_output)\n    if len(ranking) < args.require_valid:\n        raise SystemExit(\n            f\"Only {len(ranking)} candidates passed realistic certification; \"\n            f\"required {args.require_valid}.\"\n        )\n"""
    new = """    if len(ranking) < args.require_valid:\n        result[\"result_classification\"] = \"REALISTIC_FINALIST_VALIDATION_REJECTED\"\n        result[\"validation_passed\"] = False\n        args.output.parent.mkdir(parents=True, exist_ok=True)\n        args.output.write_text(\n            json.dumps(result, indent=2, ensure_ascii=False) + \"\\n\",\n            encoding=\"utf-8\",\n        )\n        _write_markdown(result, args.markdown_output)\n        raise SystemExit(\n            f\"Only {len(ranking)} candidates passed realistic certification; \"\n            f\"required {args.require_valid}.\"\n        )\n    result[\"validation_passed\"] = True\n    args.output.parent.mkdir(parents=True, exist_ok=True)\n    args.output.write_text(\n        json.dumps(result, indent=2, ensure_ascii=False) + \"\\n\",\n        encoding=\"utf-8\",\n    )\n    _write_markdown(result, args.markdown_output)\n"""
    if text.count(old) != 1:
        raise RuntimeError("validate realistic: output classification anchor changed")
    text = text.replace(old, new, 1)
    write(path, text)


def patch_historical_cash() -> None:
    path = "scripts/sync_point_in_time_universe.py"
    replace(
        path,
        """    for issuer in historical_issuers:\n        payloads[issuer] = [{\"code\": issuer, \"stockDividends\": []}]\n""",
        """    for issuer in historical_issuers:\n        # This placeholder is valid only for the share-count/split extractor. It is\n        # deliberately marked unusable for cash distributions: absence of a current\n        # B3 payload is not evidence that a historical issuer paid zero dividends/JCP.\n        payloads[issuer] = [{\n            \"code\": issuer,\n            \"stockDividends\": [],\n            \"_historical_split_placeholder\": True,\n            \"_cash_dividends_source_available\": False,\n        }]\n""",
    )
    path = "b3_strategy_lab/cash_distributions.py"
    replace(
        path,
        """        if company is None:\n            issues.append({\"ticker\": ticker, \"issuer\": issuer, \"issue\": \"issuer_missing_in_b3_payload\"})\n            continue\n\n        quotes = sorted(quotes_by_ticker[ticker], key=lambda quote: quote.date)\n""",
        """        if company is None:\n            issues.append({\"ticker\": ticker, \"issuer\": issuer, \"issue\": \"issuer_missing_in_b3_payload\"})\n            continue\n        if company.get(\"_cash_dividends_source_available\") is False:\n            issues.append({\n                \"ticker\": ticker,\n                \"issuer\": issuer,\n                \"issue\": \"historical_cash_dividend_source_unavailable\",\n            })\n            continue\n\n        quotes = sorted(quotes_by_ticker[ticker], key=lambda quote: quote.date)\n""",
    )


def patch_bonus_tax_basis() -> None:
    path = "b3_strategy_lab/realistic_certification.py"
    text = read(path)
    start = text.index("def bonus_tax_basis_dependencies")
    end = text.index("\ndef terminal_month_tax_policy", start)
    old_fn = text[start:end]
    header_end = old_fn.index("    source = Path(split_evidence_path)")
    prefix = old_fn[:header_end]
    new_body = r'''    source = Path(split_evidence_path)
    if not source.exists():
        return [{"reason": "split_evidence_missing", "split_evidence": str(source)}]
    payload = json.loads(source.read_text(encoding="utf-8"))
    bonuses: list[dict[str, object]] = []
    for event in payload.get("events") or []:
        label = str(event.get("event", "")).strip().upper()
        ex_date = str(event.get("ex_date", ""))[:10]
        ticker = str(event.get("ticker", "")).strip().upper()
        if "BONIFICACAO" not in label or not ticker or not ex_date:
            continue
        # The simulated account starts in cash at `start`; pre-start bonuses cannot
        # alter the basis of shares bought later by this replay.
        if ex_date < start or ex_date > end:
            continue
        bonuses.append(
            {
                "ticker": ticker,
                "ex_date": ex_date,
                "event": label,
                "affected_tickers": {ticker},
            }
        )
    if not bonuses:
        return []

    transitions = sorted(
        _transition_rows(transition_csv_path),
        key=lambda row: str(row.get("effective_date", ""))[:10],
    )
    # Propagate the uncertainty identity through 1:1 source-backed renames.
    for bonus in bonuses:
        affected = bonus["affected_tickers"]
        assert isinstance(affected, set)
        for transition in transitions:
            effective = str(transition.get("effective_date", ""))[:10]
            if effective < str(bonus["ex_date"]) or effective > end:
                continue
            old = str(transition.get("old_ticker", "")).strip().upper()
            new = str(transition.get("new_ticker", "")).strip().upper()
            if old in affected and new:
                affected.add(new)

    trades = sorted(
        [
            row
            for row in trade_rows
            if start <= str(_row_value(row, "date", ""))[:10] <= end
        ],
        key=lambda row: (
            str(_row_value(row, "date", ""))[:10],
            0 if str(_row_value(row, "side", "")).upper() == "BUY" else 1,
        ),
    )
    transitions_by_date: dict[str, list[dict[str, str]]] = {}
    for transition in transitions:
        effective = str(transition.get("effective_date", ""))[:10]
        if start <= effective <= end:
            transitions_by_date.setdefault(effective, []).append(transition)
    bonuses_by_date: dict[str, list[dict[str, object]]] = {}
    for bonus in bonuses:
        bonuses_by_date.setdefault(str(bonus["ex_date"]), []).append(bonus)

    holdings: dict[str, int] = {}
    tainted: set[str] = set()
    dependencies: list[dict[str, object]] = []
    processed_dates: set[str] = set()

    def apply_events_through(value_date: str) -> None:
        due = sorted(
            {
                *[d for d in transitions_by_date if d <= value_date],
                *[d for d in bonuses_by_date if d <= value_date],
            }
            - processed_dates
        )
        for event_date in due:
            processed_dates.add(event_date)
            # Rename before evaluating same-day bonus entitlement.
            for transition in transitions_by_date.get(event_date, []):
                old = str(transition.get("old_ticker", "")).strip().upper()
                new = str(transition.get("new_ticker", "")).strip().upper()
                if not old or not new:
                    continue
                quantity = holdings.pop(old, 0)
                if quantity:
                    holdings[new] = holdings.get(new, 0) + quantity
                if old in tainted:
                    tainted.discard(old)
                    tainted.add(new)
            for bonus in bonuses_by_date.get(event_date, []):
                affected = bonus["affected_tickers"]
                assert isinstance(affected, set)
                if any(holdings.get(name, 0) > 0 for name in affected):
                    tainted.update(affected)

    for row in trades:
        value_date = str(_row_value(row, "date", ""))[:10]
        apply_events_through(value_date)
        ticker = str(_row_value(row, "ticker", "")).strip().upper()
        side = str(_row_value(row, "side", "")).upper()
        quantity = int(float(_row_value(row, "shares", _row_value(row, "quantity", 0)) or 0))
        if not ticker or quantity <= 0:
            continue
        if side == "BUY":
            holdings[ticker] = holdings.get(ticker, 0) + quantity
            continue
        if side != "SELL":
            continue
        if ticker in tainted:
            candidates = [bonus for bonus in bonuses if ticker in bonus["affected_tickers"]]
            for bonus in candidates:
                if value_date >= str(bonus["ex_date"]):
                    dependencies.append(
                        {
                            "ticker": ticker,
                            "original_bonus_ticker": bonus["ticker"],
                            "bonus_ex_date": bonus["ex_date"],
                            "sale_date": value_date,
                            "event": bonus["event"],
                            "reason": "stock_bonus_tax_basis_not_applied_by_engine",
                        }
                    )
        holdings[ticker] = max(0, holdings.get(ticker, 0) - quantity)
        if holdings[ticker] == 0:
            tainted.discard(ticker)

    unique = {
        (
            item["ticker"],
            item["original_bonus_ticker"],
            item["bonus_ex_date"],
            item["sale_date"],
            item["event"],
        ): item
        for item in dependencies
    }
    return [unique[key] for key in sorted(unique)]
'''
    new_fn = prefix + new_body
    write(path, text[:start] + new_fn + text[end:])


def patch_transition_builder() -> None:
    path = "scripts/build_ticker_transitions.py"
    text = read(path)
    insert_after = '''def _stale_category(last_quote_date: str, coverage_end: str, *, transitioned: bool) -> str:\n'''
    idx = text.index(insert_after)
    # Insert helper before main, after the existing stale helper body.
    main_idx = text.index("\ndef main(", idx)
    helper = r'''

def _same_isin_transition_rows(items: list, isin: str) -> list[dict[str, object]]:
    """Return unambiguous 1:1 ticker renames for one ISIN.

    Two different symbols carrying the same ISIN on the same session are not enough
    evidence to order a rename. The previous implementation depended on input ordering
    and could manufacture A->B->A transitions. Such overlap now fails closed.
    """
    ordered = sorted(items, key=lambda item: (item.date, item.ticker.upper()))
    if not ordered:
        return []
    tickers_by_date: dict[str, set[str]] = defaultdict(set)
    for item in ordered:
        tickers_by_date[item.date].add(item.ticker.upper())
    simultaneous = {
        day: sorted(names) for day, names in tickers_by_date.items() if len(names) > 1
    }
    if simultaneous:
        raise ValueError(
            f"{isin}: simultaneous same-ISIN symbols make automatic rename ambiguous: "
            f"{simultaneous}"
        )

    rows: list[dict[str, object]] = []
    previous_ticker = ordered[0].ticker.upper()
    previous_date = ordered[0].date
    for item in ordered[1:]:
        ticker = item.ticker.upper()
        if ticker != previous_ticker:
            if not previous_date < item.date:
                raise ValueError(
                    f"{isin}: rename boundary is not strictly chronological: "
                    f"{previous_ticker}@{previous_date} -> {ticker}@{item.date}"
                )
            rows.append(
                {
                    "effective_date": item.date,
                    "old_ticker": previous_ticker,
                    "new_ticker": ticker,
                    "share_ratio": "1",
                    "cash_per_old_share": "0",
                    "evidence": "same_isin_continuity",
                    "isin": isin,
                    "last_old_quote": previous_date,
                    "first_new_quote": item.date,
                }
            )
        previous_ticker = ticker
        previous_date = item.date
    return rows
'''
    text = text[:main_idx] + helper + text[main_idx:]
    old_loop = r'''    transitions: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for isin in sorted(relevant_isins):
        ordered = sorted(by_isin[isin], key=lambda item: item.date)
        previous_ticker = ordered[0].ticker.upper()
        previous_date = ordered[0].date
        for item in ordered[1:]:
            ticker = item.ticker.upper()
            if ticker in EXCLUDED_TICKERS:
                continue
            if ticker != previous_ticker:
                key = (item.date, previous_ticker, ticker)
                if key not in seen:
                    transitions.append(
                        {
                            "effective_date": item.date,
                            "old_ticker": previous_ticker,
                            "new_ticker": ticker,
                            "share_ratio": "1",
                            "cash_per_old_share": "0",
                            "evidence": "same_isin_continuity",
                            "isin": isin,
                            "last_old_quote": previous_date,
                            "first_new_quote": item.date,
                        }
                    )
                    seen.add(key)
            previous_ticker = ticker
            previous_date = item.date
'''
    new_loop = r'''    transitions: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for isin in sorted(relevant_isins):
        eligible_items = [
            item for item in by_isin[isin] if item.ticker.upper() not in EXCLUDED_TICKERS
        ]
        for row in _same_isin_transition_rows(eligible_items, isin):
            key = (
                str(row["effective_date"]),
                str(row["old_ticker"]),
                str(row["new_ticker"]),
            )
            if key in seen:
                continue
            seen.add(key)
            transitions.append(row)
'''
    if text.count(old_loop) != 1:
        raise RuntimeError("ticker transition loop anchor changed")
    text = text.replace(old_loop, new_loop, 1)
    write(path, text)


def patch_freshness() -> None:
    path = "scripts/audit_backtest_readiness.py"
    text = read(path)
    text = text.replace("from datetime import date, datetime, timezone", "from datetime import date, datetime, timedelta, timezone", 1)
    main_idx = text.index("\ndef main(")
    helper = r'''

def _weekday_gap(last_session: date, reference: date) -> int:
    """Count weekdays strictly after the last session and before the reference date.

    This intentionally does not pretend to be a full B3 holiday calendar. Combined
    with the existing calendar-day cap, a two-weekday tolerance prevents weekends and
    common long-holiday closures from being mislabeled stale while still rejecting a
    genuinely old snapshot quickly.
    """
    if last_session > reference:
        return -1
    current = last_session + timedelta(days=1)
    total = 0
    while current < reference:
        if current.weekday() < 5:
            total += 1
        current += timedelta(days=1)
    return total
'''
    text = text[:main_idx] + helper + text[main_idx:]
    old = """    age_calendar_days = (freshness_reference - evaluation_end_date).days\n    data_is_recent = 0 <= age_calendar_days <= args.max_age_calendar_days\n"""
    new = """    age_calendar_days = (freshness_reference - evaluation_end_date).days\n    age_weekdays_without_new_session = _weekday_gap(\n        evaluation_end_date, freshness_reference\n    )\n    data_is_recent = (\n        0 <= age_calendar_days <= args.max_age_calendar_days\n        or 0 <= age_weekdays_without_new_session <= 2\n    )\n"""
    if text.count(old) != 1:
        raise RuntimeError("freshness calculation anchor changed")
    text = text.replace(old, new, 1)
    old = """        \"age_calendar_days\": age_calendar_days,\n        \"maximum_age_calendar_days\": args.max_age_calendar_days,\n"""
    new = """        \"age_calendar_days\": age_calendar_days,\n        \"age_weekdays_without_new_session\": age_weekdays_without_new_session,\n        \"maximum_age_calendar_days\": args.max_age_calendar_days,\n"""
    if text.count(old) != 1:
        raise RuntimeError("freshness payload anchor changed")
    text = text.replace(old, new, 1)
    write(path, text)


def patch_realistic_input_audit() -> None:
    path = "scripts/audit_realistic_backtest_inputs.py"
    text = read(path)
    old = '        "ex_ante_selection_claim_allowed": survivorship_safe,\n'
    if text.count(old) != 1:
        raise RuntimeError("realistic input audit ex-ante anchor changed")
    text = text.replace(old, '        "ex_ante_selection_claim_allowed": False,\n', 1)
    anchor = '    details["missing_snapshot_next_open_examples"] = missing_next_open[:50]\n'
    if text.count(anchor) != 1:
        raise RuntimeError("realistic input execution-scope anchor changed")
    text = text.replace(
        anchor,
        anchor
        + '    details["execution_coverage_scope"] = "snapshot_next_open_preflight_only"\n'
        + '    details["actual_trade_execution_validation"] = (\n'
        + '        "candidate replay fails closed on every required 010/020 leg and the final "\n'
        + '        "artifact gate independently validates every recorded execution leg"\n'
        + '    )\n',
        1,
    )
    write(path, text)


def patch_bdi_manifest() -> None:
    path = "scripts/build_survivorship_safe_realistic_universe.py"
    text = read(path)
    old = "company shares only; BDI02 market010 ON/PN classes."
    if old in text:
        text = text.replace(
            old,
            "company shares only; equity-status BDI 02/05/06/07/08/09/11 in market010 ON/PN classes.",
            1,
        )
    old = '"standard": {"market_type": "010", "bdi_code": "02"}'
    if old in text:
        text = text.replace(
            old,
            '"standard": {"market_type": "010", "bdi_codes": ["02", "05", "06", "07", "08", "09", "11"]}',
            1,
        )
    write(path, text)


def patch_combination_claim() -> None:
    path = "scripts/backtest_strategy_management_combinations.py"
    anchor = '        "combinations": combinations,\n'
    text = read(path)
    if text.count(anchor) != 1:
        raise RuntimeError("matrix combination manifest anchor changed")
    text = text.replace(
        anchor,
        anchor
        + '        "combination_identity": (\n'
        + '            "unique strategy-name x management-parameterization pairs; "\n'
        + '            "behavioral uniqueness is not claimed"\n'
        + '        ),\n'
        + '        "behavioral_uniqueness_claimed": False,\n',
        1,
    )
    write(path, text)


def patch_workflow() -> None:
    path = ".github/workflows/full-matrix-backtest-hardened.yml"
    text = read(path)
    old = '            --require-valid 1\n'
    if text.count(old) != 1:
        raise RuntimeError("workflow require-valid anchor changed")
    text = text.replace(
        old,
        '            --limit "$TOP_N" \\\n            --require-valid "$TOP_N"\n',
        1,
    )
    old = "        if: ${{ always() && steps.realistic_snapshot.outputs.ready == 'true' }}\n        uses: actions/upload-artifact@v4\n"
    if text.count(old) != 1:
        raise RuntimeError("workflow realistic upload condition anchor changed")
    text = text.replace(
        old,
        "        if: ${{ success() && steps.realistic_snapshot.outputs.ready == 'true' }}\n        uses: actions/upload-artifact@v4\n",
        1,
    )
    old = "        if: ${{ needs.realistic_validation.outputs.snapshot_ready == 'true' }}\n        uses: actions/download-artifact@v4\n        with:\n          name: b3-strategy-lab-realistic-top10-${{ github.run_number }}\n"
    if text.count(old) != 1:
        raise RuntimeError("workflow realistic download condition anchor changed")
    text = text.replace(
        old,
        "        if: ${{ needs.realistic_validation.result == 'success' && needs.realistic_validation.outputs.snapshot_ready == 'true' }}\n        uses: actions/download-artifact@v4\n        with:\n          name: b3-strategy-lab-realistic-top10-${{ github.run_number }}\n",
        1,
    )
    old = '          if [ "$REALISTIC_SNAPSHOT_READY" = "true" ]; then\n'
    if text.count(old) != 1:
        raise RuntimeError("workflow snapshot publication anchor changed")
    text = text.replace(
        old,
        '          if [ "$REALISTIC_RESULT" = "success" ] && [ "$REALISTIC_SNAPSHOT_READY" = "true" ]; then\n',
        1,
    )
    old = '              and int(realistic.get("validated_candidate_count", 0)) > 0\n'
    if text.count(old) != 1:
        raise RuntimeError("workflow realistic status anchor changed")
    text = text.replace(
        old,
        '              and int(realistic.get("validated_candidate_count", 0)) == 10\n'
        '              and int(realistic.get("excluded_candidate_count", -1)) == 0\n'
        '              and realistic.get("validation_passed") is True\n',
        1,
    )
    write(path, text)


def write_tests() -> None:
    path = ROOT / "tests/test_comprehensive_audit_fixes.py"
    path.write_text(
        r'''from __future__ import annotations

import json
import math
import tempfile
import unittest
from datetime import date
from pathlib import Path

from b3_strategy_lab.cash_distributions import build_cash_events
from b3_strategy_lab.realistic_certification import bonus_tax_basis_dependencies
from scripts.audit_backtest_readiness import _weekday_gap
from scripts.build_ticker_transitions import _same_isin_transition_rows
from scripts.research_portfolio_allocation_core import _portfolio_metrics
from scripts.validate_matrix_top_realistic import _validation_issues


class ComprehensiveAuditFixTests(unittest.TestCase):
    def test_first_session_loss_is_in_all_risk_metrics(self):
        metrics = _portfolio_metrics(
            [900.0, 900.0, 900.0],
            ["2024-01-02", "2024-01-03", "2024-01-04"],
            1000.0,
        )
        self.assertEqual(metrics["total_return"], -0.1)
        self.assertAlmostEqual(metrics["max_drawdown"], -0.1)
        self.assertGreater(metrics["annual_volatility"], 0.0)
        self.assertTrue(math.isfinite(metrics["sharpe"]))

    def test_historical_cash_placeholder_is_blocking_not_zero_events(self):
        class Quote:
            date = "2024-01-02"
            isin = "BRAAAACNOR0"

        rows, issues = build_cash_events(
            ["AAA3"],
            {"AAA3": "AAAA"},
            {
                "AAAA": [
                    {
                        "code": "AAAA",
                        "stockDividends": [],
                        "_cash_dividends_source_available": False,
                    }
                ]
            },
            {"AAA3": [Quote()]},
        )
        self.assertEqual(rows, [])
        self.assertIn(
            "historical_cash_dividend_source_unavailable",
            {item.get("issue") for item in issues},
        )

    def test_candidate_runtime_failure_is_excluded_not_misparsed(self):
        self.assertEqual(
            _validation_issues({"_candidate_execution_error": "exit_code=2"}),
            ["candidate_execution_failed:exit_code=2"],
        )

    def test_pre_start_bonus_does_not_poison_later_purchase(self):
        with tempfile.TemporaryDirectory() as tmp:
            split = Path(tmp) / "split.json"
            split.write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "event": "BONIFICACAO",
                                "ex_date": "2019-01-02",
                                "ticker": "AAA3",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            trades = [
                {"date": "2024-01-03", "side": "BUY", "ticker": "AAA3", "shares": 10},
                {"date": "2024-02-01", "side": "SELL", "ticker": "AAA3", "shares": 10},
            ]
            self.assertEqual(
                bonus_tax_basis_dependencies(
                    split, trades, start="2024-01-01", end="2024-12-31"
                ),
                [],
            )

    def test_bonus_only_blocks_when_position_crosses_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            split = Path(tmp) / "split.json"
            split.write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "event": "BONIFICACAO",
                                "ex_date": "2024-01-15",
                                "ticker": "AAA3",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            no_holding = [
                {"date": "2024-01-20", "side": "BUY", "ticker": "AAA3", "shares": 10},
                {"date": "2024-02-01", "side": "SELL", "ticker": "AAA3", "shares": 10},
            ]
            self.assertEqual(
                bonus_tax_basis_dependencies(
                    split, no_holding, start="2024-01-01", end="2024-12-31"
                ),
                [],
            )
            held = [
                {"date": "2024-01-03", "side": "BUY", "ticker": "AAA3", "shares": 10},
                {"date": "2024-02-01", "side": "SELL", "ticker": "AAA3", "shares": 10},
            ]
            issues = bonus_tax_basis_dependencies(
                split, held, start="2024-01-01", end="2024-12-31"
            )
            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0]["bonus_ex_date"], "2024-01-15")

    def test_same_isin_overlap_is_rejected(self):
        class Quote:
            def __init__(self, value_date, ticker):
                self.date = value_date
                self.ticker = ticker

        with self.assertRaisesRegex(ValueError, "simultaneous same-ISIN"):
            _same_isin_transition_rows(
                [Quote("2024-01-02", "AAA3"), Quote("2024-01-02", "BBB3")],
                "BRAAAACNOR0",
            )

    def test_same_isin_clean_rename_is_strictly_chronological(self):
        class Quote:
            def __init__(self, value_date, ticker):
                self.date = value_date
                self.ticker = ticker

        rows = _same_isin_transition_rows(
            [Quote("2024-01-02", "AAA3"), Quote("2024-01-03", "BBB3")],
            "BRAAAACNOR0",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["old_ticker"], "AAA3")
        self.assertEqual(rows[0]["new_ticker"], "BBB3")

    def test_long_weekend_does_not_look_five_days_stale(self):
        # Friday -> following Wednesday has five calendar-day age but only two
        # intervening weekdays (Monday/Tuesday). The audit can tolerate a long closure.
        self.assertEqual(_weekday_gap(date(2024, 3, 28), date(2024, 4, 2)), 1)


if __name__ == "__main__":
    unittest.main()
''',
        encoding="utf-8",
    )


def main() -> None:
    patch_metrics()
    patch_realistic_validator()
    patch_historical_cash()
    patch_bonus_tax_basis()
    patch_transition_builder()
    patch_freshness()
    patch_realistic_input_audit()
    patch_bdi_manifest()
    patch_combination_claim()
    patch_workflow()
    write_tests()
    print("audit fixes applied")


if __name__ == "__main__":
    main()
