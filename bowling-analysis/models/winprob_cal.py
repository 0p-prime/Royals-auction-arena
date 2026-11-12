"""v5: isotonic calibration of the chase score pb, with leave-one-season-out training pairs.

The v4 chase dynamic programme gives an ORDINAL score pb: monotone in runs needed but with
wicket/ball monotonicity violations in about 2% of cells, and miscalibrated (chases from low pb
states were won far more often than pb says). v5 keeps the DP as the state score and adds a
1-D isotonic calibration layer mapping pb -> P(chase win), fitted per fold on EARLIER seasons only.

CHRONOLOGY (calibration pairs): for the fold that scores season Y, the calibrator is fitted on the
same historical span as that fold's DP tables (seasons warmup..Y-1 for Y <= train_end; warmup..train_end
for later seasons). Inside that span each season's pb values are computed leave-one-season-out (tables
from the other in-span seasons), so no season's outcomes calibrate its own in-sample pb. These pairs use
matches played BEFORE the scored season; a scored match never informs its own pb or its own calibration.
Tied chases (final runs exactly target - 1) are excluded from calibration pairs.

Limits: ball rows within a match are correlated; isotonic makes pb_cal monotone in pb, but the underlying
DP violations in the raw (balls, wickets) dimensions remain; chase win rates differ by period and a pooled
historical mapping cannot remove year shift; pb_cal is a better-calibrated model score, still not a
guaranteed probability.
"""
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from winprob import outcome_tables, solve, pbat


def chase_outcomes(df):
    """match_id -> 1.0 chase won, 0.0 chase lost, NaN tie (final runs == target - 1)."""
    d = df[df.innings == 2].sort_values(['match_id', 'sequence'])
    fin = d.groupby('match_id').agg(final_runs=('total', 'sum'), target=('target', 'first'))
    lab = pd.Series(np.nan, index=fin.index, name='chase_won')
    lab[fin.final_runs >= fin.target] = 1.0
    lab[fin.final_runs <= fin.target - 2] = 0.0
    return lab


def fold_spans(cfg):
    """{scored_season: training span} following the project chronology rule."""
    te, w = cfg['train_end'], cfg['warmup_year']
    return {y: (list(range(w, y)) if y <= te else list(range(w, te + 1)))
            for y in sorted(set(cfg['years']))}


def _pre_ball_chase_frame(train_df):
    d = train_df[train_df.innings == 2].sort_values(['match_id', 'innings', 'sequence']).copy()
    d['pre_runs'] = d.groupby(['match_id', 'innings']).total.cumsum() - d.total
    return d


def loso_pairs_chase(train_df, seasons, cfg):
    """(pb, chase_won, season, excluded_season) pairs for calibration training.
    For each season s in `seasons`, pb uses tables from `seasons` without s."""
    wp = cfg['v4']['winprob']
    d = _pre_ball_chase_frame(train_df)
    lab = chase_outcomes(train_df)
    rows = []
    for s in seasons:
        others = [x for x in seasons if x != s]
        if not others:
            continue
        V = solve(outcome_tables(train_df, others, wp), wp)
        sub = d[d.season == s]
        pb = pbat(V, (sub.target - sub.pre_runs), 120 - sub.pre_balls, sub.wickets_lost)
        rows.append(pd.DataFrame({'season': s, 'excluded_season': s, 'pb': np.asarray(pb),
                                  'chase_won': sub.match_id.map(lab).to_numpy()}))
    out = pd.concat(rows, ignore_index=True).dropna(subset=['chase_won'])
    return out


def fit_isotonic(pb, y):
    iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds='clip')
    iso.fit(np.asarray(pb, float), np.asarray(y, float))
    return iso


def calibrators_chase(train_df, cfg):
    """{scored_season: {'iso': IsotonicRegression, 'train_seasons': span, 'pairs': n}}."""
    cals = {}
    for y, span in fold_spans(cfg).items():
        pairs = loso_pairs_chase(train_df, span, cfg)
        cals[y] = {'iso': fit_isotonic(pairs.pb, pairs.chase_won), 'train_seasons': span,
                   'pairs': int(len(pairs))}
    return cals


def add_pb_cal(d, cfg, train_df=None, cals=None):
    """Add pb (raw DP, as v4) and pb_cal (isotonic-calibrated) to scored deliveries."""
    from pressure_v4 import add_pb
    if 'pb' not in d.columns:
        d = add_pb(d, cfg, train_df=train_df)
    if cals is None:
        if train_df is None:
            from pressure_v4 import training_deliveries
            train_df = training_deliveries(cfg)
        cals = calibrators_chase(train_df, cfg)
    d = d.copy()
    d['pb_cal'] = np.nan
    for y, c in cals.items():
        m = (d.innings == 2) & (d.season == y)
        if m.any():
            d.loc[m, 'pb_cal'] = c['iso'].predict(d.loc[m, 'pb'].to_numpy(float))
    return d, cals
