import numpy as np, pandas as pd
from pressure_v4 import label_state, combine, uplift_table, overlap_phases, load_cfg
BAND = [0.6, 0.9]

def mk(**k):
    b = dict(innings=2, pb=0.7); b.update(k); return pd.DataFrame([b])

def lab(**k):
    return label_state(mk(**k), BAND)[0]

def test_band_edges_and_scopes():
    assert lab(pb=0.6) == 'pressure' and lab(pb=0.8999) == 'pressure'   # lower edge inclusive
    assert lab(pb=0.9) == 'above_band' and lab(pb=0.99) == 'above_band'
    assert lab(pb=0.5999) == 'normal' and lab(pb=0.02) == 'normal'
    assert lab(innings=1, pb=np.nan) == 'not_applicable'

def test_label_uses_only_pre_ball_columns():
    d = pd.concat([mk()] * 3, ignore_index=True); a = label_state(d, BAND)
    d2 = d.assign(charged=99, wicket=1, total=6, er=5.0)
    assert (label_state(d2, BAND) == a).all()

def test_combine_rank_flip_and_deterministic_tiebreak():
    r = pd.DataFrame({'slope_shrunk': [20., 1., 1.], 'CI_low': 0, 'CI_high': 1, 'deliveries': 9}, index=['A', 'B', 'C'])
    w = pd.DataFrame({'slope_shrunk': [-0.5, 0.5, 0.5]}, index=['A', 'B', 'C'])
    c = combine(r, w, [10, 15, 20, 25, 30])
    assert c.loc['A', 'comb_10'] == 15.0 and c.loc['B', 'comb_10'] == 6.0
    assert c.loc['A', 'rank_best'] == 1 and c.loc['A', 'rank_worst'] == 3
    assert list(c.index[:2]) == ['B', 'C']        # exact tie -> alphabetical, disclosed

def _frame(rng, n=400, same_phase=True):
    ph = rng.choice(['middle', 'death'], n) if same_phase else None
    d = pd.DataFrame({'bowler': 'X', 'match_id': rng.integers(0, 30, n)})
    if same_phase:
        d['phase'] = ph; d['state'] = rng.choice(['pressure', 'normal'], n); d['y'] = rng.normal(0, 1, n)
    else:   # pressure only in death, normal only in powerplay, phases differ in mean by 3
        d['state'] = np.where(np.arange(n) % 2, 'pressure', 'normal')
        d['phase'] = np.where(d.state == 'pressure', 'death', 'powerplay')
        d['y'] = np.where(d.phase == 'death', 3.0, 0.0) + rng.normal(0, 1, n)
    return d

def test_no_phase_overlap_is_omitted_not_extrapolated():
    d = _frame(np.random.default_rng(2), same_phase=False)
    assert overlap_phases(d, 10) == []
    assert len(uplift_table(d, 'y', 20, 20, 10, 3)) == 0   # a naive pressure coefficient would be ~+3 here

def test_uplift_zero_when_no_effect_with_overlap():
    d = _frame(np.random.default_rng(1)); t = uplift_table(d, 'y', 20, 20, 10, 3)
    assert len(t) == 1 and abs(t.slope_raw[0]) < 3 * t.slope_se[0]

def test_thresholds_live_in_config():
    cfg, v4 = load_cfg()
    for k in ['pressure_band_primary', 'pressure_band_alt', 'wicket_values', 'min_pressure_balls', 'min_stratum_balls', 'placebo_reps']:
        assert k in v4
