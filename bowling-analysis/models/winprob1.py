"""First-innings batting-side advantage score pb1 from the MATCH SITUATION only (no venue, no player identity).

pb1 = model-estimated P(the side batting first goes on to win the match) given pre-ball runs scored,
legal balls bowled and wickets lost. Same construct as the second-innings pb (batting side strongly
placed, bowler needs to stop them or bring it back), but a DIFFERENT estimator: second innings uses an
exact chase dynamic programme; first innings has no target, so it uses a small monotone gradient-boosted
classifier trained on earlier first-innings deliveries labelled with the eventual match result.
So pb1 and pb are NOT on a common calibrated scale; they are never merged into one list here.

TRAINING FIELDS (earlier seasons only): pre_runs, pre_balls (legal), wickets_lost per first-innings delivery;
label = first-batting side won (ties and no-result excluded). INFERENCE FIELDS: the same three, pre-ball.
CHRONOLOGY: as winprob.py: season Y <= train_end uses seasons warmup..Y-1; later seasons one fixed model
fit on warmup..train_end. No match informs its own pb1. Hyper-parameters are fixed in config (v4.inn1),
chosen before looking at results; no grid.
Limits: monotone constraints force more runs -> higher pb1, more wickets lost -> lower pb1; early in the
innings pb1 sits near 0.5 because little is known; no venue/pitch/dew/team strength; whole-match result
also depends on the second innings, which no pre-ball first-innings state fixes.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

FEATS = ['pre_runs', 'pre_balls', 'wickets_lost']


def prepare_first_innings(train_df):
    """train_df: output of pressure_v4.training_deliveries (has pre_balls, wickets_lost, total, innings)."""
    d = train_df.copy()
    d = d.sort_values(['match_id', 'innings', 'sequence'])
    d['pre_runs'] = d.groupby(['match_id', 'innings']).total.cumsum() - d.total
    fin2 = d[d.innings == 2].groupby('match_id').agg(runs2=('total', 'sum'), target=('target', 'first'))
    f = fin2.runs2 - fin2.target          # >=0 chase won, -1 tie, <=-2 first side won
    lab = pd.Series(np.nan, index=fin2.index)
    lab[f >= 0] = 0.0
    lab[f <= -2] = 1.0
    d1 = d[d.innings == 1].copy()
    d1['first_side_won'] = d1.match_id.map(lab)
    return d1.dropna(subset=['first_side_won'])


def fit_model(d1, seasons, cfg):
    p = cfg['v4']['inn1']
    tr = d1[d1.season.isin(list(seasons))]
    m = HistGradientBoostingClassifier(max_depth=p['hgb_max_depth'], learning_rate=p['hgb_learning_rate'],
                                       max_iter=p['hgb_max_iter'], l2_regularization=p['hgb_l2'],
                                       monotonic_cst=[p['monotonic'][f] for f in FEATS],
                                       early_stopping=False, random_state=cfg['seed'])
    m.fit(tr[FEATS], tr.first_side_won.astype(int))
    return m


def models_by_season(d1, cfg):
    """{season: model} following the chronology rule."""
    out, fixed = {}, None
    for y in sorted(set(cfg['years'])):
        if y <= cfg['train_end']:
            out[y] = fit_model(d1, range(cfg['warmup_year'], y), cfg)
        else:
            if fixed is None:
                fixed = fit_model(d1, range(cfg['warmup_year'], cfg['train_end'] + 1), cfg)
            out[y] = fixed
    return out


def add_pb1(d, cfg, d1_train):
    """d: scored deliveries (innings, season, pre_runs, pre_balls, wickets_in_hand). pb1 on first-innings rows."""
    ms = models_by_season(d1_train, cfg)
    d = d.copy()
    d['pb1'] = np.nan
    for y, m in ms.items():
        mask = (d.innings == 1) & (d.season == y)
        X = pd.DataFrame({'pre_runs': d.pre_runs[mask], 'pre_balls': d.pre_balls[mask],
                          'wickets_lost': 10 - d.wickets_in_hand[mask]})
        d.loc[mask, 'pb1'] = m.predict_proba(X[FEATS])[:, 1]
    return d
