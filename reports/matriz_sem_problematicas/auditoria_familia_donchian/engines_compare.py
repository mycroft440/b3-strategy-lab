import csv, json, sys
from pathlib import Path
sys.path.insert(0, ".")
from scripts.backtest_strategy_management_combinations import _build_eligibility, _load_point_in_time_membership, _load_universe
from scripts.research_portfolio_allocation import MarketData, _configs, run_portfolio
SP = sys.argv[1] if len(sys.argv) > 1 else "."  # pasta com os replays do motor realista
R = "reports/matriz_sem_problematicas/replay_realista"
W = "top1_risk_adjusted_lb126_skip21_trend0_vol21_equal_monthly_abs_cap1_adjusted"
T = "top1_risk_adjusted_lb126_skip21_trend200_vol21_equal_monthly_abs_cap1_adjusted"
runs = [
    ("campea_2018_2026", "ema_cross_50_100", W, "2018-01-02", f"{R}/campea_2018_2026"),
    ("campea_teste_2023_2026", "ema_cross_50_100", W, "2023-01-02", f"{R}/campea_teste_2023_2026"),
    ("campea_do_treino_2018_2026", "time_series_momentum_12m", T, "2018-01-02", f"{R}/campea_do_treino_2018_2026"),
    ("campea_do_treino_teste_2023_2026", "time_series_momentum_12m", T, "2023-01-02", f"{R}/campea_do_treino_teste_2023_2026"),
    ("cci_depois", "cci_trend_14_m100_100_sma100", "top1_momentum_lb126_skip21_trend0_vol63_equal_weekly_abs_cap1_adjusted", "2018-01-02", f"{SP}/cci_depois"),
    ("macd", "macd_12_26_9_trend200", "top1_roc_short_blend_risk_adjusted_roc12_6_3_w1_1_2_short21x1_trend0_vol63_equal_monthly_posscore_adjusted", "2018-01-02", f"{SP}/macd"),
    ("don_full", "donchian_breakout_100_50", "top1_momentum_lb63_skip0_trend200_vol21_equal_monthly_abs_cap1_adjusted", "2018-01-02", f"{SP}/don_full"),
    ("don_teste", "donchian_breakout_100_50", "top1_momentum_lb63_skip0_trend200_vol21_equal_monthly_abs_cap1_adjusted", "2023-01-02", f"{SP}/don_teste"),
]
universe = _load_universe(Path("reports/matriz_sem_problematicas/universo_filtrado.json"))
tickers = [str(t).upper() for t in universe["market_data_tickers"]]
data = MarketData(tickers, "1d", "adjusted", require_verified_splits_from=universe["warmup_start"],
    history_start=str(universe["warmup_start"]), data_dir=Path("data/candles_point_in_time"),
    actions_dir=Path("data/actions_point_in_time"), manifests_dir=Path("data/manifests_point_in_time"),
    split_evidence_path=Path("data/corporate_actions/point_in_time_split_evidence.json"))
membership = _load_point_in_time_membership(universe, data.dates)
configs = {c.name: c for c in _configs("adjusted", "all")}
elig = {}
out = {}
for name, s, m, start, prefix in runs:
    if s not in elig:
        elig[s] = _build_eligibility(data, [s], "adjusted", signal_start=str(universe["warmup_start"]))[s]
    summ, curve = run_portfolio(data, configs[m], start=start, end="2026-08-19", initial_cash=1000.0, cost_bps=3.2,
        slippage_bps=10.0, lot_size=1, eligibility=elig[s], universe_membership=membership, collect_curve=True)
    real = {r["date"]: r for r in csv.DictReader(open(f"{prefix}_curva.csv"))}
    resumo = json.load(open(f"{prefix}_resumo.json"))
    norm = lambda v: set(filter(None, v.split(";")))
    diff = [(r.date, r.selected, real[r.date]["selected"]) for r in curve[:-1] if r.date in real and norm(r.selected) != norm(real[r.date]["selected"])]
    out[name] = {"matriz": summ.final_equity, "matriz_cagr": summ.cagr, "realista": resumo["final_equity"], "realista_cagr": resumo["cagr"],
                 "realista_dd": resumo["max_drawdown"], "ordens": resumo["trades"], "tarifas": resumo["fees_paid"], "ir": resumo["ordinary_income_tax_paid"],
                 "dias_carteira_diferente": len(diff), "dias": len(curve) - 1, "exemplos": diff[:6]}
    print(name, f"matriz R$ {summ.final_equity:,.2f} | realista R$ {resumo['final_equity']:,.2f} ({resumo['final_equity']/summ.final_equity-1:+.1%}) | carteira diferente em {len(diff)} de {len(curve)-1} pregoes", diff[:4])
json.dump(out, open(f"{SP}/matriz_x_motor_realista.json", "w"), indent=1)
