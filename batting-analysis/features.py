"""Step 1+2: pre-ball state features (zero leakage) and targets.
Every feature uses only information available BEFORE the current delivery.
Chronology: par scores and bowler threat use expanding windows over matches
with strictly earlier dates only."""
import numpy as np
import pandas as pd
from data_loader import load_config

BOWLER_WICKET_KINDS = {"caught", "bowled", "lbw", "caught and bowled", "stumped", "hit wicket"}

def phase_of(over, scheduled_overs):
    pp_end = np.ceil(0.30 * scheduled_overs)      # 20 -> 6
    death_start = np.floor(0.75 * scheduled_overs)  # 20 -> 15
    if over < pp_end:
        return "powerplay"
    if over < death_start:
        return "middle"
    return "death"

def build_features(df, cfg):
    df["dls_chase"] = (df["dls_match"]) & (df["innings"] == 2)
    # DLS chase innings have no revised target in Cricsheet -> rrr would be false;
    # excluded from the modeling frame (count disclosed in logs)
    df = df.sort_values(["date", "match_id", "innings", "over", "ball_seq"]).reset_index(drop=True)
    df["row_id"] = np.arange(len(df))
    total_balls = df["scheduled_overs"] * 6

    g = df.groupby(["match_id", "innings"], sort=False)
    df["runs_before"] = g["runs_batter"].transform(lambda s: (s + df.loc[s.index, "runs_extras"]).cumsum().shift(fill_value=0)).astype(int)
    df["wkts_before"] = g["wicket"].transform(lambda s: s.cumsum().shift(fill_value=0)).astype(int)
    df["legal_before"] = g["is_legal"].transform(lambda s: s.cumsum().shift(fill_value=0)).astype(int)

    # innings targets (for chases): first-innings total per match
    inn_tot = df.groupby(["match_id", "innings"]).apply(
        lambda x: (x["runs_batter"] + x["runs_extras"]).sum(), include_groups=False).unstack()
    inn_tot.columns = [f"inn{c}_total" for c in inn_tot.columns]
    df = df.merge(inn_tot.reset_index(), on="match_id", how="left")
    df["target_score"] = np.where(df["innings"] == 2, df["inn1_total"] + 1, np.nan)

    overs_done = df["legal_before"] / 6.0
    overs_left = (total_balls - df["legal_before"]) / 6.0
    df["balls_left"] = (total_balls - df["legal_before"]).astype(int)
    df["crr"] = np.where(overs_done > 0, df["runs_before"] / overs_done, 0.0)
    runs_needed = df["target_score"] - df["runs_before"]
    df["rrr"] = np.where((df["innings"] == 2) & (overs_left > 0), runs_needed / overs_left, 0.0)
    df["rrr"] = df["rrr"].clip(lower=0)
    df["rr_crr_gap"] = np.where(df["innings"] == 2, ((df["rrr"] - df["crr"]) / 12.0).clip(0, 1), 0.0)
    df["is_chase"] = (df["innings"] == 2).astype(int)

    df["wickets_lost"] = df["wkts_before"]
    df["wickets_5plus"] = (df["wkts_before"] >= 5).astype(int)
    df["phase"] = [phase_of(o, s) for o, s in zip(df["over"], df["scheduled_overs"])]
    df["match_importance"] = np.where(df["event_stage"] == "league", 0.5, 1.0)

    # --- local pressure: rolling over LEGAL deliveries only, within innings ---
    legal = df[df["is_legal"]].copy()
    lg = legal.groupby(["match_id", "innings"], sort=False)
    legal["dot_flag"] = (legal["runs_batter"] == 0).astype(int)
    legal["dots_last12"] = lg["dot_flag"].transform(lambda s: s.rolling(12, min_periods=1).sum().shift(fill_value=0)) / 12.0
    legal["wkts_last18"] = lg["wicket"].transform(lambda s: s.rolling(18, min_periods=1).sum().shift(fill_value=0)) / 3.0

    # settledness: legal balls faced by this batter in this innings stint before this ball
    legal["stint_break"] = ((legal["player_dismissed"] == legal["batter"]) &
                            legal["dismissal_kind"].isin(["retired hurt", "retired out"])).astype(int)
    legal["stint_id"] = legal.groupby(["match_id", "innings", "batter"], sort=False)["stint_break"].cumsum()
    legal["batter_balls_before"] = legal.groupby(["match_id", "innings", "batter", "stint_id"], sort=False).cumcount()
    legal["settledness"] = 1 - np.minimum(legal["batter_balls_before"], 30) / 30.0

    # batting position: order of first appearance AT THE CREASE (as batter or
    # non-striker) in the innings; retired-hurt returns keep their original position
    app = pd.concat([
        df[["match_id", "innings", "batter", "row_id"]].rename(columns={"batter": "player"}),
        df[["match_id", "innings", "non_striker", "row_id"]].rename(columns={"non_striker": "player"}),
    ])
    first_app = app.groupby(["match_id", "innings", "player"], sort=False)["row_id"].min().reset_index()
    first_app["batting_position"] = first_app.groupby(["match_id", "innings"])["row_id"].rank(method="first").astype(int)
    legal = legal.merge(first_app.rename(columns={"player": "batter"})[["match_id", "innings", "batter", "batting_position"]],
                        on=["match_id", "innings", "batter"], how="left")

    df = df.merge(legal[["row_id", "dots_last12", "wkts_last18", "settledness",
                         "batter_balls_before", "batting_position"]], on="row_id", how="left")

    # --- par score (1st innings): avg final score at (over, wickets) state, earlier dates only ---
    df = add_par_features(df)

    # --- bowler threat: expanding pre-match stats ---
    df = add_bowler_threat(df, cfg)
    return df

