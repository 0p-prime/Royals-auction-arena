import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1] / 'models'))
import json,numpy as np,pandas as pd
from scipy.stats import spearmanr
from bpf_continuous import *
from bpf_continuous import _parity_map
cfg=json.load(open('config.json'))
s=add_centered_rae(pd.read_csv('outputs/delivery_scores.csv.gz'),cfg)
s['half']=s.match_id.map(_parity_map(s))
s['runs_resid']=s.er-s.charged; s['wk_resid']=s.wicket-s.ew
def st(col,minb):
    s2=s.copy(); s2['rae_c']=s2[col]; r={}
    for nm,(x,y) in {'alt':(s2[s2.half==0],s2[s2.half==1]),'time':(s2[s2.season<=2024],s2[s2.season>=2025])}.items():
        A=shrink_slopes(bowler_slopes(x,cfg,minb));B=shrink_slopes(bowler_slopes(y,cfg,minb));j=A.merge(B,on='Bowler')
        r[nm]=(len(j),round(float(spearmanr(j.slope_raw_x,j.slope_raw_y).statistic),3),round(float(spearmanr(j.slope_shrunk_x,j.slope_shrunk_y).statistic),3),round(A.attrs['tau2'],2),round(B.attrs['tau2'],2),round(A.slope_se.median(),2))
    full=shrink_slopes(bowler_slopes(s2,cfg,200)); r['full']=(len(full),round(full.attrs['mu'],2),round(full.attrs['tau2'],2),round(float(np.median(full.attrs['tau2']/(full.attrs['tau2']+full.slope_se**2))),2),full.evidence.value_counts().to_dict())
    return r
for c in ['runs_resid','wk_resid']:
    for m in (150,100): print(c,m,st(c,m))
