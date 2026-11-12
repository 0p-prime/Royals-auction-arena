import numpy as np
from scipy.stats import spearmanr
from bpf import aggregate
def correlate(a,b,col='BPF_adj'):
    j=a[['Bowler',col]].merge(b[['Bowler',col]],on='Bowler').dropna();rho=float(spearmanr(j[col+'_x'],j[col+'_y']).statistic) if len(j)>=3 else None
    if rho is not None and not np.isfinite(rho):rho=None
    return {'rho':rho,'bowlers':len(j),'note':'intersection with both cohorts; no selection-filter requirement'}
def stability(df,cfg):
    early=aggregate(df[df.season<=cfg['train_end']],cfg);late=aggregate(df[df.season>=cfg['test_start']],cfg)
    order=df[['match_id','date']].drop_duplicates().sort_values(['date','match_id']);parity={m:i%2 for i,m in enumerate(order.match_id)}
    a=aggregate(df[df.match_id.map(parity)==0],cfg);b=aggregate(df[df.match_id.map(parity)==1],cfg)
    return {'time_bpf_rank':correlate(early,late),'alternate_match_bpf_rank':correlate(a,b),'time_pressure_rae_rank':correlate(early,late,'rae100_pressure')}