def add_par_features(df):
    inn1 = df[df["innings"] == 1]
    finals = inn1.groupby("match_id").agg(final=("inn1_total", "first")).reset_index()
    # state at start of each over for each 1st innings
    st = inn1.groupby(["match_id", "over"]).agg(date=("date", "first"), wkts=("wkts_before", "min")).reset_index()
    st = st.merge(finals, on="match_id")
    dates = sorted(st["date"].unique())
    st["par"] = np.nan
    for i, d in enumerate(dates):
        hist = st[st["date"] < d]
        cur = st["date"] == d
        if len(hist) == 0:
            st.loc[cur, "par"] = np.nan  # cold start: first date
            continue
        cell = hist.groupby(["over", "wkts"])["final"].mean().rename("par_cell")
        st.loc[cur, "par"] = st.loc[cur].join(cell, on=["over", "wkts"])["par_cell"].to_numpy()
        miss = st.loc[cur, "par"].isna()
        if miss.any():  # fallback: over-only, then global
            ov = hist.groupby("over")["final"].mean().rename("par_ov")
            st.loc[cur & st["par"].isna(), "par"] = st.loc[cur & st["par"].isna()].join(ov, on="over")["par_ov"]
            still = st["par"].isna() & cur
            st.loc[still, "par"] = hist["final"].mean()
    df = df.merge(st[["match_id", "over", "par"]], on=["match_id", "over"], how="left")
    # linear projection from pre-ball state
    proj = np.where(df["legal_before"] > 0,
                    df["runs_before"] / df["legal_before"] * (df["scheduled_overs"] * 6),
                    np.nan)
    proj = pd.Series(proj, index=df.index).fillna(df["par"])
    df["projected_score"] = proj
    df["par_diff"] = np.where(df["innings"] == 1, (df["projected_score"] - df["par"]) / 100.0, 0.0)
    df["par_missing"] = df["par"].isna().astype(int)
    df["par_diff"] = df["par_diff"].fillna(0.0)
    return df

