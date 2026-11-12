"""Step 4: stacked BPI with nested, group-aware validation.
Outer grouped 5-fold by match_id: base models get inner OOF on outer-train,
stacker fit on inner OOF only, then scored on outer-test (frozen within fold).
BPI = 100 x stacked probability. No ball is ever scored by a model that saw its match."""
import numpy as np, pandas as pd, yaml
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import roc_auc_score, log_loss, brier_score_loss
from mpi_lpi_models import MPI_FEATURES, LPI_RAW, prep

def logit(p, eps=1e-4):
    p = np.clip(p, eps, 1 - eps)
    return np.log(p / (1 - p))

def fit_lr(X, y, seed):
    lr = Pipeline([("sc", StandardScaler()), ("clf", LogisticRegression(max_iter=1000, random_state=seed))])
    return lr.fit(X, y)

def stacker_design(lp, ll, interaction=True):
    cols = [logit(lp), logit(ll)]
    if interaction:
        cols.append(logit(lp) * logit(ll))
    return np.column_stack(cols)

def nested_oof(m, seed, interaction=True):
    y = m["y_dot_or_out"].to_numpy()
    groups = m["match_id"].to_numpy()
    outer = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    bpi = np.full(len(m), np.nan)
    for tr_o, te_o in outer.split(np.zeros(len(m)), y, groups):
        Xtr_mpi = m.iloc[tr_o][MPI_FEATURES].to_numpy(float)
        Xtr_lpi = m.iloc[tr_o][LPI_RAW].to_numpy(float)
        ytr = y[tr_o]
        gtr = groups[tr_o]
        inner = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
        ioof_mpi = np.full(len(tr_o), np.nan)
        ioof_lpi = np.full(len(tr_o), np.nan)
        for tr_i, te_i in inner.split(Xtr_mpi, ytr, gtr):
            ioof_mpi[te_i] = fit_lr(Xtr_mpi[tr_i], ytr[tr_i], seed).predict_proba(Xtr_mpi[te_i])[:, 1]
            ioof_lpi[te_i] = fit_lr(Xtr_lpi[tr_i], ytr[tr_i], seed).predict_proba(Xtr_lpi[te_i])[:, 1]
        stk = LogisticRegression(max_iter=1000, random_state=seed)
        stk.fit(stacker_design(ioof_mpi, ioof_lpi, interaction), ytr)
        mpi_te = fit_lr(Xtr_mpi, ytr, seed).predict_proba(m.iloc[te_o][MPI_FEATURES].to_numpy(float))[:, 1]
        lpi_te = fit_lr(Xtr_lpi, ytr, seed).predict_proba(m.iloc[te_o][LPI_RAW].to_numpy(float))[:, 1]
        bpi[te_o] = stk.predict_proba(stacker_design(mpi_te, lpi_te, interaction))[:, 1]
    return bpi

def nested_oof_all(m, seed):
    """One nested pass; returns dict of outer-OOF predictions for each stack variant."""
    y = m["y_dot_or_out"].to_numpy()
    groups = m["match_id"].to_numpy()
    outer = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    out = {"additive": np.full(len(m), np.nan), "full": np.full(len(m), np.nan)}
    for tr_o, te_o in outer.split(np.zeros(len(m)), y, groups):
        Xtr_mpi = m.iloc[tr_o][MPI_FEATURES].to_numpy(float)
        Xtr_lpi = m.iloc[tr_o][LPI_RAW].to_numpy(float)
        ytr, gtr = y[tr_o], groups[tr_o]
        inner = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
        ioof_mpi = np.full(len(tr_o), np.nan)
        ioof_lpi = np.full(len(tr_o), np.nan)
        for tr_i, te_i in inner.split(Xtr_mpi, ytr, gtr):
            ioof_mpi[te_i] = fit_lr(Xtr_mpi[tr_i], ytr[tr_i], seed).predict_proba(Xtr_mpi[te_i])[:, 1]
            ioof_lpi[te_i] = fit_lr(Xtr_lpi[tr_i], ytr[tr_i], seed).predict_proba(Xtr_lpi[te_i])[:, 1]
        mpi_te = fit_lr(Xtr_mpi, ytr, seed).predict_proba(m.iloc[te_o][MPI_FEATURES].to_numpy(float))[:, 1]
        lpi_te = fit_lr(Xtr_lpi, ytr, seed).predict_proba(m.iloc[te_o][LPI_RAW].to_numpy(float))[:, 1]
        for name, inter in [("additive", False), ("full", True)]:
            stk = LogisticRegression(max_iter=1000, random_state=seed)
            stk.fit(stacker_design(ioof_mpi, ioof_lpi, inter), ytr)
            out[name][te_o] = stk.predict_proba(stacker_design(mpi_te, lpi_te, inter))[:, 1]
    return out

if __name__ == "__main__":
    cfg = yaml.safe_load(open("config.yaml"))
    m = prep(pd.read_parquet("data/interim/features.parquet"))
    y = m["y_dot_or_out"].to_numpy()
    print("nested outer-OOF pass (base fits + 2 stackers per fold)...", flush=True)
    res = nested_oof_all(m, cfg["seed"])
    m["BPI_prob"] = res["full"]
    m["BPI"] = 100 * res["full"]
    # ablation table: MPI-only / LPI-only from step-3 grouped OOF, stacks from nested OOF
    base = pd.read_parquet("data/interim/oof_base.parquet")
    abl = {
        "MPI_only": base["MPI_lr"].to_numpy(),
        "LPI_only": base["LPI_lr"].to_numpy(),
        "additive_stack": res["additive"],
        "full_stack": res["full"],
    }
    for k, p in abl.items():
        print(f"{k}: AUC={roc_auc_score(y, p):.4f} logloss={log_loss(y, p):.4f} brier={brier_score_loss(y, p):.4f}")
    m.to_parquet("data/interim/bpi.parquet", index=False)
    print("saved data/interim/bpi.parquet")
