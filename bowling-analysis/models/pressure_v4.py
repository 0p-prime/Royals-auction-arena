"""Version 4 (exploratory research candidate): bowler pressure = batting side strongly placed.

CONSTRUCT (project owner, 11 Nov): pressure ON THE BOWLER = the batting side is in a strong position and the
bowler needs to stop them or bring the match back. A close match alone is not pressure. Only this meaning
and the three outputs are confirmed by the project owner; the measurement below is a research candidate, NOT approved as final
and NOT a final pressure definition. pb is a model-defined ordinal score from winprob.py (Markov
win-probability from pre-ball runs needed, legal balls left, wickets lost; forward-season tables).
Score bands are model-defined, not real probabilities: observed chase win rates in a pb bin differ from pb.

States (second innings only, from pre-ball inputs and pb):
  pressure     : lo <= pb < hi     model band: batting side clearly ahead
  normal       : pb < lo           everything below the band, INCLUDING states where the bowling side is
                                   almost certain to win
  above_band   : pb >= hi          excluded from pressure and normal; chases from these states were still lost
                                   about 3-7% of the time, so this is NOT an established "nearly decided" rule
  not_applicable: first innings (no target)
There is NO qualified both-tail "almost finished" exclusion: the low tail is not excluded and the top cut is
only model-defined. The version therefore cannot fulfil that part of the intent. List 1 (overall) uses all balls.

Three lists: 1 overall level, 2 pressure level, 3 uplift = pressure minus own normal, compared only in
phases where that bowler has both (min_stratum_balls each). Runs saved (E[R]-charged) and wickets above
expected (W-E[W]) are shrunk separately and combined as runs + v*wickets over config wicket values;
order = median rank, then mean rank, then name (an aggregation, not removal of the weight choice).
Descriptive of IPL 2022-26; 2025-26 already used for diagnosis; not validated for future selection.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from bpf_continuous import shrink_slopes, _parity_map
from bpf_components import add_components, level_table

PHASES = ['powerplay', 'middle', 'death']


def load_cfg(path='config.json'):
    c = json.loads(Path(path).read_text())
    return c, c['v4']


def training_deliveries(cfg, path='data/ipl_json.zip'):
    """Delivery outcomes from the bundled Cricsheet archive (warmup year onward) for win-model tables."""
    from data_loader import load
    from winprob import prepare_training
    raw, _ = load(path, cfg)
    return prepare_training(raw)


def add_pb(d, cfg, train_df=None):
    """Batting-advantage score pb for second-innings balls (NaN in first innings), using
    forward-season tables (winprob.forward_tables_by_season): no match informs its own pb."""
    from winprob import forward_tables_by_season, pbat
    if train_df is None:
        train_df = training_deliveries(cfg)
    Vs = forward_tables_by_season(train_df, cfg)
    d = d.copy()
    d['pb'] = np.nan
    for y, V in Vs.items():
        m = (d.innings == 2) & (d.season == y)
        d.loc[m, 'pb'] = pbat(V, (d.target - d.pre_runs)[m], 120 - d.pre_balls[m], 10 - d.wickets_in_hand[m])
    return d


def label_state(d, band):
    """pressure / normal / above_band (innings 2) or not_applicable (innings 1), from d.pb."""
    out = pd.Series('not_applicable', index=d.index)
    ch = d.innings == 2
    out[ch & (d.pb < band[0])] = 'normal'
    out[ch & (d.pb >= band[0]) & (d.pb < band[1])] = 'pressure'
    out[ch & (d.pb >= band[1])] = 'above_band'
    return out


def _cr_ols(X, y, cl):
    XtXi = np.linalg.pinv(X.T @ X)
    b = XtXi @ X.T @ y
    e = y - X @ b
    meat = np.zeros((X.shape[1],) * 2)
    for k in np.unique(cl):
        s = X[cl == k].T @ e[cl == k]
        meat += np.outer(s, s)
    V = XtXi @ meat @ XtXi
    return b, np.sqrt(np.clip(np.diag(V), 0, None))


def overlap_phases(g, k):
    """Phases where this bowler has >=k pressure AND >=k normal balls."""
    keep = []
    for ph in PHASES:
        gp = g[g.phase == ph]
        if (gp.state == 'pressure').sum() >= k and (gp.state == 'normal').sum() >= k:
            keep.append(ph)
    return keep


def uplift_table(d, col, min_p, min_n, k, min_matches):
    """Per-bowler pressure-minus-normal difference per 100 balls, phase-matched on
    overlapping phases only (phase fixed effects, full rank by construction)."""
    rows = []
    g0 = d[d.state.isin(['pressure', 'normal'])]
    for b, g in g0.groupby('bowler'):
        ph = overlap_phases(g, k)
        if not ph:
            continue
        g = g[g.phase.isin(ph)]
        p = (g.state == 'pressure').to_numpy()
        if p.sum() < min_p or (~p).sum() < min_n or g.match_id.nunique() < min_matches:
            continue
        cols = [np.ones(len(g)), p.astype(float)] + [(g.phase == x).to_numpy().astype(float) for x in ph[1:]]
        X = np.column_stack(cols)
        beta, se = _cr_ols(X, g[col].to_numpy(float), g.match_id.to_numpy())
        if not np.isfinite(se[1]) or se[1] <= 0:
            continue
        rows.append({'Bowler': b, 'slope_raw': 100 * beta[1], 'slope_se': 100 * se[1],
                     'deliveries': len(g), 'pressure_balls': int(p.sum()), 'normal_balls': int((~p).sum()),
                     'matches': g.match_id.nunique(), 'phases_used': '+'.join(ph)})
    return pd.DataFrame(rows, columns=['Bowler', 'slope_raw', 'slope_se', 'deliveries', 'pressure_balls',
                                       'normal_balls', 'matches', 'phases_used'])


def shrunk(t):
    if len(t) == 0:
        return t.assign(slope_shrunk=[], CI_low=[], CI_high=[]).set_index('Bowler')
    return shrink_slopes(t).set_index('Bowler')


def combine(runs, wk, vals):
    j = runs[['slope_shrunk', 'CI_low', 'CI_high', 'deliveries']].join(
        wk[['slope_shrunk']].rename(columns={'slope_shrunk': 'wk_shrunk'}), how='inner')
    j = j.rename(columns={'slope_shrunk': 'runs_shrunk'})
    for v in vals:
        j[f'comb_{v}'] = j.runs_shrunk + v * j.wk_shrunk
        j[f'rank_{v}'] = j[f'comb_{v}'].rank(ascending=False, method='min')
    rc = [f'rank_{v}' for v in vals]
    j['rank_median'] = j[rc].median(axis=1)
    j['rank_mean'] = j[rc].mean(axis=1)
    j['rank_best'] = j[rc].min(axis=1)
    j['rank_worst'] = j[rc].max(axis=1)
    j['top_n_all_values'] = (j[rc] <= 10).all(axis=1)
    # deterministic, value-neutral order: median rank, then mean rank, then name
    j.index.name = 'Bowler'
    j = j.reset_index().sort_values(['rank_median', 'rank_mean', 'Bowler']).set_index('Bowler')
    j['order'] = range(1, len(j) + 1)
    return j


def make_lists(d, cfg, v4, band):
    d = d.copy()
    d['state'] = label_state(d, band)
    vals = v4['wicket_values']
    out = {}
    out['overall'] = combine(shrunk(level_table(d, 'runs_resid', v4['min_overall_balls'])),
                             shrunk(level_table(d, 'wk_resid', v4['min_overall_balls'])), vals)
    dp = d[d.state == 'pressure']
    out['pressure'] = combine(shrunk(level_table(dp, 'runs_resid', v4['min_pressure_balls'])),
                              shrunk(level_table(dp, 'wk_resid', v4['min_pressure_balls'])), vals)
    args = (v4['min_pressure_balls'], v4['min_normal_balls_uplift'], v4['min_stratum_balls'], v4['min_matches_uplift'])
    ur = uplift_table(d, 'runs_resid', *args)
    uw = uplift_table(d, 'wk_resid', *args)
    u = combine(shrunk(ur), shrunk(uw), vals)
    ex = ur.set_index('Bowler')[['pressure_balls', 'normal_balls', 'phases_used']]
    out['uplift'] = u.join(ex)
    return out, d


def _spear(a, b):
    from scipy.stats import spearmanr
    j = a.join(b, lsuffix='_a', rsuffix='_b', how='inner').dropna()
    if len(j) < 5:
        return {'bowlers': len(j), 'spearman': None}
    return {'bowlers': len(j), 'spearman': float(spearmanr(j.iloc[:, 0], j.iloc[:, 1]).statistic)}


def split_half(d, cfg, v4):
    par = _parity_map(d)
    h = d.match_id.map(par)
    splits = {'alternate_match': (d[h == 0], d[h == 1]),
              'early_vs_late': (d[d.season <= cfg['train_end']], d[d.season >= cfg['test_start']])}
    mo, mp = v4['split_min_overall_balls'], v4['split_min_pressure_balls']
    ua = (v4['split_min_uplift_pressure'], v4['split_min_uplift_normal'], v4['min_stratum_balls'] // 2 or 1, 2)
    wv = 20 if 20 in v4['wicket_values'] else v4['wicket_values'][len(v4['wicket_values']) // 2]
    res = {}
    P = lambda x: x[x.state == 'pressure']
    for name, (a, b) in splits.items():
        res[name] = {}
        tests = {'overall_runs': lambda x: level_table(x, 'runs_resid', mo),
                 'overall_wickets': lambda x: level_table(x, 'wk_resid', mo),
                 'pressure_runs': lambda x: level_table(P(x), 'runs_resid', mp),
                 'pressure_wickets': lambda x: level_table(P(x), 'wk_resid', mp),
                 'uplift_runs': lambda x: uplift_table(x, 'runs_resid', *ua),
                 'uplift_wickets': lambda x: uplift_table(x, 'wk_resid', *ua)}
        raw = {}
        for tag, fn in tests.items():
            ta, tb = fn(a).set_index('Bowler')[['slope_raw']], fn(b).set_index('Bowler')[['slope_raw']]
            raw[tag] = (ta, tb)
            res[name][tag] = _spear(ta, tb)
        for lst in ['overall', 'pressure', 'uplift']:
            out = []
            for half in (0, 1):
                r, w = raw[f'{lst}_runs'][half], raw[f'{lst}_wickets'][half]
                j = r.join(w, lsuffix='_r', rsuffix='_w', how='inner')
                out.append((j.slope_raw_r + wv * j.slope_raw_w).to_frame('v'))
            res[name][f'{lst}_combined{wv}'] = _spear(out[0], out[1])
    return res


def run_v4(scored, cfg, v4):
    d = add_pb(add_components(scored), cfg)
    primary, dl = make_lists(d, cfg, v4, v4['pressure_band_primary'])
    alt, _ = make_lists(d, cfg, v4, v4['pressure_band_alt'])
    cnt = dl.state.value_counts().to_dict()
    # descriptive chase outcome by pb bin (NOT used for labelling)
    c = dl[dl.innings == 2].copy()
    fin = c.groupby('match_id').apply(lambda g: bool(g.pre_runs.iloc[-1] + g.total.iloc[-1] >= g.target.iloc[0]),
                                      include_groups=False).rename('win')
    c = c.join(fin, on='match_id')
    c['bin'] = pd.cut(c.pb, v4['win_rate_bins'], right=False)
    wr = c.groupby('bin', observed=True).agg(balls=('win', 'size'), chase_win_rate=('win', 'mean'),
                                           matches=('match_id', 'nunique')).round(3)
    val = {'version': 'v4 batting-advantage pressure (exploratory, descriptive)',
           'pressure_proxy': 'batting-advantage score pb (Markov chase win-probability, ordinal); pressure = pb in band, second innings only',
           'band_primary': v4['pressure_band_primary'], 'band_alt': v4['pressure_band_alt'],
           'scope_counts_deliveries': {k: int(x) for k, x in cnt.items()},
           'scope_note': 'pressure = pb in band; normal = pb below band (includes near-certain bowling-side wins); above_band excluded from both; first innings not_applicable for lists 2-3 (list 1 uses all balls); no qualified both-tail exclusion',
           'descriptive_chase_win_rate_by_pb_bin': {str(k): {a: float(b) for a, b in r.items()} for k, r in wr.iterrows()},
           'wicket_values_tested': v4['wicket_values'],
           'order_rule': 'median rank across wicket values, then mean rank, then name; an aggregation choice, not elimination of the weight choice'}
    val['split_half_spearman_primary'] = split_half(dl, cfg, v4)
    sens = {}
    for lst in ['pressure', 'uplift']:
        a, b = primary[lst], alt[lst]
        j = a[['rank_median']].join(b[['rank_median']], how='inner', lsuffix='_p', rsuffix='_v')
        n = v4['top_n']
        sens[lst] = {'bowlers_both': len(j),
                     'spearman_rank_median': float(j.corr(method='spearman').iloc[0, 1]) if len(j) > 4 else None,
                     'top_n_overlap': len(set(a.head(n).index) & set(b.head(n).index))}
    val['definition_sensitivity_alt_band'] = sens
    wv = {}
    n = v4['top_n']
    for lst, t in primary.items():
        base = 20 if 20 in v4['wicket_values'] else v4['wicket_values'][0]
        top = {v: set(t.nsmallest(n, f'rank_{v}').index) for v in v4['wicket_values']}
        wv[lst] = {'bowlers_ranked': len(t), 'topn_overlap_with_v%d' % base: {str(v): len(top[base] & top[v]) for v in v4['wicket_values']},
                   'topn_in_all_values': int(t.top_n_all_values.sum())}
    val['wicket_value_sensitivity'] = wv
    val['caveats'] = [
        'Research candidate only. Only the construct (batting side strongly placed, bowler must stop or recover) and the three outputs are confirmed by the project owner; this measurement is not approved as final and is not a final pressure definition.',
        'pb is an ORDINAL model-defined score from a simple Markov win-probability (forward-season tables), not a calibrated probability: it underpredicts chase wins when behind and observed win rates in a pb bin differ from pb. Band edges are model-defined design choices, not proven thresholds.',
        'No qualified both-tail "almost finished" exclusion. States above the band (pb >= hi) are excluded, but chases from pb >= 0.9 states were still lost about 3-7% of the time (outputs/winprob_check.json), so this is not an established decided state; states below the band include near-certain bowling-side wins and are not excluded. This version cannot fulfil that intent.',
        'Second innings only. First-innings balls are outside pressure/normal (no target); list 1 uses all balls. First-innings bowler pressure is not defined here.',
        'Uplift compares each bowler only within phases where they have both pressure and normal balls; bowlers without overlap are omitted.',
        'pb assumes outcomes depend only on over and wickets lost; no batter/bowler identity, no risk-taking change. Wicket/ball monotonicity violations exist (see winprob_check.json, max up to several points), run values are clipped at run_clip, and runs needed must stay <= nmax (checked).',
        '2025-26 was already used for diagnosis; no fresh test. Descriptive of IPL 2022-26, not validated for future selection.',
        'Interval labels are exploratory: cluster SEs may be optimistic, no multiple-comparison adjustment, band/model uncertainty omitted.',
        'Level is not role-free; bowlers used in different overs/teams face different contexts the models only partly capture.',
        'Uplift subtracts two noisy levels; read it only with the repeatability and placebo results. Only runs saved repeats; the combined ranking is not validated.',
        'No availability filter applied; Team is latest observed team.']
    return primary, alt, val, dl


if __name__ == '__main__':
    cfg, v4 = load_cfg()
    s = pd.read_csv('outputs/delivery_scores.csv.gz')
    primary, alt, val, dl = run_v4(s, cfg, v4)
    meta = pd.read_csv('outputs/all_bowlers.csv')[['Bowler', 'Team', 'Type']].drop_duplicates('Bowler').set_index('Bowler')
    for lst, t in primary.items():
        t.join(meta, how='left').reset_index().to_csv(f'outputs/v4_list_{lst}.csv', index=False)
    for lst in ['pressure', 'uplift']:
        alt[lst].reset_index().to_csv(f'outputs/v4_sens_alt_band_{lst}.csv', index=False)
    Path('outputs/validation_v4.json').write_text(json.dumps(val, indent=2, default=str))
    print(json.dumps({k: val[k] for k in ['scope_counts_deliveries', 'descriptive_chase_win_rate_by_pb_bin', 'definition_sensitivity_alt_band', 'wicket_value_sensitivity']}, indent=1, default=str))
    print(json.dumps(val['split_half_spearman_primary'], indent=1))
