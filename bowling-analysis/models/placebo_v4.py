"""Placebo for UPLIFT (runs): shuffle pressure/normal labels within bowler x phase among
second-innings balls (counts preserved), recompute shrunk uplift spread. Reps/seed from config."""
import json, numpy as np, pandas as pd
from pathlib import Path
from bpf_components import add_components
from pressure_v4 import load_cfg, label_state, uplift_table, shrunk, add_pb
cfg, v4 = load_cfg()
d = add_pb(add_components(pd.read_csv('outputs/delivery_scores.csv.gz')), cfg); d['state'] = label_state(d, v4['pressure_band_primary'])
args = (v4['min_pressure_balls'], v4['min_normal_balls_uplift'], v4['min_stratum_balls'], v4['min_matches_uplift'])
def stats(x):
    s = shrunk(uplift_table(x, 'runs_resid', *args))
    return dict(n=len(s), sd_shrunk=float(s.slope_shrunk.std()), max_shrunk=float(s.slope_shrunk.max()))
real = stats(d)
rng = np.random.default_rng(v4['placebo_seed']); out = []
m = d.state.isin(['pressure', 'normal'])
for i in range(v4['placebo_reps']):
    x = d.copy(); idx = x.index[m]; sub = x.loc[idx, ['bowler', 'phase', 'state']].copy()
    sub['state'] = sub.groupby(['bowler', 'phase']).state.transform(lambda s: rng.permutation(s.values))
    x.loc[idx, 'state'] = sub.state; out.append(stats(x))
o = pd.DataFrame(out)
res = {'reps': v4['placebo_reps'], 'real': real,
       'placebo_sd_shrunk_quantiles': o.sd_shrunk.quantile([0, .5, .9, 1]).to_dict(),
       'placebo_max_shrunk_quantiles': o.max_shrunk.quantile([0, .5, .9, 1]).to_dict(),
       'real_sd_percentile_in_placebo': float((o.sd_shrunk < real['sd_shrunk']).mean()),
       'note': 'shuffles labels within bowler x phase, removing any real pressure effect but keeping ball-to-ball noise; exploratory'}
Path('outputs/placebo_v4.json').write_text(json.dumps(res, indent=2)); print(json.dumps(res, indent=2))
