"""Continuous pressure response: per-bowler slope of RAE on BoPI, all deliveries.

Bounded revision approved 2026-11-11: replace hard pressure/normal quantile
buckets with a per-bowler continuous response, and credit wickets relative to
expectation (centered wicket term) so easy wicket-taking situations do not
earn automatic extra credit. Slopes are shrunk toward the population mean by
DerSimonian-Laird empirical-Bayes shrinkage using match-clustered standard
errors. Neutral evidence labels only; no psychological claims.
"""
import numpy as np
import pandas as pd

# Exploratory interval labels only. Intervals condition on the estimated
# population mean/tau2 and the frozen fitted models and cutoffs, use a CR0
# cluster sandwich that can understate uncertainty with few matches per bowler,
# and carry no multiple-comparison adjustment across bowlers. An interval
# excluding 0 is NOT a confirmed effect and an interval including 0 is NOT
# proof of no effect.
EVIDENCE_POSITIVE = 'exploratory_interval_above_0'
EVIDENCE_NEGATIVE = 'exploratory_interval_below_0'
EVIDENCE_INSUFFICIENT = 'interval_includes_0'

NOT_ESTIMABLE_CLUSTERS = 'fewer than 2 distinct matches'
NOT_ESTIMABLE_SE = 'zero slope standard error (perfect fit / no cluster variation)'


def add_centered_rae(df, cfg):
    """Centered RAE: expected runs minus charged runs, plus wicket value times
    (actual wickets minus expected wickets). Uses the pipeline's existing ew."""
    d = df.copy()
    d['rae_c'] = d.er - d.charged + cfg['wicket_value'] * (d.wicket - d.ew)
    return d


def _ols_slope_cluster(x, y, clusters):
    """Slope of y on within-bowler centered x, with match-clustered SE.

    Model: y - mean(y) = b * (x - mean(x)) + e. Variance uses the CR0
    cluster sandwich for a single regressor after absorbing both means.
    Returns (slope, se, n). Slope is per 1 BoPI point; caller scales.
    """
    xc = x - x.mean()
    yc = y - y.mean()
    denom = float((xc ** 2).sum())
    if denom < 1e-12:
        return None
    b = float((xc * yc).sum() / denom)
    e = yc - b * xc
    meat = 0.0
    for _, idx in pd.Series(clusters).groupby(clusters).groups.items():
        s = float((xc[idx] * e[idx]).sum())
        meat += s * s
    var = meat / (denom * denom)
    return b, float(np.sqrt(var)), len(x)


def bowler_slopes(df, cfg, min_balls, excluded=None):
    """Raw per-bowler continuous slopes with match-clustered SEs.

    Bowlers without an estimable uncertainty are excluded explicitly (never
    assigned a zero-SE slope): fewer than 2 distinct matches, degenerate
    regressor, or a zero standard error. Exclusions are recorded with reasons
    in the optional `excluded` list.
    """
    rows = []
    for bowler, g in df.groupby('bowler'):
        if len(g) < min_balls:
            continue
        if g.match_id.nunique() < 2:
            if excluded is not None:
                excluded.append({'Bowler': bowler, 'reason': NOT_ESTIMABLE_CLUSTERS,
                                 'deliveries': len(g)})
            continue
        r = _ols_slope_cluster(g.bopi.to_numpy(float), g.rae_c.to_numpy(float),
                               g.match_id.to_numpy())
        if r is None:
            if excluded is not None:
                excluded.append({'Bowler': bowler, 'reason': 'degenerate regressor',
                                 'deliveries': len(g)})
            continue
        b, se, n = r
        if not np.isfinite(se) or se <= 0:
            if excluded is not None:
                excluded.append({'Bowler': bowler, 'reason': NOT_ESTIMABLE_SE,
                                 'deliveries': n})
            continue
        rows.append({'Bowler': bowler, 'slope_raw': 100.0 * b, 'slope_se': 100.0 * se,
                     'deliveries': n, 'matches': g.match_id.nunique()})
    cols = ['Bowler', 'slope_raw', 'slope_se', 'deliveries', 'matches']
    return pd.DataFrame(rows, columns=cols)


