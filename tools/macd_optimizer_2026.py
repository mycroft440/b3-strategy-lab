#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, math, time
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf
from numba import njit, prange

SYMBOLS = [
    "BBSE3","PETR3","VALE3","ITUB4","PRIO3","WEGE3","B3SA3","BPAC11","GGBR4","EMBJ3",
    "TOTS3","RADL3","RDOR3","FLRY3","PSSA3","SBSP3","CPFE3","EGIE3","VIVT3","CYRE3",
    "CURY3","RENT3","MULT3","SMFT3","LREN3","VBBR3","EQTL3","CPLE3","AXIA3","ENEV3",
    "RAIL3","CSMG3","ABEV3","BBDC4","BBAS3","CMIG4","CMIN3","KLBN11","SUZB3","DIRR3",
]
START = pd.Timestamp("2026-01-01")
END = pd.Timestamp("2026-07-31")
WARMUP_START = pd.Timestamp("2024-01-01")
DOWNLOAD_END = pd.Timestamp("2026-08-03")
MOM = 126
VOL = 63
INITIAL = 1000.0


def history(symbol: str, cache: Path) -> pd.DataFrame:
    cache.mkdir(parents=True, exist_ok=True)
    p = cache / f"{symbol.lower()}.csv"
    if p.exists():
        x = pd.read_csv(p, parse_dates=["Date"], index_col="Date")
        x.index = pd.to_datetime(x.index).normalize()
        return x
    last = None
    for attempt in range(4):
        try:
            x = yf.Ticker(symbol + ".SA").history(
                start=WARMUP_START.strftime("%Y-%m-%d"), end=DOWNLOAD_END.strftime("%Y-%m-%d"),
                interval="1d", auto_adjust=False, actions=True, repair=True,
            )
            if not x.empty:
                x = x.copy()
                if x.index.tz is not None:
                    x.index = x.index.tz_localize(None)
                x.index = pd.to_datetime(x.index).normalize()
                ratios = pd.to_numeric(x.get("Stock Splits", 0.0), errors="coerce")
                if not isinstance(ratios, pd.Series):
                    ratios = pd.Series(1.0, index=x.index)
                else:
                    ratios = ratios.fillna(0.0).where(ratios > 0.0, 1.0)
                # Split-only adjustment. A split on D adjusts dates before D, not D itself.
                f = ratios.iloc[::-1].cumprod().iloc[::-1] / ratios
                for c in ("Open","High","Low","Close"):
                    x[c] = pd.to_numeric(x[c], errors="coerce") / f
                x[[c for c in ("Open","High","Low","Close","Volume","Stock Splits") if c in x]].to_csv(p, index_label="Date")
                return x
        except Exception as e:
            last = e
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Falha ao baixar {symbol}.SA: {last}")


def seeded_ema(v: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(v), np.nan)
    a = 2.0 / (n + 1.0)
    buf, state = [], np.nan
    for i, x in enumerate(v):
        if not np.isfinite(x):
            continue
        if not np.isfinite(state):
            buf.append(float(x))
            if len(buf) == n:
                state = float(np.mean(buf))
                out[i] = state
        else:
            state = x * a + state * (1.0 - a)
            out[i] = state
    return out


def score_series(v: np.ndarray) -> np.ndarray:
    out = np.full(len(v), np.nan)
    idx = np.flatnonzero(np.isfinite(v))
    if len(idx) < MOM + 2:
        return out
    c = v[idx]
    r = np.full(len(c), np.nan)
    r[1:] = c[1:] / c[:-1] - 1.0
    for j in range(MOM, len(c)):
        m = c[j] / c[j-MOM] - 1.0
        if m <= 0:
            continue
        s = j - VOL + 1
        if s < 1:
            continue
        w = r[s:j+1]
        if len(w) != VOL or not np.all(np.isfinite(w)):
            continue
        vol = float(np.std(w, ddof=1)) * math.sqrt(252.0)
        if vol > 0 and np.isfinite(vol):
            out[idx[j]] = m / vol
    return out


def prepare(cache: Path, max_period: int):
    raw = {}
    for i, s in enumerate(SYMBOLS, 1):
        print(f"[{i:02d}/40] {s}", flush=True)
        raw[s] = history(s, cache)

    ref = raw["ITUB4"]
    cal = ref.index[(ref.index >= WARMUP_START) & (ref.index <= END)]
    cal = pd.DatetimeIndex(cal[ref.loc[cal, "Close"].notna()]).sort_values().unique()
    pos = {d:i for i,d in enumerate(cal)}
    days = cal[(cal >= START) & (cal <= END)]
    rebs, prev_key = [], None
    for d in days:
        iso = d.isocalendar(); key = (int(iso.year), int(iso.week))
        if key != prev_key:
            rebs.append(d); prev_key = key
    reb = np.array([pos[d] for d in rebs if pos[d] > 0], np.int32)
    snap = reb - 1
    final_idx = pos[days[-1]]

    A, T = 40, len(cal)
    close = np.full((A,T), np.nan)
    opn = np.full((A,T), np.nan)
    score = np.full((A,T), np.nan)
    ema = np.full((A,max_period+1,T), np.nan)
    for a,s in enumerate(SYMBOLS):
        x = raw[s].reindex(cal)
        close[a] = pd.to_numeric(x["Close"], errors="coerce").to_numpy(float)
        opn[a] = pd.to_numeric(x["Open"], errors="coerce").to_numpy(float)
        score[a] = score_series(close[a])
        for p in range(1,max_period+1):
            ema[a,p] = seeded_ema(close[a], p)
    return cal, close, opn, score, ema, reb, snap, final_idx


