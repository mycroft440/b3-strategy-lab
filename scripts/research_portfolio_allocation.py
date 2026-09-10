from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from b3_strategy_lab.candles import cache_path, load_candles
from b3_strategy_lab.cotahist import load_verified_candles
from b3_strategy_lab.portfolio_risk import covariance_target_weights
from scripts import research_portfolio_allocation_core as _core


_original_date_window = _core._date_window
_original_is_rebalance_date = _core._is_rebalance_date
_original_rebalance = _core._rebalance
_DATE_WINDOW_CACHE: dict[tuple[int, str | None, str | None], tuple[list[str], list[str]]] = {}
_TRANSITION_REVIEWS = PROJECT_ROOT / "data/corporate_actions/instrument_transition_reviews.json"


def _date_window(values: list[str], start: str | None, end: str | None) -> list[str]:
    """Reuse immutable market-session slices while retaining canonical list semantics."""

    key = (id(values), start, end)
    cached = _DATE_WINDOW_CACHE.get(key)
    if cached is not None and cached[0] is values:
        return cached[1]
    result = _original_date_window(values, start, end)
    _DATE_WINDOW_CACHE[key] = (values, result)
    return result


@lru_cache(maxsize=None)
def _is_rebalance_date(current_date: str, next_date: str, frequency: str) -> bool:
    return _original_is_rebalance_date(current_date, next_date, frequency)


@lru_cache(maxsize=1)
def _certified_unit_transitions() -> dict[str, tuple[tuple[str, str], ...]]:
    """Load only source-reviewed 1:1 no-cash symbol/class changes.

    Research replay must not fabricate an opening for a predecessor after its final
    session. For transitions that the repository has already certified as preserving
    units and tax basis with no cash leg, carrying the position into the successor is
    the exact economic operation and avoids a fictitious sale/rebuy round-trip.
    Anything more complex remains fail-closed in the dedicated realistic engine.
    """
    if not _TRANSITION_REVIEWS.exists():
        return {}
    payload = json.loads(_TRANSITION_REVIEWS.read_text(encoding="utf-8"))
    reviews = payload.get("reviews", []) if isinstance(payload, dict) else []
    by_date: dict[str, list[tuple[str, str]]] = {}
    for raw in reviews:
        if not isinstance(raw, dict):
            continue
        try:
            ratio = float(raw.get("share_ratio", 0.0))
            cash = float(raw.get("cash_per_old_share", 0.0))
        except (TypeError, ValueError):
            continue
        old = str(raw.get("old_ticker", "")).strip().upper()
        new = str(raw.get("new_ticker", "")).strip().upper()
        effective = str(raw.get("effective_date", "")).strip()[:10]
        if (
            raw.get("certification_status") != "certified"
            or str(raw.get("event_type", "")) not in {"ticker_change", "class_change", "incorporation"}
            or abs(ratio - 1.0) > 1e-12
            or abs(cash) > 1e-12
            or raw.get("fractional_treatment") != "preserve_units"
            or raw.get("tax_basis_treatment") != "carry_total_basis"
            or not old
            or not new
            or not effective
        ):
            continue
        by_date.setdefault(effective, []).append((old, new))
    return {day: tuple(items) for day, items in by_date.items()}


def _applicable_unit_transitions(current_date: str):
    day = str(current_date)[:10]
    for effective in sorted(_certified_unit_transitions()):
        if effective > day:
            break
        for transition in _certified_unit_transitions()[effective]:
            yield transition


@lru_cache(maxsize=1)
def _certified_unsupported_transition_boundaries() -> tuple[tuple[str, str, str, str], ...]:
    """Return certified events the price-only research engine must not fabricate."""
    if not _TRANSITION_REVIEWS.exists():
        return ()
    payload = json.loads(_TRANSITION_REVIEWS.read_text(encoding="utf-8"))
    reviews = payload.get("reviews", []) if isinstance(payload, dict) else []
    boundaries: list[tuple[str, str, str, str]] = []
    for raw in reviews:
        if not isinstance(raw, dict) or raw.get("certification_status") != "certified":
            continue
        old = str(raw.get("old_ticker", "")).strip().upper()
        new = str(raw.get("new_ticker", "")).strip().upper()
        effective = str(raw.get("effective_date", "")).strip()[:10]
        event_type = str(raw.get("event_type", "unknown")).strip() or "unknown"
        try:
            ratio = float(raw.get("share_ratio", 0.0))
            cash = float(raw.get("cash_per_old_share", 0.0))
        except (TypeError, ValueError):
            ratio = 0.0
            cash = 0.0
        unit_preserving = (
            bool(new)
            and abs(ratio - 1.0) <= 1e-12
            and abs(cash) <= 1e-12
            and raw.get("fractional_treatment") == "preserve_units"
            and raw.get("tax_basis_treatment") == "carry_total_basis"
        )
        if old and effective and not unit_preserving:
            boundaries.append((effective, old, new, event_type))
    return tuple(sorted(boundaries))


