"""Step 4B: relation between MPI, LPI and BPI + calibration/monotonicity checks."""
import numpy as np, pandas as pd, yaml, json
from sklearn.linear_model import LogisticRegression
from scipy.stats import pearsonr, spearmanr
import statsmodels.api as sm
from stacker import logit, stacker_design

cfg = yaml.safe_load(open("config.yaml"))
m = pd.read_parquet("data/interim/bpi.parquet")
base = pd.read_parquet("data/interim/oof_base.parquet")
m["MPI_lr"], m["LPI_lr"] = base["MPI_lr"], base["LPI_lr"]
y = m["y_dot_or_out"].to_numpy()

# stacker fit on full-data grouped OOF (interpretation model)
X = stacker_design(m["MPI_lr"].to_numpy(), m["LPI_lr"].to_numpy(), True)
Xs = sm.add_constant(X)
fit = sm.Logit(y, Xs).fit(disp=0, cov_type="cluster", cov_kwds={"groups": m["match_id"].to_numpy()})
print("=== Stacker coefficients (full-data grouped OOF, interpretation) ===")
for name, b, se, p in zip(["const", "b1_logitMPI", "b2_logitLPI", "b3_interaction"],
                          fit.params, fit.bse, fit.pvalues):
    print(f"{name}: {b:.4f} (SE {se:.4f}, p={p:.2e})")

pr, pp = pearsonr(m["MPI_lr"], m["LPI_lr"])
sr, sp = spearmanr(m["MPI_lr"], m["LPI_lr"])
print(f"\nMPI-LPI correlation: Pearson={pr:.3f} (p={pp:.1e}), Spearman={sr:.3f} (p={sp:.1e})")

# decile monotonicity of BPI
m["bpi_dec"] = pd.qcut(m["BPI"], 10, labels=False)
dec = m.groupby("bpi_dec")["y_dot_or_out"].agg(["mean", "count"])
print("\n=== BPI decile vs observed dot-or-out rate ===")
print(dec.round(4))
mono = np.all(np.diff(dec["mean"].to_numpy()) > 0)
spr = spearmanr(np.arange(10), dec["mean"]).statistic
print(f"strictly monotonic: {mono} | Spearman(decile, rate)={spr:.4f}")
viol = int((np.diff(dec["mean"].to_numpy()) <= 0).sum())
print(f"adjacent non-increases: {viol} of 9")

# calibration: predicted vs observed in 10 bins of predicted prob
m["prob_bin"] = pd.qcut(m["BPI_prob"], 10, labels=False)
cal = m.groupby("prob_bin").agg(pred=("BPI_prob", "mean"), obs=("y_dot_or_out", "mean"), n=("y_dot_or_out", "size"))
print("\n=== Calibration (predicted vs observed) ===")
print(cal.round(4))
cal.to_csv("outputs/calibration.csv"); dec.to_csv("outputs/bpi_deciles.csv")

# heatmap: MPI decile x LPI decile observed rate
m["mpi_dec"] = pd.qcut(m["MPI_lr"], 10, labels=False)
m["lpi_dec"] = pd.qcut(m["LPI_lr"], 10, labels=False)
hm = m.pivot_table(index="lpi_dec", columns="mpi_dec", values="y_dot_or_out", aggfunc="mean")
hm_n = m.pivot_table(index="lpi_dec", columns="mpi_dec", values="y_dot_or_out", aggfunc="size")
print("\n=== MPI decile x LPI decile observed rate (min cell n=%d) ===" % hm_n.min().min())
print(hm.round(3))
hm.to_csv("outputs/mpi_lpi_heatmap.csv")
# stacked surface agreement: mean BPI_prob in same cells
hm_bpi = m.pivot_table(index="lpi_dec", columns="mpi_dec", values="BPI_prob", aggfunc="mean")
corr_cells = np.corrcoef(hm.to_numpy().ravel(), hm_bpi.to_numpy().ravel())[0, 1]
print(f"heatmap vs stacked-surface cell correlation: {corr_cells:.3f}")

# BPI vs MPI-only disagreements > 20 points
mpi100 = 100 * m["MPI_lr"]
diff = (m["BPI"] - mpi100).abs()
print(f"\n|BPI - 100xMPI| > 20 pts: {(diff > 20).mean() * 100:.2f}% of balls ({(diff > 20).sum()})")
ex = m.nlargest(3, "BPI")[["match_id", "date", "innings", "over", "batter", "bowler",
                            "wickets_lost", "balls_left", "rrr", "BPI"]]
ex2 = m.loc[diff.nlargest(3).index, ["match_id", "date", "innings", "over", "batter", "bowler",
                                      "wickets_lost", "balls_left", "rrr", "settledness", "dots_last12", "BPI"]]
ex2["MPI_x100"] = mpi100.loc[diff.nlargest(3).index]
print("\n3 largest BPI-vs-MPI disagreements:")
print(ex2.round(2).to_string())
m.to_parquet("data/interim/bpi.parquet", index=False)
