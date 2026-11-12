"""Forward association test v2 - bounded, no tuning.
Fixes from review: (a) per-transition associations (no pooling across seasons),
(b) within-innings pressure->next-pressure and uplift->next-uplift,
(c) expanding-window forward fit only (never future transitions), scaler fit on train only,
(d) baseline = training-mean predictor, (e) Fisher-z 95% CIs, (f) cohort counts explicit.
RETROSPECTIVE labels: associations between consecutive bowler-seasons are descriptive of 2022-26,
not a prospectively deployed forecast."""
import numpy as np, pandas as pd
from scipy.stats import spearmanr
from pressure_v4 import load_cfg
from pressure_v5 import run_v5, label_state_v5

cfg,_ = load_cfg(); v5 = cfg['v5']
s = pd.read_csv('outputs/delivery_scores.csv.gz')
overall, res, val, d = run_v5(s, cfg, v5)
band, dec = v5['band'], v5['decided']
d['state'] = 'na'
m2 = d.innings==2; m1 = d.innings==1
d.loc[m2,'state'] = label_state_v5(d.loc[m2,'pb_cal'], band, dec)
d.loc[m1,'state'] = label_state_v5(d.loc[m1,'pb1_cal'], band, dec)

def uplift_pm(g, col='runs_resid', lo=10):
    ups=[]; wts=[]
    for ph,gp in g.groupby('phase'):
        pp=gp[gp.state=='pressure']; nn=gp[gp.state=='normal']
        if len(pp)>=lo and len(nn)>=lo:
            ups.append(100*(pp[col].mean()-nn[col].mean())); wts.append(min(len(pp),len(nn)))
    return np.average(ups,weights=wts) if ups else np.nan

rows=[]
for (b,y),g in d.groupby(['bowler','season']):
    if len(g)<60: continue
    r={'bowler':b,'season':y,'n':len(g),
       'overall':100*g.runs_resid.mean(), 'wk':100*g.wk_resid.mean()}
    for inn,gg in [('ch',g[g.innings==2]),('i1',g[g.innings==1])]:
        p=gg[gg.state=='pressure']; nm=gg[gg.state=='normal']
        r[f'{inn}_press']=100*p.runs_resid.mean() if len(p)>=30 else np.nan
        r[f'{inn}_npress']=len(p)
        r[f'{inn}_uplift']=uplift_pm(gg)
    rows.append(r)
bs=pd.DataFrame(rows)

trans=[(2022,2023),(2023,2024),(2024,2025),(2025,2026)]
pairs={}
for y0,y1 in trans:
    a=bs[bs.season==y0].set_index('bowler'); b=bs[bs.season==y1].set_index('bowler')
    pairs[f'{y0}->{y1}']=a.join(b,lsuffix='_p',rsuffix='_n',how='inner')

def fci(r,n):
    if n<6 or not np.isfinite(r) or abs(r)>=1: return (np.nan,np.nan)
    z=np.arctanh(r); se=1/np.sqrt(n-3)
    return (float(np.tanh(z-1.96*se)), float(np.tanh(z+1.96*se)))

RESULTS={'associations':{}, 'cohorts_per_transition':{}}
def rep(x,y):
    m=np.isfinite(x)&np.isfinite(y); n=int(m.sum())
    if n<8: return f'n={n} (too few)', {'pairs':n,'spearman':None,'ci_low':None,'ci_high':None}
    r=float(spearmanr(x[m],y[m]).statistic); lo,hi=fci(r,n)
    return f'rho={r:+.2f}  CI[{lo:+.2f},{hi:+.2f}]  n={n}', {'pairs':n,'spearman':r,'ci_low':lo,'ci_high':hi}

METRICS=[('overall_p','overall_n','prior overall -> next overall'),
         ('ch_press_p','ch_press_n','chase press lvl -> next chase press lvl'),
         ('i1_press_p','i1_press_n','inn1 press lvl -> next inn1 press lvl'),
         ('ch_uplift_p','ch_uplift_n','chase uplift -> next chase uplift'),
         ('i1_uplift_p','i1_uplift_n','inn1 uplift -> next inn1 uplift'),
         ('ch_press_p','overall_n','chase press lvl -> next overall'),
         ('i1_press_p','overall_n','inn1 press lvl -> next overall'),
         ('ch_uplift_p','overall_n','chase uplift -> next overall'),
         ('i1_uplift_p','overall_n','inn1 uplift -> next overall'),
         ('wk_p','wk_n','prior wickets -> next wickets')]
