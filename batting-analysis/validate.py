"""Step 9: stability diagnostics (descriptive analysis of recorded data, not
future prediction). Temporal 2022-24 -> 2025-26 with FROZEN fits,
split-half reliability, naive baselines, threshold/shrinkage stability."""
import numpy as np, pandas as pd, yaml
import lightgbm as lgb
from scipy.stats import spearmanr
from sklearn.model_selection import StratifiedGroupKFold
from stacker import fit_lr, stacker_design
from mpi_lpi_models import MPI_FEATURES, LPI_RAW, prep
from expected_runs import SIT_FEATURES
from ppf import bucketize, batsman_bucket_stats, eb_shrinkage, role_of
from selector import funnel

cfg = yaml.safe_load(open("config.yaml"))
wmap = cfg["ppf"]["recency_weights"]
m = prep(pd.read_parquet("data/interim/features.parquet"))
m = m[m["is_legal"]].reset_index(drop=True)
rae_full = pd.read_parquet("data/interim/rae.parquet")
m = m.merge(rae_full[["match_id", "innings", "over", "ball_seq", "wicket_penalty"]],
            on=["match_id", "innings", "over", "ball_seq"], how="left")
tr_se, te_se = cfg["validation"]["train_seasons"], cfg["validation"]["test_seasons"]
tr = m[m["season"].isin(tr_se)].reset_index(drop=True)
te = m[m["season"].isin(te_se)].reset_index(drop=True)

def fit_stack(df, seed):
    """Full-train base fits + grouped-OOF stacker; return predictors."""
    X_mpi, X_lpi = df[MPI_FEATURES].to_numpy(float), df[LPI_RAW].to_numpy(float)
    y = df["y_dot_or_out"].to_numpy(); g = df["match_id"].to_numpy()
    cv = StratifiedGroupKFold(5, shuffle=True, random_state=seed)
    oof_mpi, oof_lpi = np.full(len(df), np.nan), np.full(len(df), np.nan)
    for itr, ite in cv.split(X_mpi, y, g):
        oof_mpi[ite] = fit_lr(X_mpi[itr], y[itr], seed).predict_proba(X_mpi[ite])[:, 1]
        oof_lpi[ite] = fit_lr(X_lpi[itr], y[itr], seed).predict_proba(X_lpi[ite])[:, 1]
    from sklearn.linear_model import LogisticRegression
    stk = LogisticRegression(max_iter=1000, random_state=seed)
    stk.fit(stacker_design(oof_mpi, oof_lpi, True), y)
    bm = fit_lr(X_mpi, y, seed); bl = fit_lr(X_lpi, y, seed)
    return bm, bl, stk

def apply_stack(df, bm, bl, stk):
    pm = bm.predict_proba(df[MPI_FEATURES].to_numpy(float))[:, 1]
    pl = bl.predict_proba(df[LPI_RAW].to_numpy(float))[:, 1]
    return 100 * stk.predict_proba(stacker_design(pm, pl, True))[:, 1]

def fit_expected(df, seed):
    X = df[SIT_FEATURES].to_numpy(float)
    reg = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.05, num_leaves=31,
                            random_state=seed, verbose=-1, n_jobs=4).fit(X, df["runs_batter"].to_numpy(float))
    clf = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31,
                             random_state=seed, verbose=-1, n_jobs=4).fit(
        X, (df["player_dismissed"] == df["batter"]).to_numpy(int))
    return reg, clf

def penalty_grid(train_df):
    """New-batsman expected stint runs by arrival (over, wkts), from train matches only."""
    st = train_df.groupby(["match_id", "innings", "batter"], sort=False).agg(
        arr_over=("over", "min"), arr_wkts=("wkts_before", "min"),
        stint_runs=("runs_batter", "sum")).reset_index()
    st = st[st["arr_wkts"] <= 9]
    cell = st.groupby(["arr_over", "arr_wkts"])["stint_runs"].mean()
    ov = st.groupby("arr_over")["stint_runs"].mean()
    glob = st["stint_runs"].mean()
    def lookup(o, w):
        if w > 9: return 0.0
        v = cell.get((o, w), np.nan)
        if np.isnan(v): v = ov.get(o, glob)
        return v
    return lookup

