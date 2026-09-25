"""Family review of the 10 donchian_breakout_* strategies."""
import json, random, sys
from pathlib import Path
sys.path.insert(0, ".")
from b3_strategy_lab.strategies import build_signals, strategy_parameters, portfolio_strategies
from scripts.backtest_strategy_management_combinations import _build_eligibility, _load_universe
from scripts.research_portfolio_allocation import MarketData

FAM = [s for s in portfolio_strategies() if s.startswith("donchian_breakout")]
universe = _load_universe(Path("reports/matriz_sem_problematicas/universo_filtrado.json"))
tickers = [str(t).upper() for t in universe["market_data_tickers"]]
data = MarketData(tickers, "1d", "adjusted", require_verified_splits_from=universe["warmup_start"],
    history_start=str(universe["warmup_start"]), data_dir=Path("data/candles_point_in_time"),
    actions_dir=Path("data/actions_point_in_time"), manifests_dir=Path("data/manifests_point_in_time"),
    split_evidence_path=Path("data/corporate_actions/point_in_time_split_evidence.json"))
out = {"strategies": FAM}

# 1) OHLC consistency of the adjusted candles the family reads
bad_ohlc, split_checks = [], []
for t in tickers:
    cs = data.candles[t]
    for i, c in enumerate(cs):
        if not (c.low <= min(c.open, c.close) + 1e-9 and c.high >= max(c.open, c.close) - 1e-9 and c.low > 0):
            bad_ohlc.append((t, c.date, c.open, c.high, c.low, c.close))
        # high/low must carry the same adjustment factor as close
        if c.raw_close > 0 and c.raw_high > 0 and c.raw_low > 0:
            f = c.close / c.raw_close
            if abs(c.high / c.raw_high - f) > 1e-6 * f or abs(c.low / c.raw_low - f) > 1e-6 * f:
                split_checks.append((t, c.date, f, c.high / c.raw_high, c.low / c.raw_low))
out["ohlc_inconsistent"] = len(bad_ohlc); out["ohlc_examples"] = bad_ohlc[:10]
out["high_low_factor_mismatch"] = len(split_checks); out["factor_examples"] = split_checks[:10]
print("OHLC incoerente:", len(bad_ohlc), bad_ohlc[:5])
print("fator de ajuste de max/min diferente do fechamento:", len(split_checks), split_checks[:5])

# 2) independent re-implementation vs engine eligibility
def donchian(cs, entry, exit_, trend):
    pos, out_ = 0, []
    for i, c in enumerate(cs):
        if i >= max(entry, exit_):
            ok = trend == 0 or (i >= trend - 1 and c.close > sum(x.close for x in cs[i - trend + 1:i + 1]) / trend)
            if pos == 0:
                if c.close > max(x.high for x in cs[i - entry:i]) and ok: pos = 1
            elif c.close < min(x.low for x in cs[i - exit_:i]): pos = 0
        out_.append(pos)
    return out_

elig = _build_eligibility(data, FAM, "adjusted", signal_start=str(universe["warmup_start"]))
res = {}
for s in FAM:
    p = strategy_parameters(s)
    mism = days = 0
    for t in tickers:
        mine = donchian(data.candles[t], p["entry_window"], p["exit_window"], p["trend_window"])
        mism += sum(a != b for a, b in zip(mine, elig[s][t])); days += len(mine)
    res[s] = {"params": p, "ticker_days": days, "mismatches_vs_independent": mism}
    print(s, p, "dias-ativo", days, "divergencias", mism)

# 3) causality: prefix signals equal full-series signals
rng = random.Random(11)
for s in FAM:
    p = strategy_parameters(s); checks = mism = 0
    for t in tickers:
        cs = data.candles[t]; full = build_signals(s, cs, **p)
        lo = max(p["entry_window"], p["exit_window"], p["trend_window"]) + 5
        for cut in rng.sample(range(lo, len(cs)), min(12, max(0, len(cs) - lo))):
            checks += 1; mism += build_signals(s, cs[:cut + 1], **p) != full[:cut + 1]
    res[s]["causality_checks"] = checks; res[s]["causality_mismatches"] = mism
    print(s, "cortes", checks, "divergencias", mism)

# 4) sanity of entries/exits: every 0->1 is a close above the prior N-day high, every 1->0 below prior M-day low
for s in FAM:
    p = strategy_parameters(s); viol = entries = exits = 0; hold = []
    for t in tickers:
        cs = data.candles[t]; sig = elig[s][t]; run = 0
        for i in range(1, len(sig)):
            if sig[i] == 1 and sig[i - 1] == 0:
                entries += 1
                viol += not cs[i].close > max(x.high for x in cs[i - p["entry_window"]:i])
            if sig[i] == 0 and sig[i - 1] == 1:
                exits += 1; hold.append(run)
                viol += not cs[i].close < min(x.low for x in cs[i - p["exit_window"]:i])
            run = run + 1 if sig[i] == 1 else 0
    hold.sort()
    res[s].update({"entries": entries, "exits": exits, "rule_violations": viol,
                   "median_holding_days": hold[len(hold) // 2] if hold else None})
    print(s, "entradas", entries, "saidas", exits, "violacoes", viol, "mediana dias", res[s]["median_holding_days"])
out["per_strategy"] = res
json.dump(out, open(sys.argv[1], "w"), indent=1)
