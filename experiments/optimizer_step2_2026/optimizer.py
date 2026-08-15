from __future__ import annotations

import argparse
import csv
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
from numba import njit, prange, set_num_threads, get_num_threads

BT_START = pd.Timestamp('2026-01-01')
BT_END = pd.Timestamp('2026-07-31')
LOAD_START = pd.Timestamp('2024-01-01')
INITIAL_CAPITAL = 1000.0

UNIVERSE = [
    'BBSE3','PETR3','VALE3','ITUB4','PRIO3','WEGE3','B3SA3','BPAC11','GGBR4','EMBJ3',
    'TOTS3','RADL3','RDOR3','FLRY3','PSSA3','SBSP3','CPFE3','EGIE3','VIVT3','CYRE3',
    'CURY3','RENT3','MULT3','SMFT3','LREN3','VBBR3','EQTL3','CPLE3','AXIA3','ENEV3',
    'RAIL3','CSMG3','ABEV3','BBDC4','BBAS3','CMIG4','CMIN3','KLBN11','SUZB3','DIRR3',
]
REFERENCE = 'ITUB4'
MACD_VALUES = np.arange(1, 121, 2, dtype=np.int16)
MOM_VALUES = np.arange(1, 201, 2, dtype=np.int16)
VOL_VALUES = np.arange(2, 201, 2, dtype=np.int16)
N_MACD_VALUES = len(MACD_VALUES)
N_MOM_VALUES = len(MOM_VALUES)
N_VOL_VALUES = len(VOL_VALUES)
N_MGMT = N_MOM_VALUES * N_VOL_VALUES
N_MACD = N_MACD_VALUES * (N_MACD_VALUES - 1) * N_MACD_VALUES
TOTAL_COMBINATIONS = N_MACD * N_MGMT


def candle_path(root: Path, ticker: str) -> Path:
    return root / 'data' / 'candles' / f'{ticker.lower()}_1d.csv'


def actions_path(root: Path, ticker: str) -> Path:
    return root / 'data' / 'corporate_actions' / f'{ticker.lower()}_actions.csv'


def _read_raw_prices(root: Path, ticker: str) -> pd.DataFrame:
    path = candle_path(root, ticker)
    if not path.exists():
        raise FileNotFoundError(str(path))
    df = pd.read_csv(path, parse_dates=['date'])
    required = {'date','raw_open','raw_close'}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f'{ticker}: missing columns {sorted(missing)}')
    df = df[['date','raw_open','raw_close']].copy()
    df['date'] = pd.to_datetime(df['date']).dt.normalize()
    df = df.drop_duplicates('date', keep='last').sort_values('date').set_index('date')
    for c in ('raw_open','raw_close'):
        df[c] = pd.to_numeric(df[c], errors='coerce')
        df.loc[df[c] <= 0, c] = np.nan
    return df


def _split_only_adjust(root: Path, ticker: str, df: pd.DataFrame) -> pd.DataFrame:
    ap = actions_path(root, ticker)
    actions = []
    if ap.exists():
        adf = pd.read_csv(ap, parse_dates=['date'])
        if 'split_ratio' not in adf.columns:
            raise ValueError(f'{ticker}: corporate-actions file lacks split_ratio')
        for row in adf[['date','split_ratio']].itertuples(index=False):
            d = pd.Timestamp(row.date).normalize()
            r = float(row.split_ratio) if pd.notna(row.split_ratio) else 1.0
            if math.isfinite(r) and r > 0 and abs(r - 1.0) > 1e-12:
                actions.append((d, r))
    idx = df.index
    factor = np.ones(len(df), dtype=np.float64)
    for d, ratio in actions:
        factor[idx < d] *= ratio
    out = pd.DataFrame(index=idx)
    out['open'] = df['raw_open'].to_numpy(dtype=np.float64) / factor
    out['close'] = df['raw_close'].to_numpy(dtype=np.float64) / factor
    return out