def compute_rae(df, reg, clf, pen_lookup):
    X = df[SIT_FEATURES].to_numpy(float)
    e_runs = reg.predict(X)
    e_out = clf.predict_proba(X)[:, 1]
    pen = np.array([pen_lookup(o, w + 1) for o, w in zip(df["over"], df["wkts_before"])])
    dis = (df["player_dismissed"] == df["batter"]).to_numpy(float)
    return df["runs_batter"].to_numpy(float) - e_runs - pen * (dis - e_out)

def ppf_table(df, wmap_local):
    p = batsman_bucket_stats(df, df["bucket"] == "pressure", wmap_local).add_suffix("_p")
    n = batsman_bucket_stats(df, df["bucket"] == "normal", wmap_local).add_suffix("_n")
    ov = batsman_bucket_stats(df, pd.Series(True, index=df.index), wmap_local).add_suffix("_all")
    bt = p.join(n, how="inner").join(ov[["RAE100_all"]])
    bt["PPF"] = bt["RAE100_p"] - bt["RAE100_n"]
    bt["PPF_fallback"] = bt["balls_p"] / (bt["balls_p"] + 60) * bt["PPF"]
    return bt

print("=== temporal diagnostic: fit frozen on 2022-24, apply to 2025-26 ===", flush=True)
from stacker import nested_oof_all
tr["BPI"] = 100 * nested_oof_all(tr, cfg["seed"])["full"]   # train BPI: within-train nested OOF
bm, bl, stk = fit_stack(tr, cfg["seed"])
pen = penalty_grid(tr)
# train RAE uses within-train GROUPED OOF predictions (no in-sample fit into train PPF);
# test RAE uses models fitted on all of train, frozen.
from sklearn.model_selection import GroupKFold
def fit_expected_oof(df, seed):
    X = df[SIT_FEATURES].to_numpy(float)
    y_r = df["runs_batter"].to_numpy(float)
    y_o = (df["player_dismissed"] == df["batter"]).to_numpy(int)
    oof_r, oof_o = np.full(len(df), np.nan), np.full(len(df), np.nan)
    for itr, ite in GroupKFold(5).split(X, y_r, df["match_id"].to_numpy()):
        reg = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.05, num_leaves=31,
                                random_state=seed, verbose=-1, n_jobs=4).fit(X[itr], y_r[itr])
        clf = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31,
                                 random_state=seed, verbose=-1, n_jobs=4).fit(X[itr], y_o[itr])
        oof_r[ite] = reg.predict(X[ite])
        oof_o[ite] = clf.predict_proba(X[ite])[:, 1]
    return oof_r, oof_o
tr["_E_runs_oof"], tr["_E_out_oof"] = fit_expected_oof(tr, cfg["seed"])
reg, clf = fit_expected(tr, cfg["seed"])
te["BPI"] = apply_stack(te, bm, bl, stk)   # test scored FROZEN (base fit on all train, stacker on train grouped-OOF)
te["RAE"] = compute_rae(te, reg, clf, pen)
_dis = (tr["player_dismissed"] == tr["batter"]).to_numpy(float)
_pen_tr = np.array([pen(o, w + 1) for o, w in zip(tr["over"], tr["wkts_before"])])
tr["RAE"] = tr["runs_batter"].to_numpy(float) - tr["_E_runs_oof"] - _pen_tr * (_dis - tr["_E_out_oof"])
# frozen bucket edges from train distribution
hi = tr["BPI"].quantile(1 - cfg["bpi"]["pressure_top_q"])
lo = tr["BPI"].quantile(cfg["bpi"]["normal_bottom_q"])
for d in (tr, te):
    d["bucket"] = "drop"
    d.loc[d["BPI"] >= hi, "bucket"] = "pressure"
    d.loc[d["BPI"] <= lo, "bucket"] = "normal"
