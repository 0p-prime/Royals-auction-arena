import pandas as pd, numpy as np, json
# New pressure recipe: leverage .35 / win-uncertainty .10 / RRR .25 / collapse .30
# Same delivered machinery: per-fold calibrated inner refs, leverage ECDF percentile,
# inn1 raw quantile-mapped onto inn2 raw scale; pooled 65th-pct cut over all balls.
a = pd.read_parquet('v3_historical/scored_smooth_stable.parquet').reset_index(drop=True)
out = a[['match_id','innings','sequence','fold']].copy()
P = np.zeros(len(a)); raw_all = np.zeros(len(a))
for fold, va in a.groupby('fold', sort=False):
    ref = pd.concat([pd.read_parquet(f'v3_historical/calibrated_ref_{fold}_{j}.parquet') for j in range(3)])
    lev = np.sort(ref.leverage.to_numpy())
    lp = np.searchsorted(lev, ref.leverage, side='right')/len(lev)
    h_ref = np.where(ref.innings.eq(2), np.clip((ref.rrr-ref.rr_ref)/6,0,1), 0)
    ref_raw = np.clip(.30*lp + .20*4*ref.pwin*(1-ref.pwin) + .25*h_ref + .25*ref.collapse, 0, 1)
    vp = np.searchsorted(lev, va.leverage.to_numpy(), side='right')/len(lev)
    vh = np.where(va.innings.eq(2), np.clip((va.rrr-va.rr_ref)/6,0,1), 0)
    raw = np.clip(.30*vp + .20*4*va.pwin.to_numpy()*(1-va.pwin.to_numpy()) + .25*vh + .25*va.collapse.to_numpy(), 0, 1)
    f = np.sort(ref_raw[ref.innings.eq(1).to_numpy()]); c = np.sort(ref_raw[ref.innings.eq(2).to_numpy()])
    ranks = np.searchsorted(f, raw, side='right')/len(f)
    mapped = np.quantile(c, ranks)
    ix = va.index.to_numpy()
    P[ix] = np.where(va.innings.eq(1).to_numpy(), mapped, raw)
    raw_all[ix] = raw
cut = float(pd.Series(P).quantile(.65))
ties_at_cut = int((P==cut).sum())
high = P>=cut
out['pressure_new']=P; out['pressure_new_raw']=raw_all; out['high_new']=high
out.to_parquet('v3_historical/newmethod_pressure_30202525.parquet')
rep = {'cut':cut,'ties_at_cut':ties_at_cut,'actual_fraction':float(high.mean()),
 'n_high':int(high.sum()),'n':len(a),
 'inn1_high':int((high & a.innings.eq(1).to_numpy()).sum()),'inn2_high':int((high & a.innings.eq(2).to_numpy()).sum()),
 'inn1_total':int(a.innings.eq(1).sum()),'inn2_total':int(a.innings.eq(2).sum())}
json.dump(rep, open('v3_historical/newmethod_reblend_report_30202525.json','w'), indent=2)
print(json.dumps(rep, indent=2))