def load_universe(root: Path):
    frames = {}
    missing = [t for t in UNIVERSE if not candle_path(root, t).exists()]
    if missing:
        raise FileNotFoundError('Missing candle files for current 40-stock universe: ' + ', '.join(missing))
    for ticker in UNIVERSE:
        frames[ticker] = _split_only_adjust(root, ticker, _read_raw_prices(root, ticker))
    ref = frames[REFERENCE]
    calendar = ref.index[(ref.index >= LOAD_START) & (ref.index <= BT_END) & ref['close'].notna()]
    calendar = pd.DatetimeIndex(calendar).sort_values().unique()
    if len(calendar) < 250:
        raise RuntimeError(f'Reference calendar has only {len(calendar)} bars')
    a, d = len(UNIVERSE), len(calendar)
    opens = np.full((a,d), np.nan, dtype=np.float64)
    closes = np.full((a,d), np.nan, dtype=np.float64)
    for i,ticker in enumerate(UNIVERSE):
        aligned = frames[ticker].reindex(calendar)
        opens[i] = aligned['open'].to_numpy(dtype=np.float64)
        closes[i] = aligned['close'].to_numpy(dtype=np.float64)
    return calendar, opens, closes


def build_weeks(calendar):
    in_bt = np.flatnonzero((calendar >= BT_START) & (calendar <= BT_END))
    if len(in_bt) == 0:
        raise RuntimeError('No B3 dates inside backtest window')
    rebs, last_key = [], None
    for idx in in_bt:
        iso = calendar[idx].isocalendar(); key = (int(iso.year), int(iso.week))
        if key != last_key:
            rebs.append(int(idx)); last_key = key
    rebs = np.asarray(rebs, dtype=np.int32); snaps = rebs - 1
    if np.any(snaps < 0):
        raise RuntimeError('Insufficient warm-up before first rebalance')
    return rebs, snaps, int(in_bt[-1])


@njit(cache=True)
def seeded_ema_matrix(closes, periods):
    a,d = closes.shape; pcount = len(periods)
    out = np.full((a,pcount,d), np.nan, np.float32)
    for ai in range(a):
        for pi in range(pcount):
            p = int(periods[pi]); alpha = 2.0 / (p + 1.0)
            buf = np.empty(p, np.float64); bcount = 0; state = np.nan
            for t in range(d):
                x = closes[ai,t]
                if not np.isfinite(x):
                    continue
                if not np.isfinite(state):
                    if bcount < p:
                        buf[bcount] = x; bcount += 1
                    if bcount == p:
                        s = 0.0
                        for k in range(p): s += buf[k]
                        state = s / p; out[ai,pi,t] = state
                else:
                    state = x * alpha + state * (1.0-alpha); out[ai,pi,t] = state
    return out


@njit(cache=True)
def build_momentum_snapshots(closes, snaps, periods):
    a,d = closes.shape; w=len(snaps); pc=len(periods)
    out = np.full((pc,w,a), np.nan, np.float32)
    for pi in range(pc):
        p = int(periods[pi])
        for wi in range(w):
            t = int(snaps[wi])
            for ai in range(a):
                if t-p >= 0:
                    c = closes[ai,t]; old = closes[ai,t-p]
                    if np.isfinite(c) and np.isfinite(old) and old > 0:
                        out[pi,wi,ai] = c/old - 1.0
    return out


@njit(cache=True)
def build_vol_snapshots(closes, snaps, periods):
    a,d=closes.shape; w=len(snaps); pc=len(periods)
    rets = np.full((a,d), np.nan, np.float64)
    for ai in range(a):
        for t in range(1,d):
            c=closes[ai,t]; p=closes[ai,t-1]
            if np.isfinite(c) and np.isfinite(p) and p>0:
                rets[ai,t]=c/p-1.0
    out=np.full((pc,w,a),np.nan,np.float32)
    for pi in range(pc):
        n=int(periods[pi])
        for wi in range(w):
            t=int(snaps[wi]); start=t-n+1
            if start < 1: continue
            for ai in range(a):
                count=0; s=0.0; ss=0.0
                for k in range(start,t+1):
                    x=rets[ai,k]
                    if np.isfinite(x): count+=1; s+=x; ss+=x*x
                if count==n and n>1:
                    var=(ss - s*s/n)/(n-1)
                    if var < 0 and var > -1e-15: var=0.0
                    if var>=0: out[pi,wi,ai]=math.sqrt(var)*math.sqrt(252.0)
    return out


