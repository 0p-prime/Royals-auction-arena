"""Unit tests: bucket sizes, shrinkage maths, funnel filters, calibration."""
import numpy as np, pandas as pd, sys, os, yaml
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ppf import bucketize, eb_shrinkage
from selector import funnel

def test_bucket_sizes():
    m = pd.read_parquet("data/interim/rae.parquet")
    b = bucketize(m, 0.25, 0.40)
    shares = b.value_counts(normalize=True)
    assert abs(shares["pressure"] - 0.25) < 0.01
    assert abs(shares["normal"] - 0.40) < 0.01
    assert abs(shares["drop"] - 0.35) < 0.01

def test_shrinkage_maths():
    bt = pd.read_csv("outputs/batsman_ppf.csv", index_col=0)
    assert ((bt["eb_lambda"] >= 0) & (bt["eb_lambda"] <= 1)).all()
    assert (bt["PPF_adj"].abs() <= bt["PPF"].abs() + 1e-9).all()
    fb = bt["balls_p"] / (bt["balls_p"] + 60) * bt["PPF"]
    assert np.allclose(bt["PPF_fallback"], fb)
    lam, between = bt["eb_lambda"], None
    # EB: players with larger bootstrap variance shrink more
    hi_var = bt["within_var"] > bt["within_var"].median()
    assert bt.loc[hi_var, "eb_lambda"].mean() <= bt.loc[~hi_var, "eb_lambda"].mean() + 1e-9

def test_funnel_filters():
    cfg = yaml.safe_load(open("config.yaml"))
    bt = pd.read_csv("outputs/batsman_ppf.csv", index_col=0)
    short, top10 = funnel(bt, cfg)
    assert len(top10) == cfg["funnel"]["final_size"]
    assert len(short) == cfg["funnel"]["shortlist_size"]
    assert (top10["balls_p"] >= cfg["funnel"]["min_pressure_balls"]).all()
    assert (top10["balls_n"] >= cfg["funnel"]["min_normal_balls"]).all()
    assert (top10["RAE100_p"] >= 0).all()
    _, top10_q = funnel(bt, cfg, quota=True)
    assert len(top10_q) == 10

def test_calibration_close():
    cal = pd.read_csv("outputs/calibration.csv")
    assert (cal["pred"] - cal["obs"]).abs().max() < 0.05

def test_rae_mean_near_zero():
    m = pd.read_parquet("data/interim/rae.parquet")
    assert abs(m["RAE"].mean()) < 0.1
