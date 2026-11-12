"""Sanity, truncation and out-of-sample calibration checks for pb (writes outputs/winprob_check.json)."""
import json, numpy as np, pandas as pd
from pathlib import Path
from winprob import outcome_tables, solve, pbat
from pressure_v4 import training_deliveries, add_pb
cfg = json.loads(Path('config.json').read_text()); v4 = cfg['v4']; wp = v4['winprob']
tr = training_deliveries(cfg)
fixed_tabs = outcome_tables(tr, range(cfg['warmup_year'], cfg['train_end'] + 1), wp)
V = solve(fixed_tabs, wp)
ext = {f'need {n} off {b} balls, {w} wickets lost': round(float(V[b, w, n]), 3)
       for n, b, w in [(1, 1, 5), (4, 1, 5), (6, 1, 5), (10, 1, 5), (2, 6, 9), (20, 12, 2), (8, 6, 2), (30, 18, 8), (60, 60, 3), (120, 120, 0), (180, 120, 0)]}
dw = np.diff(V[:, :, 1:], axis=1); db = np.diff(V[1:, :, 1:], axis=0)
iw = np.unravel_index(np.argmax(dw), dw.shape); ib = np.unravel_index(np.argmin(db), db.shape)
V40 = solve(fixed_tabs, wp, iters=wp['illegal_repeat_iters'] * 5)
out = {'extreme_state_pb_fixed_tables_2019_24': ext,
       'terminals': {'n<=0 is 1': bool((V[:, :, 0] == 1).all()), 'w=10 and n>0 is 0': bool((V[:, 10, 1:] == 0).all()), 'b=0 and n>0 is 0': bool((V[0, :, 1:] == 0).all())},
       'monotone_in_runs_needed': bool((np.diff(V[:, :, 1:], axis=2) <= 1e-9).all()),
       'wickets_violation_share_of_cells': float((dw > 1e-9).mean()), 'wickets_violation_max': float(dw.max()),
       'wickets_violation_at_balls_left_wickets_runs_needed': [int(iw[0]), int(iw[1]), int(iw[2]) + 1],
       'balls_violation_share_of_cells': float((db < -1e-6).mean()), 'balls_violation_max': float(-db.min()),
       'balls_violation_at_balls_left_wickets_runs_needed': [int(ib[0]) + 1, int(ib[1]), int(ib[2]) + 1],
       'illegal_repeat_truncation_max_abs_diff_vs_5x_iters': float(np.abs(V - V40).max()),
       'deliveries_with_total_runs_above_clip': int((tr.total > wp['run_clip']).sum()), 'training_deliveries': int(len(tr)),
       'max_runs_needed_in_second_innings': int((tr[tr.innings == 2].target - 0).max()), 'nmax': wp['nmax'],
       'violation_note': 'violations come from over/wickets-bucket frequency tables and can reach several points of pb; they are not small enough to ignore'}
s = pd.read_csv('outputs/delivery_scores.csv.gz'); s = add_pb(s, cfg, tr)
c = s[s.innings == 2].copy()
fin = c.groupby('match_id').apply(lambda g: float(g.pre_runs.iloc[-1] + g.total.iloc[-1] >= g.target.iloc[0]), include_groups=False).rename('win')
c = c.join(fin, on='match_id')
out['chronology'] = 'pb for season Y<=2024 uses tables from seasons 2019..Y-1 only; 2025-26 use fixed 2019-2024 tables; all pb below are out of sample for their own match'
for name, m in [('seasons_2022_24_forward', c.season <= cfg['train_end']), ('seasons_2025_26_fixed', c.season > cfg['train_end'])]:
    x = c[m]
    g = x.groupby(pd.cut(x.pb, v4['win_rate_bins'], right=False), observed=True).agg(balls=('win', 'size'), mean_pb=('pb', 'mean'), chase_win_rate=('win', 'mean'), matches=('match_id', 'nunique')).round(3)
    out[name] = {'brier_pb': float(((x.pb - x.win) ** 2).mean()), 'brier_constant_baseline': float(((x.win.mean() - x.win) ** 2).mean()),
                 'overall_chase_win_rate': float(x.win.mean()), 'bins': {str(k): r.to_dict() for k, r in g.iterrows()}}
out['limits'] = ['pb is ordinal and model-defined, not a calibrated probability: observed chase win rate differs from pb in many bins (see bins).',
                 'Outcome mix depends only on over and wickets lost; no identity or risk-taking effects.', '2025-26 already used for diagnosis.']
Path('outputs/winprob_check.json').write_text(json.dumps(out, indent=2))
print(json.dumps({k: out[k] for k in out if k not in ('seasons_2022_24_forward', 'seasons_2025_26_fixed')}, indent=1))
for k in ['seasons_2022_24_forward', 'seasons_2025_26_fixed']:
    print(k, round(out[k]['brier_pb'], 3), round(out[k]['brier_constant_baseline'], 3)); [print(' ', b, r['balls'], r['mean_pb'], r['chase_win_rate']) for b, r in out[k]['bins'].items()]
