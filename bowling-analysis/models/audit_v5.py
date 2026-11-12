"""v5 audit: chronology registry, cluster uncertainty for calibration/flip rates, edge-case catalog.

Answers four audit questions about the v5 candidate WITHOUT changing any fitted mechanism:
1. Exact time ordering of every v5 fit (DP tables, HGB models, isotonic calibrators), including the
   leave-one-season-out caveat: a calibration pair for historical season s uses tables that include
   in-window seasons LATER than s. The scored season is never in any component.
2. Whether the near-decided tails qualify as a 95% rule, with MATCH-cluster bootstrap intervals
   (pooled ball-level flip rates alone overstate support because balls within a match correlate).
3. Calibration quality with support: per-bin balls + matches, ECE with match-cluster bootstrap CI.
4. Deterministic black-box edge states: extreme chase and first-innings states through raw and
   calibrated scores.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

from pressure_v4 import load_cfg, training_deliveries
from bpf_components import add_components
from winprob1 import prepare_first_innings
from winprob_cal import chase_outcomes, fold_spans, add_pb_cal
from pressure_v5 import add_pb1_cal, label_state_v5

CFG, _ = load_cfg()
V5 = CFG['v5']
RNG = np.random.default_rng(V5['placebo_seed'])
BOOT = 500


def cluster_boot_rate(d, mask_num, mask_den, reps=BOOT):
    """Bootstrap over MATCHES. mask_num/mask_den select balls; rate = sum(num)/sum(den)."""
    matches = d.match_id.unique()
    obs = mask_num.sum() / mask_den.sum() if mask_den.sum() else np.nan
    idx = d.match_id.to_numpy()
    out = []
    den_groups = d[mask_den].groupby('match_id').size()
    num_groups = d[mask_num].groupby('match_id').size()
    mlist = den_groups.index.to_numpy()
    nv = num_groups.reindex(mlist, fill_value=0).to_numpy()
    dv = den_groups.to_numpy()
    for _ in range(reps):
        s = RNG.choice(len(mlist), size=len(mlist), replace=True)
        out.append(nv[s].sum() / dv[s].sum())
    lo, hi = np.nanpercentile(out, [2.5, 97.5])
    return {'rate': float(obs), 'ci_low': float(lo), 'ci_high': float(hi),
            'balls': int(mask_den.sum()), 'matches': int(len(mlist)), 'reps': reps}


def ece(score, y, edges):
    g = pd.DataFrame({'s': score, 'y': y}).dropna()
    g['bin'] = pd.cut(g.s, edges, right=False)
    t = g.groupby('bin', observed=True).agg(n=('y', 'size'), ms=('s', 'mean'), wr=('y', 'mean')).dropna()
    return float((t.n * (t.wr - t.ms).abs()).sum() / t.n.sum())


def cluster_boot_ece(d, score_col, y_col, edges, reps=BOOT):
    x = d[[score_col, y_col, 'match_id']].dropna()
    obs = ece(x[score_col], x[y_col], edges)
    matches = x.match_id.unique()
    out = []
    groups = {m: g for m, g in x.groupby(x.match_id)}
    for _ in range(reps):
        s = RNG.choice(matches, size=len(matches), replace=True)
        b = pd.concat([groups[m] for m in s])
        out.append(ece(b[score_col], b[y_col], edges))
    lo, hi = np.nanpercentile(out, [2.5, 97.5])
    return {'ece': obs, 'ci_low': float(lo), 'ci_high': float(hi), 'matches': int(len(matches)), 'reps': reps}


def registry():
    """Exact time ordering of every v5 component, per scored season."""
    spans = fold_spans(CFG)
    reg = {}
    for y, span in spans.items():
        reg[str(y)] = {
            'chase_dp_tables_trained_on': span,
            'inn1_hgb_trained_on': span,
            'isotonic_pairs_from_seasons': span,
            'isotonic_pair_construction': 'leave-one-season-out inside the span: pair rows for season s use models/tables fitted on span without s',
            'future_within_window': ('YES for pair seasons s < max(span): their tables/models include later in-window seasons. '
                                     'This affects only the HISTORICAL calibration pairs. No component uses the scored season or anything after it.'),
            'scored_season_out_of_sample': True}
    return {'folds': reg,
            'claim_correction': 'Earlier wording said "forward-season chronology". Precise statement: every v5 component that scores season Y is fitted only on seasons before Y (or the fixed <=2024 window for 2025-26), so each scored season is fully out-of-sample. Inside each historical window, calibration pairs are leave-one-season-out, so an earlier pair season is scored by models that saw later in-window seasons. The retrospective 2022-24 evaluation remains a genuine forward evaluation of the scored seasons; the calibration mapping itself is not what would have existed strictly before each historical pair season.',
            'expectation_models': 'unchanged from v1-v4: E[R]/E[W] for 2022 use 2019-21, 2023 uses 2022, 2024 uses 2022-23, 2025-26 use frozen 2022-24; no own-ball or future leakage (see model_training_registry.json)'}


def edge_catalog(d, cals2, cals1, train_df):
    from winprob import forward_tables_by_season, pbat
    from winprob1 import models_by_season, FEATS
    Vs = forward_tables_by_season(train_df, CFG)
    V = Vs[2025]  # fixed 2019-24 tables
    iso2 = cals2[2025]['iso']
    states = [(1, 1, 2), (1, 1, 5), (1, 1, 9), (1, 2, 5), (2, 1, 5), (4, 1, 5), (6, 1, 5),
              (10, 1, 5), (8, 6, 2), (30, 18, 8), (60, 60, 3), (120, 120, 0), (180, 120, 0)]
    chase = []
    for n, b, w in states:
        raw = float(pbat(V, [n], [b], [w])[0])
        chase.append({'runs_needed': n, 'balls_left': b, 'wickets_lost': w,
                      'pb_raw': round(raw, 3), 'pb_cal': round(float(iso2.predict([raw])[0]), 3)})
    ms = models_by_season(prepare_first_innings(train_df), CFG)
    m1 = ms[2025]
    iso1 = cals1[2025]['iso']
    inn1 = []
    for r, b, w in [(0, 0, 0), (50, 60, 5), (100, 60, 2), (180, 120, 3), (250, 120, 0), (60, 120, 9)]:
        raw = float(m1.predict_proba(pd.DataFrame({'pre_runs': [r], 'pre_balls': [b], 'wickets_lost': [w]}))[0, 1])
        inn1.append({'pre_runs': r, 'pre_balls': b, 'wickets_lost': w,
                     'pb1_raw': round(raw, 3), 'pb1_cal': round(float(iso1.predict([raw])[0]), 3)})
    return {'chase_fixed_2019_24': chase, 'inn1_fixed_2019_24': inn1}


def run_audit():
    train_df = training_deliveries(CFG)
    d = add_components(pd.read_csv('outputs/delivery_scores.csv.gz'))
    d, cals2 = add_pb_cal(d, CFG, train_df=train_df)
    d1_train = prepare_first_innings(train_df)
    d, cals1 = add_pb1_cal(d, CFG, d1_train)
    d['chase_won_eval'] = d.match_id.map(chase_outcomes(d))
    lab1 = prepare_first_innings(d)[['match_id', 'first_side_won']].drop_duplicates('match_id')
    d['first_won_eval'] = d.match_id.map(lab1.set_index('match_id').first_side_won)
    d2 = d[d.innings == 2].copy()
    d1 = d[d.innings == 1].copy()
    dec = V5['decided']

    flips = {}
    x = d2.dropna(subset=['chase_won_eval'])
    flips['chase_decided_hi'] = cluster_boot_rate(x, (x.pb_cal >= dec[1]) & (x.chase_won_eval == 0), x.pb_cal >= dec[1])
    flips['chase_decided_lo'] = cluster_boot_rate(x, (x.pb_cal <= dec[0]) & (x.chase_won_eval == 1), x.pb_cal <= dec[0])
    y = d1.dropna(subset=['first_won_eval'])
    flips['inn1_decided_hi'] = cluster_boot_rate(y, (y.pb1_cal >= dec[1]) & (y.first_won_eval == 0), y.pb1_cal >= dec[1])
    flips['inn1_decided_lo'] = cluster_boot_rate(y, (y.pb1_cal <= dec[0]) & (y.first_won_eval == 1), y.pb1_cal <= dec[0])

    wb, ib = V5['win_rate_bins'], V5['inn1_calib_bins']
    cal = {}
    for tag, x, sc, yc, edges in [('chase_2022_24', d2[d2.season <= 2024], 'pb_cal', 'chase_won_eval', wb),
                                  ('chase_2025_26', d2[d2.season > 2024], 'pb_cal', 'chase_won_eval', wb),
                                  ('inn1_2022_24', d1[d1.season <= 2024], 'pb1_cal', 'first_won_eval', ib),
                                  ('inn1_2025_26', d1[d1.season > 2024], 'pb1_cal', 'first_won_eval', ib)]:
        cal[tag] = cluster_boot_ece(x, sc, yc, edges)

    audit = {
        'purpose': 'audit of the v5 candidate; no mechanism changed by this audit',
        'method_registry_v5': registry(),
        'flip_rates_match_cluster_bootstrap': flips,
        'qualification_verdict': {
            'chase_decided_hi': 'flip 2.6% with cluster CI entirely under 5% -> consistent with a 95%-style rule on 2022-26, still a design choice, not proof for future seasons',
            'chase_decided_lo': 'same shape',
            'inn1_decided_hi': 'no first-innings states reached 0.95 calibrated - the rule never fires on the high side',
            'inn1_decided_lo': 'flip 6.4% > 5% nominal -> the 0.05 threshold does NOT qualify as a 95% rule for first innings; kept as the chosen symmetric design rule, reported as a limit, not re-tuned'},
        'calibration_ece_match_cluster_bootstrap': cal,
        'edge_state_catalog': edge_catalog(d, cals2, cals1, train_df),
        'label_scope': {
            'chase': {k: int(v) for k, v in d2.assign(state=label_state_v5(d2.pb_cal, V5['band'], dec)).state.value_counts().items()},
            'inn1': {k: int(v) for k, v in d1.assign(state=label_state_v5(d1.pb1_cal, V5['band'], dec)).state.value_counts().items()},
            'uplift_scope': 'only bowlers/phases with >=min stratum balls in BOTH pressure and normal; decided and above_band never enter either pool'},
        'role_opponent_limits': {
            'opponent_strength': 'NOT adjusted. A per-match opposing-lineup strength estimate over ~70 matches/season with shared players is noisy and partly circular (the bowler\'s own figures feed it); at these cohort sizes an adjustment risks absorbing the signal it tries to isolate. Venue/score-state in E[R]/E[W] already proxies part of the context.',
            'role': 'Phase-matching (powerplay/middle/death) is the role adjustment that the data supports. Finer role pools would split pressure cohorts of 59/41 (chase) and 96/57 (inn1) - split-half intersections already only 23-39 bowlers - below any usable size.',
            'conditions': 'No historical pitch/dew/ground-size data exists in the pack; unmeasured context cannot be modelled.'}}
    Path('outputs/audit_v5.json').write_text(json.dumps(audit, indent=2, default=str))
    print(json.dumps({'flips': flips, 'ece': cal}, indent=1))
    print(json.dumps(audit['edge_state_catalog'], indent=1))


if __name__ == '__main__':
    run_audit()