def shrink_slopes(slopes):
    """DerSimonian-Laird empirical-Bayes shrinkage toward the precision-
    weighted mean slope. Returns slopes with shrunk estimate, CI and label."""
    t = slopes.copy()
    if len(t) == 0:
        for c in ['slope_shrunk', 'slope_shrunk_se', 'CI_low', 'CI_high']:
            t[c] = np.nan
        t['evidence'] = pd.Series(dtype=object)
        t.attrs['mu'] = np.nan
        t.attrs['tau2'] = np.nan
        return t
    w = 1.0 / t.slope_se.pow(2)
    mu = float((w * t.slope_raw).sum() / w.sum())
    k = len(t)
    q = float((w * (t.slope_raw - mu) ** 2).sum())
    c = float(w.sum() - (w ** 2).sum() / w.sum())
    tau2 = max(0.0, (q - (k - 1)) / c) if c > 0 and k > 1 else 0.0
    if tau2 > 0:
        prec = 1.0 / t.slope_se.pow(2) + 1.0 / tau2
        t['slope_shrunk'] = (t.slope_raw / t.slope_se.pow(2) + mu / tau2) / prec
        t['slope_shrunk_se'] = np.sqrt(1.0 / prec)
    else:
        t['slope_shrunk'] = mu
        t['slope_shrunk_se'] = np.sqrt(1.0 / w.sum())
    t['CI_low'] = t.slope_shrunk - 1.96 * t.slope_shrunk_se
    t['CI_high'] = t.slope_shrunk + 1.96 * t.slope_shrunk_se
    t['evidence'] = EVIDENCE_INSUFFICIENT
    t.loc[t.CI_low > 0, 'evidence'] = EVIDENCE_POSITIVE
    t.loc[t.CI_high < 0, 'evidence'] = EVIDENCE_NEGATIVE
    t.attrs['mu'] = mu
    t.attrs['tau2'] = tau2
    return t


def _parity_map(df):
    order = df[['match_id', 'date']].drop_duplicates().sort_values(['date', 'match_id'])
    return {m: i % 2 for i, m in enumerate(order.match_id)}


def _cohort_rho(a, b):
    from scipy.stats import spearmanr
    j = a[['Bowler', 'slope_shrunk']].merge(
        b[['Bowler', 'slope_shrunk']], on='Bowler').dropna()
    if len(j) < 3:
        return {'rho': None, 'bowlers': len(j),
                'note': 'intersection of per-cohort shrunk slopes; undefined below 3'}
    rho = float(spearmanr(j.slope_shrunk_x, j.slope_shrunk_y).statistic)
    if not np.isfinite(rho):
        rho = None
    return {'rho': rho, 'bowlers': len(j),
            'note': 'intersection of per-cohort shrunk slopes; no selection filter'}


def _cohort_bowlers(a, b):
    return sorted(set(a.Bowler) & set(b.Bowler))


def _matched_bucket_baseline(df, cfg, bowlers):
    """Bucket BPF_adj Spearman between two delivery subsets, restricted to a
    given bowler intersection: a matched-cohort baseline for the slope test,
    using the ORIGINAL bucket method on the same players. Diagnostic only."""
    from bpf import aggregate
    from scipy.stats import spearmanr
    a, b = df
    need = {'bowler', 'bucket', 'legal', 'weight', 'rae', 'season', 'match_id',
            'date', 'team', 'type'}
    if not need <= set(a.columns) or len(bowlers) < 3:
        return {'rho': None, 'bowlers': 0, 'note': 'matched bucket baseline not '
                'estimable (scoring columns absent or fewer than 3 bowlers)'}
    ta = aggregate(a[a.bowler.isin(bowlers)], cfg)[['Bowler', 'BPF_adj']]
    tb = aggregate(b[b.bowler.isin(bowlers)], cfg)[['Bowler', 'BPF_adj']]
    j = ta.merge(tb, on='Bowler').dropna()
    if len(j) < 3:
        return {'rho': None, 'bowlers': len(j),
                'note': 'original bucket BPF_adj on the slope cohort intersection'}
    rho = float(spearmanr(j.BPF_adj_x, j.BPF_adj_y).statistic)
    return {'rho': rho if np.isfinite(rho) else None, 'bowlers': len(j),
            'note': 'original bucket BPF_adj on the slope cohort intersection'}


