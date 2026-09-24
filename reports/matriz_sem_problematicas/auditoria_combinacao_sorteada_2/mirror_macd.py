"""Independent re-implementation of macd_12_26_9_trend200 +
top1_roc_short_blend_risk_adjusted_roc12_6_3_w1_1_2_short21x1_trend0_vol63_equal_monthly_posscore
compared day by day with the matrix engine."""
import datetime as dt, json, math, statistics, sys
from pathlib import Path
sys.path.insert(0, ".")
from scripts.backtest_strategy_management_combinations import _build_eligibility, _load_point_in_time_membership, _load_universe
from scripts.research_portfolio_allocation import MarketData, _configs, run_portfolio

S = "macd_12_26_9_trend200"
M = "top1_roc_short_blend_risk_adjusted_roc12_6_3_w1_1_2_short21x1_trend0_vol63_equal_monthly_posscore_adjusted"
START, END = sys.argv[1], sys.argv[2]
COST, SLIP = 3.2 / 1e4, 10 / 1e4
universe = _load_universe(Path("reports/matriz_sem_problematicas/universo_filtrado.json"))
tickers = [str(t).upper() for t in universe["market_data_tickers"]]
data = MarketData(tickers, "1d", "adjusted", require_verified_splits_from=universe["warmup_start"],
    history_start=str(universe["warmup_start"]), data_dir=Path("data/candles_point_in_time"),
    actions_dir=Path("data/actions_point_in_time"), manifests_dir=Path("data/manifests_point_in_time"),
    split_evidence_path=Path("data/corporate_actions/point_in_time_split_evidence.json"))
membership = _load_point_in_time_membership(universe, data.dates)
config = next(c for c in _configs("adjusted", "all") if c.name == M)
elig = _build_eligibility(data, [S], "adjusted", signal_start=str(universe["warmup_start"]))[S]
summary, curve = run_portfolio(data, config, start=START, end=END, initial_cash=1000.0, cost_bps=3.2,
    slippage_bps=10.0, lot_size=1, eligibility=elig, universe_membership=membership, collect_curve=True)
engine = {r.date: r for r in curve}

# ---------------- independent signal ----------------
def ema(values, n):
    out = [None] * len(values); cur = None; seen = []
    a = 2 / (n + 1)
    for i, v in enumerate(values):
        if v is None: continue
        if cur is None:
            seen.append(v)
            if len(seen) == n: cur = sum(seen) / n; out[i] = cur
            continue
        cur = a * v + (1 - a) * cur; out[i] = cur
    return out

sig, score, cl = {}, {}, {}
for t in tickers:
    cs = data.candles[t]; c = [x.close for x in cs]
    e12, e26 = ema(c, 12), ema(c, 26)
    macd = [None if a is None or b is None else a - b for a, b in zip(e12, e26)]
    sl = ema(macd, 9)
    s, sc = {}, {}
    for i, x in enumerate(cs):
        sma = sum(c[i - 199:i + 1]) / 200 if i >= 199 else None
        s[x.date] = int(macd[i] is not None and sl[i] is not None and macd[i] > sl[i] and sma is not None and c[i] > sma)
        if i >= 252:
            r = lambda w: c[i] / c[i - w] - 1
            base = (r(252) * 1 + r(126) * 1 + r(63) * 2) / 4
            if base > 0:
                blend = (base + r(21)) / 2
                rets = [c[k] / c[k - 1] - 1 for k in range(i - 62, i + 1)]
                vol = statistics.stdev(rets) * math.sqrt(252)
                if blend > 0 and vol > 0:
                    sc[x.date] = blend / vol
    sig[t], score[t] = s, sc
    cl[t] = {x.date: x for x in cs}

# signal agreement with the engine's eligibility
mism = sum(1 for t in tickers for i, x in enumerate(data.candles[t]) if sig[t][x.date] != elig[t][i])
print("dias-ativo com sinal diferente do motor:", mism)

# ---------------- independent execution ----------------
dates = [d for d in data.dates if START <= d <= END]
prev = [d for d in data.dates if d < START][-1]
bars = data.by_date  # includes certified transition aliases
cash, held, sh = 1000.0, None, 0
designated = None; mirror = {}; picks = []
active = None
def pick(d):
    cands = [(score[t][d], t) for t in tickers if t in membership.get(d, set()) and sig[t].get(d) == 1 and d in score[t]]
    return max(cands)[1] if cands else None
pending = None; todo = False
if prev[:7] != START[:7]:
    designated = pick(prev); pending = designated; picks.append((prev, designated)); todo = True
for k, d in enumerate(dates):
    nxt = dates[k + 1] if k + 1 < len(dates) else None
    # execute pending target (value of None means "go to cash")
    if todo:
        tgt = pending
        opn = lambda t: bars[t][d].open
        eq_open = cash + (sh * opn(held) if held else 0.0)
        if held and held != tgt:
            cash += sh * opn(held) * (1 - SLIP) * (1 - COST); held, sh = None, 0
        if tgt:
            p = opn(tgt); fill = p * (1 + SLIP)
            cur = sh * p if held == tgt else 0.0
            n = math.floor(max(0.0, eq_open - cur) / p)
            if n * fill * (1 + COST) > cash:
                n = math.floor(n * max(0.0, min(1.0, cash / (n * fill * (1 + COST)))))
            if n * fill * (1 + COST) > cash:
                n = math.floor(max(0.0, cash) / (fill * (1 + COST)))
            if n > 0:
                cash -= n * fill * (1 + COST); sh += n; held = tgt
        active = tgt
    todo = False
    eq = cash + (sh * bars[held][d].close if held else 0.0)
    if nxt is None and held:
        cash += sh * bars[held][d].close * (1 - SLIP) * (1 - COST); held, sh = None, 0; eq = cash
    mirror[d] = eq
    if nxt is None: break
    if d[:7] != nxt[:7]:
        designated = pick(d); picks.append((d, designated)); pending = designated; todo = True
    else:
        want = designated if designated and sig[designated].get(d) == 1 else None
        if want != active:
            pending = want; todo = True

common = [d for d in dates if d in engine]
diff = [abs(engine[d].equity / mirror[d] - 1) for d in common]
last = common[-1]
print(f"motor R$ {engine[last].equity:,.2f} | espelho R$ {mirror[last]:,.2f} | maior diferenca {max(diff):.6%} | dias > 0,01%: {sum(x > 1e-4 for x in diff)} de {len(common)}")
eng_sel = [(d, engine[d].selected) for d in common]
bad = next((d for d in common if abs(engine[d].equity / mirror[d] - 1) > 1e-9), None)
print("primeiro dia divergente:", bad)
if bad:
    i = common.index(bad)
    for d in common[max(0, i - 3): i + 3]: print(d, engine[d].selected, round(engine[d].equity, 4), round(mirror[d], 4))
json.dump({"picks": picks, "engine_final": engine[last].equity, "mirror_final": mirror[last]}, open(sys.argv[3], "w"))
