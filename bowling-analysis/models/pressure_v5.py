"""Version 5 (research candidate): calibrated pressure score + symmetric near-decided exclusion.

What v5 changes vs v4 (everything else - expectation models, residuals, shrinkage, phase-matched
uplift regression, wicket-value rank aggregation, floors - is unchanged):

1. CALIBRATED STATE SCORE. The chase DP score pb and the first-innings HGB score pb1 each get a
   1-D isotonic calibration layer fitted per fold on earlier seasons only, with leave-one-season-out
   pairs inside each training span (winprob_cal.py for the chase; this module for the first innings).
   pb_cal / pb1_cal are better-calibrated model scores; residual limits are documented, not hidden.

2. BOTH-TAIL NEAR-DECIDED EXCLUSION (the v4 gap this version exists to close). On the CALIBRATED
   scale, states with score >= decided_hi OR <= decided_lo are labelled 'decided' and removed from
   BOTH the pressure and the normal pools, for BOTH innings. Default 0.05/0.95: on a calibrated scale
   these are states where one side wins about 19 times in 20. This is a DESIGN CHOICE on a model
   scale, not a proven "match is over" rule - observed flip rates from these states are reported in
   validation_v5.json, and an alternate 0.10/0.90 rule is run as sensitivity.

3. The pressure band stays [0.6, 0.9) on the calibrated scale (continuity with v4; still a design
   choice), with the [0.7, 0.95) alternate reported. Because the scale is now calibrated, band edges
   are approximate batting-side win probabilities rather than purely ordinal cut points.

What v5 does NOT change: pb and pb1 are still not on one common scale (separate innings lists, never
merged); the expectation models E[R]/E[W] still use venue while the pressure scores use only
score/balls/wickets (venue excluded from pressure features per project decision); 2025-26 was used
in development, so all results are retrospective descriptions of 2022-26, not a fresh validation;
no role/opponent-strength adjustment is added (documented limitation, not silently modelled).
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from pressure_v4 import (load_cfg, training_deliveries, combine, shrunk, uplift_table,
                         split_half, add_pb)
from bpf_components import add_components, level_table
from winprob1 import prepare_first_innings, fit_model, FEATS
from winprob_cal import chase_outcomes, fold_spans, loso_pairs_chase, fit_isotonic, add_pb_cal


# ---------------- first-innings calibration ----------------

def loso_pairs_inn1(d1, seasons, cfg):
    """(pb1, first_side_won, season, excluded_season) pairs; season s scored by a model fit without s."""
    rows = []
    for s in seasons:
        others = [x for x in seasons if x != s]
        if not others:
            continue
        m = fit_model(d1, others, cfg)
        sub = d1[d1.season == s]
        pb1 = m.predict_proba(sub[FEATS])[:, 1]
        rows.append(pd.DataFrame({'season': s, 'excluded_season': s, 'pb1': pb1,
                                  'first_side_won': sub.first_side_won.to_numpy(float)}))
    return pd.concat(rows, ignore_index=True)


def calibrators_inn1(d1, cfg):
    """{scored_season: {'iso', 'train_seasons', 'pairs'}} for the first-innings score."""
    cals = {}
    for y, span in fold_spans(cfg).items():
        pairs = loso_pairs_inn1(d1, span, cfg)
        cals[y] = {'iso': fit_isotonic(pairs.pb1, pairs.first_side_won), 'train_seasons': span,
                   'pairs': int(len(pairs))}
    return cals


def add_pb1_cal(d, cfg, d1_train):
    """Add pb1 (raw HGB, as v4) and pb1_cal (isotonic-calibrated) to first-innings rows."""
    from winprob1 import add_pb1
    if 'pb1' not in d.columns:
        d = add_pb1(d, cfg, d1_train)
    cals = calibrators_inn1(d1_train, cfg)
    d = d.copy()
    d['pb1_cal'] = np.nan
    for y, c in cals.items():
        m = (d.innings == 1) & (d.season == y)
        if m.any():
            d.loc[m, 'pb1_cal'] = c['iso'].predict(d.loc[m, 'pb1'].to_numpy(float))
    return d, cals


# ---------------- v5 state labels ----------------

def label_state_v5(score, band, decided):
    """normal / pressure / above_band / decided from a calibrated score.
    decided: score <= decided[0] or >= decided[1] - removed from BOTH pools (both-tail rule).
    pressure: band[0] <= score < band[1]; above_band: band[1] <= score < decided[1] (excluded);
    normal: decided[0] < score < band[0]."""
    s = pd.Series('normal', index=score.index)
    s[(score >= band[0]) & (score < band[1])] = 'pressure'
    s[(score >= band[1]) & (score < decided[1])] = 'above_band'
    s[(score <= decided[0]) | (score >= decided[1])] = 'decided'
    return s


def _compat(v5, floors):
    """Dict with the keys the v4 helpers (lists1 / split_half) expect."""
    return {'wicket_values': v5['wicket_values'],
            'split_min_overall_balls': v5['split_min_overall_balls'],
            'split_min_pressure_balls': v5['split_min_pressure_balls'],
            'split_min_uplift_pressure': v5['split_min_uplift_pressure'],
            'split_min_uplift_normal': v5['split_min_uplift_normal'],
            'min_stratum_balls': v5['min_stratum_balls'],
            'inn1': floors}


def lists_innings(di, v5, floors):
    """Pressure-level and uplift lists for one innings frame with a 'state' column."""
    vals = v5['wicket_values']
    dp = di[di.state == 'pressure']
    out = {'pressure': combine(shrunk(level_table(dp, 'runs_resid', floors['min_pressure_balls'])),
                               shrunk(level_table(dp, 'wk_resid', floors['min_pressure_balls'])), vals)}
    args = (floors['min_pressure_balls'], floors['min_normal_balls_uplift'],
            floors['min_stratum_balls'], floors['min_matches_uplift'])
    ur, uw = uplift_table(di, 'runs_resid', *args), uplift_table(di, 'wk_resid', *args)
    u = combine(shrunk(ur), shrunk(uw), vals)
    out['uplift'] = u.join(ur.set_index('Bowler')[['pressure_balls', 'normal_balls', 'phases_used']])
    return out


def overall_list(d, v5):
    vals = v5['wicket_values']
    return combine(shrunk(level_table(d, 'runs_resid', v5['min_overall_balls'])),
                   shrunk(level_table(d, 'wk_resid', v5['min_overall_balls'])), vals)


# ---------------- evaluation helpers ----------------

def _brier(score, y):
    return float(((score - y) ** 2).mean())


def _bins(score, y, edges, per_match):
    g = pd.DataFrame({'s': score, 'y': y, 'm': per_match})
    g['bin'] = pd.cut(g.s, edges, right=False)
    t = g.groupby('bin', observed=True).agg(balls=('y', 'size'), mean_score=('s', 'mean'),
                                            win_rate=('y', 'mean'), matches=('m', 'nunique')).round(3)
    return {str(k): {a: (float(b) if pd.notna(b) else None) for a, b in r.items()}
            for k, r in t.iterrows()}


def calib_eval(d, score_raw, score_cal, y, edges, mask, name):
    x = d[mask]
    out = {}
    for label, m in [('seasons_2022_24_forward_retrospective', x.season <= 2024),
                     ('seasons_2025_26_fixed_reused_development', x.season > 2024)]:
        z = x[m].dropna(subset=[y])
        out[label] = {
            f'brier_{name}_raw': _brier(z[score_raw], z[y]),
            f'brier_{name}_calibrated': _brier(z[score_cal], z[y]),
            'bins_calibrated': _bins(z[score_cal], z[y], edges, z.match_id)}
    return out


def flip_rates(d, score, y, decided, mask):
    """Observed outcome rates in the decided tails: how often the 'near-certain' side still loses."""
    x = d[mask].dropna(subset=[y])
    hi = x[x[score] >= decided[1]]
    lo = x[x[score] <= decided[0]]
    return {'decided_hi_share_of_balls': float(len(hi) / len(x)) if len(x) else None,
            'decided_hi_favoured_side_lost': float(1 - hi[y].mean()) if len(hi) else None,
            'decided_hi_balls': int(len(hi)),
            'decided_lo_share_of_balls': float(len(lo) / len(x)) if len(x) else None,
            'decided_lo_favoured_side_lost': float(lo[y].mean()) if len(lo) else None,
            'decided_lo_balls': int(len(lo))}


def _sens(primary, alt, top_n):
    out = {}
    for lst in ['pressure', 'uplift']:
        a, b = primary[lst], alt[lst]
        j = a[['rank_median']].join(b[['rank_median']], how='inner', lsuffix='_p', rsuffix='_v')
        out[lst] = {'bowlers_both': len(j),
                    'spearman_rank_median': float(j.corr(method='spearman').iloc[0, 1]) if len(j) > 4 else None,
                    'top_n_overlap': len(set(a.head(top_n).index) & set(b.head(top_n).index))}
    return out


def placebo_uplift(d, v5, floors, seed):
    """Shuffle pressure/normal labels within bowler x phase (chase frame, v5 states), recompute
    shrunk runs-uplift spread. Same design as placebo_v4."""
    args = (floors['min_pressure_balls'], floors['min_normal_balls_uplift'],
            floors['min_stratum_balls'], floors['min_matches_uplift'])
    def stats(x):
        s = shrunk(uplift_table(x, 'runs_resid', *args))
        return dict(n=len(s), sd_shrunk=float(s.slope_shrunk.std()), max_shrunk=float(s.slope_shrunk.max()))
    real = stats(d)
    rng = np.random.default_rng(seed)
    out = []
    m = d.state.isin(['pressure', 'normal'])
    for _ in range(v5['placebo_reps']):
        x = d.copy()
        idx = x.index[m]
        sub = x.loc[idx, ['bowler', 'phase', 'state']].copy()
        sub['state'] = sub.groupby(['bowler', 'phase']).state.transform(lambda s: rng.permutation(s.values))
        x.loc[idx, 'state'] = sub.state
        out.append(stats(x))
    o = pd.DataFrame(out)
    return {'reps': v5['placebo_reps'], 'real': real,
            'placebo_sd_shrunk_quantiles': o.sd_shrunk.quantile([0, .5, .9, 1]).to_dict(),
            'placebo_max_shrunk_quantiles': o.max_shrunk.quantile([0, .5, .9, 1]).to_dict(),
            'real_sd_percentile_in_placebo': float((o.sd_shrunk < real['sd_shrunk']).mean()),
            'note': 'shuffles labels within bowler x phase; exploratory'}


# ---------------- main pipeline ----------------

def run_v5(scored, cfg, v5):
    train_df = training_deliveries(cfg)
    d = add_components(scored)
    d, cals2 = add_pb_cal(d, cfg, train_df=train_df)
    d1_train = prepare_first_innings(train_df)
    d, cals1 = add_pb1_cal(d, cfg, d1_train)

    band, band_alt = v5['band'], v5['band_alt']
    dec, dec_alt = v5['decided'], v5['decided_alt']
    chase_f, inn1_f = v5['chase'], v5['inn1']

    # outcome columns for EVALUATION ONLY (never used to label states)
    ch_won = chase_outcomes(d)
    d['chase_won_eval'] = d.match_id.map(ch_won)
    lab1 = prepare_first_innings(d)[['match_id', 'first_side_won']].drop_duplicates('match_id')
    d['first_won_eval'] = d.match_id.map(lab1.set_index('match_id').first_side_won)

    d2 = d[d.innings == 2].copy()
    d1 = d[d.innings == 1].copy()

    res = {'chase': {}, 'inn1': {}}
    for tag, b, dc in [('primary', band, dec), ('alt_band', band_alt, dec), ('alt_decided', band, dec_alt)]:
        d2['state'] = label_state_v5(d2.pb_cal, b, dc)
        res['chase'][tag] = lists_innings(d2, v5, chase_f)
        d1['state'] = label_state_v5(d1.pb1_cal, b, dc)
        res['inn1'][tag] = lists_innings(d1, v5, inn1_f)

    overall = overall_list(d, v5)

    # primary states restored for split-half + placebo
    d2['state'] = label_state_v5(d2.pb_cal, band, dec)
    d1['state'] = label_state_v5(d1.pb1_cal, band, dec)
    compat_ch = _compat(v5, chase_f)
    compat_i1 = _compat(v5, inn1_f)
    d_full = d.copy()
    d_full['state'] = 'not_applicable'
    d_full.loc[d2.index, 'state'] = d2.state
    splits_full = split_half(d_full, cfg, compat_ch)   # overall list stability uses ALL balls (both innings)
    splits = {'overall_list_all_balls': {s: {k: r for k, r in v.items() if k.startswith('overall')}
                                         for s, v in splits_full.items()},
              'chase': split_half(d2, cfg, compat_ch), 'inn1': split_half(d1, cfg, compat_i1)}

    wb = v5['win_rate_bins']
    ib = v5['inn1_calib_bins']
    val = {
        'version': 'v5 calibrated batting-advantage pressure with symmetric near-decided exclusion (research candidate)',
        'changes_from_v4': [
            'isotonic calibration layer on pb and pb1 (leave-one-season-out pairs inside each forward fold)',
            'both-tail near-decided exclusion on the calibrated scale, removed from BOTH pressure and normal pools, both innings',
            'isotonic calibration reduces average historical error (ECE about 0.04 on 2022-24 under match-cluster bootstrap; about 0.11-0.12 on the shifted 2025-26); band edges remain model-defined design choices with sensitivity, NOT verified probabilities'],
        'band_primary': band, 'band_alt': band_alt, 'decided_primary': dec, 'decided_alt': dec_alt,
        'decided_rule': 'calibrated score >= hi or <= lo -> "decided", excluded from BOTH pressure and normal pools; 0.05/0.95 primary, 0.10/0.90 sensitivity; a design choice, NOT a validated 95% rule: observed flip rates with match-cluster bootstrap CIs (audit_v5.json) are chase 2.6% [0-7.3%] hi / 3.2% [1.4-5.3%] lo, first innings 6.4% [0-18.6%] lo on 23 matches; the first-innings high side never fires',
        'calibration_training': 'per fold, leave-one-season-out pairs inside the historical span (a scored season never informs its own score or calibrator); ties excluded',
        'calibration_pairs': {'chase': {str(y): c['pairs'] for y, c in cals2.items()},
                              'inn1': {str(y): c['pairs'] for y, c in cals1.items()}},
        'chase_calibration': calib_eval(d2, 'pb', 'pb_cal', 'chase_won_eval', wb,
                                        d2.chase_won_eval.notna(), 'pb'),
        'inn1_calibration': calib_eval(d1, 'pb1', 'pb1_cal', 'first_won_eval', ib,
                                       d1.first_won_eval.notna(), 'pb1'),
        'chase_flip_rates_primary': flip_rates(d2, 'pb_cal', 'chase_won_eval', dec, d2.chase_won_eval.notna()),
        'inn1_flip_rates_primary': flip_rates(d1, 'pb1_cal', 'first_won_eval', dec, d1.first_won_eval.notna()),
        'scope_counts_primary': {
            'chase': {k: int(x) for k, x in d2.state.value_counts().items()},
            'inn1': {k: int(x) for k, x in d1.state.value_counts().items()}},
        'bowlers_ranked': {'overall': len(overall),
                           'chase': {k: len(v) for k, v in res['chase']['primary'].items()},
                           'inn1': {k: len(v) for k, v in res['inn1']['primary'].items()}},
        'split_half_spearman_primary': splits,
        'sensitivity_alt_band': {'chase': _sens(res['chase']['primary'], res['chase']['alt_band'], v5['top_n']),
                                 'inn1': _sens(res['inn1']['primary'], res['inn1']['alt_band'], v5['top_n'])},
        'sensitivity_alt_decided': {'chase': _sens(res['chase']['primary'], res['chase']['alt_decided'], v5['top_n']),
                                    'inn1': _sens(res['inn1']['primary'], res['inn1']['alt_decided'], v5['top_n'])},
        'placebo_chase_uplift_runs': placebo_uplift(d2, v5, chase_f, v5['placebo_seed']),
        'caveats': [
            'Research candidate. Only the construct (batting side strongly placed, bowler must stop or recover) and the three outputs are confirmed by the project owner; the measurement is not approved as final truth.',
            'Retrospective description of IPL 2022-26. 2025-26 was reused during development of earlier versions, so it is NOT a fresh holdout; no resplit of seen data is presented as one.',
            'pb_cal/pb1_cal are better-calibrated MODEL scores, not guaranteed probabilities: ball rows within a match are correlated, chase win rates shift by period, and the first-innings score has no venue/pitch/dew/team-strength input.',
            'The decided rule is a design choice on the model scale. Match-cluster bootstrap CIs on the flip rates include 5% in every tail, and the first-innings low tail flips more often than nominal on few matches - it is not a validated 95% rule anywhere; see outputs/audit_v5.json.',
            'The pressure band [0.6, 0.9) remains a design choice; alternate band and alternate decided thresholds are reported as sensitivity.',
            'Underlying chase DP still has wicket/ball monotonicity violations in about 2% of cells in the raw state dimensions; isotonic makes the calibrated score monotone in pb only.',
            'Uplift compares each bowler only within phases with both pressure and normal balls; no phase extrapolation; role and opponent strength are NOT adjusted for.',
            'Runs and wickets are shrunk separately and combined at five wicket values; order = median rank, mean rank, name. The runs-wickets trade-off is aggregated, not removed. Wicket residuals did not repeat in earlier versions; the combined ranking is not validated.',
            'Intervals condition on frozen models, mu/tau2 and the chosen bands; no model-fitting, band or selection uncertainty; no multiple-comparison adjustment across bowlers.',
            'Rates are per 100 delivery ATTEMPTS (wides and no-balls count), not per legal ball or per over.',
            'Venue: excluded from the pressure scores (project decision); still used by the E[R]/E[W] expectation models that produce the residuals.',
            'No availability/retention/eligibility filter; Team is the latest observed IPL team.']}
    return overall, res, val, d


if __name__ == '__main__':
    cfg, _ = load_cfg()
    v5 = cfg['v5']
    s = pd.read_csv('outputs/delivery_scores.csv.gz')
    overall, res, val, d = run_v5(s, cfg, v5)
    meta = pd.read_csv('outputs/all_bowlers.csv')[['Bowler', 'Team', 'Type']].drop_duplicates('Bowler').set_index('Bowler')
    overall.join(meta, how='left').reset_index().to_csv('outputs/v5_list_overall.csv', index=False)
    for inn in ['chase', 'inn1']:
        for lst, t in res[inn]['primary'].items():
            t.join(meta, how='left').reset_index().to_csv(f'outputs/v5_{inn}_list_{lst}.csv', index=False)
        for var in ['alt_band', 'alt_decided']:
            for lst, t in res[inn][var].items():
                t.reset_index().to_csv(f'outputs/v5_{inn}_sens_{var}_{lst}.csv', index=False)
    Path('outputs/validation_v5.json').write_text(json.dumps(val, indent=2, default=str))
    print(json.dumps({'bowlers_ranked': val['bowlers_ranked'],
                      'scope_counts_primary': val['scope_counts_primary'],
                      'chase_flip_rates_primary': val['chase_flip_rates_primary'],
                      'inn1_flip_rates_primary': val['inn1_flip_rates_primary']}, indent=1))
    print(json.dumps(val['split_half_spearman_primary'], indent=1))