RESULTS['cohorts_per_transition']={t:len(j) for t,j in pairs.items()}
print('cohorts per transition:', RESULTS['cohorts_per_transition'])
print()
for a,b,lab in METRICS:
    print(lab)
    RESULTS['associations'][lab]={}
    for t,j in pairs.items():
        s,rec=rep(j[a].to_numpy(float), j[b].to_numpy(float))
        RESULTS['associations'][lab][t]=rec
        print(f'  {t}: {s}')

# expanding-window forward fit: predict next-season overall, train on EARLIER transitions only
RESULTS['forward_fit']=[]
print('\nEXPANDING-WINDOW FORWARD FIT (target: next-season overall runs-saved/100)')
FEATS=['overall_p']; FEATS2=['overall_p','ch_uplift_p','i1_uplift_p','ch_press_p','i1_press_p']
tnames=list(pairs)
from numpy.linalg import lstsq
for i in range(1,len(tnames)):
    tr=pd.concat([pairs[t] for t in tnames[:i]]); te=pairs[tnames[i]]
    for fs,nm in [(FEATS,'overall-only'),(FEATS2,'overall+pressure terms')]:
        trn=tr.dropna(subset=fs+['overall_n']); ten=te.dropna(subset=fs+['overall_n'])
        if len(trn)<15 or len(ten)<8: print(f'  {tnames[i]} {nm}: too few (train {len(trn)}, test {len(ten)})'); continue
        mu=trn[fs].mean(); sd=trn[fs].std().replace(0,np.nan)
        X=np.column_stack([np.ones(len(trn))]+[(trn[f]-mu[f])/sd[f] for f in fs])
        beta,*_=lstsq(X,trn.overall_n,rcond=None)
        Xte=np.column_stack([np.ones(len(ten))]+[(ten[f]-mu[f])/sd[f] for f in fs])
        pred=Xte@beta; y=ten.overall_n.to_numpy()
        base=np.full(len(ten),trn.overall_n.mean())
        mse_ratio=float(((y-pred)**2).mean()/((y-base)**2).mean())
        rr=float(spearmanr(pred,y).statistic)
        RESULTS['forward_fit'].append({'test_transition':tnames[i],'features':nm,'train_n':len(trn),'test_n':len(ten),'mse_over_train_mean_baseline':mse_ratio,'pred_actual_spearman':rr})
        print(f'  {tnames[i]} {nm}: train_n={len(trn)} test_n={len(ten)} MSE/historical-mean={mse_ratio:.2f} pred-actual rho={rr:+.2f}')

RESULTS['scope_note']=('Retrospective association between consecutive bowler-seasons inside the 2022-26 '
 'development period; not a prospectively deployed forecast and not a fresh holdout (2025-26 was used in '
 'development). Predictors for season y use only models/calibrators fitted on seasons before y '
 '(audit_v5.json registry); the forward fit trains on earlier transitions only, scalers on train only; '
 'baseline is the training-mean predictor.')
RESULTS['verdict']=('Overall runs-saved level: weak-to-modest forward association (per-transition rho '
 '0.11-0.44, only 2024->25 CI excludes 0; forward-fit MSE 3-11% below the training-mean baseline). '
 'Pressure level, uplift and wicket metrics: no demonstrated forward signal - cohorts are thin '
 '(n=1-36), signs are mixed and every CI spans 0; the full-pressure-feature forward fit is infeasible '
 '(train n 0-18). Pressure predictive signal is NOT demonstrated and the data is insufficient to settle '
 'it - that is not proof no such signal exists.')
import json
from pathlib import Path
Path('outputs/forward_association_v2.json').write_text(json.dumps(RESULTS,indent=2,default=str))
print('saved outputs/forward_association_v2.json')
