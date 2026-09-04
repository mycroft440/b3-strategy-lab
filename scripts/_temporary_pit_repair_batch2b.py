from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement, found {count}: {old!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


# Survivorship-safe universe: source-reviewed successors are continuity-only market data.
replace_once(
    "scripts/build_survivorship_safe_realistic_universe.py",
    "from b3_strategy_lab.cotahist import download_cotahist  # noqa: E402\n",
    "from b3_strategy_lab.cotahist import download_cotahist  # noqa: E402\n"
    "from b3_strategy_lab.instrument_transitions import load_transition_reviews  # noqa: E402\n",
)
replace_once(
    "scripts/build_survivorship_safe_realistic_universe.py",
    'DEFAULT_EXECUTION = Path("data/execution/b3_standard_fractional_open.csv")\n',
    'DEFAULT_EXECUTION = Path("data/execution/b3_standard_fractional_open.csv")\n'
    'DEFAULT_TRANSITION_REVIEWS = Path("data/corporate_actions/instrument_transition_reviews.json")\n',
)
replace_once(
    "scripts/build_survivorship_safe_realistic_universe.py",
    '    parser.add_argument("--execution-output", type=Path, default=DEFAULT_EXECUTION)\n',
    '    parser.add_argument("--execution-output", type=Path, default=DEFAULT_EXECUTION)\n'
    '    parser.add_argument("--transition-reviews", type=Path, default=DEFAULT_TRANSITION_REVIEWS)\n',
)
replace_once(
    "scripts/build_survivorship_safe_realistic_universe.py",
    "    market_data_set = selected_set | continuity_set\n    market_data_tickers = sorted(market_data_set)\n",
    "    market_data_set = selected_set | continuity_set\n"
    "    # A successor with a changed ISIN cannot be discovered by same-ISIN continuity.\n"
    "    # Add it only when a source-reviewed transition whose effective date is inside\n"
    "    # the replay horizon connects from an already-required symbol. This expands\n"
    "    # valuation/execution data only; it never grants historical selection eligibility.\n"
    "    transition_reviews = load_transition_reviews(args.transition_reviews)\n"
    "    quoted_tickers = {quote.ticker.upper() for quote in causal_standard_quotes}\n"
    "    reviewed_successors: set[str] = set()\n"
    "    changed = True\n"
    "    while changed:\n"
    "        changed = False\n"
    "        for transition in transition_reviews:\n"
    "            if transition.certification_status != \"certified\" or transition.effective_date > end:\n"
    "                continue\n"
    "            if transition.old_ticker not in market_data_set or not transition.new_ticker:\n"
    "                continue\n"
    "            if transition.new_ticker not in quoted_tickers:\n"
    "                raise ValueError(\n"
    "                    f\"Certified successor {transition.new_ticker} has no COTAHIST quote through {end}.\"\n"
    "                )\n"
    "            if transition.new_ticker not in market_data_set:\n"
    "                market_data_set.add(transition.new_ticker)\n"
    "                reviewed_successors.add(transition.new_ticker)\n"
    "                changed = True\n"
    "    market_data_tickers = sorted(market_data_set)\n",
)
replace_once(
    "scripts/build_survivorship_safe_realistic_universe.py",
    '                "company shares only; equity-status BDI 02/05/06/07/08/09/11 in market010 ON/PN classes. UNITS are excluded "\n',
    '                "company shares only; equity-status BDI 02/05/06/07/08/09/11 plus conditional BDI58 in market010 ON/PN classes. UNITS are excluded "\n',
)
replace_once(
    "scripts/build_survivorship_safe_realistic_universe.py",
    '            "standard": {"market_type": "010", "bdi_codes": ["02", "05", "06", "07", "08", "09", "11"]},\n',
    '            "standard": {"market_type": "010", "bdi_codes": ["02", "05", "06", "07", "08", "09", "11", "58"], "bdi58_policy": "ON_PN_valid_ticker_only"},\n',
)
replace_once(
    "scripts/build_survivorship_safe_realistic_universe.py",
    '        "continuity_only_tickers": sorted(market_data_set - selected_set),\n        "continuity_rule": (\n            "same_isin_ON_PN_history_only_at_or_before_selection_end; never grants selection eligibility"\n        ),\n',
    '        "continuity_only_tickers": sorted(market_data_set - selected_set),\n'
    '        "source_reviewed_successor_tickers": sorted(reviewed_successors),\n'
    '        "instrument_transition_review_file": str(args.transition_reviews),\n'
    '        "continuity_rule": (\n'
    '            "same_isin_ON_PN_history plus certified source-reviewed instrument successors "\n'
    '            "effective at or before selection_end; continuity never grants selection eligibility"\n'
    '        ),\n',
)

# Transition builder: merge only certified primary-source reviews with deterministic same-ISIN rows.
replace_once(
    "scripts/build_ticker_transitions.py",
    "from b3_strategy_lab.cotahist import download_cotahist  # noqa: E402\n",
    "from b3_strategy_lab.cotahist import download_cotahist  # noqa: E402\n"
    "from b3_strategy_lab.instrument_transitions import load_transition_reviews  # noqa: E402\n",
)
replace_once(
    "scripts/build_ticker_transitions.py",
    'DEFAULT_UNRESOLVED = Path("reports/unresolved_historical_delistings.csv")\n',
    'DEFAULT_UNRESOLVED = Path("reports/unresolved_historical_delistings.csv")\n'
    'DEFAULT_REVIEWS = Path("data/corporate_actions/instrument_transition_reviews.json")\n',
)
replace_once(
    "scripts/build_ticker_transitions.py",
    '    parser.add_argument("--unresolved-output", type=Path, default=DEFAULT_UNRESOLVED)\n',
    '    parser.add_argument("--unresolved-output", type=Path, default=DEFAULT_UNRESOLVED)\n'
    '    parser.add_argument("--transition-reviews", type=Path, default=DEFAULT_REVIEWS)\n',
)
replace_once(
    "scripts/build_ticker_transitions.py",
    "    transitions.sort(\n",
    "    manual_transitions = 0\n"
    "    for item in load_transition_reviews(args.transition_reviews):\n"
    "        if item.certification_status != \"certified\" or item.effective_date > coverage_end:\n"
    "            continue\n"
    "        if item.old_ticker not in relevant_tickers:\n"
    "            continue\n"
    "        if item.new_ticker and item.new_ticker not in relevant_tickers:\n"
    "            raise ValueError(\n"
    "                f\"Certified transition successor {item.new_ticker} is absent from the market-data scope.\"\n"
    "            )\n"
    "        key = (item.effective_date, item.old_ticker, item.new_ticker)\n"
    "        if key in seen:\n"
    "            continue\n"
    "        seen.add(key)\n"
    "        transitions.append(\n"
    "            {\n"
    "                \"effective_date\": item.effective_date,\n"
    "                \"old_ticker\": item.old_ticker,\n"
    "                \"new_ticker\": item.new_ticker,\n"
    "                \"share_ratio\": f\"{item.share_ratio:.15g}\",\n"
    "                \"cash_per_old_share\": f\"{item.cash_per_old_share:.15g}\",\n"
    "                \"old_isin\": item.old_isin,\n"
    "                \"new_isin\": item.new_isin,\n"
    "                \"old_quotation_factor\": item.old_quotation_factor,\n"
    "                \"new_quotation_factor\": item.new_quotation_factor,\n"
    "                \"cutoff_date\": item.cutoff_date,\n"
    "                \"first_successor_trade_date\": item.first_successor_trade_date,\n"
    "                \"event_type\": item.event_type,\n"
    "                \"fractional_treatment\": item.fractional_treatment,\n"
    "                \"tax_basis_treatment\": item.tax_basis_treatment,\n"
    "                \"source_authority\": item.source_authority,\n"
    "                \"source_url\": item.source_url,\n"
    "                \"source_reference\": item.source_reference,\n"
    "                \"certification_status\": item.certification_status,\n"
    "                \"evidence\": \"source_reviewed_instrument_transition\",\n"
    "                \"isin\": item.old_isin,\n"
    "                \"last_old_quote\": item.cutoff_date,\n"
    "                \"first_new_quote\": item.first_successor_trade_date,\n"
    "            }\n"
    "        )\n"
    "        manual_transitions += 1\n\n"
    "    transitions.sort(\n",
)
replace_once(
    "scripts/build_ticker_transitions.py",
    '''        [
            "effective_date",
            "old_ticker",
            "new_ticker",
            "share_ratio",
            "cash_per_old_share",
            "evidence",
            "isin",
            "last_old_quote",
            "first_new_quote",
        ],
''',
    '''        [
            "effective_date",
            "old_ticker",
            "new_ticker",
            "share_ratio",
            "cash_per_old_share",
            "old_isin",
            "new_isin",
            "old_quotation_factor",
            "new_quotation_factor",
            "cutoff_date",
            "first_successor_trade_date",
            "event_type",
            "fractional_treatment",
            "tax_basis_treatment",
            "source_authority",
            "source_url",
            "source_reference",
            "certification_status",
            "evidence",
            "isin",
            "last_old_quote",
            "first_new_quote",
        ],
''',
)
replace_once(
    "scripts/build_ticker_transitions.py",
    '        "schema_version": 5,\n        "method": "same_isin_continuity_only",\n',
    '        "schema_version": 6,\n'
    '        "method": "same_isin_continuity_plus_source_reviewed_instrument_transitions",\n'
    '        "instrument_transition_review_file": str(args.transition_reviews),\n'
    '        "instrument_transition_review_sha256": sha256_file(args.transition_reviews) if args.transition_reviews.exists() else "",\n'
    '        "source_reviewed_transitions": manual_transitions,\n',
)
replace_once(
    "scripts/build_ticker_transitions.py",
    '    print(f"Auto-approved ticker transitions: {len(transitions)}")\n',
    '    print(f"Transition rows: {len(transitions)} (source-reviewed={manual_transitions})")\n',
)
