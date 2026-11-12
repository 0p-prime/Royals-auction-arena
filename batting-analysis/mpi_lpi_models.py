"""Step 3: MPI (match-pressure) and LPI (local-pressure) models.
Grouped 5-fold CV by match_id (StratifiedGroupKFold, fixed seed); OOF preds for every ball."""
import numpy as np, pandas as pd, yaml
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import roc_auc_score, log_loss, brier_score_loss
import lightgbm as lgb

MPI_FEATURES = ["crr", "rrr", "rr_crr_gap", "is_chase", "wickets_lost", "wickets_5plus",
                "balls_left", "match_importance", "par_diff", "par_missing",
                "phase_powerplay", "phase_middle", "phase_death"]
LPI_RAW = ["dots_last12", "wkts_last18", "settledness", "bowler_eco", "bowler_sr", "batting_position"]

def prep(df):
    m = df[df["is_legal"] & ~df["dls_chase"]].copy()
    m = pd.get_dummies(m, columns=["phase"], dtype=int)
    for p in ["phase_powerplay", "phase_middle", "phase_death"]:
        if p not in m.columns:
            m[p] = 0
    return m

def fit_oof(m, features, target, seed, scale_conts=()):
    X = m[features].to_numpy(float)
    y = m[target].to_numpy()
    groups = m["match_id"].to_numpy()
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    oof_lr = np.full(len(m), np.nan)
    oof_gbm = np.full(len(m), np.nan)
    for tr, te in cv.split(X, y, groups):
        lr = Pipeline([("sc", StandardScaler()), ("clf", LogisticRegression(max_iter=1000, random_state=seed))])
        lr.fit(X[tr], y[tr])
        oof_lr[te] = lr.predict_proba(X[te])[:, 1]
        gbm = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31,
                                 random_state=seed, verbose=-1, n_jobs=4)
        gbm.fit(X[tr], y[tr])
        oof_gbm[te] = gbm.predict_proba(X[te])[:, 1]
    return oof_lr, oof_gbm

def metrics(y, p):
    return {"auc": roc_auc_score(y, p), "logloss": log_loss(y, p), "brier": brier_score_loss(y, p)}

if __name__ == "__main__":
    cfg = yaml.safe_load(open("config.yaml"))
    df = pd.read_parquet("data/interim/features.parquet")
    m = prep(df)
    y = m["y_dot_or_out"].to_numpy()
    res = {}
    for name, feats in [("MPI", MPI_FEATURES), ("LPI", LPI_RAW)]:
        oof_lr, oof_gbm = fit_oof(m, feats, "y_dot_or_out", cfg["seed"])
        m[f"{name}_lr"], m[f"{name}_gbm"] = oof_lr, oof_gbm
        res[f"{name}_lr"] = metrics(y, oof_lr)
        res[f"{name}_gbm"] = metrics(y, oof_gbm)
    for k, v in res.items():
        print(k, {kk: round(vv, 4) for kk, vv in v.items()})
    # robustness: how do primary-target scores rank the secondary target?
    y6 = m["y_out_6"].to_numpy()
    for name in ["MPI", "LPI"]:
        print(f"{name} vs y_out_6 AUC: lr={roc_auc_score(y6, m[name+'_lr']):.4f} gbm={roc_auc_score(y6, m[name+'_gbm']):.4f}")
    # feature importance: logistic coefficients + gbm importances (full-fit for display only)
    for name, feats in [("MPI", MPI_FEATURES), ("LPI", LPI_RAW)]:
        X = m[feats].to_numpy(float)
        lr = Pipeline([("sc", StandardScaler()), ("clf", LogisticRegression(max_iter=1000, random_state=cfg["seed"]))])
        lr.fit(X, y)
        coef = pd.Series(lr.named_steps["clf"].coef_[0], index=feats).sort_values(key=abs, ascending=False)
        gbm = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31,
                                 random_state=cfg["seed"], verbose=-1, n_jobs=4).fit(X, y)
        imp = pd.Series(gbm.feature_importances_, index=feats).sort_values(ascending=False)
        print(f"\n{name} logistic coefs:\n{coef.round(3)}\n{name} gbm importance top5: {list(imp.head(5).index)}")
    m.to_parquet("data/interim/oof_base.parquet", index=False)
    print("\nsaved data/interim/oof_base.parquet", len(m), "rows")
