import numpy as np, pandas as pd
from pressure_v4 import load_cfg, training_deliveries
from winprob1 import prepare_first_innings, fit_model, FEATS, models_by_season
from pressure_inn1 import label1
cfg, v4 = load_cfg()
TR = prepare_first_innings(training_deliveries(cfg))
BAND = v4['inn1']['band']

def test_features_have_no_venue_or_identity():
    assert FEATS == ['pre_runs', 'pre_balls', 'wickets_lost']

def test_labels_only_first_innings_and_exclude_ties():
    assert (TR.innings == 1).all() and set(TR.first_side_won.unique()) == {0.0, 1.0}
    raw = training_deliveries(cfg)
    f = raw[raw.innings == 2].groupby('match_id').agg(r=('total', 'sum'), t=('target', 'first'))
    ties = set(f[f.r - f.t == -1].index)
    assert not ties & set(TR.match_id)

def test_band_edges_and_scope():
    d = pd.DataFrame({'innings': [1, 1, 1, 1, 2], 'pb1': [0.6, 0.5999, 0.9, 0.2, 0.7]})
    assert list(label1(d, BAND)) == ['pressure', 'normal', 'above_band', 'normal', 'not_applicable']

def test_chronology_no_future_leak():
    m = fit_model(TR, range(2019, 2022), cfg)
    keep = TR[TR.season <= 2021]
    m2 = fit_model(keep, range(2019, 2022), cfg)       # later seasons physically removed
    X = TR[FEATS].iloc[:2000]
    assert np.allclose(m.predict_proba(X), m2.predict_proba(X))
    m3 = fit_model(TR, range(2019, 2023), cfg)         # adding 2022 must change it
    assert not np.allclose(m.predict_proba(X), m3.predict_proba(X))

def test_monotone_in_runs_and_wickets():
    m = fit_model(TR, range(2019, 2025), cfg)
    runs = pd.DataFrame({'pre_runs': np.arange(0, 200, 5), 'pre_balls': 90, 'wickets_lost': 3})
    p = m.predict_proba(runs[FEATS])[:, 1]; assert (np.diff(p) >= -1e-12).all()
    wk = pd.DataFrame({'pre_runs': 120, 'pre_balls': 90, 'wickets_lost': np.arange(0, 10)})
    p = m.predict_proba(wk[FEATS])[:, 1]; assert (np.diff(p) <= 1e-12).all()

def test_labelling_uses_only_pre_ball_pb1():
    d = pd.DataFrame({'innings': [1] * 3, 'pb1': [0.7] * 3}); a = label1(d, BAND)
    assert (label1(d.assign(charged=99, wicket=1, total=6), BAND) == a).all()

def test_fixed_model_for_2025_26():
    ms = models_by_season(TR, cfg); assert ms[2025] is ms[2026]

def test_labels_match_official_winner():
    import json
    v = json.load(open('outputs/validation_inn1.json'))['label_evidence']
    assert v['checked_against_cricsheet_official_winner']['disagree'] == 0 and v['checked_against_cricsheet_official_winner']['no_winner_listed'] == 0
