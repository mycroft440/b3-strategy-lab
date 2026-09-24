"""Compare every held ticker-day (raw open/close) of the drawn combo with official COTAHIST
and check that adjusted/raw ratio changes only on documented corporate-action dates."""
import io, sys, zipfile, collections
from pathlib import Path
sys.path.insert(0, ".")
from scripts.backtest_strategy_management_combinations import _build_eligibility, _load_point_in_time_membership, _load_universe
from scripts.research_portfolio_allocation import MarketData, _configs, run_portfolio
S = "macd_12_26_9_trend200"
M = "top1_roc_short_blend_risk_adjusted_roc12_6_3_w1_1_2_short21x1_trend0_vol63_equal_monthly_posscore_adjusted"
universe = _load_universe(Path("reports/matriz_sem_problematicas/universo_filtrado.json"))
tickers = [str(t).upper() for t in universe["market_data_tickers"]]
data = MarketData(tickers, "1d", "adjusted", require_verified_splits_from=universe["warmup_start"],
    history_start=str(universe["warmup_start"]), data_dir=Path("data/candles_point_in_time"),
    actions_dir=Path("data/actions_point_in_time"), manifests_dir=Path("data/manifests_point_in_time"),
    split_evidence_path=Path("data/corporate_actions/point_in_time_split_evidence.json"))
membership = _load_point_in_time_membership(universe, data.dates)
config = next(c for c in _configs("adjusted", "all") if c.name == M)
elig = _build_eligibility(data, [S], "adjusted", signal_start=str(universe["warmup_start"]))[S]
_, curve = run_portfolio(data, config, start="2018-01-02", end="2026-08-19", initial_cash=1000.0, cost_bps=3.2,
    slippage_bps=10.0, lot_size=1, eligibility=elig, universe_membership=membership, collect_curve=True)
need = collections.defaultdict(set)  # (ticker) -> dates held or traded
prev_sel = ""
for r in curve:
    for t in set(filter(None, r.selected.split(";"))) | set(filter(None, prev_sel.split(";"))):
        need[t].add(r.date)
    prev_sel = r.selected
held = collections.Counter(t for r in curve for t in filter(None, r.selected.split(";")))
print("dias em carteira por acao:", held.most_common())
want = {(t, d) for t, ds in need.items() for d in ds}
official = {}
for z in sorted(Path(".cache/cotahist").glob("COTAHIST_A20*.ZIP")):
    with zipfile.ZipFile(z) as f:
        for line in io.TextIOWrapper(f.open(f.namelist()[0]), encoding="latin-1"):
            if not line.startswith("01") or line[24:27] != "010": continue
            t = line[12:24].strip(); d = f"{line[2:6]}-{line[6:8]}-{line[8:10]}"
            if (t, d) in want:
                official[(t, d)] = (int(line[56:69]) / 100, int(line[108:121]) / 100)
ok = bad = missing = 0; examples = []
for (t, d) in sorted(want):
    c = data.by_date[t].get(d)
    if c is None: missing += 1; continue
    o = official.get((t, d))
    if o is None: missing += 1; examples.append(("sem COTAHIST", t, d)); continue
    if abs(c.raw_open - o[0]) < 0.005 and abs(c.raw_close - o[1]) < 0.005: ok += 1
    else: bad += 1; examples.append((t, d, c.raw_open, c.raw_close, o))
print("conferem:", ok, "divergem:", bad, "sem dado:", missing)
for e in examples[:10]: print(e)
print("--- mudancas do fator de ajuste em dias em carteira ---")
for r0, r1 in zip(curve, curve[1:]):
    for t in set(filter(None, r0.selected.split(";"))) & set(filter(None, r1.selected.split(";"))):
        a, b = data.by_date[t].get(r0.date), data.by_date[t].get(r1.date)
        fa, fb = a.close / a.raw_close, b.close / b.raw_close
        if abs(fa / fb - 1) > 1e-6 or a.ticker != b.ticker:
            print(t, r0.date, "->", r1.date, a.ticker, b.ticker, f"raw {a.raw_close}->{b.raw_close}", f"ajustado {a.close:.4f}->{b.close:.4f}", f"ret ajustado {b.close/a.close-1:.2%}")
for t in ("BTOW3", "VVAR3", "OIBR3"):
    ds = sorted(d for d in need[t])
    print(t, ds[0], ds[-1])
