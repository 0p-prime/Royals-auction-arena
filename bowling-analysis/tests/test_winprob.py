import json, numpy as np, pandas as pd
from pathlib import Path
from winprob import outcome_tables, solve, pbat, prepare_training
from pressure_v4 import training_deliveries

CFG = json.loads(Path('config.json').read_text()); WP = CFG['v4']['winprob']
TR = training_deliveries(CFG)
TABS = outcome_tables(TR, range(2019, 2025), WP)
V = solve(TABS, WP)

def test_terminals():
    assert pbat(V, [0], [30], [3])[0] == 1.0
    assert pbat(V, [5], [30], [10])[0] == 0.0 and pbat(V, [5], [0], [3])[0] == 0.0

def test_monotone_in_runs_needed():
    assert (np.diff(V[:, :, 1:], axis=2) <= 1e-9).all()

def test_extreme_states_sensible():
    assert pbat(V, [10], [1], [5])[0] < 0.01        # 10 off 1 ball
    assert pbat(V, [1], [12], [5])[0] > 0.95        # 1 off 12 balls
    assert pbat(V, [4], [1], [5])[0] < pbat(V, [1], [1], [5])[0]

def test_illegal_repeat_truncation_is_negligible():
    V5 = solve(TABS, WP, iters=WP['illegal_repeat_iters'] * 5)
    assert np.abs(V - V5).max() < 1e-6

def test_run_clip_and_nmax_not_binding():
    assert (TR.total > WP['run_clip']).sum() == 0
    assert TR[TR.innings == 2].target.max() <= WP['nmax']

def test_nmax_guard_raises():
    import pytest
    with pytest.raises(ValueError):
        pbat(V, [WP['nmax'] + 1], [30], [3])

def test_forward_season_tables_exclude_own_and_later_seasons():
    a = outcome_tables(TR, range(2019, 2022), WP)                       # what 2022 may use
    b = outcome_tables(TR[TR.season <= 2021], range(2019, 2022), WP)    # same, with later data physically removed
    assert all(np.allclose([x[3] for x in a[k]], [x[3] for x in b[k]]) for k in a)
    c = outcome_tables(TR, range(2019, 2023), WP)                       # adding 2022 must change the table (so it was excluded above)
    assert any(not np.allclose([x[3] for x in a[k]], [x[3] for x in c[k]]) for k in a if len(a[k]) == len(c[k]))

def test_prepare_training_is_pre_ball():
    d = TR[TR.match_id == TR.match_id.iloc[0]]
    first = d[d.innings == 1].sort_values('sequence').iloc[0]
    assert first.pre_balls == 0 and first.wickets_lost == 0
