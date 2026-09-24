import random, sys
from pathlib import Path
sys.path.insert(0, ".")
from b3_strategy_lab.strategies import build_signals, strategy_parameters
from scripts.backtest_strategy_management_combinations import _load_universe
from scripts.research_portfolio_allocation import MarketData
S = "macd_12_26_9_trend200"
universe = _load_universe(Path("reports/matriz_sem_problematicas/universo_filtrado.json"))
tickers = [str(t).upper() for t in universe["market_data_tickers"]]
data = MarketData(tickers, "1d", "adjusted", require_verified_splits_from=universe["warmup_start"],
    history_start=str(universe["warmup_start"]), data_dir=Path("data/candles_point_in_time"),
    actions_dir=Path("data/actions_point_in_time"), manifests_dir=Path("data/manifests_point_in_time"),
    split_evidence_path=Path("data/corporate_actions/point_in_time_split_evidence.json"))
rng = random.Random(7); checks = mism = 0
for t in tickers:
    cs = data.candles[t]; full = build_signals(S, cs, **strategy_parameters(S))
    for cut in rng.sample(range(210, len(cs)), min(12, max(0, len(cs) - 210))):
        pre = build_signals(S, cs[:cut + 1], **strategy_parameters(S))
        checks += 1; mism += pre != full[:cut + 1]
print("cortes", checks, "divergencias", mism)
