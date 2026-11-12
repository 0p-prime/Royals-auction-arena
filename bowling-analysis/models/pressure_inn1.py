"""First-innings bowler pressure lists (research candidate, separate from the second-innings v4 lists).

Pressure (first innings) = pb1 in config band: the side batting first is strongly placed by the score,
balls bowled and wickets lost. No venue. normal = pb1 below band. above_band = excluded. Same band edges as
the second innings, NOT retuned. No qualified near-decided rule; no claim that first/second-innings
pressure is on one scale, so nothing here is merged with the second-innings lists.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from pressure_v4 import (load_cfg, training_deliveries, combine, shrunk, uplift_table, split_half)
from bpf_components import add_components, level_table
from winprob1 import prepare_first_innings, add_pb1, models_by_season, FEATS


def label1(d, band):
    s = pd.Series('not_applicable', index=d.index)
    f = d.innings == 1
    s[f & (d.pb1 < band[0])] = 'normal'
    s[f & (d.pb1 >= band[0]) & (d.pb1 < band[1])] = 'pressure'
    s[f & (d.pb1 >= band[1])] = 'above_band'
    return s


def lists1(d1, v4):
    p = v4['inn1']
    vals = v4['wicket_values']
    dp = d1[d1.state == 'pressure']
    out = {'pressure': combine(shrunk(level_table(dp, 'runs_resid', p['min_pressure_balls'])),
                               shrunk(level_table(dp, 'wk_resid', p['min_pressure_balls'])), vals)}
    args = (p['min_pressure_balls'], p['min_normal_balls_uplift'], p['min_stratum_balls'], p['min_matches_uplift'])
    ur, uw = uplift_table(d1, 'runs_resid', *args), uplift_table(d1, 'wk_resid', *args)
    u = combine(shrunk(ur), shrunk(uw), vals)
    out['uplift'] = u.join(ur.set_index('Bowler')[['pressure_balls', 'normal_balls', 'phases_used']])
    return out


def run_inn1(scored, cfg, v4):
    p = v4['inn1']
    tr = prepare_first_innings(training_deliveries(cfg))
    d = add_pb1(add_components(scored), cfg, tr)
    d['state'] = label1(d, p['band'])
    d1 = d[d.innings == 1].copy()
    # win label for evaluation (outcome used ONLY for checks, never for labelling)
    lab = prepare_first_innings(training_deliveries(cfg))[['match_id', 'first_side_won']].drop_duplicates('match_id').set_index('match_id').first_side_won
    d1['won'] = d1.match_id.astype(str).map(lab.rename(index=str))
    ev = d1.dropna(subset=['won'])
    chk = {}
    for name, m in [('seasons_2022_24_forward', ev.season <= cfg['train_end']), ('seasons_2025_26_fixed', ev.season > cfg['train_end'])]:
        x = ev[m]
        g = x.groupby(pd.cut(x.pb1, p['calibration_bins'], right=False), observed=True).agg(
            balls=('won', 'size'), mean_pb1=('pb1', 'mean'), first_side_win_rate=('won', 'mean'), matches=('match_id', 'nunique')).round(3)
        chk[name] = {'brier_pb1': float(((x.pb1 - x.won) ** 2).mean()),
                     'brier_constant_baseline_oracle_prevalence': float(((x.won.mean() - x.won) ** 2).mean()),
                     'bins': {str(k): r.to_dict() for k, r in g.iterrows()}}
    d1['stage'] = pd.cut(d1.pre_balls, [-1, 35, 89, 120], labels=['balls 0-35', 'balls 36-89', 'balls 90+'])
    stage = d1.groupby('stage', observed=True).agg(deliveries=('pb1', 'size'), mean_pb1=('pb1', 'mean'),
                                                  share_pressure=('state', lambda s: float((s == 'pressure').mean())),
                                                  share_above=('state', lambda s: float((s == 'above_band').mean()))).round(3)
    prim = lists1(d1, v4)
    import zipfile
    raw = training_deliveries(cfg)
    both = set(raw[raw.innings == 1].match_id) & set(raw[raw.innings == 2].match_id)
    z = zipfile.ZipFile('data/ipl_json.zip'); labs = lab.copy(); labs.index = labs.index.astype(str)
    agree = dis = nowin = 0
    for n in z.namelist():
        if not n.endswith('.json'): continue
        mid = n.rsplit('/', 1)[-1][:-5]
        if mid not in labs.index: continue
        x = json.loads(z.read(n)); w = x['info'].get('outcome', {}).get('winner')
        if w is None: nowin += 1
        elif (w == x['innings'][0]['team']) == (labs[mid] == 1.0): agree += 1
        else: dis += 1
    label_evidence = {'matches_in_scope_with_both_innings': len(both), 'matches_labelled': int(len(labs)),
                      'excluded_ties_runs_equal_target_minus_1': len(both) - int(len(labs)),
                      'label_rule': 'first side won if chase total <= target-2; chase won if >= target; exactly target-1 is a tie and is excluded; matches failing the data loader (reduced overs, revised target, no result, missing innings) are not in scope at all',
                      'checked_against_cricsheet_official_winner': {'agree': agree, 'disagree': dis, 'no_winner_listed': nowin}}
    cnt = d1.state.value_counts().to_dict()
    val = {'version': 'first-innings batting-advantage pressure (exploratory research candidate, no venue)',
           'construct': 'pb1 = model P(side batting first wins match) from pre-ball runs, legal balls bowled, wickets lost; pressure = pb1 in band',
           'band': p['band'], 'scope_counts_first_innings_deliveries': {k: int(v) for k, v in cnt.items()},
           'check_by_season_group': chk, 'by_stage': {str(k): r.to_dict() for k, r in stage.iterrows()},
           'split_half_spearman': {k: v for k, v in split_half(d1, cfg, v4).items()},
           'bowlers_ranked': {k: len(v) for k, v in prim.items()}, 'label_evidence': label_evidence}
    return prim, val, d1


if __name__ == '__main__':
    cfg, v4 = load_cfg()
    s = pd.read_csv('outputs/delivery_scores.csv.gz')
    prim, val, d1 = run_inn1(s, cfg, v4)
    meta = pd.read_csv('outputs/all_bowlers.csv')[['Bowler', 'Team', 'Type']].drop_duplicates('Bowler').set_index('Bowler')
    for k, t in prim.items():
        t.join(meta, how='left').reset_index().to_csv(f'outputs/v4_inn1_list_{k}.csv', index=False)
    Path('outputs/validation_inn1.json').write_text(json.dumps(val, indent=2, default=str))
    print(json.dumps({k: val[k] for k in ['scope_counts_first_innings_deliveries', 'by_stage', 'bowlers_ranked']}, indent=1, default=str))
    for k, g in val['check_by_season_group'].items():
        print(k, round(g['brier_pb1'], 4), round(g['brier_constant_baseline_oracle_prevalence'], 4))
        for b, r in g['bins'].items(): print('  ', b, r['balls'], r['mean_pb1'], r['first_side_win_rate'])
    print(json.dumps(val['split_half_spearman'], indent=1))
