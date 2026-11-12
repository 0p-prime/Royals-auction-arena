"""Version 3 (exploratory): separate runs and wickets components, report LEVELS.

Why: diagnostics on the delivered scores showed the 20-run wicket term
(20*(W-E[W])) is about 75% of per-ball variance of rae_c (81% with its covariance
share; observational, not a sole cause) and bowler-level wicket residuals did not repeat between alternate matches, while the runs-prevented component
(E[R]-charged) is repeatable. Fusing them at an assumed exchange rate hides that.
This stage keeps the two components apart and describes each bowler's
runs prevented vs expected overall and inside the frozen boundary-risk buckets.
It is a DESCRIPTIVE summary of past IPL 2022-26 deliveries, not a selection model.
Nothing here is validated for future selection or auction decisions.
"""
import numpy as np
import pandas as pd
from bpf_continuous import shrink_slopes, _parity_map


def add_components(df):
    d = df.copy()
    d['runs_resid'] = d.er - d.charged          # runs prevented vs expected
    d['wk_resid'] = d.wicket - d.ew             # wickets above expected
    return d


def _mean_cluster(g, col):
    y = g[col].to_numpy(float)
    m = g.match_id.to_numpy()
    n = len(y)
    if n < 2 or len(np.unique(m)) < 2:
        return None
    yc = y - y.mean()
    se = np.sqrt(sum(yc[m == k].sum() ** 2 for k in np.unique(m))) / n
    if not np.isfinite(se) or se <= 0:
        return None
    return float(y.mean()), float(se)


def level_table(d, col, min_balls, subset=None):
    """Per-bowler mean of `col` (x100, i.e. per 100 deliveries) with match-
    clustered SE, optionally within a bucket. Bowlers lacking >=2 matches or an
    estimable SE are omitted, never zero-filled."""
    rows = []
    for b, g in d.groupby('bowler'):
        if subset is not None:
            g = g[g.bucket == subset]
        if len(g) < min_balls:
            continue
        r = _mean_cluster(g, col)
        if r is None:
            continue
        rows.append({'Bowler': b, 'slope_raw': 100 * r[0], 'slope_se': 100 * r[1],
                     'deliveries': len(g), 'matches': g.match_id.nunique()})
    return pd.DataFrame(rows, columns=['Bowler', 'slope_raw', 'slope_se', 'deliveries', 'matches'])


def reliability(t):
    """Median model-based shrinkage factor tau2/(tau2+se^2) using the sample's
    DL tau2 and CR0 SEs. A conditional model quantity, NOT a validated reliability
    and not a bound; it disagreed with observed split-half results (e.g. wickets)."""
    s = shrink_slopes(t)
    tau2 = s.attrs['tau2']
    if len(s) == 0:
        return s, None, None
    return s, float(tau2), float(np.median(tau2 / (tau2 + s.slope_se ** 2))) if tau2 > 0 else 0.0


MEASURES = {
    'runs_overall': ('runs_resid', None),
    'runs_pressure_bucket': ('runs_resid', 'pressure'),
    'runs_normal_bucket': ('runs_resid', 'normal'),
    'wickets_overall': ('wk_resid', None),
}


