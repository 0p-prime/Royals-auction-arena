from pathlib import Path
import numpy as np,pandas as pd,joblib,json
R=Path(__file__).resolve().parent

def make_rows_filtered(d,disc,ref,h=1e9,anchor=None):
 ex='faced' if disc=='batting' else 'legal';role='bat' if disc=='batting' else 'bowl';pid='batter_pid' if disc=='batting' else 'bowler_pid';name='batter' if disc=='batting' else 'bowler';anchor=pd.to_datetime(d.date).max() if anchor is None else pd.Timestamp(anchor);dec=np.exp(-np.log(2)*(anchor-pd.to_datetime(d.date)).dt.days/h);scale=np.array(ref['utility_scale']);pref=ref['P_ref']
 def frame(pid,name,role,ex):
  z=pd.DataFrame({'pid':d[pid],'name':d[name],'match_id':d.match_id,'P':d.pressure,'w':dec,'ex':d[ex] if ex else 0.,'A':100*d[role+'_utility']/scale[0],'K':100*d[role+'_wpa']/scale[1],'vAA':10000*d[role+'_event_var_A']/scale[0]**2,'vKK':10000*d[role+'_event_var_K']/scale[1]**2,'vAK':10000*d[role+'_event_cov_AK']/(scale[0]*scale[1])});return z
 z=frame(pid,name,role,ex)
 if disc=='batting':z=pd.concat([z,frame('non_striker_pid','non_striker','nonstriker',None)],ignore_index=True)
 out=[];notes=[];stats={'null_reductions':0,'constraint_blocks':0,'min_redundancy_check':[],'max_whitening_condition':0.,'negative_cov_eigenvalue':0.,'no_exposure_observations':0}
 for (ident,mid),a in z.groupby(['pid','match_id'],sort=False):
  x=np.c_[np.ones(len(a)),a.P.to_numpy()-pref];w=a.w.to_numpy();e=a.ex.to_numpy();H=x.T@((w*e)[:,None]*x);L=np.zeros((4,4));L[:2,:2]=H;L[2:,2:]=H;y=(x.T@(w[:,None]*a[['A','K']].to_numpy())).T.reshape(-1);C=np.zeros((4,4));ix=np.einsum('ni,nj,n->nij',x,x,w*w);C[:2,:2]=np.einsum('nij,n->ij',ix,a.vAA);C[2:,2:]=np.einsum('nij,n->ij',ix,a.vKK);C[:2,2:]=np.einsum('nij,n->ij',ix,a.vAK);C[2:,:2]=C[:2,2:].T;C=(C+C.T)/2;n=x.T@(w*e);RR=np.zeros((4,2));RR[:2,0]=n;RR[2:,1]=n
  # Factor SVD avoids squaring condition numbers in E+RR. No measurement variance is added.
  covs=np.zeros((len(a),2,2));covs[:,0,0]=a.vAA;covs[:,1,1]=a.vKK;covs[:,0,1]=a.vAK;covs[:,1,0]=a.vAK;ce,cu=np.linalg.eigh(covs);ctol=np.finfo(float).eps*np.maximum(covs[:,0,0]+covs[:,1,1],1e-300)*100
  assert np.all(ce[:,0]>=-ctol)
  roots=cu*np.sqrt(np.maximum(ce,0))[:,None,:];des=np.zeros((len(a),4,2));des[:,:2,0]=x;des[:,2:,1]=x;F=np.einsum('nai,nij,n->naj',des,roots,w).transpose(1,0,2).reshape(4,-1);U,sv,_=np.linalg.svd(np.c_[F,RR],full_matrices=False);mx=max(float(sv.max()),1e-300);keep=sv>np.finfo(float).eps*mx*8;null=U[:,~keep].T
  if len(null):
   checks=[np.linalg.norm(null@F)/max(np.linalg.norm(F),1e-300),np.linalg.norm(null@RR)/max(np.linalg.norm(RR),1e-300),np.linalg.norm(null@y)/max(np.linalg.norm(y),1e-300),np.linalg.norm(null@L)/max(np.linalg.norm(L),1e-300)]
   if max(checks)<1e-10:stats['null_reductions']+=1
   else:stats['constraint_blocks']+=1;notes.append({'id':ident,'match':int(mid),'singular_values':sv.tolist(),'null_checks':checks});continue
  if not keep.any():notes.append({'id':ident,'match':int(mid),'status':'zero full information'});continue
  stats['max_whitening_condition']=max(stats['max_whitening_condition'],float(sv[keep].max()/sv[keep].min()));Q=(U[:,keep]/sv[keep]).T;EF=Q@F;E=EF@EF.T;E=(E+E.T)/2
  if not e.sum():stats['no_exposure_observations']+=1
  out.append({'id':ident,'name':a.name.iloc[0],'match_id':mid,'y':Q@y,'L':Q@L,'R':Q@RR,'E':E,'exposure':float((w*e).sum())})
 return out,notes,stats
if __name__=='__main__':
 d=pd.read_parquet(R/'scored_smooth_stable.parquet');logs={}
 for disc,role,ex in [('batting','bat','faced'),('bowling','bowl','legal')]:
  ref={'P_ref':float(np.average(d.pressure,weights=d[ex])),'utility_scale':[float(np.sqrt(np.mean(d[role+'_event_var_A']*10000))),float(np.sqrt(np.mean(d[role+'_event_var_K']*10000)))]};obs,notes,stats=make_rows(d,disc,ref);eig=[]
  for o in obs:eig.extend(np.linalg.eigvalsh(o['E']+.05*o['R']@o['R'].T).tolist())
  logs[disc]={'players':len(set(o['id'] for o in obs)),'observations':len(obs),'reference_DIAGNOSTIC_ALLSEASON':ref,'stats':stats,'unresolved_blocks':notes,'D_eigen_quantiles':np.quantile(eig,[0,.001,.01,.5,1]).tolist()};joblib.dump(obs,R/f'{disc}_smooth_raw_match_observations.joblib');print(json.dumps(logs[disc]),flush=True)
 (R/'smooth_raw_geometry.json').write_text(json.dumps(logs,indent=2))
