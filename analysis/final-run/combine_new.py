import sys, os
os.environ['OPENBLAS_NUM_THREADS']='2';os.environ['OMP_NUM_THREADS']='2'
import numpy as np,pandas as pd,joblib,json
V='v3_historical'; N=32; CUT=0.5066943362382735
paths=sorted(__import__('pathlib').Path(V).glob('NM_mixture_posterior_*.joblib'))
assert len(paths)==N, len(paths)
allpost=[joblib.load(f'{V}/NM_mixture_posterior_{k:02d}.joblib') for k in range(N)]
summary={}
for disc in ['batting','bowling']:
 ref=json.load(open(f'{V}/{disc}_filtered_ref.json'))
 ref['G_Pmean']=ref['P_ref']; ref['HP_threshold']=CUT
 ids=[o['id'] for o in allpost[0][disc]];maps=[{o['id']:o for o in a[disc]} for a in allpost];out=[]
 for ident in ids:
  means=np.array([m[ident]['mean'] for m in maps]);within=np.mean([m[ident]['cov'] for m in maps],axis=0);between=np.cov(means,rowvar=False,bias=True);mean=means.mean(0);total=within+between
  out.append({'id':ident,'mean':mean,'cov':total,'conditional_cov_mean':within,'between_rating_cov':between,'nuisance_means':means,'nuisance_factors':[m[ident]['factor'] for m in maps],'weighted_exposure':maps[0][ident]['weighted_exposure'],'matches':maps[0][ident]['matches'],'n_eff':maps[0][ident]['n_eff']})
 joblib.dump({'posteriors':out,'reference':ref,'hyper':joblib.load(f'{V}/{disc}_fit_filtered.joblib')['x'],'nuisance_draws':N,'scope':'ConditionalfixedmodelhyperparameterGammaquantilecopulamixture, notfullpipelineuncertainty; FILTERED top35pct pressure balls only'},f'{V}/{disc}_rating_mixture_filtered.joblib')
 summary[disc]={'identities':len(out),'max_between_cov_A':max(o['between_rating_cov'][0,0] for o in out),'min_total_minus_within_eigen':min(np.linalg.eigvalsh(o['cov']-o['conditional_cov_mean']).min() for o in out),'max_MCSE_mean_A':max(np.std(o['nuisance_means'][:,0],ddof=1)/np.sqrt(N) for o in out)}
open(f'{V}/rating_mixture_checks_filtered.json','w').write(json.dumps(summary,indent=2))
print(summary,flush=True)
