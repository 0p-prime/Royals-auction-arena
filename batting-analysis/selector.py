"""Step 8: selection funnel."""
import numpy as np, pandas as pd, yaml

def funnel(bt, cfg, quota=False):
    e = bt[bt["eligible"]].copy()
    e["rank_n"] = e["RAE100_n"].rank(ascending=False)
    e["rank_all"] = e["RAE100_all"].rank(ascending=False)
    e["avg_rank"] = (e["rank_n"] + e["rank_all"]) / 2
    short = e.nsmallest(cfg["funnel"]["shortlist_size"], "avg_rank")
    s2 = short[short["RAE100_p"] >= 0].sort_values(["PPF_adj", "balls_p"], ascending=[False, False])
    if not quota:
        return short, s2.head(cfg["funnel"]["final_size"])
    q = cfg["funnel"]["role_quota"]
    picks, count = [], {"opener": 0, "middle": 0, "finisher": 0}
    for name, r in s2.iterrows():
        if count[r["role"]] < q[{"opener": "openers", "middle": "middle", "finisher": "finishers"}[r["role"]]]:
            picks.append(name); count[r["role"]] += 1
        if len(picks) == cfg["funnel"]["final_size"]:
            break
    if len(picks) < cfg["funnel"]["final_size"]:  # backfill unfilled quota slots by PPF_adj
        for name in s2.index:
            if name not in picks:
                picks.append(name)
            if len(picks) == cfg["funnel"]["final_size"]:
                break
    return short, s2.loc[picks]

def context_2x2(m, names):
    d = m[m["batter"].isin(names)].copy()
    mpi_med, lpi_med = m["MPI_lr"].median(), m["LPI_lr"].median()
    d["mpi_hi"] = d["MPI_lr"] >= mpi_med
    d["lpi_hi"] = d["LPI_lr"] >= lpi_med
    out = d.groupby(["batter", "mpi_hi", "lpi_hi"]).apply(
        lambda x: 100 * x["RAE"].mean(), include_groups=False).unstack(["mpi_hi", "lpi_hi"])
    out.columns = [f"RAE100_MPI{'hi' if a else 'lo'}_LPI{'hi' if b else 'lo'}" for a, b in out.columns]
    return out.round(2)

if __name__ == "__main__":
    cfg = yaml.safe_load(open("config.yaml"))
    bt = pd.read_csv("outputs/batsman_ppf.csv", index_col=0)
    m = pd.read_parquet("data/interim/rae.parquet")
    short, top10 = funnel(bt, cfg, quota=False)
    _, top10_q = funnel(bt, cfg, quota=True)
    cols = ["team", "role", "RAE100_n", "RAE100_p", "PPF_adj", "ci_low_adj", "ci_high_adj",
            "balls_p", "balls_n", "confidence"]
    print("=== TOP 10 (no quota) ===")
    print(top10[cols].round(2).to_string())
    print("\n=== TOP 10 (role quota 3/4/3) ===")
    print(top10_q[cols].round(2).to_string())
    top10.to_csv("outputs/top10_batsmen.csv")
    short.to_csv("outputs/shortlist_35.csv")
    bt.sort_values("PPF_adj", ascending=False).to_csv("outputs/full_ranking.csv")
    ctx = context_2x2(m, short.index)
    ctx.to_csv("outputs/shortlist_2x2_context.csv")
    print("\n2x2 context (shortlist head):")
    print(ctx.head(6).to_string())
    print("\nsaved top10_batsmen.csv, shortlist_35.csv, full_ranking.csv, shortlist_2x2_context.csv")