w_train = {k: (1.0 if int(k) in te_se else 0.6) for k in ["2022", "2023", "2024", "2025", "2026"]}
bt_tr = ppf_table(tr, w_train)
tr_elig = bt_tr[(bt_tr["balls_p"] >= cfg["funnel"]["min_pressure_balls"]) & (bt_tr["balls_n"] >= cfg["funnel"]["min_normal_balls"])]
p_te = batsman_bucket_stats(te, te["bucket"] == "pressure", w_train).add_suffix("_p")
cmp = tr_elig.join(p_te[["RAE100_p", "balls_p"]], how="inner", rsuffix="_te").dropna(subset=["RAE100_p"])
cmp = cmp[cmp["balls_p_te"] >= cfg["validation"].get("min_test_pressure_balls", 20)]
cmp[["PPF_fallback", "RAE100_p"]].to_csv("outputs/validation_scatter.csv")
n_te = batsman_bucket_stats(te, te["bucket"] == "normal", w_train).add_suffix("_n")
cmp2 = tr_elig.drop(columns=["RAE100_p", "balls_p"]).join(p_te[["RAE100_p", "balls_p"]].rename(columns={"RAE100_p": "RAE100_p_te", "balls_p": "balls_p_te"}), how="inner").join(n_te[["RAE100_n"]].rename(columns={"RAE100_n": "RAE100_n_te"}))
cmp2 = cmp2.dropna(subset=["RAE100_p_te", "RAE100_n_te"])
cmp2 = cmp2[cmp2["balls_p_te"] >= cfg["validation"].get("min_test_pressure_balls", 20)]
cmp2["PPF_test"] = cmp2["RAE100_p_te"] - cmp2["RAE100_n_te"]
rho_ppf, p_ppf = spearmanr(cmp2["PPF_fallback"], cmp2["PPF_test"])
print(f"train PPF vs TEST PPF (descriptive): Spearman={rho_ppf:.3f} (p={p_ppf:.3f}, n={len(cmp2)})")
print(f"mean PPF train={cmp2['PPF_fallback'].mean():.2f} vs test={cmp2['PPF_test'].mean():.2f}")
rho, pval = spearmanr(cmp["PPF_fallback"], cmp["RAE100_p"])
print(f"train PPF vs test pressure RAE100: Spearman={rho:.3f} (p={pval:.3f}, n={len(cmp)} batsmen)")
if rho < cfg["validation"]["noise_corr_threshold"]:
    print("WARNING: correlation < 0.2 - PPF is mostly unstable across periods; list is indicative only.")

print("\n=== split-half reliability (alternate matches, full data) ===")
full = pd.read_parquet("data/interim/rae.parquet")   # reported estimator: nested-OOF BPI + OOF RAE
full["bucket"] = bucketize(full, cfg["bpi"]["pressure_top_q"], cfg["bpi"]["normal_bottom_q"])
mnum = {mid: i for i, mid in enumerate(sorted(full["match_id"].unique()))}
full["half"] = full["match_id"].map(mnum) % 2
def ppf_adj_half(d):
    bt_h = ppf_table(d, wmap)
    mb = d[d["bucket"].isin(["pressure", "normal"])].copy()
    mb["w"] = mb["season"].map(lambda s: 1.0 if int(s) in (2025, 2026) else 0.6)
    mb["wRAE"] = mb["w"] * mb["RAE"]
    agg = mb.groupby(["batter", "match_id", "bucket"]).agg(wRAE=("wRAE", "sum"), w=("w", "sum")).reset_index()
    rng = np.random.RandomState(7)
    boot = {}
    for batter, dd in agg.groupby("batter"):
        dp = dd[dd["bucket"] == "pressure"]; dn = dd[dd["bucket"] == "normal"]
        mall = np.union1d(dp["match_id"].unique(), dn["match_id"].unique())
        if len(dp) < 3 or len(dn) < 3: continue
        wp = dp.set_index("match_id")[["wRAE", "w"]]; wn = dn.set_index("match_id")[["wRAE", "w"]]
        vals = []
        for row in rng.randint(0, len(mall), (200, len(mall))):
            ms = mall[row]
            sp = wp.reindex(ms).fillna(0.0); sn = wn.reindex(ms).fillna(0.0)
            if sp["w"].sum() > 0 and sn["w"].sum() > 0:
                vals.append(100 * sp["wRAE"].sum() / sp["w"].sum() - 100 * sn["wRAE"].sum() / sn["w"].sum())
        if vals: boot[batter] = np.var(vals)
    wv = pd.Series(boot)
    bt_h = bt_h.join(wv.rename("within_var"))
    bt_h["within_var"] = bt_h["within_var"].fillna(bt_h["PPF"].var())
    adj, _ = eb_shrinkage(bt_h["PPF"].to_numpy(), bt_h["within_var"].to_numpy())
    return pd.Series(adj, index=bt_h.index)
