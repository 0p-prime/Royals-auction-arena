import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1] / 'models'))
import json,numpy as np,pandas as pd
from scipy.stats import spearmanr
from bpf_continuous import *
from bpf_continuous import _parity_map
cfg=json.load(open('config.json'))
s=add_centered_rae(pd.read_csv('outputs/delivery_scores.csv.gz'),cfg)
s['half']=s.match_id.map(_parity_map(s))
s['econ']=s.charged; s['runs_resid']=s.er-s.charged; s['wk_resid']=s.wicket-s.ew
res={}
def lvl(col,minb=150):
    g=s.groupby(['bowler','half']).agg(n=(col,'size'),m=(col,'mean')).reset_index()
    g=g[g.n>=minb].pivot(index='bowler',columns='half',values='m').dropna()
    return len(g),float(spearmanr(g[0],g[1]).statistic)
for c in ['charged','runs_resid','wicket','wk_resid','rae_c','rae']:
    res[c]=lvl(c)
print(res)
# shuffle heuristic: shuffle rae_c within bowler (null slope), how often |slope/se|>1.96, and the raw-slope sd
rng=np.random.default_rng(1);fp=[];
for rep in range(5):
    d=s.copy(); d['rae_c']=d.groupby('bowler').rae_c.transform(lambda x: rng.permutation(x.values))
    t=bowler_slopes(d,cfg,200); fp.append(float((t.slope_raw.abs()/t.slope_se>1.96).mean()))
print('shuffle heuristic exclude-0 rate (raw z)',np.mean(fp),fp)
# cluster-level shuffle heuristic: shuffle match-level residual blocks
def block(d):
    out=[]
    for b,g in d.groupby('bowler'):
        ms=[x for _,x in g.groupby('match_id')]
        ys=[x.rae_c.values for x in ms]
        perm=rng.permutation(len(ms))
        newy=[]
        for i,x in enumerate(ms):
            y=ys[perm[i]]; 
            y=np.resize(y,len(x)); newy.append(pd.Series(y,index=x.index))
        out.append(pd.concat(newy))
    d=d.copy(); d['rae_c']=pd.concat(out).reindex(d.index); return d
fp2=[]
for rep in range(5):
    d=block(s); t=bowler_slopes(d,cfg,200); fp2.append(float((t.slope_raw.abs()/t.slope_se>1.96).mean()))
print('block shuffle heuristic',np.mean(fp2),fp2)
print('per-ball sd rae_c',s.rae_c.std(),'wk term sd',(20*s.wk_resid).std(),'runs resid sd',s.runs_resid.std())