def split_half_levels(d, cfg, min_balls=150, min_bucket=60):
    from scipy.stats import spearmanr
    par = _parity_map(d)
    h = d.match_id.map(par)
    splits = {'alternate_match': (d[h == 0], d[h == 1]),
              'early_vs_late': (d[d.season <= cfg['train_end']], d[d.season >= cfg['test_start']])}
    out = {}
    for sname, (a, b) in splits.items():
        out[sname] = {}
        for m, (col, sub) in MEASURES.items():
            mb = min_bucket if sub else min_balls
            ta = level_table(a, col, mb, sub)
            tb = level_table(b, col, mb, sub)
            j = ta.merge(tb, on='Bowler')
            if len(j) < 5:
                out[sname][m] = {'bowlers': len(j), 'spearman': None}
                continue
            out[sname][m] = {'bowlers': len(j),
                             'spearman': float(spearmanr(j.slope_raw_x, j.slope_raw_y).statistic)}
        # pressure-minus-normal difference, same bowlers, for comparison with the old BPF idea
        pa = level_table(a, 'runs_resid', min_bucket, 'pressure').merge(
            level_table(a, 'runs_resid', min_bucket * 2, 'normal'), on='Bowler')
        pb = level_table(b, 'runs_resid', min_bucket, 'pressure').merge(
            level_table(b, 'runs_resid', min_bucket * 2, 'normal'), on='Bowler')
        da = pd.DataFrame({'Bowler': pa.Bowler, 'x': pa.slope_raw_x - pa.slope_raw_y})
        db = pd.DataFrame({'Bowler': pb.Bowler, 'y': pb.slope_raw_x - pb.slope_raw_y})
        j = da.merge(db, on='Bowler')
        out[sname]['runs_pressure_minus_normal'] = {
            'bowlers': len(j),
            'spearman': float(spearmanr(j.x, j.y).statistic) if len(j) >= 5 else None}
    return out


def run_components(scored, cfg):
    d = add_components(scored)
    minb = cfg['continuous_min_balls_full']
    tabs = {}
    summary = {}
    for m, (col, sub) in MEASURES.items():
        mb = 60 if sub else minb
        t = level_table(d, col, mb, sub)
        s, tau2, rel = reliability(t)
        tabs[m] = s.set_index('Bowler')
        summary[m] = {'bowlers': len(s), 'tau2': tau2, 'median_model_shrinkage_factor': rel,
                      'population_mean_per100': s.attrs['mu']}
    full = pd.concat({m: t[['slope_raw', 'slope_se', 'slope_shrunk', 'CI_low', 'CI_high']]
                      for m, t in tabs.items()}, axis=1)
    full.columns = [f'{a}__{b}' for a, b in full.columns]
    full = full.reset_index()
    w = cfg['wicket_value'] * d.wk_resid
    a = d.runs_resid
    var = {'per_ball_var_runs_part': float(a.var()),
           'per_ball_var_wicket_part': float(w.var()),
           'per_ball_cov_runs_wicket': float(np.cov(a, w)[0, 1]),
           'per_ball_corr_runs_wicket': float(np.corrcoef(a, w)[0, 1]),
           'per_ball_var_total_rae_c': float((a + w).var()),
           'wicket_share_of_total_variance': float(w.var() / (a + w).var()),
           'wicket_share_incl_covariance': float((w.var() + np.cov(a, w)[0, 1]) / (a + w).var()),
           'note': 'observational ball-level decomposition; not a sole-cause or skill statement'}
    val = {'version': 'v3 components (exploratory, descriptive)',
           'units': 'per 100 deliveries: runs prevented vs expected (positive = fewer runs than expected); wickets above expected',
           'measures': summary, 'variance_diagnostic': var,
           'split_half_spearman_of_levels': split_half_levels(d, cfg),
           'caveats': [
               'Descriptive of IPL 2022-26 deliveries only. Not validated for future selection or auction decisions.',
               'Expected-runs/wicket models are frozen from 2022-24 and reused on 2025-26, so 2025-26 is development evidence, not a fresh test.',
               'Boundary-risk buckets (BoPI) measure boundary risk, not competitive pressure.',
               'Cluster-robust SEs may be optimistic: an exploratory 5-repetition shuffle heuristic (diagnostics/diag3.out) gave exclude-0 rates of 8-11% vs nominal 5%; not a defensible coverage test.',
               'median_model_shrinkage_factor is a conditional model quantity, not a validated reliability or bound; it disagreed with split-half results for wickets.',
               'Level is not role-free: bowlers who bowl different overs/teams face different contexts the models only partly capture.',
               'Wicket and runs components are kept separate; no exchange rate is assumed here.',
               'Spearman on small intersecting cohorts is itself noisy (see bowler counts).']}
    return full, val
