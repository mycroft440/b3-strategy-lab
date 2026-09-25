import sys
from pathlib import Path
sys.path.insert(0, ".")
from scripts.backtest_strategy_management_combinations import _build_eligibility, _load_point_in_time_membership, _load_universe
from scripts.research_portfolio_allocation import MarketData, _configs, run_portfolio
from scripts.research_portfolio_allocation_core import _candidate_profile
universe = _load_universe(Path("reports/matriz_sem_problematicas/universo_filtrado.json"))
tickers = [str(t).upper() for t in universe["market_data_tickers"]]
data = MarketData(tickers, "1d", "adjusted", require_verified_splits_from=universe["warmup_start"],
    history_start=str(universe["warmup_start"]), data_dir=Path("data/candles_point_in_time"),
    actions_dir=Path("data/actions_point_in_time"), manifests_dir=Path("data/manifests_point_in_time"),
    split_evidence_path=Path("data/corporate_actions/point_in_time_split_evidence.json"))
membership = _load_point_in_time_membership(universe, data.dates)
A, B = "donchian_breakout_55_20", "donchian_breakout_55_20_trend200"
el = _build_eligibility(data, [A, B], "adjusted", signal_start=str(universe["warmup_start"]))
M = "top1_roc_short_blend_risk_adjusted_roc12_6_3_w1_1_2_short21x2_trend0_vol63_equal_monthly_posscore_adjusted"
config = next(c for c in _configs("adjusted", "all") if c.name == M)
diff = on = 0; diff_scored = 0; diff_member = 0
for t in tickers:
    for i, c in enumerate(data.candles[t]):
        if c.date < "2018-01-02": continue
        a, b = el[A][t][i], el[B][t][i]
        on += a
        if a != b:
            diff += 1
            if t in membership.get(c.date, set()):
                diff_member += 1
                if _candidate_profile(data, t, i, config) is not None: diff_scored += 1
print(f"dias-ativo com sinal ligado ({A}): {on}; diferentes entre as duas: {diff} ({diff/on:.1%})")
print(f"diferentes e no universo daquela semana: {diff_member}; e com pontuacao positiva no gerenciamento: {diff_scored}")
curves = {}
for s in (A, B):
    summ, curve = run_portfolio(data, config, start="2018-01-02", end="2026-08-19", initial_cash=1000.0, cost_bps=3.2,
        slippage_bps=10.0, lot_size=1, eligibility=el[s], universe_membership=membership, collect_curve=True)
    curves[s] = curve; print(s, round(summ.final_equity, 2), summ.trades)
print("carteiras identicas em todos os pregoes:", all(x.selected == y.selected and x.equity == y.equity for x, y in zip(curves[A], curves[B])))