def _research_invalid_transition_reason(message: str) -> str | None:
    """Classify only fresh-price failures explained by a certified complex event."""
    match = re.match(
        r"^(?P<date>\d{4}-\d{2}-\d{2}): "
        r"(?:abertura fresca obrigatoria|fechamento fresco obrigatorio) "
        r"ausente para (?P<tickers>.+)$",
        message.strip(),
    )
    if match is None:
        return None
    value_date = match.group("date")
    missing = {item.strip().upper() for item in match.group("tickers").split(",")}
    for effective, old, new, event_type in _certified_unsupported_transition_boundaries():
        if effective <= value_date and old in missing:
            successor = new or "TERMINAL"
            return (
                f"{value_date}:{old}->{successor}:{event_type}:"
                "CERTIFIED_COMPLEX_TRANSITION_UNSUPPORTED_IN_PRICE_ONLY_RESEARCH"
            )
    return None


def _install_transition_price_aliases(data) -> None:
    """Expose successor candles for a held predecessor after a certified 1:1 rename.

    The alias is used only for same-session valuation/execution preflight. Signal and
    ranking histories remain attached to their actual listed symbols. On the next trade
    opportunity `_rebalance` moves holdings/targets to the successor before execution.
    """
    for effective, transitions in _certified_unit_transitions().items():
        for old, new in transitions:
            if old not in data.by_date or new not in data.by_date:
                continue
            for value_date, candle in data.by_date[new].items():
                if value_date >= effective and value_date not in data.by_date[old]:
                    data.by_date[old][value_date] = candle


def _rebalance(
    current_date,
    tickers,
    today_candles,
    last_prices,
    shares,
    cash,
    target_weights,
    cost_rate,
    slippage_rate,
    lot_size,
):
    """Carry certified unit-preserving ticker changes before execution checks."""
    for old, new in _applicable_unit_transitions(str(current_date)):
        old_relevant = float(shares.get(old, 0.0)) > 0 or float(target_weights.get(old, 0.0)) > 0
        if not old_relevant:
            continue
        if old not in shares or new not in shares:
            raise ValueError(
                f"{current_date}: transicao certificada {old}->{new} fora do escopo carregado"
            )
        shares[new] = float(shares.get(new, 0.0)) + float(shares.get(old, 0.0))
        shares[old] = 0.0
        if old in target_weights:
            target_weights[new] = float(target_weights.get(new, 0.0)) + float(
                target_weights.pop(old)
            )
    return _original_rebalance(
        current_date,
        tickers,
        today_candles,
        last_prices,
        shares,
        cash,
        target_weights,
        cost_rate,
        slippage_rate,
        lot_size,
    )


def _install_performance_caches(data) -> None:
    """Attach per-MarketData caches for values that are immutable during a replay."""

    if not hasattr(data, "trend_average_cache"):
        data.trend_average_cache = {}
    if not hasattr(data, "volatility_window_cache"):
        data.volatility_window_cache = {}
    if not hasattr(data, "price_roc_cache"):
        data.price_roc_cache = {}
    if not hasattr(data, "eligibility_tickers_cache"):
        data.eligibility_tickers_cache = {}


@lru_cache(maxsize=None)
def _parse_ints_cached(text: str) -> tuple[int, ...]:
    return tuple(_core._parse_ints(text))


@lru_cache(maxsize=None)
def _parse_floats_cached(text: str) -> tuple[float, ...]:
    return tuple(_core._parse_floats(text))


def _price_roc(data, ticker: str, recent_index: int, window: int) -> float | None:
    cache = getattr(data, "price_roc_cache", None)
    key = (ticker, recent_index, int(window))
    if cache is not None and key in cache:
        return cache[key]

    prices = data.signal_prices[ticker]
    past_index = recent_index - window
    result: float | None
    if past_index < 0 or recent_index <= 0:
        result = None
    else:
        recent_price = prices[recent_index]
        past_price = prices[past_index]
        result = recent_price / past_price - 1 if recent_price > 0 and past_price > 0 else None
    if cache is not None:
        cache[key] = result
    return result


