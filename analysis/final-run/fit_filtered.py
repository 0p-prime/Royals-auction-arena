import sys, os
os.environ['OPENBLAS_NUM_THREADS']='2';os.environ['OMP_NUM_THREADS']='2'
sys.path.insert(0,'/tmp/v3/deps');sys.path.insert(0,'/tmp/v3/codezip')
import numpy as np, joblib, os
from scipy.optimize import minimize
from hybrid_qr_likelihood import prepare, objective
disc=os.environ.get('DISC','bowling')
rows=joblib.load(f'v3_historical/{disc}_filtered_rows_h1e9.joblib')
path=f'v3_historical/{disc}_fit_filtered.joblib'
pr=prepare(rows)
if os.path.exists(path):
    a=joblib.load(path);base=a['x'];trace=a['trace']
else:
    base=joblib.load(f'/tmp/v3/codezip/{disc}_rank2face.joblib')['x'];trace=[]
diagscale=np.array([.001,.003,1e-6,5e-6,.001,.003,.003,1e-6,1e-6,1e-6,5e-6,5e-6,5e-6,5e-6,.001,1e-6,1e-6]);H=np.zeros((17,17));step=.001
for k in range(17):
 up=base.copy();dn=base.copy();up[k]+=diagscale[k]*step;dn[k]-=diagscale[k]*step;gu=objective(up,pr,1e-5)[1]*diagscale;gd=objective(dn,pr,1e-5)[1]*diagscale;H[:,k]=(gu-gd)/(2*step)
H=(H+H.T)/2;ev,U=np.linalg.eigh(H);P=diagscale[:,None]*U/np.sqrt(np.maximum(abs(ev),1e-6));print('START',disc,'n',len(rows),'resume_iter',len(trace),flush=True)
def fun(z):
 f,g=objective(base+P@z,pr,1e-5);return f,P.T@g
def cb(z):
 f,g=fun(z);trace.append({'iteration':len(trace)+1,'f':f,'transformed_gradient':float(abs(g).max())});joblib.dump({'x':base+P@z,'trace':trace,'P':P},path)
 if len(trace)%10==0:print(disc,trace[-1],flush=True)
o=minimize(fun,np.zeros(17),jac=True,method='BFGS',callback=cb,options={'maxiter':int(os.environ.get('ITER','60')),'gtol':1e-7});f,g=fun(o.x)
joblib.dump({'x':base+P@o.x,'trace':trace,'P':P,'success':bool(o.success),'message':str(o.message),'objective':f,'transformed_gradient':float(abs(g).max())},path)
print('DONE',disc,'objective',f,'grad',float(abs(g).max()),o.message,flush=True)
