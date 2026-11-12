import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1] / 'models'))
import json,numpy as np,pandas as pd
from scipy.stats import spearmanr,pearsonr
from bpf_continuous import *
from bpf_continuous import _parity_map
cfg=json.load(open('config.json'))
s=add_centered_rae(pd.read_csv('outputs/delivery_scores.csv.gz'),cfg)
print(len(s), s.season.value_counts().sort_index().to_dict())
par=_parity_map(s); s['half']=s.match_id.map(par)
# 1 overall level: mean rae_c per ball, per half, shrunk reliability
def level(d,minb=150):
    r=[]
    for b,g in d.groupby('bowler'):
        if len(g)<minb or g.match_id.nunique()<2: continue
        m=g.match_id.values; y=g.rae_c.values
        # cluster-robust se of mean
        yc=y-y.mean(); se=np.sqrt(sum(yc[m==k].sum()**2 for k in np.unique(m)))/len(y)
        r.append((b,100*y.mean(),100*se,len(y)))
    return pd.DataFrame(r,columns=['Bowler','slope_raw','slope_se','deliveries'])
def rel(t):
    w=1/t.slope_se**2; mu=(w*t.slope_raw).sum()/w.sum(); q=(w*(t.slope_raw-mu)**2).sum(); c=w.sum()-(w**2).sum()/w.sum()
    tau2=max(0,(q-len(t)+1)/c); return tau2, float(np.median(tau2/(tau2+t.slope_se**2)))
out={}
a=level(s[s.half==0]);b=level(s[s.half==1]);j=a.merge(b,on='Bowler')
out['level_rae_c_per100balls']={'n':len(j),'spearman':float(spearmanr(j.slope_raw_x,j.slope_raw_y).statistic),'pearson':float(pearsonr(j.slope_raw_x,j.slope_raw_y)[0]),'tau2_half0':rel(a),'tau2_half1':rel(b)}
# 2 slope axes
def axis_slopes(d,col,minb,sub=None):
    d=d.copy(); d['bopi']=d[col]
    return bowler_slopes(d,cfg,minb)
def stab(col,sub,minb):
    d=s if sub is None else s[sub(s)]
    r={}
    for nm,(x,y) in {'alt':(d[d.half==0],d[d.half==1]),'time':(d[d.season<=2024],d[d.season>=2025])}.items():
        A=shrink_slopes(axis_slopes(x,col,minb));B=shrink_slopes(axis_slopes(y,col,minb))
        j=A.merge(B,on='Bowler')
        r[nm]={'n':len(j),'rho_shrunk':float(spearmanr(j.slope_shrunk_x,j.slope_shrunk_y).statistic),
          'rho_raw':float(spearmanr(j.slope_raw_x,j.slope_raw_y).statistic),'tau2':(A.attrs['tau2'],B.attrs['tau2']),'mu':(A.attrs['mu'],B.attrs['mu'])}
    return r
s['rrr_c']=s.rrr.clip(0,24)
s['gap']=(s.rrr-s.crr).clip(-12,12)
out['bopi_all_min150']=stab('bopi',None,150)
out['bopi_all_min100']=stab('bopi',None,100)
out['rrr_chase']=stab('rrr_c',lambda d:(d.innings==2)&(d.over>=6),100)
out['rrr_gap_chase']=stab('gap',lambda d:(d.innings==2)&(d.over>=6),100)
out['bopi_chase_only']=stab('bopi',lambda d:(d.innings==2)&(d.over>=6),100)
# 3 how does bopi relate to context
print(s[['bopi','rrr','crr','wickets_in_hand','over','recent_boundaries','batter_sr','spell_runs']].corr()['bopi'].round(2).to_dict())
print(s.groupby('phase').bopi.mean().round(1).to_dict(), s.groupby('phase').rae_c.mean().mul(100).round(2).to_dict())
print('mean rae_c x100',100*s.rae_c.mean(), 'mean rae',100*s.rae.mean())
json.dump(out,open('/tmp/diag2.json','w'),indent=1,default=float)
print(json.dumps(out,indent=1,default=float))