def build_management_rankings(mom, vol):
    m = mom[:,None,:,:]; v = vol[None,:,:,:]
    valid = np.isfinite(m) & np.isfinite(v) & (m > 0.0) & (v > 0.0)
    scores = np.where(valid, m/v, -np.inf).astype(np.float32)
    flat = scores.reshape(N_MGMT, scores.shape[2], scores.shape[3])
    rankings = np.argsort(-flat, axis=2).astype(np.uint8)
    valid_mask = np.zeros((N_MGMT, flat.shape[1]), dtype=np.uint64)
    finite = np.isfinite(flat)
    for a in range(flat.shape[2]):
        valid_mask |= (finite[:,:,a].astype(np.uint64) << np.uint64(a))
    return rankings, valid_mask


def build_macd_index():
    fast=[]; slow=[]; sig=[]
    for fi in range(N_MACD_VALUES):
        for si in range(N_MACD_VALUES):
            if fi == si: continue
            for gi in range(N_MACD_VALUES):
                fast.append(fi); slow.append(si); sig.append(gi)
    return np.asarray(fast,np.uint8), np.asarray(slow,np.uint8), np.asarray(sig,np.uint8)


@njit(parallel=True, cache=True)
def build_macd_masks(emas, snaps, fast_idx, slow_idx, signal_idx, signal_periods):
    n=len(fast_idx); a=emas.shape[0]; d=emas.shape[2]; w=len(snaps)
    masks=np.zeros((n,w),np.uint64); snapmap=np.full(d,-1,np.int16)
    for wi in range(w): snapmap[int(snaps[wi])] = wi
    for ci in prange(n):
        fi=int(fast_idx[ci]); si=int(slow_idx[ci]); sp=int(signal_periods[int(signal_idx[ci])])
        alpha=2.0/(sp+1.0); local=np.zeros(w,np.uint64)
        for ai in range(a):
            state=np.nan; seed_sum=0.0; seed_count=0
            for t in range(d):
                ef=emas[ai,fi,t]; es=emas[ai,si,t]; macd=np.nan
                if np.isfinite(ef) and np.isfinite(es):
                    macd=float(ef-es)
                    if not np.isfinite(state):
                        seed_sum += macd; seed_count += 1
                        if seed_count == sp: state = seed_sum/sp
                    else:
                        state = macd*alpha + state*(1.0-alpha)
                wi=int(snapmap[t])
                if wi>=0 and np.isfinite(macd) and np.isfinite(state) and macd>state:
                    local[wi] |= (np.uint64(1) << np.uint64(ai))
        for wi in range(w): masks[ci,wi]=local[wi]
    return masks


def build_period_prices(opens, closes, rebs, snaps, final_idx):
    w=len(rebs); a=opens.shape[0]
    entry=np.full((w,a),np.nan,np.float32); exitp=np.full((w,a),np.nan,np.float32); open_mask=np.zeros(w,np.uint64)
    for wi in range(w):
        t=int(rebs[wi])
        for ai in range(a):
            x=opens[ai,t]
            if np.isfinite(x) and x>0:
                entry[wi,ai]=x; open_mask[wi] |= (np.uint64(1)<<np.uint64(ai))
        if wi+1 < w:
            nt=int(rebs[wi+1]); ps=int(snaps[wi+1])
            for ai in range(a):
                x=opens[ai,nt]
                if not (np.isfinite(x) and x>0): x=closes[ai,ps]
                if np.isfinite(x) and x>0: exitp[wi,ai]=x
        else:
            for ai in range(a):
                x=closes[ai,final_idx]
                if np.isfinite(x) and x>0: exitp[wi,ai]=x
    return entry,exitp,open_mask


@njit(parallel=True, cache=True)
def evaluate_pairs(start_pair, count, macd_masks, rankings, mgmt_valid, open_mask, entry, exitp):
    out=np.empty(count,np.float64); mcount=rankings.shape[0]; wcount=rankings.shape[1]
    for j in prange(count):
        pair=start_pair+j; ci=pair//mcount; mi=pair-ci*mcount; cap=INITIAL_CAPITAL
        for wi in range(wcount):
            mask = macd_masks[ci,wi] & mgmt_valid[mi,wi] & open_mask[wi]
            if mask == 0: continue
            chosen=-1
            for ri in range(rankings.shape[2]):
                ai=int(rankings[mi,wi,ri])
                if (mask & (np.uint64(1)<<np.uint64(ai))) != 0:
                    chosen=ai; break
            if chosen>=0:
                buy=float(entry[wi,chosen]); sell=float(exitp[wi,chosen])
                if np.isfinite(buy) and buy>0 and np.isfinite(sell) and sell>0:
                    qty=math.floor(cap/buy)
                    if qty>=1: cap=(cap-qty*buy)+qty*sell
        out[j]=cap
    return out


