from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from b3_strategy_lab.candles import cache_path, load_candles
from b3_strategy_lab.cotahist import load_verified_candles
from b3_strategy_lab.portfolio_risk import covariance_target_weights
from scripts import research_portfolio_allocation_core as _core

# Keep this symbol local so unittest.mock.patch and external instrumentation on
# the public module still intercept candidate-profile computation.
_candidate_profile_uncached = _core._candidate_profile_uncached


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


_core._candidate_profile = _candidate_profile
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
            # The public wrapper is an instrumentation boundary. Synchronize the
            # core loader symbols immediately before delegation so unittest.mock
            # patches and external diagnostics on this module intercept the same call.
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


def __getattr__(name: str):
    return getattr(_core, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_core)))


def main(argv: list[str] | None = None) -> int:
    return _core.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
