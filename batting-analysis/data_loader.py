"""Step 0: load Cricsheet IPL JSON -> one row per delivery, seasons from config."""
import json, glob, os
import pandas as pd
import yaml

def load_config(path="config.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)

def iter_matches(raw_dir, seasons):
    for f in sorted(glob.glob(os.path.join(raw_dir, "*.json"))):
        with open(f) as fh:
            d = json.load(fh)
        if int(str(d["info"]["season"])[:4]) in seasons:
            yield os.path.splitext(os.path.basename(f))[0], d

def build_deliveries(raw_dir, seasons):
    rows = []
    for match_id, d in iter_matches(raw_dir, seasons):
        info = d["info"]
        teams = info["teams"]
        scheduled_overs = info.get("overs", 20)
        dls = info.get("outcome", {}).get("method") == "D/L"
        reduced = scheduled_overs < 20 or dls
        for inn_idx, inn in enumerate(d["innings"], start=1):
            if inn.get("super_over"):
                continue
            batting = inn["team"]
            bowling = [t for t in teams if t != batting][0]
            for ov in inn["overs"]:
                for ball_seq, dl in enumerate(ov["deliveries"], start=1):
                    extras = dl.get("extras", {})
                    etype = "+".join(sorted(extras.keys())) if extras else ""
                    is_legal = not ("wides" in extras or "noballs" in extras)
                    wkts = dl.get("wickets", [])
                    rows.append({
                        "match_id": match_id,
                        "season": int(info["season"]),
                        "date": info["dates"][0],
                        "innings": inn_idx,
                        "over": ov["over"],                 # 0-indexed
                        "ball_seq": ball_seq,               # within over, incl. non-legal
                        "batter": dl["batter"],
                        "non_striker": dl["non_striker"],
                        "bowler": dl["bowler"],
                        "runs_batter": dl["runs"]["batter"],
                        "runs_extras": dl["runs"]["extras"],
                        "extras_type": etype,
                        "is_legal": is_legal,
                        "wicket": 1 if wkts else 0,
                        "player_dismissed": wkts[0]["player_out"] if wkts else "",
                        "dismissal_kind": wkts[0]["kind"] if wkts else "",
                        "venue": info.get("venue", ""),
                        "city": info.get("city", ""),
                        "event_stage": info.get("event", {}).get("stage", "league"),
                        "batting_team": batting,
                        "bowling_team": bowling,
                        "scheduled_overs": scheduled_overs,
                        "dls_match": dls,
                        "reduced_dls": reduced,
                    })
    return pd.DataFrame(rows)

if __name__ == "__main__":
    cfg = load_config()
    raw = os.environ.get("IPL_JSON_DIR", "data/raw/ipl_json")
    df = build_deliveries(raw, cfg["seasons"])
    os.makedirs("data/interim", exist_ok=True)
    df.to_parquet("data/interim/deliveries.parquet", index=False)
    print("=== STEP 0 AUDIT (Cricsheet ipl_json.zip, downloaded 2026-11-12) ===")
    print("columns:", list(df.columns))
    print("\nrows (deliveries) per season:")
    print(df.groupby("season").size())
    print("\nmatches per season:")
    print(df.groupby("season")["match_id"].nunique())
    print("\nunique batsmen:", df["batter"].nunique())
    print("unique bowlers:", df["bowler"].nunique())
    print("\nmissing values (nonzero):")
    print(df.isna().sum()[df.isna().sum() > 0])
    print("\nvenue empty:", (df["venue"] == "").sum(), "| city empty:", (df["city"] == "").sum())
    print("super overs: excluded at load | reduced/DLS matches:", df.groupby("match_id")["reduced_dls"].first().sum())
    print("event stages:", df["event_stage"].value_counts().to_dict())
    print("extras types:", df["extras_type"].value_counts().to_dict())
    print("dismissal kinds:", df.loc[df.wicket == 1, "dismissal_kind"].value_counts().to_dict())
    print("legal-ball share: %.4f" % df["is_legal"].mean())