def stability_continuous(df, cfg):
    """Same stability criteria as the bucket BPF: alternate-match and
    early(<=train_end)/late(>=test_start) Spearman rank correlations of
    shrunk continuous slopes, each cohort estimated independently. Because
    the slope cohorts differ from the original bucket-BPF cohorts, matched-
    cohort bucket baselines are reported beside each slope correlation."""
    min_half = cfg['continuous_min_balls_half']
    par = _parity_map(df)
    d0 = df[df.match_id.map(par) == 0]
    d1 = df[df.match_id.map(par) == 1]
    de = df[df.season <= cfg['train_end']]
    dl = df[df.season >= cfg['test_start']]
    h0 = shrink_slopes(bowler_slopes(d0, cfg, min_half))
    h1 = shrink_slopes(bowler_slopes(d1, cfg, min_half))
    early = shrink_slopes(bowler_slopes(de, cfg, min_half))
    late = shrink_slopes(bowler_slopes(dl, cfg, min_half))
    alt_bowlers = _cohort_bowlers(h0, h1)
    time_bowlers = _cohort_bowlers(early, late)
    return {'alternate_match_slope_rank': _cohort_rho(h0, h1),
            'time_slope_rank': _cohort_rho(early, late),
            'matched_cohort_bucket_bpf_baseline': {
                'alternate_match': _matched_bucket_baseline((d0, d1), cfg, alt_bowlers),
                'time': _matched_bucket_baseline((de, dl), cfg, time_bowlers)},
            'cohorts': {'min_balls_per_cohort': min_half,
                        'half0': len(h0), 'half1': len(h1),
                        'early': len(early), 'late': len(late)}}


def run_continuous(scored, cfg):
    """Full continuous-revision stage on scored deliveries (needs bopi/er/ew)."""
    s = add_centered_rae(scored, cfg)
    excluded = []
    full = shrink_slopes(bowler_slopes(s, cfg, cfg['continuous_min_balls_full'],
                                       excluded))
    val = stability_continuous(s, cfg)
    val.update({'estimator': 'per-bowler OLS slope of rae_c on centered bopi, '
                             'match-clustered SE, DerSimonian-Laird shrinkage',
                'rae_c': 'er - charged + wicket_value*(wicket - ew)',
                'slope_units': 'runs-equivalent per 100 BoPI points',
                'population_mean_slope': full.attrs['mu'],
                'between_bowler_tau2': full.attrs['tau2'],
                'full_cohort_min_balls': cfg['continuous_min_balls_full'],
                'full_cohort_bowlers': len(full),
                'not_estimable': excluded,
                'evidence_counts': full.evidence.value_counts().to_dict(),
                'interval_caveats': [
                    'Intervals condition on the estimated population mean and tau2, '
                    'and on the frozen fitted models and cutoffs; they omit '
                    'model-fitting, cutoff and selection uncertainty.',
                    'CR0 match-cluster sandwich can understate uncertainty for '
                    'bowlers with few matches.',
                    'No multiple-comparison adjustment across bowlers: with ~118 '
                    'exploratory intervals, some will exclude 0 by chance.',
                    'An interval excluding 0 is an exploratory signal, not a '
                    'confirmed effect; an interval including 0 is not proof of '
                    'no effect.'],
                'comparison_note': 'Slope cohorts (min 150 balls/half) differ from '
                                   'the original bucket-BPF correlation cohorts; '
                                   'use matched_cohort_bucket_bpf_baseline for a '
                                   'same-player comparison, never the original '
                                   'headline correlations.',
                'holdout_note': '2025-26 had already been evaluated; this stage '
                                'reuses it as development evidence, not fresh validation.'})
    return full, val
