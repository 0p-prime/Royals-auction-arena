"""Step 5: player-independent expected-performance model.
E[runs] and E[dismissal] per ball from SITUATION features only (no batter id,
no batter hand/bowler type - not available in Cricsheet data).
Match-grouped OOF predictions. Centered RAE:
RAE = runs_batter - E[runs] - wicket_penalty x (dismissal - E[dismissal]).
wicket_penalty = expected remaining team runs from that (over, wickets) state,
estimated leave-one-match-out."""
import numpy as np, pandas as pd, yaml
import lightgbm as lgb
from sklearn.model_selection import StratifiedGroupKFold, GroupKFold
from sklearn.metrics import mean_absolute_error, log_loss

SIT_FEATURES = ["over", "wkts_before", "rrr", "crr", "balls_left", "is_chase",
                "phase_powerplay", "phase_middle", "phase_death"]

def loo_remaining_runs(df):
    """Expected runs a NEW BATSMAN adds from arrival (over, wickets) state until his
    own dismissal or innings end. PURE leave-one-match-out CELL lookup keyed on
    (over, wkts+1) - no dependence on what actually happened after this ball."""
    d = df.copy()
    st = d.groupby(["match_id", "innings", "batter"], sort=False).agg(
        arr_over=("over", "min"), arr_wkts=("wkts_before", "min"),
        stint_runs=("runs_batter", "sum")).reset_index()
    st = st[st["arr_wkts"] <= 9]
    glob_all = st["stint_runs"].mean()
    out = pd.Series(np.nan, index=d.index)
    for mid, sub in d.groupby("match_id"):
        hist = st[st["match_id"] != mid]
        cell = hist.groupby(["arr_over", "arr_wkts"])["stint_runs"].mean()
        ov = hist.groupby("arr_over")["stint_runs"].mean()
        key = list(zip(sub["over"], sub["wkts_before"] + 1))
        val = [0.0 if w > 9 else cell.get((o, w), np.nan) for o, w in key]
        val = [ov.get(o, glob_all) if (isinstance(v, float) and np.isnan(v)) else v
               for (o, w), v in zip(key, val)]
        out.loc[sub.index] = val
    d["wicket_penalty"] = out.fillna(glob_all)
    return d[["match_id", "innings", "over", "ball_seq", "wicket_penalty"]]

def fit_expected(m, seed):
    X = m[SIT_FEATURES].to_numpy(float)
    y_runs = m["runs_batter"].to_numpy(float)
    y_out = (m["player_dismissed"] == m["batter"]).to_numpy(int)
    groups = m["match_id"].to_numpy()
    cv = GroupKFold(n_splits=5)
    oof_runs = np.full(len(m), np.nan)
    oof_out = np.full(len(m), np.nan)
    for tr, te in cv.split(X, y_runs, groups):
        reg = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.05, num_leaves=31,
                                random_state=seed, verbose=-1, n_jobs=4)
        reg.fit(X[tr], y_runs[tr])
        oof_runs[te] = reg.predict(X[te])
        clf = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31,
                                 random_state=seed, verbose=-1, n_jobs=4)
        clf.fit(X[tr], y_out[tr])
        oof_out[te] = clf.predict_proba(X[te])[:, 1]
    return oof_runs, oof_out

if __name__ == "__main__":
    cfg = yaml.safe_load(open("config.yaml"))
    m = pd.read_parquet("data/interim/bpi.parquet")
    m = m[m["is_legal"] & ~m["dls_chase"]].reset_index(drop=True)
    print("leave-one-match-out wicket penalty...", flush=True)
    pen = loo_remaining_runs(m)
    m = m.merge(pen, on=["match_id", "innings", "over", "ball_seq"], how="left")
    print("expected runs/dismissal OOF...", flush=True)
    m["E_runs"], m["E_dismissal"] = fit_expected(m, cfg["seed"])
    y_out = ((m["player_dismissed"] == m["batter"]) & (~m["dismissal_kind"].isin(["retired hurt", "retired out"]))).astype(int)
    print(f"E[runs] MAE: {mean_absolute_error(m['runs_batter'], m['E_runs']):.4f}")
    print(f"E[dismissal] logloss: {log_loss(y_out, m['E_dismissal']):.4f} (base rate {y_out.mean():.4f})")
    m["dismissal"] = y_out
    m["RAE"] = (m["runs_batter"] - m["E_runs"]
                - m["wicket_penalty"] * (m["dismissal"] - m["E_dismissal"]))
    print(f"mean RAE: {m['RAE'].mean():.6f} (check ~0) | sd {m['RAE'].std():.3f}")
    print("\nwicket_penalty by phase:")
    print(m.groupby(["phase_powerplay", "phase_middle", "phase_death"]).size())
    ph = np.where(m["phase_powerplay"] == 1, "powerplay", np.where(m["phase_middle"] == 1, "middle", "death"))
    print(m.groupby(ph)["wicket_penalty"].mean().round(2).to_dict())
    m.to_parquet("data/interim/rae.parquet", index=False)
    print("saved data/interim/rae.parquet", len(m))
