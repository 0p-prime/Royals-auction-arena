"""Leakage proofs for Step 1 features."""
import numpy as np, pandas as pd, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from features import build_features, add_targets, BOWLER_WICKET_KINDS
from data_loader import load_config, build_deliveries

RAW = "/downloads/ipl_json"

def _load():
    cfg = load_config()
    raw = pd.read_parquet("data/interim/deliveries.parquet")
    return cfg, raw, pd.read_parquet("data/interim/features.parquet")

def test_shift_check_random_innings():
    """Pre-ball cumulative state equals manual recompute excluding current ball."""
    cfg, raw, feat = _load()
    rng = np.random.RandomState(0)
    keys = feat.groupby(["match_id", "innings"]).size().sample(5, random_state=rng).index
    for mid, inn in keys:
        sub = feat[(feat.match_id == mid) & (feat.innings == inn)].sort_values(["over", "ball_seq"])
        tot = (sub["runs_batter"] + sub["runs_extras"]).to_numpy()
        wk = sub["wicket"].to_numpy()
        assert (sub["runs_before"].to_numpy() == np.concatenate([[0], np.cumsum(tot)[:-1]])).all()
        assert (sub["wkts_before"].to_numpy() == np.concatenate([[0], np.cumsum(wk)[:-1]])).all()
        legal = sub[sub["is_legal"]]
        dots = (legal["runs_batter"] == 0).astype(float).to_numpy()
        exp = pd.Series(dots).rolling(12, min_periods=1).sum().shift(fill_value=0).to_numpy() / 12.0
        assert np.allclose(legal["dots_last12"].to_numpy(), exp)

def test_current_ball_outcome_does_not_change_features():
    """Zeroing a row's own outcome must not change its own features (pre-ball proof).
    One row perturbed per rebuild so no other row's past legitimately shifts it."""
    cfg, raw, _ = _load()
    f1 = build_features(raw.copy(), cfg).set_index("row_id")
    sample = f1[f1.index.notna()].sample(5, random_state=1)
    cols = ["runs_before", "wkts_before", "legal_before", "crr", "rrr", "rr_crr_gap",
            "wickets_lost", "dots_last12", "wkts_last18", "settledness",
            "par_diff", "batting_position", "match_importance", "bowler_eco", "bowler_sr"]
    for rid, r in sample.iterrows():
        key = (r["match_id"], r["innings"], r["over"], r["ball_seq"])
        mask = ((raw["match_id"] == key[0]) & (raw["innings"] == key[1])
                & (raw["over"] == key[2]) & (raw["ball_seq"] == key[3]))
        assert mask.sum() == 1
        raw2 = raw.copy()
        raw2.loc[mask, ["runs_batter", "runs_extras", "wicket"]] = 0
        raw2.loc[mask, ["player_dismissed", "dismissal_kind"]] = ""
        f2 = build_features(raw2, cfg).set_index("row_id")
        for c in cols:
            a, b = f1.loc[rid, c], f2.loc[rid, c]
            assert (pd.isna(a) == pd.isna(b)), (rid, c)
            if pd.notna(a):
                assert np.isclose(float(a), float(b)), (rid, c, a, b)


