import numpy as np, pandas as pd
from bpf_components import add_components, level_table, run_components

def mk(n=400, seed=0):
    r = np.random.default_rng(seed)
    return pd.DataFrame({'bowler': ['A'] * n + ['B'] * n, 'match_id': np.tile(np.repeat(np.arange(20), n // 20), 2),
        'er': r.normal(1.2, 1, 2 * n), 'charged': r.integers(0, 5, 2 * n).astype(float),
        'wicket': r.integers(0, 2, 2 * n) * (r.random(2 * n) < .05), 'ew': 0.05,
        'bucket': r.choice(['pressure', 'normal', 'middle'], 2 * n), 'season': 2024, 'date': '2024-01-01'})

def test_components_separate():
    d = add_components(mk())
    assert np.allclose(d.runs_resid, d.er - d.charged) and np.allclose(d.wk_resid, d.wicket - d.ew)

def test_single_match_bowler_omitted():
    d = add_components(mk()); d.loc[d.bowler == 'B', 'match_id'] = 1
    t = level_table(d, 'runs_resid', 50)
    assert list(t.Bowler) == ['A']

def test_constant_bowler_omitted_not_zero_se():
    d = mk(); d.loc[d.bowler == 'B', 'er'] = 1.0; d.loc[d.bowler == 'B', 'charged'] = 1.0; d = add_components(d)
    t = level_table(d, 'runs_resid', 50)
    assert 'B' not in set(t.Bowler)

def test_bucket_subset_counts():
    d = add_components(mk()); t = level_table(d, 'runs_resid', 10, 'pressure')
    assert (t.deliveries == [(d[(d.bowler == b) & (d.bucket == 'pressure')]).shape[0] for b in t.Bowler]).all()