def params_for_pair(pair, fast_idx, slow_idx, signal_idx):
    ci=pair//N_MGMT; mi=pair%N_MGMT; momi=mi//N_VOL_VALUES; voli=mi%N_VOL_VALUES
    return {'fast':int(MACD_VALUES[int(fast_idx[ci])]),'slow':int(MACD_VALUES[int(slow_idx[ci])]),'signal':int(MACD_VALUES[int(signal_idx[ci])]),'momentum':int(MOM_VALUES[momi]),'volatility':int(VOL_VALUES[voli])}


def validate(root):
    missing=[t for t in UNIVERSE if not candle_path(root,t).exists()]
    report={'universe':UNIVERSE,'missing':missing,'total_expected_combinations':int(TOTAL_COMBINATIONS)}
    if missing: report['ok']=False; return report
    calendar,opens,closes=load_universe(root); rebs,snaps,final_idx=build_weeks(calendar)
    ready=[]; first_snap=int(snaps[0])
    for ai,t in enumerate(UNIVERSE): ready.append(int(np.isfinite(closes[ai,:first_snap+1]).sum()))
    report.update({'ok':min(ready)>=240,'calendar_bars':len(calendar),'weekly_rebalances':len(rebs),'bars_before_first_rebalance_min':min(ready),'bars_before_first_rebalance_max':max(ready)})
    return report


def prepare(root, out):
    t0=time.perf_counter(); calendar,opens,closes=load_universe(root); rebs,snaps,final_idx=build_weeks(calendar)
    print(f'calendar={len(calendar)} weeks={len(rebs)} assets={len(UNIVERSE)}')
    emas=seeded_ema_matrix(closes,MACD_VALUES); print(f'EMA ready {time.perf_counter()-t0:.1f}s')
    mom=build_momentum_snapshots(closes,snaps,MOM_VALUES); vol=build_vol_snapshots(closes,snaps,VOL_VALUES)
    rankings,mgmt_valid=build_management_rankings(mom,vol); print(f'management rankings ready {time.perf_counter()-t0:.1f}s')
    fi,si,gi=build_macd_index(); print(f'MACD configs={len(fi):,}; numba threads={get_num_threads()}')
    masks=build_macd_masks(emas,snaps,fi,si,gi,MACD_VALUES); print(f'MACD masks ready {time.perf_counter()-t0:.1f}s')
    entry,exitp,open_mask=build_period_prices(opens,closes,rebs,snaps,final_idx)
    out.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(out, macd_masks=masks, rankings=rankings, mgmt_valid=mgmt_valid, open_mask=open_mask, entry=entry, exitp=exitp, fast_idx=fi, slow_idx=si, signal_idx=gi)
    meta={'total_combinations':int(TOTAL_COMBINATIONS),'macd_configs':int(N_MACD),'management_configs':int(N_MGMT),'weeks':int(len(rebs)),'assets':UNIVERSE,'prepare_seconds':time.perf_counter()-t0}
    out.with_suffix('.json').write_text(json.dumps(meta,indent=2),encoding='utf-8'); print(json.dumps(meta,indent=2))


def load_prepared(path):
    z=np.load(path,allow_pickle=False)
    return tuple(z[k] for k in ('macd_masks','rankings','mgmt_valid','open_mask','entry','exitp','fast_idx','slow_idx','signal_idx'))


