from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement, found {count}: {old!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


replace_once(
    "b3_strategy_lab/realistic_portfolio_core.py",
    "from .strategies import build_signals, strategy_parameters\n\n\n@dataclass(frozen=True)\nclass TickerTransition:\n    effective_date: str\n    old_ticker: str\n    new_ticker: str\n    share_ratio: float = 1.0\n    cash_per_old_share: float = 0.0\n\n\n",
    "from .instrument_transitions import (\n"
    "    InstrumentTransition,\n"
    "    TickerTransition,\n"
    "    load_instrument_transitions,\n"
    ")\n"
    "from .strategies import build_signals, strategy_parameters\n\n\n",
)
replace_once(
    "b3_strategy_lab/realistic_portfolio_core.py",
    '''def load_transitions(path: Path | str) -> dict[str, list[TickerTransition]]:
    source = Path(path)
    if not source.exists():
        return {}
    result: dict[str, list[TickerTransition]] = {}
    with source.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            item = TickerTransition(
                effective_date=str(row["effective_date"])[:10],
                old_ticker=str(row["old_ticker"]).upper(),
                new_ticker=str(row.get("new_ticker", "")).upper(),
                share_ratio=float(row.get("share_ratio", 1.0) or 1.0),
                cash_per_old_share=float(row.get("cash_per_old_share", 0.0) or 0.0),
            )
            result.setdefault(item.effective_date, []).append(item)
    return result
''',
    '''def load_transitions(path: Path | str) -> dict[str, list[TickerTransition]]:
    """Backward-compatible loader for the extended instrument-transition schema."""
    return load_instrument_transitions(path)
''',
)
replace_once(
    "b3_strategy_lab/realistic_portfolio.py",
    '''def _apply_ticker_transitions(account, transitions) -> None:
    for transition in transitions:
        if not math.isclose(float(transition.cash_per_old_share), 0.0, abs_tol=1e-12):
            raise ValueError(
                f"{transition.old_ticker}->{transition.new_ticker}: cash component is not "
                "supported without an explicit, source-tested tax-basis rule."
            )
        if not math.isclose(float(transition.share_ratio), 1.0, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError(
                f"{transition.old_ticker}->{transition.new_ticker}: only 1:1 ticker "
                "transitions are supported without an explicit, source-tested tax-basis rule."
            )
    _original_apply_ticker_transitions(account, transitions)
''',
    '''def _apply_ticker_transitions(account, transitions) -> None:
    for transition in transitions:
        if not math.isclose(float(transition.cash_per_old_share), 0.0, abs_tol=1e-12):
            raise ValueError(
                f"{transition.old_ticker}->{transition.new_ticker}: cash component is not "
                "supported without an explicit, source-tested tax-basis rule."
            )
        ratio_is_one = math.isclose(
            float(transition.share_ratio), 1.0, rel_tol=1e-12, abs_tol=1e-12
        )
        if not ratio_is_one:
            if getattr(transition, "certification_status", "unresolved") != "certified":
                raise ValueError(
                    f"{transition.old_ticker}->{transition.new_ticker}: non-1:1 conversion "
                    "requires a certified source-bound instrument transition."
                )
            if getattr(transition, "tax_basis_treatment", "") != "carry_total_basis":
                raise ValueError(
                    f"{transition.old_ticker}->{transition.new_ticker}: non-1:1 conversion "
                    "requires explicit carry_total_basis treatment."
                )
        if not transition.new_ticker:
            if (
                getattr(transition, "certification_status", "unresolved") != "certified"
                or getattr(transition, "event_type", "") != "economic_termination"
                or getattr(transition, "tax_basis_treatment", "") != "terminal_worthless"
            ):
                raise ValueError(
                    f"{transition.old_ticker}: terminal transition requires a certified "
                    "economic_termination with terminal_worthless treatment."
                )
    _original_apply_ticker_transitions(account, transitions)
''',
)
