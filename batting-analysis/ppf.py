"""Steps 6-8: pressure buckets, PPF with EB shrinkage + match bootstrap, selection funnel."""
import numpy as np, pandas as pd, yaml

def bucketize(m, top_q, bot_q):
    hi = m["BPI"].quantile(1 - top_q)
    lo = m["BPI"].quantile(bot_q)
    b = pd.Series("drop", index=m.index)
    b[m["BPI"] >= hi] = "pressure"
    b[m["BPI"] <= lo] = "normal"
    return b

def recency_w(season, w):
    return w.get(str(int(season)), 0.6)

def batsman_bucket_stats(m, bucket_mask, wmap):
    d = m[bucket_mask].copy()
    d["w"] = d["season"].map(lambda s: recency_w(s, wmap))
    d["wRAE"] = d["w"] * d["RAE"]
    d["dismissed"] = (d["player_dismissed"] == d["batter"]).astype(int)
    d["dot"] = (d["runs_batter"] == 0).astype(int)
    g = d.groupby("batter")
    out = pd.DataFrame({
        "balls": g.size(),
        "wballs": g["w"].sum(),
        "wRAE_sum": g["wRAE"].sum(),
        "sr": 100 * g["runs_batter"].sum() / g.size(),
        "dot_pct": 100 * g["dot"].mean(),
        "dismissal_rate": 100 * g["dismissed"].mean(),
    })
    out["RAE100"] = 100 * out["wRAE_sum"] / out["wballs"]
    return out


def joint_bootstrap(agg, B, seed):
    """ONE joint resample of the batsman's matches per draw; both bucket RAEs
    recomputed from the SAME draw (preserves match-level covariance).
    Draws where a resample leaves a bucket with zero weight are skipped and
    counted (joint_bootstrap.skipped). Returns DataFrame (rows=draws, cols=batsman)."""
    rng = np.random.RandomState(seed)
    boot = {}
    skipped = {}
    for batter, d in agg.groupby("batter"):
        dp = d[d["bucket"] == "pressure"]; dn = d[d["bucket"] == "normal"]
        mp = dp["match_id"].unique(); mn = dn["match_id"].unique()
        mall = np.union1d(mp, mn)
        if len(mp) < 3 or len(mn) < 3:
            continue
        wp = dp.set_index("match_id")[["wRAE", "w"]]
        wn = dn.set_index("match_id")[["wRAE", "w"]]
        draws = rng.randint(0, len(mall), (B, len(mall)))
        res_p, res_n = [], []
        for row in draws:
            ms = mall[row]
            sp = wp.reindex(ms).fillna(0.0)
            sn = wn.reindex(ms).fillna(0.0)
            res_p.append(100 * sp["wRAE"].sum() / sp["w"].sum() if sp["w"].sum() > 0 else np.nan)
            res_n.append(100 * sn["wRAE"].sum() / sn["w"].sum() if sn["w"].sum() > 0 else np.nan)
        diff = np.array(res_p) - np.array(res_n)
        skipped[batter] = int(np.isnan(diff).sum())
        boot[batter] = diff
    joint_bootstrap.skipped = skipped
    return pd.DataFrame(boot)

def eb_shrinkage(ppf, within_var):
    between = max(1e-9, np.var(ppf, ddof=1) - np.mean(within_var))
    lam = between / (between + within_var)
    return lam * ppf, lam

def role_of(pos):
    if pos <= 2: return "opener"
    if pos <= 5: return "middle"
    return "finisher"

