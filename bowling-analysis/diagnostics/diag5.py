import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1] / 'models'))
import json,numpy as np,pandas as pd
from scipy.stats import spearmanr
from bpf_continuous import *
from bpf_continuous import _parity_map
cfg=json.load(open('config.json'))
s=add_centered_rae(pd.read_csv('outputs/delivery_scores.csv.gz'),cfg)
s['half']=s.match_id.map(_parity_map(s)); s['rr']=s.er-s.charged
print(s.bucket.value_counts().to_dict())
def agg(d,minb):
    out={}
    for b,g in d.groupby('bowler'):
        p=g[g.bucket=='pressure'];n=g[g.bucket=='normal']
        if g.legal.sum()<minb: continue
        if len(p)<40 or len(n)<80: continue
        out[b]=(100*p.rr.mean(),100*n.rr.mean(),100*g.rr.mean(),len(p),len(n))
    return pd.DataFrame(out,index=['p','n','o','np','nn']).T
for nm,(x,y) in {'alt':(s[s.half==0],s[s.half==1]),'time':(s[s.season<=2024],s[s.season>=2025])}.items():
    A=agg(x,150);B=agg(y,150);j=A.join(B,lsuffix='0',rsuffix='1',how='inner')
    j['d0']=j.p0-j.n0;j['d1']=j.p1-j.n1
    print(nm,len(j),{k:round(float(spearmanr(j[k+'0'],j[k+'1']).statistic),3) for k in ['p','n','o','d']})
