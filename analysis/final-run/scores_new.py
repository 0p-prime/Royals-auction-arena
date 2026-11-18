import sys, os
os.environ['OPENBLAS_NUM_THREADS']='2';os.environ['OMP_NUM_THREADS']='2'
sys.path.insert(0,'/tmp/v3/deps');sys.path.insert(0,'/tmp/v3/codezip')
import numpy as np,pandas as pd,joblib,json
from scipy.special import ndtr
from scipy.stats import spearmanr
from match_factor import unpack
V='v3_historical';rng=np.random.default_rng(679);logs={}
d=pd.read_parquet(f'{V}/scored_smooth_stable.parquet')
fu=pd.read_parquet(f'{V}/full_utilities.parquet')
overlap=[c for c in d.columns if c in fu.columns and c not in ('match_id','innings','sequence')]
d=d.drop(columns=overlap).merge(fu,on=['match_id','innings','sequence'],validate='1:1')
nm=pd.read_parquet(f'{V}/newmethod_pressure_30202525.parquet')
d=d.merge(nm[['match_id','innings','sequence','pressure_new','high_new']],on=['match_id','innings','sequence'],validate='1:1')
for disc,role,pid,name,ex,floor,finalfloor in [('batting','bat','batter_pid','batter','faced',75,230),('bowling','bowl','bowler_pid','bowler','legal',100,300)]:
 a=joblib.load(f'{V}/{disc}_rating_mixture_filtered.joblib');ref=a['reference'];mu,A,B=unpack(a['hyper']);T=A@A.T;l=np.array([1,ref['G_Pmean']-ref['P_ref'],0,0]);M=np.array([l,[0,0,1,ref['G_Pmean']-ref['P_ref']],[0,ref['G_Pmean']-ref['P_ref'],0,0]]);center=M@mu;sd=np.sqrt(np.diag(M@T@M.T));out=[];drawstore={}
 for o in a['posteriors']:
  ident=o['id'];q=d[d[pid].eq(ident)];ns=d[d.non_striker_pid.eq(ident)] if role=='bat' else q.iloc[:0];pname=q[name].mode().iloc[0] if len(q) else ns.non_striker.mode().iloc[0];means=o['nuisance_means'];samples=[]
  for k,F in enumerate(o['nuisance_factors']):samples.append(means[k]+rng.normal(size=(512,F.shape[1]))@F.T)
  samples=np.concatenate(samples);mv=M@o['mean'];z=(mv-center)/sd;score=100*ndtr(z[0]);sscore=100*ndtr((samples@l-center[0])/sd[0]);drawstore[ident]=samples;high=q.high_new;n=int((q.legal*high).sum());above=float(np.mean(samples@l>center[0]));abilitysd=float(np.sqrt(l@o['cov']@l));consistent=bool(mv[0]>center[0] and abilitysd<sd[0]*.5 and n>=floor)
  row={'player_id':ident,'player':pname,'Score':score,'Score80low_conditional_mixture':float(np.quantile(sscore,.1)),'Score80high_conditional_mixture':float(np.quantile(sscore,.9)),'Score95low_conditional_mixture':float(np.quantile(sscore,.025)),'Score95high_conditional_mixture':float(np.quantile(sscore,.975)),'A_common':mv[0],'A_SD_conditional_mixture':abilitysd,'A_probability_above_reference_conditional':above,'K_common':mv[1],'C_pressure_increment':mv[2],'Pr_pressure_slope_positive_conditional':float((samples[:,1]>0).mean()),'HP_legal_balls':n,'HP_matches':int(q.loc[high,'match_id'].nunique()),'matches':int(q.match_id.nunique()),'innings':int(q[['match_id','innings']].drop_duplicates().shape[0]),'weighted_exposure':o['weighted_exposure'],'effective_events':o['n_eff'],'eligible':n>=floor,'evidence_status':'Established exposure' if n>=floor else 'Provisional exposure','consistency_label':'Meets declared historical benchmark' if consistent else 'Not established under declared benchmark','consistency_benchmark':center[0],'consistency_SD_tolerance':sd[0]*.5,'consistency_policy':'Meanabovepopulationreference; posteriorSD<0.5latentpopulationSD; legalHPfloor75bat/100bowl. Analysttransparentlabelthreshold, sensitivityrequired, notscientificconstant','role_style':'Unknown - not inferred','interval_scope':'Conditional32ratingdrawmixture; fixedoutcome/winmodelcoefficients,hyperparameters,reference; notcalibratedfullpipelinecoverage; filteredtop35pctpressureballsonly','component_unit':'Modelscaledper100opportunity; rawrunvalue=A*utility_scale_A/100','H_days':365,'score_definition':'100Phi(standardizedhistoricalposterior_mean_A), NO uncertainty penalty','score_MCSE_rating':float(np.std(means@l,ddof=1)/np.sqrt(len(means))/sd[0]*100/np.sqrt(2*np.pi)*np.exp(-z[0]**2/2)),'mean16_score':float(100*ndtr((means[:16].mean(0)@l-center[0])/sd[0]))};out.append(row)
 df=pd.DataFrame(out).sort_values('Score',ascending=False);df['rank']=np.nan;df.loc[df.eligible,'rank']=np.arange(1,int(df.eligible.sum())+1);df=pd.concat([df[df.eligible],df[~df.eligible].sort_values(['player','player_id'])]);df.to_csv(f'{V}/{disc}_Historical_Scores_filtered.csv',index=False)
 joblib.dump({'samples':drawstore,'reference':ref,'M':M,'latent_mean':center,'latent_SD':sd},f'{V}/{disc}_mixture_samples_filtered.joblib')
 eligible=df[df.eligible];r16=eligible.sort_values('mean16_score',ascending=False)
 fin=eligible[eligible.HP_legal_balls>=finalfloor].sort_values('Score',ascending=False).copy();fin['final_rank']=np.arange(1,len(fin)+1)
 if disc=='batting': fin=fin[fin.player!='Agha Salman'].copy();fin['final_rank']=np.arange(1,len(fin)+1)
 fin.to_csv(f'{V}/{disc}_Final_List_filtered.csv',index=False)
 logs[disc]={'identities':len(df),'eligible':int(df.eligible.sum()),'final_list':len(fin),'latentSD':sd.tolist(),'MC16vs32_Spearman':float(spearmanr(eligible.Score,eligible.mean16_score).statistic),'MC16vs32_top10_overlap':len(set(eligible.head(10).player_id)&set(r16.head(10).player_id)),'max_score_MCSE_rating':float(df.score_MCSE_rating.max()),'max_score16_32_difference':float(abs(df.Score-df.mean16_score).max()),'agha_in_batting_eligible':bool((eligible.player=='Agha Salman').any()) if disc=='batting' else None,'agha_HP_legal_balls':int(eligible.loc[eligible.player=='Agha Salman','HP_legal_balls'].iloc[0]) if disc=='batting' and (eligible.player=='Agha Salman').any() else None,'scope':'Reviewonly: finite32nuisancedrawMCstabilitynotcoveragevalidation. Consistencythresholdpolicyrequires sensitivity.'}
 print(disc,logs[disc],flush=True)
open(f'{V}/historical_scores_checks_filtered.json','w').write(json.dumps(logs,indent=2))