if __name__ == "__main__":
    cfg = yaml.safe_load(open("config.yaml"))
    m = pd.read_parquet("data/interim/rae.parquet")
    wmap = cfg["ppf"]["recency_weights"]
    m["bucket"] = bucketize(m, cfg["bpi"]["pressure_top_q"], cfg["bpi"]["normal_bottom_q"])
    print("bucket counts overall:", m["bucket"].value_counts().to_dict())
    print("\nbucket counts per season:")
    print(m.groupby(["season", "bucket"]).size().unstack(fill_value=0)[["pressure", "normal"]])
    print("\ninnings mix within buckets:")
    print(m.groupby(["bucket", "innings"]).size().unstack(fill_value=0).loc[["pressure", "normal"]])

    p = batsman_bucket_stats(m, m["bucket"] == "pressure", wmap).add_suffix("_p")
    n = batsman_bucket_stats(m, m["bucket"] == "normal", wmap).add_suffix("_n")
    ov = batsman_bucket_stats(m, pd.Series(True, index=m.index), wmap).add_suffix("_all")
    bt = p.join(n, how="inner").join(ov[["RAE100_all"]])
    bt["PPF"] = bt["RAE100_p"] - bt["RAE100_n"]

    # match-level aggregates for bootstrap + within-player variance
    mb = m[m["bucket"].isin(["pressure", "normal"])].copy()
    mb["w"] = mb["season"].map(lambda s: recency_w(s, wmap))
    mb["wRAE"] = mb["w"] * mb["RAE"]
    agg = mb.groupby(["batter", "match_id", "bucket"]).agg(wRAE=("wRAE", "sum"), w=("w", "sum"), n=("wRAE", "size")).reset_index()

    boot = joint_bootstrap(agg, cfg["ppf"]["bootstrap_resamples"], cfg["seed"])
    bt["PPF_boot_mean"] = boot.mean()
    bt["PPF_boot_var"] = boot.var()
    bt["ci_low"] = boot.quantile(0.05)
    bt["ci_high"] = boot.quantile(0.95)

    # empirical-Bayes shrinkage using bootstrap within-player variance
    bt = bt.dropna(subset=["PPF"])
    bt.loc[:, "within_var"] = bt["PPF_boot_var"].fillna(bt["PPF"].var())
    ppf_adj, lam = eb_shrinkage(bt["PPF"].to_numpy(), bt["within_var"].to_numpy())
    bt["PPF_adj"] = ppf_adj
    bt["eb_lambda"] = lam
    bt["PPF_fallback"] = bt["balls_p"] / (bt["balls_p"] + 60) * bt["PPF"]
    sk = pd.Series(joint_bootstrap.skipped)
    print(f"bootstrap skipped draws (bucket absent in resample): total {sk.sum()} of "
          f"{sk.count() * cfg['ppf']['bootstrap_resamples']} ({100 * sk.sum() / (sk.count() * cfg['ppf']['bootstrap_resamples']):.2f}%), "
          f"max per batsman {sk.max()}")

    # bootstrap CIs on PPF_adj (scale boot by lambda)
    lam_map = bt["eb_lambda"]
    bt["ci_low_adj"] = bt["ci_low"] * lam_map
    bt["ci_high_adj"] = bt["ci_high"] * lam_map

    # confidence labels
    eligible = (bt["balls_p"] >= cfg["funnel"]["min_pressure_balls"]) & (bt["balls_n"] >= cfg["funnel"]["min_normal_balls"])
    seasons_active = m.groupby("batter")["season"].max()
    bt["active"] = seasons_active.reindex(bt.index).isin(cfg["funnel"]["active_seasons"])
    bt["eligible"] = eligible & bt["active"]
    ci_excl0 = (bt["ci_low_adj"] > 0) | (bt["ci_high_adj"] < 0)
    bt["confidence"] = "Low"
    bt.loc[bt["eligible"], "confidence"] = "Medium"
    bt.loc[bt["eligible"] & ci_excl0 & (bt["balls_p"] >= cfg["ppf"]["high_conf_balls"]), "confidence"] = "High"

    # majority batting position -> role; team = latest season team
    pos = m.groupby(["batter", "match_id"])["batting_position"].first()
    maj_pos = pos.groupby("batter").agg(lambda s: s.mode().iloc[0])
    bt["role"] = maj_pos.map(role_of)
    last_team = m.sort_values("date").groupby("batter")["batting_team"].last()
    bt["team"] = last_team

    bt.to_csv("outputs/batsman_ppf.csv")
    print(f"\nbatsmen with any pressure balls: {len(bt)} | eligible: {int(bt['eligible'].sum())}")
    print("confidence labels:", bt["confidence"].value_counts().to_dict())
    print("\ntop 15 eligible by PPF_adj:")
    cols = ["team", "role", "RAE100_n", "RAE100_p", "PPF", "PPF_adj", "ci_low_adj", "ci_high_adj",
            "balls_p", "balls_n", "confidence"]
    print(bt[bt["eligible"]].sort_values("PPF_adj", ascending=False)[cols].head(15).round(2).to_string())
