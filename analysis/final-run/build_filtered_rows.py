import sys, os
os.environ['OPENBLAS_NUM_THREADS']='2'
sys.path.insert(0,'/tmp/v3/deps');sys.path.insert(0,'/tmp/v3/codezip');sys.path.insert(0,'/tmp/v3/replay')
import pandas as pd, numpy as np, joblib, json
from raw_match_design_filtered import make_rows_filtered
disc = os.environ.get('DISC','batting')
h = float(os.environ.get('HDECAY','1e9'))
base = pd.read_parquet('v3_historical/scored_smooth_stable.parquet')
fu = pd.read_parquet('v3_historical/full_utilities.parquet')
overlap = [c for c in base.columns if c in fu.columns and c not in ('match_id','innings','sequence')]
d = base.drop(columns=overlap).merge(fu, on=['match_id','innings','sequence'], validate='1:1')
nm = pd.read_parquet('v3_historical/newmethod_pressure_30202525.parquet')
d = d.merge(nm[['match_id','innings','sequence','pressure_new','high_new']], on=['match_id','innings','sequence'], validate='1:1')
d = d[d.high_new].copy()
d['pressure'] = d['pressure_new']   # filtered frame carries NEW pressure as P
role='bat' if disc=='batting' else 'bowl'; ex='faced' if disc=='batting' else 'legal'
# shared-baseline scaling stays broad (all balls), P_ref = exposure-weighted mean of FILTERED pressure
full = base.drop(columns=overlap).merge(fu, on=['match_id','innings','sequence'], validate='1:1')
ref={'P_ref':float(np.average(d.pressure,weights=d[ex])),'utility_scale':[float(np.sqrt(np.mean(full[role+'_event_var_A']*10000))),float(np.sqrt(np.mean(full[role+'_event_var_K']*10000)))]}
anchor = pd.Timestamp('2026-11-18')
rows,notes,stats = make_rows_filtered(d,disc,ref,h=h,anchor=anchor)
print(disc,'h',h,'P_ref %.12f'%ref['P_ref'],'rows',len(rows),'players',len(set(r['id'] for r in rows)),'constraint_blocks',stats['constraint_blocks'],'null_reductions',stats['null_reductions'],'no_exposure',stats['no_exposure_observations'])
joblib.dump(rows, f'v3_historical/{disc}_filtered_rows_h{"1e9" if h>1e8 else "365"}.joblib')
json.dump({'P_ref':ref['P_ref'],'utility_scale':ref['utility_scale'],'stats':stats,'notes_count':len(notes)}, open(f'v3_historical/{disc}_filtered_ref.json','w'))