def benchmark(prepared, pairs, out):
    masks,rankings,mgmt_valid,open_mask,entry,exitp,fi,si,gi=load_prepared(prepared); pairs=min(int(pairs),TOTAL_COMBINATIONS)
    evaluate_pairs(0,min(1024,pairs),masks,rankings,mgmt_valid,open_mask,entry,exitp)
    t0=time.perf_counter(); done=0; chunk=250_000; best_cap=-1.0; best_pair=-1
    while done<pairs:
        n=min(chunk,pairs-done); vals=evaluate_pairs(done,n,masks,rankings,mgmt_valid,open_mask,entry,exitp); k=int(np.argmax(vals)); v=float(vals[k])
        if v>best_cap: best_cap=v; best_pair=done+k
        done+=n
    elapsed=time.perf_counter()-t0; rate=done/elapsed; est_full=TOTAL_COMBINATIONS/rate; est_shard=math.ceil(TOTAL_COMBINATIONS/256)/rate
    result={'pairs':done,'elapsed_seconds':elapsed,'pairs_per_second':rate,'estimated_full_single_runner_hours':est_full/3600,'estimated_256_shard_job_hours_each':est_shard/3600,'best_sample_pair':best_pair,'best_sample_capital':best_cap,'best_sample_params':params_for_pair(best_pair,fi,si,gi),'numba_threads':get_num_threads()}
    out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,indent=2),encoding='utf-8'); print(json.dumps(result,indent=2)); return result


def run_shard(prepared, shard, shards, out, topk=100):
    masks,rankings,mgmt_valid,open_mask,entry,exitp,fi,si,gi=load_prepared(prepared); per=math.ceil(TOTAL_COMBINATIONS/shards); start=shard*per; end=min(TOTAL_COMBINATIONS,start+per)
    if start>=end: raise SystemExit('empty shard')
    best=[]; chunk=250_000; pos=start; t0=time.perf_counter()
    while pos<end:
        n=min(chunk,end-pos); vals=evaluate_pairs(pos,n,masks,rankings,mgmt_valid,open_mask,entry,exitp); take=min(topk,n); ids=np.argpartition(vals,-take)[-take:]
        for idx in ids: best.append((float(vals[int(idx)]),pos+int(idx)))
        best=sorted(best,reverse=True)[:topk]; pos+=n
        if (pos-start)%(chunk*8)==0 or pos==end:
            rate=(pos-start)/(time.perf_counter()-t0); print(f'shard {shard}: {pos-start:,}/{end-start:,} rate={rate:,.0f}/s best={best[0][0]:.2f}',flush=True)
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['capital','return_pct','pair','fast','slow','signal','momentum','volatility']); w.writeheader()
        for cap,pair in best: w.writerow({'capital':cap,'return_pct':(cap/INITIAL_CAPITAL-1)*100,'pair':pair,**params_for_pair(pair,fi,si,gi)})


def merge_results(results_dir, out, topk=200):
    rows=[]
    for p in results_dir.rglob('*.csv'):
        try: rows.extend(pd.read_csv(p).to_dict('records'))
        except Exception as e: print(f'skip {p}: {e}')
    if not rows: raise RuntimeError('No shard CSV results found')
    df=pd.DataFrame(rows).sort_values(['capital','pair'],ascending=[False,True]).head(topk); out.parent.mkdir(parents=True,exist_ok=True); df.to_csv(out,index=False)
    best=df.iloc[0].to_dict(); (out.parent/'winner.json').write_text(json.dumps(best,indent=2),encoding='utf-8'); print(json.dumps(best,indent=2))


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('mode',choices=['validate','prepare','benchmark','shard','merge']); ap.add_argument('--root',type=Path,default=Path('.')); ap.add_argument('--prepared',type=Path,default=Path('artifacts/prepared_step2.npz')); ap.add_argument('--out',type=Path,default=Path('artifacts/result.json')); ap.add_argument('--pairs',type=int,default=1_000_000); ap.add_argument('--shard',type=int,default=0); ap.add_argument('--shards',type=int,default=256); ap.add_argument('--results-dir',type=Path,default=Path('artifacts/shards')); ap.add_argument('--threads',type=int,default=0); args=ap.parse_args()
    if args.threads>0: set_num_threads(args.threads)
    if args.mode=='validate':
        r=validate(args.root); args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(json.dumps(r,indent=2),encoding='utf-8'); print(json.dumps(r,indent=2)); raise SystemExit(0 if r.get('ok') else 2)
    if args.mode=='prepare': prepare(args.root,args.prepared)
    elif args.mode=='benchmark': benchmark(args.prepared,args.pairs,args.out)
    elif args.mode=='shard': run_shard(args.prepared,args.shard,args.shards,args.out)
    elif args.mode=='merge': merge_results(args.results_dir,args.out)

if __name__=='__main__': main()
