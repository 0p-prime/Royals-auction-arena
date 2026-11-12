"""Overall skill only in shortlist. Final sort is BPF_adj, then pressure exposure."""
def select(table,cfg):
    t=table.copy();t['eligible']=t.pressure_balls.ge(cfg['min_pressure_balls'])&t.normal_balls.ge(cfg['min_normal_balls'])&t.active
    t['shortlist_rank']=None;t['selected']=False
    e=t[t.eligible].copy();e['shortlist_rank']=(e.rae100_normal.rank(ascending=False,method='min')+e.rae100_overall.rank(ascending=False,method='min'))/2
    e=e.sort_values(['shortlist_rank','pressure_balls','Bowler'],ascending=[True,False,True]).head(cfg['shortlist']);t.loc[e.index,'shortlist_rank']=e.shortlist_rank
    e=e[e.rae100_pressure>=cfg['min_pressure_rae']].sort_values(['BPF_adj','pressure_balls','Bowler'],ascending=[False,False,True])
    if cfg['use_role_quota']:
        import pandas as pd
        e=pd.concat([a.head(cfg['roles'].get(role,0)) for role,a in e.groupby('role')]).sort_values(['BPF_adj','pressure_balls','Bowler'],ascending=[False,False,True])
    top=e.head(cfg['top_n']).copy();t.loc[top.index,'selected']=True;top['selected']=True
    return t,top