@njit(cache=True)
def one(fast, slow, siglen, ema, close, opn, score, reb, snap, final_idx):
    A, T = close.shape
    W = len(reb)
    chosen = np.full(W, -1, np.int32)
    best = np.full(W, -1e300)
    alpha = 2.0 / (siglen + 1.0)

    for a in range(A):
        seed_sum = 0.0; seed_count = 0; state = np.nan; wp = 0
        for t in range(T):
            ef = ema[a,fast,t]; es = ema[a,slow,t]
            macd = np.nan
            if np.isfinite(ef) and np.isfinite(es):
                macd = ef - es
                if not np.isfinite(state):
                    seed_sum += macd; seed_count += 1
                    if seed_count == siglen:
                        state = seed_sum / siglen
                else:
                    state = macd * alpha + state * (1.0-alpha)
            if wp < W and t == snap[wp]:
                sc = score[a,t]; ex = reb[wp]; px = opn[a,ex]
                if np.isfinite(macd) and np.isfinite(state) and macd > state and np.isfinite(sc) and np.isfinite(px) and px > 0:
                    if sc > best[wp]:
                        best[wp] = sc; chosen[wp] = a
                wp += 1
            if wp >= W and t >= final_idx:
                break

    cash = INITIAL; holding = -1; qty = 0; rotations = 0
    for w in range(W):
        ex = reb[w]; sp = snap[w]
        equity = cash
        if holding >= 0 and qty > 0:
            mark = opn[holding,ex]
            if not (np.isfinite(mark) and mark > 0):
                mark = close[holding,sp]
            if np.isfinite(mark) and mark > 0:
                equity += qty * mark
        nh = chosen[w]
        if w > 0 and nh != holding:
            rotations += 1
        cash = equity; holding = -1; qty = 0
        if nh >= 0:
            px = opn[nh,ex]
            units = int(math.floor(cash/px))
            if units >= 1:
                holding = nh; qty = units; cash -= units*px
    final = cash
    if holding >= 0 and qty > 0:
        mark = close[holding,final_idx]
        if np.isfinite(mark) and mark > 0:
            final += qty*mark
    return final, rotations


@njit(parallel=True, cache=True)
def sweep(combos, ema, close, opn, score, reb, snap, final_idx):
    n = len(combos); final = np.empty(n); rot = np.empty(n, np.int32)
    for i in prange(n):
        f,s,g = combos[i]
        final[i], rot[i] = one(int(f),int(s),int(g),ema,close,opn,score,reb,snap,final_idx)
    return final, rot


def combos(lo=1, hi=50):
    # Testa os dois ordenamentos (ex.: 12/26 e 26/12); fast==slow e degenerado.
    return np.array([(f,s,g) for f in range(lo,hi+1) for s in range(lo,hi+1) if f != s for g in range(lo,hi+1)], dtype=np.int16)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=1)
    ap.add_argument("--max", type=int, default=50)
    ap.add_argument("--cache", type=Path, default=Path(".cache/macd_optimizer_2026"))
    ap.add_argument("--out", type=Path, default=Path("artifacts/macd_optimizer_2026"))
    args = ap.parse_args()
    c = combos(args.min,args.max)
    print(f"Combinacoes: {len(c):,}", flush=True)
    cal,close,opn,score,ema,reb,snap,final_idx = prepare(args.cache,args.max)
    print(f"Pregoes carregados: {len(cal)} | rebalanceamentos: {len(reb)}", flush=True)
    t=time.time(); final,rot=sweep(c,ema,close,opn,score,reb,snap,final_idx)
    print(f"Sweep concluido em {time.time()-t:.1f}s", flush=True)
    ret=final/INITIAL-1.0
    order=np.lexsort((rot,-ret)); b=int(order[0]); f,s,g=map(int,c[b])
    args.out.mkdir(parents=True,exist_ok=True)
    top=order[:min(500,len(order))]
    pd.DataFrame({"rank":np.arange(1,len(top)+1),"fast":c[top,0],"slow":c[top,1],"signal":c[top,2],"return_2026":ret[top],"capital_final":final[top],"rotations":rot[top]}).to_csv(args.out/"top_results.csv",index=False)
    result={"range":[args.min,args.max],"combinations":int(len(c)),"period":[str(START.date()),str(END.date())],"stocks":SYMBOLS,"winner":{"fast":f,"slow":s,"signal":g,"return":float(ret[b]),"return_pct":float(ret[b]*100),"capital_final":float(final[b]),"rotations":int(rot[b])}}
    (args.out/"winner.json").write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    summary=f"PERIODO VENCEDOR DO MACD: {f} {s} {g}\nRESULTADO 2026: {ret[b]*100:.2f}%\nCAPITAL: R${INITIAL:.2f} -> R${final[b]:.2f}\nCOMBINACOES TESTADAS: {len(c)}\nPERIODO: {START.date()} a {END.date()}\n"
    (args.out/"optimizer_summary.txt").write_text(summary,encoding="utf-8")
    (args.out/"pine_winner_constants.txt").write_text(f"const int OPT_MACD_FAST = {f}\nconst int OPT_MACD_SLOW = {s}\nconst int OPT_MACD_SIGNAL = {g}\nconst float OPT_MACD_RETURN_2026 = {ret[b]:.10f}\n",encoding="utf-8")
    print("\n"+summary,flush=True)

if __name__ == "__main__":
    main()
