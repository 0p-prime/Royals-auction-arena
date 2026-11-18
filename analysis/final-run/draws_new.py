from pathlib import Path
import os,joblib,json,time,hashlib
from scipy.stats import gamma as gamma_distribution
import numpy as np,pandas as pd
import v3_core as core
V=core.V;D=core.d;N=32
for fold,va0 in D.groupby('fold',sort=False):
 if os.environ.get('FOLD') and fold!=os.environ['FOLD']:continue
 tr=D[D.fold.ne(fold)].copy();tr,va=core.ratings(tr,va0.copy());model=joblib.load(V/f'models_{fold}.joblib');base=pd.read_parquet(V/f'full_scored_{fold}.parquet').set_index(['match_id','innings','sequence']);re,win,cal=model['re'],model['win'],model['cal'];rng=np.random.default_rng(804+int(fold[-1]));pids={r:{} for r in ['bat','bowl']};logs={};draws={}
 for role,pid,rcol,runs in [('bat','batter_pid','bat_rating','runs_batter'),('bowl','bowler_pid','bowl_rating','conceded')]:
  ag=tr.groupby([pid,'match_id']).agg(run=(runs,'sum'),balls=('legal','sum'),mean=(rcol,'first'));valid=ag.balls.gt(0);pear=(ag.loc[valid,'run']-ag.loc[valid,'mean']*ag.loc[valid,'balls'])**2/(ag.loc[valid,'mean']*ag.loc[valid,'balls']);phi=max(1.,float(pear.mean()));logs[role]={'cluster_quasi_dispersion':phi,'training_player_matches':int(valid.sum()),'estimator':'MeanPearsonmatchsumresidualsquare/(priorrate*legalexposure), constrainedoverdispersion>=1. Fixedoutertrainnuisance, noheldoutoutcomes.'};arr=np.zeros((N,len(va)))
  for ident,a in va.groupby(pid,sort=False):
   a=a.sort_values('date');seed=int.from_bytes(hashlib.sha256((role+str(ident)).encode()).digest()[:8],'little');uniform=np.random.default_rng(seed).uniform(1e-10,1-1e-10,N)
   for date,b in a.groupby('date',sort=False):
    shape=float(b[rcol+'_shape'].iloc[0])/phi;rate=float(b[rcol+'_rate'].iloc[0])/phi;idx=va.index.get_indexer(b.index);arr[:,idx]=gamma_distribution.ppf(uniform,shape,scale=1/rate)[:,None]
  assert np.all(arr>0);draws[role]=arr
 # Cache role-owned outcome values for this exactfrozenV/RE, sharedbyall32ratingdraws.
 cache={}
 def val(r,l,w):
  key=(r,l,w)
  if key not in cache:
   z=core.after(va,r,l,w);cache[key]=(re.predict(z),core.wp_pred(win,cal,z))
  return cache[key]
 values={}
 for role in ['bat','bowl','nonstriker']:
  AA=np.empty((len(va),len(core.ct)));KK=np.empty_like(AA)
  for j,c in core.ct.iterrows():
   l=int(c.legal);r=int(c.runs_batter if role=='bat' else c.conceded if role=='bowl' else 0);w=int(c.striker_dismissal if role=='bat' else c.bowler_wicket if role=='bowl' else c.nonstriker_dismissal);br,bw=val(0,l,0);ar,aw=val(r,l,w);sign=-1 if role=='bowl' else 1;AA[:,j]=sign*(r+ar-br);KK[:,j]=sign*(aw-bw)
  values[role]=(AA,KK)
 for k in range(N):
  out=V/f'NM_rating_shared_{k:02d}_{fold}.parquet'
  if out.exists():continue
  z=va.copy();z['bat_rating']=draws['bat'][k];z['bowl_rating']=draws['bowl'][k];qb=core.prob(model['qb'],z,'bat');qw=core.prob(model['qw'],z,'bowl');a=va[['match_id','innings','sequence']].copy();ix=pd.MultiIndex.from_frame(a);baseline=base.loc[ix]
  for role,q in [('bat',qb),('bowl',qw),('nonstriker',qb)]:
   AA,KK=values[role];ma=(q*AA).sum(1);mk=(q*KK).sum(1);ac=AA-ma[:,None];kc=KK-mk[:,None];a[role+'_utility']=baseline['observed_'+role+'_utility'].to_numpy()-ma;a[role+'_wpa']=baseline['observed_'+role+'_wpa'].to_numpy()-mk;a[role+'_event_var_A']=(q*ac*ac).sum(1);a[role+'_event_var_K']=(q*kc*kc).sum(1);a[role+'_event_cov_AK']=(q*ac*kc).sum(1)
  a.to_parquet(out,index=False)
 (V/f'NM_rating_shared_contract_{fold}.json').write_text(json.dumps({'fold':fold,'draws':N,'dispersion':logs,'coupling':'Globallysharedactor-roleuniformGAMMAQUANTILEcopulaacrossdatesANDouterfolds. Eachmarginalusesstrictlyprior-dateGamma-Poissonworkingposteriorandfixedoutertrainingphi. ComonotoniccouplingASSUMPTION, nottruestaticabilityjointposterior, notanuncertaintybound.','frozen':'V/RE/pressure/roleqcoefficients/playerhyperparameters/referencefixed. Onlyopponentinputdrawandderivedownedmomentsvary.','uncertainty':'Conditionalwithin+betweenposterior mixture; noadditionalbetweenvarianceaddedtoeventnoise.'},indent=2));print('DRAW_FOLD_DONE',fold,flush=True)
