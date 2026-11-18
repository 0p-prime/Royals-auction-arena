import numpy as np,pandas as pd
from scipy.linalg import solve_triangular
from match_factor import unpack

def aggregate_posterior_filtered(d,disc,ref,hyper,h=1e9,anchor=None):
 mu,A,B=unpack(hyper);role='bat' if disc=='batting' else 'bowl';pid='batter_pid' if disc=='batting' else 'bowler_pid';ex='faced' if disc=='batting' else 'legal';anchor=pd.Timestamp(anchor) if anchor is not None else pd.to_datetime(d.date).max();decay=np.exp(-np.log(2)*(anchor-pd.to_datetime(d.date)).dt.days/h);scale=np.array(ref['utility_scale']);pref=ref['P_ref']
 def frame(pid,role,ex):
  return pd.DataFrame({'pid':d[pid],'match':d.match_id,'P':d.pressure,'w':decay,'ex':d[ex] if ex else 0.,'A':100*d[role+'_utility']/scale[0],'K':100*d[role+'_wpa']/scale[1],'vAA':10000*d[role+'_event_var_A']/scale[0]**2,'vKK':10000*d[role+'_event_var_K']/scale[1]**2,'vAK':10000*d[role+'_event_cov_AK']/(scale[0]*scale[1])})
 z=frame(pid,role,ex)
 if role=='bat':z=pd.concat([z,frame('non_striker_pid','nonstriker',None)],ignore_index=True)
 out=[];active=np.linalg.norm(A,axis=0)>0;AA=A[:,active];rank=AA.shape[1]
 for ident,a in z.groupby('pid',sort=False):
  x=np.c_[np.ones(len(a)),a.P.to_numpy()-pref];w=a.w.to_numpy();e=a.ex.to_numpy();H=x.T@((w*e)[:,None]*x);L=np.kron(np.eye(2),H);y=(x.T@(w[:,None]*a[['A','K']].to_numpy())).T.reshape(-1);cv=np.zeros((len(a),2,2));cv[:,0,0]=a.vAA;cv[:,1,1]=a.vKK;cv[:,0,1]=a.vAK;cv[:,1,0]=a.vAK;ev,U=np.linalg.eigh(cv);tol=np.finfo(float).eps*np.maximum(np.trace(cv,axis1=1,axis2=2),1e-300)*100
  if np.any(ev[:,0]<-tol):raise ValueError('Event covariance materially nonPSD')
  roots=U*np.sqrt(np.maximum(ev,0))[:,None,:];design=np.zeros((len(a),4,2));design[:,:2,0]=x;design[:,2:,1]=x;F=np.einsum('nai,nij,n->naj',design,roots,w).transpose(1,0,2).reshape(4,-1);mf=[]
  for mid,ix in a.groupby('match').indices.items():
   n=x[ix].T@(w[ix]*e[ix]);R=np.zeros((4,2));R[:2,0]=n;R[2:,1]=n;mf.append(R@B)
  noise=np.concatenate([F]+mf,axis=1);factor=np.c_[L@AA,noise];SU,sv,_=np.linalg.svd(factor,full_matrices=False);keep=sv>np.finfo(float).eps*max(sv.max(),1e-300)*8;null=SU[:,~keep].T;r=y-L@mu
  if len(null) and np.linalg.norm(null@r)>1e-9*max(np.linalg.norm(r),1e-300):raise ValueError('Unresolved deterministic aggregate constraint')
  Q=(SU[:,keep]/sv[keep]).T;lf=Q@L@AA;nf=Q@noise;rr=Q@r;joint=np.zeros((len(rr)+rank,rank+nf.shape[1]));joint[:len(rr)]=np.c_[lf,nf];joint[len(rr):,:rank]=np.eye(rank);_,U=np.linalg.qr(joint.T,mode='reduced');ll=U.T;Ly=ll[:len(rr),:len(rr)];cross=ll[len(rr):,:len(rr)];Cz=ll[len(rr):,len(rr):];mean=mu+AA@cross@solve_triangular(Ly,rr,lower=True);pc=AA@Cz
  out.append({'id':ident,'mean':mean,'factor':pc,'cov':pc@pc.T,'weighted_exposure':float((w*e).sum()),'matches':int(a['match'].nunique()),'n_eff':float((w*e).sum()**2/((w*e)**2).sum()) if ((w*e)**2).sum()>0 else 0.,'y':y,'L':L,'noise_covariance':noise@noise.T,'reference':ref})
 return out
