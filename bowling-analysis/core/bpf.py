"""Recency-weighted per-100-legal-ball rates, with all delivery costs retained."""
import pandas as pd
import numpy as np
def add_scores(df,cfg,cutoffs):
    d=df.copy();d['bucket']=np.select([d.bopi>=cutoffs[1],d.bopi<=cutoffs[0]],['pressure','normal'],default='middle');d['weight']=np.where(d.season>=cfg['test_start'],cfg['recent_weight'],cfg['old_weight']);d['rae']=d.er-d.charged+cfg['wicket_value']*d.wicket;return d
def rate(g,col):
    denom=(g.legal*g.weight).sum();return (g[col]*g.weight).sum()/denom if denom else np.nan
def aggregate(df,cfg):
    rows=[]
    for bowler,g in df.groupby('bowler'):
        x={'Bowler':bowler,'Team':g.sort_values('date').iloc[-1].team,'Type':g.iloc[-1]['type'],'active':bool((g.season>=cfg['test_start']).any()),'matches':g.match_id.nunique(),'role':g.groupby('phase').legal.sum().idxmax(),'rae100_overall':100*rate(g,'rae')}
        for bucket in ['pressure','normal']:
            a=g[g.bucket==bucket];x[bucket+'_balls']=int(a.legal.sum());x['rae100_'+bucket]=100*rate(a,'rae');x['economy_'+bucket]=6*rate(a,'charged');x['wickets100_'+bucket]=100*rate(a,'wicket');den=(a.legal*a.weight).sum();x['dotpct_'+bucket]=100*(a.legal*a.charged.eq(0)*a.weight).sum()/den if den else np.nan
        x['BPF']=x['rae100_pressure']-x['rae100_normal'];x['BPF_adj']=x['pressure_balls']/(x['pressure_balls']+cfg['shrinkage'])*x['BPF'];rows.append(x)
    return pd.DataFrame(rows)
def bootstrap(df,cfg):
    rng=np.random.default_rng(cfg['seed']);rows=[]
    for bowler,g in df.groupby('bowler'):
        # Match-cluster resampling retains within-match dependence and empty cohorts.
        chunks=[]
        for _,a in g.groupby('match_id'):
            chunks.append([*(v for b in ['pressure','normal'] for v in [(a.loc[a.bucket==b,'rae']*a.loc[a.bucket==b,'weight']).sum(),(a.loc[a.bucket==b,'legal']*a.loc[a.bucket==b,'weight']).sum()]),a.loc[a.bucket=='pressure','legal'].sum()])
        a=np.array(chunks);draw=rng.integers(0,len(a),size=(cfg['bootstrap'],len(a)));s=a[draw].sum(axis=1);valid=(s[:,1]>0)&(s[:,3]>0);v=(100*s[valid,0]/s[valid,1]-100*s[valid,2]/s[valid,3])*s[valid,4]/(s[valid,4]+cfg['shrinkage']);lo,hi=np.quantile(v,cfg['bootstrap_ci']) if len(v)>cfg['bootstrap_min_valid'] else (np.nan,np.nan);rows.append({'Bowler':bowler,'CI_low':lo,'CI_high':hi,'bootstrap_valid':int(valid.sum())})
    return pd.DataFrame(rows)
