"""v5 tests: state labelling (both-tail exclusion), calibration chronology and monotonicity,
tie handling, and consistency of the v5 outputs with the frozen earlier versions."""
import json
import numpy as np
import pandas as pd
import pytest
from pathlib import Path

from pressure_v4 import load_cfg, training_deliveries, uplift_table
from pressure_v5 import label_state_v5
from winprob_cal import chase_outcomes, fold_spans, loso_pairs_chase, fit_isotonic

CFG, _ = load_cfg()
V5 = CFG['v5']


def test_state_band_edges():
    s = pd.Series([0.0, 0.049, 0.05, 0.051, 0.599, 0.6, 0.89, 0.9, 0.949, 0.95, 1.0])
    lab = label_state_v5(s, V5['band'], V5['decided'])
    assert list(lab) == ['decided', 'decided', 'decided', 'normal', 'normal', 'pressure',
                         'pressure', 'above_band', 'above_band', 'decided', 'decided']


def test_decided_excluded_from_both_pools():
    # decided balls must enter neither pressure nor normal, so uplift never sees them
    n = 300
    rng = np.random.default_rng(0)
    d = pd.DataFrame({
        'bowler': ['A'] * (n // 2) + ['B'] * (n // 2),
        'match_id': np.repeat(np.arange(30), n // 30),
        'phase': ['middle'] * n,
        'state': 'decided', 'runs_resid': rng.normal(size=n), 'wk_resid': rng.normal(size=n)})
    assert uplift_table(d, 'runs_resid', 1, 1, 1, 1).empty
    d2 = d.copy()
    d2['state'] = np.where(np.arange(n) % 2 == 0, 'pressure', 'normal')  # both states present
    assert not uplift_table(d2, 'runs_resid', 1, 1, 1, 1).empty  # sanity: pressure/normal do flow through


def test_fold_spans_chronology():
    spans = fold_spans(CFG)
    assert spans[2022] == [2019, 2020, 2021]
    assert spans[2023] == [2019, 2020, 2021, 2022]
    assert spans[2024] == [2019, 2020, 2021, 2022, 2023]
    assert spans[2025] == spans[2026] == [2019, 2020, 2021, 2022, 2023, 2024]
    for y, span in spans.items():
        if y <= CFG['train_end']:
            assert max(span) < y  # a scored season never informs its own score or calibrator


def test_chase_outcomes_tie_excluded():
    df = pd.DataFrame({
        'match_id': [1, 1, 2, 2], 'innings': [2, 2, 2, 2], 'sequence': [1, 2, 1, 2],
        'total': [5, 10, 5, 10], 'target': [16, 16, 15, 15]})
    lab = chase_outcomes(df)
    assert pd.isna(lab[1])   # 15 == target-1: tie, excluded
    assert lab[2] == 1.0     # 15 >= target: chase won


@pytest.fixture(scope='module')
def fold_2022_pairs():
    train_df = training_deliveries(CFG)
    return loso_pairs_chase(train_df, [2019, 2020, 2021], CFG)


def test_loso_pairs_exclude_own_season(fold_2022_pairs):
    p = fold_2022_pairs
    assert (p.season == p.excluded_season).all()
    assert set(p.season.unique()) == {2019, 2020, 2021}
    assert p.chase_won.isin([0.0, 1.0]).all()  # ties dropped


def test_isotonic_monotone_and_bounded(fold_2022_pairs):
    iso = fit_isotonic(fold_2022_pairs.pb, fold_2022_pairs.chase_won)
    grid = np.linspace(0, 1, 501)
    pred = iso.predict(grid)
    assert np.all(np.diff(pred) >= -1e-12)          # non-decreasing in pb
    assert pred.min() >= 0 and pred.max() <= 1
    # calibration must actually move the raw score where v4 was wrong: low-pb states
    assert iso.predict([0.05])[0] > 0.05            # v4 under-predicted chase wins from behind


def test_overall_list_unchanged_from_v4():
    a = pd.read_csv('outputs/v5_list_overall.csv').set_index('Bowler')
    b = pd.read_csv('outputs/v4_list_overall.csv').set_index('Bowler')
    assert a.index.equals(b.index)
    assert float((a.runs_shrunk - b.runs_shrunk).abs().max()) == 0.0
    assert (a.order == b.order).all()


def test_v5_outputs_schema():
    need = {'Bowler', 'runs_shrunk', 'wk_shrunk', 'rank_median', 'rank_mean', 'rank_best',
            'rank_worst', 'order', 'CI_low', 'CI_high', 'deliveries', 'Team', 'Type'}
    for f in ['v5_list_overall', 'v5_chase_list_pressure', 'v5_chase_list_uplift',
              'v5_inn1_list_pressure', 'v5_inn1_list_uplift']:
        t = pd.read_csv(f'outputs/{f}.csv')
        assert need <= set(t.columns), f
        assert t.order.is_unique and (t.order == np.arange(1, len(t) + 1)).all()
        assert t[['runs_shrunk', 'wk_shrunk']].notna().all().all()
    v = json.loads(Path('outputs/validation_v5.json').read_text())
    assert v['decided_primary'] == V5['decided']
    for inn in ['chase', 'inn1']:
        c = v['scope_counts_primary'][inn]
        assert set(c) <= {'normal', 'pressure', 'above_band', 'decided'}
        assert c.get('decided', 0) > 0 or inn == 'inn1'  # tail rule actually removes balls