def _trend_average(data, ticker: str, index: int, window: int) -> float:
    cache = getattr(data, "trend_average_cache", None)
    key = (ticker, index, int(window))
    if cache is not None and key in cache:
        return cache[key]

    prices = data.signal_prices[ticker]
    values = prices[index - window + 1 : index + 1]
    result = sum(values) / len(values)
    if cache is not None:
        cache[key] = result
    return result


def _window_volatility(data, ticker: str, index: int, window: int) -> float:
    cache = getattr(data, "volatility_window_cache", None)
    key = (ticker, index, int(window))
    if cache is not None and key in cache:
        return cache[key]

    values = data.raw_returns[ticker][max(0, index - window + 1) : index + 1]
    result = _core._annualized_volatility(values)
    if cache is not None:
        cache[key] = result
    return result


def _candidate_profile_uncached(data, ticker: str, index: int, config):
    """Canonical candidate profile with exact memoization of invariant subexpressions."""

    prices = data.signal_prices[ticker]
    recent_index = index - config.skip
    roc_windows = _parse_ints_cached(config.roc_windows)
    lookback = max(roc_windows) if roc_windows else config.lookback
    past_index = recent_index - lookback
    if past_index < 0 or recent_index <= 0:
        return None
    if config.trend_window > 0 and index + 1 < config.trend_window:
        return None
    if index < config.vol_window:
        return None

    current_price = prices[index]
    recent_price = prices[recent_index]
    past_price = prices[past_index]
    if current_price <= 0 or recent_price <= 0 or past_price <= 0:
        return None

    base_momentum = _price_roc(data, ticker, recent_index, lookback)
    if base_momentum is None:
        return None
    momentum = base_momentum
    component_rocs = [momentum]
    if roc_windows:
        weights = _parse_floats_cached(config.roc_weights) or (1.0,) * len(roc_windows)
        if len(weights) != len(roc_windows):
            raise ValueError("roc_weights precisa ter o mesmo tamanho de roc_windows.")
        component_rocs = []
        weighted_sum = 0.0
        total_weight = 0.0
        for window, weight in zip(roc_windows, weights):
            roc = _price_roc(data, ticker, recent_index, window)
            if roc is None:
                return None
            component_rocs.append(roc)
            weighted_sum += roc * weight
            total_weight += abs(weight)
        if total_weight <= 0:
            return None
        momentum = weighted_sum / total_weight
    if config.absolute_momentum and momentum <= 0:
        return None
    if config.positive_rule == "all_windows" and any(roc <= 0 for roc in component_rocs):
        return None
    if config.short_window > 0:
        short_momentum = _price_roc(data, ticker, recent_index, config.short_window)
        if short_momentum is None:
            return None
        if config.score.startswith("roc_short_blend"):
            momentum = (momentum + config.short_weight * short_momentum) / (
                1 + abs(config.short_weight)
            )
            if config.absolute_momentum and momentum <= 0:
                return None
        elif config.score == "short_risk_adjusted_roc_filter":
            momentum = short_momentum
            if config.absolute_momentum and momentum <= 0:
                return None
    if config.trend_window > 0:
        if current_price <= _trend_average(data, ticker, index, config.trend_window):
            return None

    volatility = _window_volatility(data, ticker, index, config.vol_window)
    if volatility <= 0:
        return None

    if config.score in {
        "risk_adjusted",
        "roc_combo_risk_adjusted",
        "roc_short_blend_risk_adjusted",
        "short_risk_adjusted_roc_filter",
    }:
        score = momentum / volatility
    elif config.score == "all":
        score = 1.0
    elif config.score in {"momentum", "roc_combo", "roc_short_blend"}:
        score = momentum
    else:
        raise ValueError(f"Score desconhecido: {config.score}")

    return {
        "ticker": ticker,
        "momentum": momentum,
        "volatility": volatility,
        "score": score,
    }


def _candidate_profile(data, ticker: str, index: int, config):
    cache = getattr(data, "candidate_profile_cache", None)
    cache_key = (
        ticker,
        index,
        config.lookback,
        config.skip,
        config.trend_window,
        config.vol_window,
        config.score,
        config.absolute_momentum,
        config.roc_windows,
        config.roc_weights,
        config.positive_rule,
        config.short_window,
        config.short_weight,
    )
    if cache is not None and cache_key in cache:
        return cache[cache_key]
    profile = _candidate_profile_uncached(data, ticker, index, config)
    if cache is not None:
        cache[cache_key] = profile
    return profile