def add_bowler_threat(df, cfg):
    dl = df[df["is_legal"]]
    bw = dl.copy()
    bw["bowler_wkt"] = ((bw["wicket"] == 1) & (bw["dismissal_kind"].isin(BOWLER_WICKET_KINDS))).astype(int)
    per = bw.groupby(["date", "match_id", "bowler"]).agg(
        balls=("row_id", "count"), runs=("runs_batter", "sum"), wkts=("bowler_wkt", "sum")).reset_index()
    # runs conceded should include wides/noballs against bowler
    extras = df[df["extras_type"].str.contains("wides|noballs", na=False)].groupby(
        ["date", "match_id", "bowler"])["runs_extras"].sum().rename("extra_runs").reset_index()
    per = per.merge(extras, on=["date", "match_id", "bowler"], how="left").fillna({"extra_runs": 0})
    per["runs"] = per["runs"] + per["extra_runs"]
    dates = sorted(per["date"].unique())
    hist_balls, hist_runs, hist_wkts = {}, {}, {}
    out = []
    league = {"balls": 0, "runs": 0, "wkts": 0}
    for d in dates:
        day = per[per["date"] == d]
        for r in day.itertuples():
            b = hist_balls.get(r.bowler, 0); ru = hist_runs.get(r.bowler, 0); w = hist_wkts.get(r.bowler, 0)
            shrink = b / (b + 300.0)
            eco = (ru / b * 6) if b > 0 else (league["runs"] / league["balls"] * 6 if league["balls"] else 7.5)
            sr = (b / w) if w > 0 else 60.0
            lg_eco = league["runs"] / league["balls"] * 6 if league["balls"] else 7.5
            lg_sr = league["balls"] / league["wkts"] if league["wkts"] else 20.0
            out.append((r.match_id, r.bowler,
                        shrink * eco + (1 - shrink) * lg_eco,
                        shrink * sr + (1 - shrink) * lg_sr))
        for r in day.itertuples():  # add AFTER all today's matches are scored
            hist_balls[r.bowler] = hist_balls.get(r.bowler, 0) + r.balls
            hist_runs[r.bowler] = hist_runs.get(r.bowler, 0) + r.runs
            hist_wkts[r.bowler] = hist_wkts.get(r.bowler, 0) + r.wkts
            league["balls"] += r.balls; league["runs"] += r.runs; league["wkts"] += r.wkts
    th = pd.DataFrame(out, columns=["match_id", "bowler", "bowler_eco", "bowler_sr"])
    df = df.merge(th, on=["match_id", "bowler"], how="left")
    return df

NON_DISMISSAL = {"retired hurt", "retired out"}  # not failures of the batsman

def add_targets(df):
    # striker dismissal excludes retired hurt/out (batsman not beaten)
    striker_out = (df["player_dismissed"] == df["batter"]) & (~df["dismissal_kind"].isin(NON_DISMISSAL))
    df["y_dot_or_out"] = (((df["runs_batter"] == 0)) | striker_out).astype(int)
    df.loc[~df["is_legal"], "y_dot_or_out"] = np.nan
    # secondary: the CURRENT STRIKER is dismissed within the next 6 legal balls
    # of the innings (current ball + next 5), whoever faces them. Non-striker
    # runouts do not count; window truncates (censors) at innings end.
    legal = df[df["is_legal"]].copy()
    legal["y_out_6"] = np.nan
    for _, inn in legal.groupby(["match_id", "innings"], sort=False):
        bat = inn["batter"].to_numpy()
        dis = inn["player_dismissed"].to_numpy()
        kind = inn["dismissal_kind"].to_numpy()
        dis = np.where(np.isin(kind, list(NON_DISMISSAL)), "", dis)  # retired != dismissal
        y6 = np.zeros(len(inn))
        for off in range(6):
            shifted = np.concatenate([dis[off:], [""] * off]) if off else dis.copy()
            y6 = np.maximum(y6, (shifted == bat).astype(float))
        legal.loc[inn.index, "y_out_6"] = y6
    df = df.merge(legal[["row_id", "y_out_6"]], on="row_id", how="left")
    return df

if __name__ == "__main__":
    cfg = load_config()
    df = pd.read_parquet("data/interim/deliveries.parquet")
    df = build_features(df, cfg)
    df = add_targets(df)
    df.to_parquet("data/interim/features.parquet", index=False)
    m = df["is_legal"]
    print("rows:", len(df), "| legal rows:", int(m.sum()),
          "| DLS chase legal rows excluded from modeling:", int((df["is_legal"] & df["dls_chase"]).sum()))
    print("class balance y_dot_or_out: %.4f" % df.loc[m, "y_dot_or_out"].mean())
    print("class balance y_out_6: %.4f" % df.loc[m, "y_out_6"].mean())
    print("par missing (cold-start first date): %d rows" % df["par_missing"].sum())
    print(df[["crr", "rrr", "rr_crr_gap", "wickets_lost", "dots_last12", "wkts_last18",
              "settledness", "bowler_eco", "bowler_sr", "par_diff", "batting_position"]].describe().round(3))
