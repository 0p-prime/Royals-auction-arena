import sys, os
os.environ['OPENBLAS_NUM_THREADS']='2';os.environ['OMP_NUM_THREADS']='2'
sys.path.insert(0,'/tmp/v3/deps');sys.path.insert(0,'/tmp/v3/codezip');sys.path.insert(0,'/tmp/v3/replay')
import numpy as np, pandas as pd, joblib, json, time
from weighted_summary_posterior_filtered import aggregate_posterior_filtered
V='v3_historical'; N=32
d = pd.read_parquet(f'{V}/scored_smooth_stable.parquet')
fu = pd.read_parquet(f'{V}/full_utilities.parquet')
overlap=[c for c in d.columns if c in fu.columns and c not in ('match_id','innings','sequence')]
d = d.drop(columns=overlap).merge(fu,on=['match_id','innings','sequence'],validate='1:1')
nm = pd.read_parquet(f'{V}/newmethod_pressure_30202525.parquet')
d = d.merge(nm[['match_id','innings','sequence','pressure_new','high_new']],on=['match_id','innings','sequence'],validate='1:1')
refs = {disc: json.load(open(f'{V}/{disc}_filtered_ref.json')) for disc in ['batting','bowling']}
keys=['match_id','innings','sequence']
for k in range(N):
 if os.environ.get('DRAW') is not None and k!=int(os.environ['DRAW']):continue
 out=f'{V}/NM_mixture_posterior_{k:02d}.joblib'
 if os.path.exists(out):continue
 t0=time.time()
 p = pd.concat([pd.read_parquet(f'{V}/NM_rating_shared_{k:02d}_HIST{j}.parquet') for j in range(1,8)])
 assert not p.duplicated(keys).any() and len(p)==len(d)
 q = d.set_index(keys).copy(); p = p.set_index(keys).reindex(q.index); q[p.columns]=p; q=q.reset_index()
 q = q[q.high_new].copy(); q['pressure']=q['pressure_new']
 results={}
 for disc in ['batting','bowling']:
  fit=joblib.load(f'{V}/{disc}_fit_filtered.joblib')
  results[disc]=aggregate_posterior_filtered(q,disc,refs[disc],fit['x'],365,anchor='2026-11-18')
 joblib.dump(results,out);print('POSTERIOR_DRAW',k,'seconds',round(time.time()-t0,1),flush=True)
