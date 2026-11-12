"""Tests for the bounded continuous-pressure revision (bpf_continuous)."""
import json
import numpy as np
import pandas as pd
from bpf_continuous import (add_centered_rae, bowler_slopes, shrink_slopes,
                            stability_continuous, run_continuous,
                            EVIDENCE_POSITIVE, EVIDENCE_NEGATIVE,
                            EVIDENCE_INSUFFICIENT)

CFG = json.load(open('config.json'))
RNG = np.random.default_rng(7)


def make(bowler, n, slope, matches=20, seed=1):
    r = np.random.default_rng(seed)
    bopi = r.uniform(5, 35, n)
    rae_c = slope * (bopi - bopi.mean()) / 100.0 + r.normal(0, 4, n)
    return pd.DataFrame({'bowler': bowler, 'bopi': bopi, 'rae_c': rae_c,
                         'match_id': [f'{bowler}-m{i % matches}' for i in range(n)],
                         'date': '2024-01-01', 'season': 2024})


def test_centered_rae_formula():
    d = pd.DataFrame({'er': [1.5], 'charged': [2], 'wicket': [1], 'ew': [0.05]})
    out = add_centered_rae(d, dict(CFG, wicket_value=20.0))
    assert abs(out.rae_c.iloc[0] - (1.5 - 2 + 20 * (1 - 0.05))) < 1e-9


def test_slope_recovers_known_positive_and_zero():
    pos = make('A', 400, slope=50.0, seed=2)
    flat = make('B', 400, slope=0.0, seed=3)
    sl = bowler_slopes(pd.concat([pos, flat]), CFG, min_balls=100).set_index('Bowler')
    assert sl.loc['A', 'slope_raw'] > 30.0
    assert abs(sl.loc['B', 'slope_raw']) < 15.0
    assert sl.loc['A', 'slope_se'] > 0


def test_shrinkage_pulls_small_sample_toward_mean():
    big = make('BIG', 2000, slope=0.0, seed=4)
    small = make('SMALL', 160, slope=80.0, seed=5)
    sl = bowler_slopes(pd.concat([big, small]), CFG, min_balls=100)
    sh = shrink_slopes(sl).set_index('Bowler')
    # Small-sample outlier slope must shrink toward the population mean.
    assert abs(sh.loc['SMALL', 'slope_shrunk'] - sh.attrs['mu']) <= \
        abs(sh.loc['SMALL', 'slope_raw'] - sh.attrs['mu']) + 1e-9
    assert 'mu' in sh.attrs and sh.attrs['tau2'] >= 0


def test_evidence_labels_neutral_and_conservative():
    pos = make('P', 800, slope=200.0, seed=6)
    flat = make('F', 800, slope=0.0, seed=8)
    sh = shrink_slopes(bowler_slopes(pd.concat([pos, flat]), CFG, 100)).set_index('Bowler')
    assert sh.loc['P', 'evidence'] == EVIDENCE_POSITIVE
    assert sh.loc['F', 'evidence'] == EVIDENCE_INSUFFICIENT


def test_single_match_bowler_excluded_with_reason():
    one = make('ONEMATCH', 200, slope=50.0, matches=1, seed=9)
    ok = make('OK', 200, slope=0.0, seed=10)
    excluded = []
    sl = bowler_slopes(pd.concat([one, ok]), CFG, 100, excluded)
    assert set(sl.Bowler) == {'OK'}
    assert any(e['Bowler'] == 'ONEMATCH' and '2 distinct matches' in e['reason']
               for e in excluded)


def test_zero_standard_error_excluded_with_reason():
    # Perfect linear fit within every cluster => zero residuals => zero SE.
    n = 200
    bopi = np.tile(np.linspace(5, 35, 20), 10)
    rae_c = 0.5 * (bopi - 20.0)
    d = pd.DataFrame({'bowler': 'PERFECT', 'bopi': bopi, 'rae_c': rae_c,
                      'match_id': [f'm{i // 20}' for i in range(n)],
                      'date': '2024-01-01', 'season': 2024})
    excluded = []
    sl = bowler_slopes(d, CFG, 100, excluded)
    assert len(sl) == 0
    assert any(e['Bowler'] == 'PERFECT' and 'zero slope standard error' in e['reason']
               for e in excluded)


def test_stability_undefined_below_three_bowlers():
    df = pd.concat([make('A', 200, 10), make('B', 200, -10)])
    val = stability_continuous(add_centered_rae(
        df.assign(er=0, charged=0, wicket=0, ew=0).drop(columns=['rae_c']), CFG), CFG)
    assert val['alternate_match_slope_rank']['rho'] is None
    assert val['alternate_match_slope_rank']['bowlers'] <= 2


def test_run_continuous_contract():
    df = pd.concat([make(c, 300, s, seed=i) for i, (c, s) in
                    enumerate([('A', 40), ('B', 0), ('C', -40), ('D', 20)])])
    # Route the constructed response through er-charged so add_centered_rae keeps it.
    df['er'] = 1.4 + df['rae_c']; df['charged'] = 1.4; df['wicket'] = 0; df['ew'] = 0.0
    full, val = run_continuous(df, CFG)
    assert {'Bowler', 'slope_raw', 'slope_se', 'slope_shrunk', 'CI_low', 'CI_high',
            'evidence'} <= set(full.columns)
    assert {'alternate_match_slope_rank', 'time_slope_rank', 'population_mean_slope',
            'between_bowler_tau2', 'evidence_counts', 'holdout_note'} <= set(val)
