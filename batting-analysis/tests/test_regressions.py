"""Regression tests for pipeline correctness properties (2026-11-12)."""
import numpy as np, pandas as pd, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_retired_not_dismissal_target():
    """retired hurt/out must not count as striker dismissal in y."""
    feat = pd.read_parquet("data/interim/features.parquet")
    ret = feat[feat["dismissal_kind"].isin(["retired hurt", "retired out"]) & feat["is_legal"]]
    assert len(ret) > 0
    for _, r in ret.iterrows():
        assert r["y_dot_or_out"] == int(r["runs_batter"] == 0)

def test_dls_chase_excluded_from_modeling():
    from mpi_lpi_models import prep
    feat = pd.read_parquet("data/interim/features.parquet")
    m = prep(feat)
    assert not m["dls_chase"].any()
    n_excl = int((feat["is_legal"] & feat["dls_chase"]).sum())
    assert n_excl == 414  # 4 DLS matches; disclosed in METHODOLOGY.md

def test_position_first_appearance_either_role():
    """Both openers (incl. the non-facing one) get positions 1 and 2."""
    feat = pd.read_parquet("data/interim/features.parquet")
    rng = np.random.RandomState(3)
    keys = feat.groupby(["match_id", "innings"]).size().sample(10, random_state=rng).index
    for mid, inn in keys:
        sub = feat[(feat.match_id == mid) & (feat.innings == inn) & feat["is_legal"]]
        first = sub.iloc[0]
        openers = {first["batter"], first["non_striker"]}
        pos = sub[sub["batter"].isin(openers)].groupby("batter")["batting_position"].min()
        # openers who faced at least one legal ball must hold positions 1 and 2
        # (an opener run out without facing, e.g. Williamson 1304100, keeps pos 2)
        assert set(pos.tolist()) <= {1.0, 2.0} and len(pos) >= 1, (mid, inn, pos)
        assert pos.min() == 1.0

def test_penalty_pure_state_lookup():
    """Same (over, wickets) state in a match -> identical penalty regardless of outcome."""
    rae = pd.read_parquet("data/interim/rae.parquet")
    samp = rae.groupby(["match_id", "over", "wkts_before"])["wicket_penalty"].nunique()
    assert (samp <= 1).all()

def test_joint_bootstrap_same_draw():
    """Joint resampling: crafted data where pressure and normal move together per match
    must give zero-variance PPF under joint draws (independent draws would vary)."""
    from ppf import joint_bootstrap
    rows = []
    for i in range(5):
        rows.append({"batter": "X", "match_id": f"m{i}", "bucket": "pressure", "wRAE": 10.0, "w": 1.0, "n": 10})
        rows.append({"batter": "X", "match_id": f"m{i}", "bucket": "normal", "wRAE": 5.0, "w": 1.0, "n": 10})
        rows.append({"batter": "Y", "match_id": f"m{i}", "bucket": "pressure", "wRAE": 2.0, "w": 1.0, "n": 10})
        rows.append({"batter": "Y", "match_id": f"m{i}", "bucket": "normal", "wRAE": 8.0, "w": 1.0, "n": 10})
    agg = pd.DataFrame(rows)
    boot = joint_bootstrap(agg, B=200, seed=0)
    assert np.isclose(boot["X"].var(), 0.0)   # 10-5 per match, always
    assert np.isclose(boot["Y"].var(), 0.0)   # 2-8 per match, always
    assert np.isclose(boot["X"].mean(), 500.0) and np.isclose(boot["Y"].mean(), -600.0)

def test_penalty_loo_excludes_own_match():
    """Independently recompute the LOO cell penalty for sampled matches from raw
    stints EXCLUDING that match; must equal the pipeline value exactly."""
    from data_loader import load_config
    feat = pd.read_parquet("data/interim/features.parquet")
    rae = pd.read_parquet("data/interim/rae.parquet")
    d = feat[feat["is_legal"] & ~feat["dls_chase"]]
    st = d.groupby(["match_id", "innings", "batter"], sort=False).agg(
        arr_over=("over", "min"), arr_wkts=("wkts_before", "min"),
        stint_runs=("runs_batter", "sum")).reset_index()
    st = st[st["arr_wkts"] <= 9]
    glob_all = st["stint_runs"].mean()
    rng = np.random.RandomState(5)
    for mid in rng.choice(d["match_id"].unique(), 5, replace=False):
        hist = st[st["match_id"] != mid]
        cell = hist.groupby(["arr_over", "arr_wkts"])["stint_runs"].mean()
        ov = hist.groupby("arr_over")["stint_runs"].mean()
        sub = rae[rae["match_id"] == mid]
        for r in sub.sample(min(50, len(sub)), random_state=1).itertuples():
            o, w = r.over, r.wkts_before + 1
            if w > 9:
                exp = 0.0
            else:
                exp = cell.get((o, w), np.nan)
                if isinstance(exp, float) and np.isnan(exp):
                    exp = ov.get(o, glob_all)
            assert np.isclose(r.wicket_penalty, exp), (mid, o, w, r.wicket_penalty, exp)

def test_joint_bootstrap_skip_counted():
    from ppf import joint_bootstrap
    rows = []
    for i in range(4):
        rows.append({"batter": "X", "match_id": f"a{i}", "bucket": "pressure", "wRAE": 1.0, "w": 1.0, "n": 5})
        rows.append({"batter": "X", "match_id": f"b{i}", "bucket": "normal", "wRAE": 1.0, "w": 1.0, "n": 5})
    agg = pd.DataFrame(rows)
    boot = joint_bootstrap(agg, B=300, seed=1)
    # pressure and normal matches are disjoint: many resamples leave one bucket empty
    assert joint_bootstrap.skipped["X"] > 0
    assert boot["X"].notna().sum() + joint_bootstrap.skipped["X"] == 300