halves = []
for h in (0, 1):
    d = full[full["half"] == h]
    halves.append(ppf_adj_half(d).rename(f"h{h}"))
sh = pd.concat(halves, axis=1, join="inner").dropna()
rho_h, p_h = spearmanr(sh["h0"], sh["h1"])
print(f"split-half ALL batsmen: Spearman={rho_h:.3f} (p={p_h:.3f}, n={len(sh)})")
elig_full = sh.index.to_series().map(
    (full.groupby("batter").apply(lambda x: ((x["bucket"] == "pressure").sum() >= 60)
     and ((x["bucket"] == "normal").sum() >= 200), include_groups=False))).fillna(False)
sh_e = sh[elig_full]
rho_he, p_he = spearmanr(sh_e["h0"], sh_e["h1"])
print(f"split-half ELIGIBLE only: Spearman={rho_he:.3f} (p={p_he:.3f}, n={len(sh_e)})")

print("\n=== naive baselines vs funnel top10 (test period pressure RAE100) ===")
bt_full = ppf_table(full, wmap)
pos = full.groupby(["batter", "match_id"])["batting_position"].first().groupby("batter").agg(lambda s: s.mode().iloc[0])
bt_full["role"] = pos.map(role_of)
bt_full["eligible"] = ((bt_full["balls_p"] >= cfg["funnel"]["min_pressure_balls"])
                       & (bt_full["balls_n"] >= cfg["funnel"]["min_normal_balls"])
                       & full.groupby("batter")["season"].max().isin(cfg["funnel"]["active_seasons"]).reindex(bt_full.index))
_, top10 = funnel(bt_full.rename(columns={"PPF_fallback": "PPF_adj"}), cfg)
death = full[(full["phase_death"] == 1)]
dsr = death.groupby("batter").agg(sr=("runs_batter", lambda s: 100 * s.sum() / len(s)), n=("runs_batter", "size"))
naive_death = dsr[dsr["n"] >= 100].nlargest(10, "sr").index
naive_rae = bt_full[bt_full["eligible"]].nlargest(10, "RAE100_all").index
te_pressure = te[te["bucket"] == "pressure"]
def test_perf(names):
    d = te_pressure[te_pressure["batter"].isin(names)]
    return d.groupby("batter")["RAE"].mean().mean() * 100
print(f"our top10 mean test pressure RAE100: {test_perf(top10.index):.2f}")
print(f"naive death-SR top10: {test_perf(naive_death):.2f} | naive overall-RAE top10: {test_perf(naive_rae):.2f}")
print("overlap our top10 vs naive death-SR:", len(set(top10.index) & set(naive_death)),
      "| vs naive overall-RAE:", len(set(top10.index) & set(naive_rae)))

print("\n=== stability: bucket thresholds + shrinkage K ===")
for tq, bq in [(s["top"], s["bottom"]) for s in cfg["bpi"]["sensitivity"]]:
    full["bucket"] = bucketize(full, tq, bq)
    bt_s = ppf_table(full, wmap)
    bt_s["role"] = pos.map(role_of)
    bt_s["eligible"] = bt_full["eligible"].reindex(bt_s.index).fillna(False)
    _, t10s = funnel(bt_s.rename(columns={"PPF_fallback": "PPF_adj"}), cfg)
    print(f"split {tq}/{bq}: top10 overlap with base = {len(set(t10s.index) & set(top10.index))}/10")
full["bucket"] = bucketize(full, cfg["bpi"]["pressure_top_q"], cfg["bpi"]["normal_bottom_q"])
bt_k = ppf_table(full, wmap)
for K in cfg["ppf"]["shrinkage_k_sensitivity"]:
    bt_k["PPF_adj"] = bt_k["balls_p"] / (bt_k["balls_p"] + K) * bt_k["PPF"]
    bt_k["role"] = pos.map(role_of)
    bt_k["eligible"] = bt_full["eligible"].reindex(bt_k.index).fillna(False)
    _, t10k = funnel(bt_k, cfg)
    print(f"K={K}: top10 overlap with base = {len(set(t10k.index) & set(top10.index))}/10")