def _eligible_tickers(data, current_date: str, eligibility):
    if eligibility is None:
        return None
    cache = getattr(data, "eligibility_tickers_cache", None)
    key = (id(eligibility), current_date)
    if cache is not None and key in cache:
        return cache[key]

    eligible = frozenset(
        ticker
        for ticker in data.tickers
        if (
            (index := data.index_by_date[ticker].get(current_date)) is not None
            and (signals := eligibility.get(ticker)) is not None
            and index < len(signals)
            and signals[index] == 1
        )
    )
    if cache is not None:
        cache[key] = eligible
    return eligible


_core._date_window = _date_window
_core._is_rebalance_date = _is_rebalance_date
_core._rebalance = _rebalance
_core._candidate_profile = _candidate_profile
_core._eligible_tickers = _eligible_tickers
_core._target_weights = covariance_target_weights

_target_weights = covariance_target_weights


class MarketData(_core.MarketData):
    """MarketData with optional isolated storage and verification roots."""

    def __init__(
        self,
        tickers: list[str],
        interval: str,
        signal_mode: str,
        *,
        allow_unverified_data: bool = False,
        require_verified_splits_from: str | None = None,
        history_start: str | None = None,
        data_dir: Path | str | None = None,
        actions_dir: Path | str | None = None,
        manifests_dir: Path | str | None = None,
        split_evidence_path: Path | str | None = None,
    ) -> None:
        custom_roots = any(
            value is not None
            for value in (data_dir, actions_dir, manifests_dir, split_evidence_path)
        )
        if not custom_roots:
            _core.load_verified_candles = load_verified_candles
            _core.load_candles = load_candles
            super().__init__(
                tickers,
                interval,
                signal_mode,
                allow_unverified_data=allow_unverified_data,
                require_verified_splits_from=require_verified_splits_from,
                history_start=history_start,
            )
            _install_transition_price_aliases(self)
            _install_performance_caches(self)
            return

        self.tickers = tickers
        self.interval = interval
        self.signal_mode = signal_mode
        self.candles = {}
        self.by_date = {}
        self.index_by_date = {}
        self.signal_prices = {}
        self.raw_returns = {}
        self.manifests = {}
        self.candidate_profile_cache = {}
        dates: set[str] = set()

        for ticker in tickers:
            if allow_unverified_data:
                candle_path = (
                    cache_path(ticker, interval, data_dir)
                    if data_dir is not None
                    else cache_path(ticker, interval)
                )
                candles = load_candles(candle_path)
                if history_start is not None:
                    candles = [candle for candle in candles if candle.date >= history_start]
            else:
                kwargs = {}
                if data_dir is not None:
                    kwargs["data_dir"] = data_dir
                if actions_dir is not None:
                    kwargs["actions_dir"] = actions_dir
                if manifests_dir is not None:
                    kwargs["manifests_dir"] = manifests_dir
                if split_evidence_path is not None:
                    kwargs["split_evidence_path"] = split_evidence_path
                candles, manifest = load_verified_candles(
                    ticker,
                    interval,
                    start=history_start,
                    require_verified_splits_from=require_verified_splits_from,
                    **kwargs,
                )
                self.manifests[ticker] = manifest
            if not candles:
                raise ValueError(
                    f"{ticker}: nenhum candle disponivel desde "
                    f"{history_start or 'o inicio da serie'}."
                )
            self.candles[ticker] = candles
            self.by_date[ticker] = {candle.date: candle for candle in candles}
            self.index_by_date[ticker] = {
                candle.date: index for index, candle in enumerate(candles)
            }
            self.signal_prices[ticker] = [
                candle.close if signal_mode == "adjusted" else candle.raw_close
                for candle in candles
            ]
            self.raw_returns[ticker] = _core._returns(self.signal_prices[ticker])
            dates.update(candle.date for candle in candles)

        self.dates = sorted(dates, key=_core._point_datetime)
        _install_transition_price_aliases(self)
        _install_performance_caches(self)


def __getattr__(name: str):
    return getattr(_core, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_core)))


def main(argv: list[str] | None = None) -> int:
    return _core.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