def test_bowler_threat_expanding_window():
    """Bowler threat at match M uses only matches with strictly earlier dates."""
    cfg, raw, feat = _load()
    legal = raw[raw["is_legal"]].copy()
    legal["bw"] = ((legal["wicket"] == 1) & (legal["dismissal_kind"].isin(BOWLER_WICKET_KINDS))).astype(int)
    per = legal.groupby(["date", "match_id", "bowler"]).agg(balls=("batter", "count")).reset_index()
    mid, bowler = per[per["date"] > per["date"].min()].iloc[100][["match_id", "bowler"]]
    mdate = raw.loc[raw.match_id == mid, "date"].iloc[0]
    hist = per[(per["bowler"] == bowler) & (per["date"] < mdate)]
    assert (hist["date"] < mdate).all() and len(hist) > 0
    row = feat[(feat.match_id == mid) & (feat.bowler == bowler)].iloc[0]
    # recompute expected shrunk eco/sr from history only
    lr = legal[(legal["bowler"] == bowler) & (legal["date"] < mdate)]
    er = raw[raw["extras_type"].str.contains("wides|noballs", na=False)]
    er = er[(er["bowler"] == bowler) & (er["date"] < mdate)]["runs_extras"].sum()
    b = len(lr); ru = lr["runs_batter"].sum() + er; w = lr["bw"].sum()
    lg = legal[legal["date"] < mdate]
    lger = raw[(raw["date"] < mdate) & raw["extras_type"].str.contains("wides|noballs", na=False)]["runs_extras"].sum()
    lruns, lw = lg["runs_batter"].sum() + lger, lg["bw"].sum()
    shrink = b / (b + 300.0)
    eco = shrink * (ru / b * 6) + (1 - shrink) * (lruns / len(lg) * 6)
    sr = shrink * (b / w if w else 60.0) + (1 - shrink) * (len(lg) / lw if lw else 20.0)
    assert np.isclose(row["bowler_eco"], eco, atol=1e-9)
    assert np.isclose(row["bowler_sr"], sr, atol=1e-9)

def test_par_uses_earlier_dates_only():
    """First-date innings have no par (cold start); par varies by date, not future."""
    _, _, feat = _load()
    d0 = feat["date"].min()
    first_day = feat[(feat["date"] == d0) & (feat["innings"] == 1)]
    assert first_day["par_missing"].all()
    later = feat[(feat["date"] > d0) & (feat["innings"] == 1) & (feat["par_missing"] == 0)]
    assert later["par"].notna().all()

def test_targets_legal_only_and_forward_window():
    _, _, feat = _load()
    assert feat.loc[~feat["is_legal"], "y_dot_or_out"].isna().all()
    m = feat["is_legal"]
    assert set(feat.loc[m, "y_dot_or_out"].unique()) <= {0, 1}
    assert set(feat.loc[m, "y_out_6"].dropna().unique()) <= {0, 1}

def test_secondary_target_striker_identity_and_censoring():
    """y_out_6: current striker dismissed within 6 legal innings balls; non-striker
    runouts excluded; window truncates at innings end."""
    _, _, feat = _load()
    legal = feat[feat["is_legal"]]
    rng = np.random.RandomState(2)
    keys = legal.groupby(["match_id", "innings"]).size().sample(3, random_state=rng).index
    for mid, inn in keys:
        sub = legal[(legal.match_id == mid) & (legal.innings == inn)].sort_values(["over", "ball_seq"])
        bat = sub["batter"].to_numpy(); dis = sub["player_dismissed"].to_numpy()
        y6 = np.zeros(len(sub))
        for off in range(6):
            shifted = np.concatenate([dis[off:], [""] * off]) if off else dis.copy()
            y6 = np.maximum(y6, (shifted == bat).astype(float))
        assert np.allclose(sub["y_out_6"].to_numpy(), y6)
        # innings-end censoring: final legal ball's y6 equals its own striker dismissal
        assert sub["y_out_6"].iloc[-1] == float(dis[-1] == bat[-1])
    # non-striker runout must not count: find one
    nsr = legal[(legal["player_dismissed"] != "") & (legal["player_dismissed"] != legal["batter"])
                & (legal["dismissal_kind"] == "run out")]
    assert len(nsr) > 0
    r = nsr.iloc[0]
    sub = legal[(legal.match_id == r["match_id"]) & (legal.innings == r["innings"])].sort_values(["over", "ball_seq"])
    i = sub.index.get_loc(r.name) if r.name in sub.index else None
    pos = list(sub["row_id"]).index(r["row_id"])
    # if no striker dismissal in the same window, that row's y6 must be 0
    window = sub.iloc[pos:pos + 6]
    if not ((window["player_dismissed"] == window["batter"]).any()):
        assert r["y_out_6"] == 0
