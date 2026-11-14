# Bowling Analysis

Historical bowling analysis for the Royals Auction Arena project, on the
supplied 2022-26 matches (IPL, T20I and Asia Cup tournaments). The pipeline
scores each bowler against per-ball model expectation: overall, in
high-pressure states, and against his own normal states, split by innings.
It describes past performance on those matches.

Current published list: **bucket BPF funnel** (pressure-minus-normal RAE100
with sample shrinkage, ordered through the eligibility and shortlist
funnel). Experimental versions (continuous slope, v3 components, v4/v5
win-score states) remain in `models/` for development history; outputs are
versioned and must not be mixed.

## Repository layout

- `core/` - data loading, feature construction, BoPI boundary-risk model,
  expected runs/wickets, BPF scoring, selection funnel, validation
- `models/` - chase win score (exact DP), first-innings win score (HGB),
  pressure state models (v4, first-innings, v5), placebo, component and
  continuous estimators, forward-association check, v5 audit
- `tests/` - 61 tests (`python -m pytest tests/ -q`)
- `data/` - Cricsheet license, reporting metadata; raw match data is not
  committed
- `diagnostics/` - standalone check scripts
- `outputs/` - only `frozen_models.joblib` is committed; all other outputs
  are regenerated

## Setup and run

Python 3.10-3.13. Windows:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python download_data.py
.venv\Scripts\python run.py
.venv\Scripts\python -m pytest tests/ -q
```

macOS/Linux: `python3 -m venv .venv`, `.venv/bin/python`.

`download_data.py` fetches the public Cricsheet IPL archive,
`run.py` rebuilds every output: delivery scores, all-bowler CSVs, top-10
funnel output, pace/spin views, wicket-value sensitivity, validation JSONs,
plots, logs. Exact package versions in `environment.txt`. The documented
run used the archive SHA256 in `SOURCES.json`; a fresh download can shift
results. Some tests read generated outputs, so run the pipeline before the
test suite.

`outputs/frozen_models.joblib` holds the trained BoPI / expected-runs /
expected-wickets estimators so the v5 lists reproduce without retraining.
Treat it as a trusted local artifact; do not load untrusted pickle/joblib
files.

## Data and coverage

Ball-by-ball source: Cricsheet IPL JSON (ODC Attribution, license bundled
at `data/Cricsheet_LICENSE.txt`). Links and checksums in `SOURCES.json`.

867 playable fixtures from 2022-26. 687 fixtures from 2023-26 are scored
(158,496 deliveries); the 180 fixtures of the 2022 season are warmup
training and historical profiles only and carry no out-of-sample scores.
Exclusions for revised targets, reduced overs, no results and missing
innings are logged (`excluded_matches.csv`, `source_match_manifest.csv`).
Both regular innings are used; super overs are excluded.

The loader accepts the Cricsheet JSON ZIP or JSON directories directly.
CSV aliases are autodetected; ambiguous extras, wicket credit, sequence,
target or innings conventions are never invented - missing critical fields
raise specific errors (`data_loader.ALIASES` documents the canonical CSV
schema).

Pace/spin reporting tags join a secondary public squad/people dataset by
Cricsheet registry ID -> Cricinfo player ID, never fuzzy names
(`data/reporting_metadata.csv`, sources in `SOURCES.json`). The tags are
undated, so they are used for reporting views only, never as model
features; `run.py --metadata path.csv` enables dated type/hand features
when every row carries a source-grounded `valid_from`.

## Feature and target definitions

- State is recorded before the current delivery is applied. Legal clock
  excludes wides/no-balls. RRR = 6 * runs needed / legal balls remaining;
  CRR = 6 * team runs / legal balls bowled (0 at innings start).
- Chase pressure proxy: `chase_mode=intent` uses `clip((CRR-RRR)/12, 0, 1)`;
  `literal` keeps RRR-CRR. Raw CRR and RRR are retained either way.
- First-innings projection: current rate * 20 minus prior-date venue par
  (mean completed first-innings score at the venue over >=5 earlier
  matches, else all earlier venues, else fallback 170). Same-date matches
  cannot inform each other.
- Wickets in hand counts all dismissals except retired hurt/not out.
  Bowler credit: bowled, caught, caught-and-bowled, lbw, stumped, hit
  wicket only.
- Boundary target: genuine batter 4/6 (excluding `non_boundary`). Recent
  boundary streak: previous 12 delivery attempts / 12. Spell cost:
  bowler's previous 12 attempts in the current spell; a spell resets after
  a gap of more than two overs.
- Set batter: prior balls faced > 20. Historical SR uses earlier dates
  only, fallback 130. Powerplay/death carry a 1.25 phase feature, middle
  1.0; the effect is learned, not forced.

## Models and scoring

Boundary logistic regression vs XGBoost: fit 2022-23, select once on 2024
development Brier, refit 2022-24, report 2025-26 held-out for both. The
final estimator is not chosen by the 2025-26 winner; hyperparameters are
fixed in `config.json`.

Chronology: season Y scores are out-of-sample, trained on earlier seasons
only (2022 uses the 2019-21 warmup). 2025-26 models are fitted on exactly
2022-24 with bucket cutoffs frozen through 2024; player and par features
update from earlier dated matches as they would in live use. No feature
reads a later ball or a same-date later match.

Expected runs/wickets use innings, over, wickets, CRR/RRR, pre-ball par
gap, set-batter/prior SR, venue and available hand. No bowler identity,
team, current-ball result, spell cost or boundary streak enters E[R]/E[W].

Selection scoring preserves the original formula:

```
RAE = E[R] - actual_bowler_charged_runs + wicket_value * actual_credited_wicket
```

Wicket value 20 is an exposed assumption; 10/20/30 are reported side by
side. E[W] is fitted and evaluated but not subtracted in the selection
formula, so an average bowler sits at roughly `20*E[W]` rather than zero -
the centered-wicket diagnostic `E[R]-actual + 20*(W-E[W])` is saved and
tested separately. Exposure thresholds and shrinkage use raw legal balls;
recency weights (0.6 old / 1.0 recent) apply to numerators and rate
denominators, not to n in n/(n+60).

Selection funnel: >=60 pressure legal balls, >=200 normal legal balls, at
least one 2025/26 appearance, top 35 by average descending rank of
normal/overall RAE100, retain pressure RAE100 >= 0, order by BPF_adj
descending then pressure balls. Pace/spin views run the same funnel within
tagged players. Majority-phase quotas are implemented, off by default, and
never silently backfilled.

## Pressure states and win scores (exploratory v4/v5, not the published list)

- Chase win score pb (`winprob.py`): exact dynamic programming over (runs
  needed, legal balls left, wickets lost). Training frequencies from
  earlier seasons only, by over x wickets-lost bucket shrunk toward
  all-delivery frequencies; 2025-26 use one fixed 2019-24 table. Checks in
  `winprob_check.json` and the test suite: terminals, monotonicity in runs
  needed, extreme states, illegal-delivery truncation error 8e-10. Known
  issue: monotonicity in wickets and balls is violated in ~2% of cells (up
  to 0.064/0.037) from the bucketed tables. pb is ordinal, not a
  calibrated probability (Brier 0.160 forward / 0.153 on 2025-26 vs 0.249
  / 0.247 constant). Not Duckworth-Lewis-Stern, not validated for live
  use.
- First-innings score pb1 (`winprob1.py`): monotone gradient-boosted
  classifier on runs scored, legal balls bowled, wickets lost; no venue,
  no player identity; trained on earlier seasons only. Brier 0.224
  (2022-24) vs 0.250 constant; 0.229 vs 0.244 on 2025-26, miscalibrated at
  high pb1.
- v4 states (second innings): pressure = pb in [0.6, 0.9), normal = pb <
  0.6, above band excluded. v5 adds 1-D isotonic calibration per fold
  (leave-one-season-out pairs inside the training span; a scored season
  never informs its own calibrator) and excludes calibrated scores >= 0.95
  or <= 0.05 from both pools in both innings. Observed tail flip rates
  with cluster-bootstrap intervals are in `outputs/audit_v5.json`; every
  interval includes 5%, so the exclusion is a design rule, not a proven
  almost-finished rule. Band edges are design choices on the calibrated
  score; the [0.7, 0.95) alternative is reported (rank Spearman 0.59-0.79,
  top-10 overlap 3-6 of 10).
- Estimators: per-bowler mean residuals over all balls (min 200) and
  pressure balls (min 60); plus a per-bowler regression of the delivery
  residual on a pressure indicator with phase indicators (>=10 pressure
  and >=10 normal balls per phase, min 60/120 total, 3 matches), so the
  pressure coefficient is a within-phase difference with match-clustered
  SEs. Runs and wickets parts shrink separately toward the population mean
  (DerSimonian-Laird), then combine as runs + v*wickets across v in
  10..30, ordered by median rank. Placebo: pressure labels shuffled within
  bowler x phase 30 times.

## Validation

- Model holdout: boundary model selected once on 2024 development Brier
  (both candidates fitted on seasons up to 2023); held-out 2025-26 AUC
  0.600, Brier 0.150. Expected-runs holdout MAE 1.30 runs per delivery.
- Consistency across matches, measured: BPF rank correlation 0.05 across
  alternate matches (361 bowlers) and -0.01 early versus late (227).
  Overall runs-saved level repeats better than the uplift difference;
  subtracting two noisy levels is the weak step, so fine rank differences
  in the uplift list are approximate.
- Sensitivity: wicket value 10 instead of 20 keeps 7 of the 10 names;
  30 keeps 9 of the 10
  selected names. Pressure-cutoff choices move individual placings.
- Bootstrap: 500 within-bowler match-cluster resamples; model fits,
  feature history and cutoffs held fixed, so intervals cover sampling
  noise only, not fitting, cutoff or selection uncertainty.
- Confidence labels are a declared heuristic (High: >=30 matches, >=200
  pressure balls, CI lower bound > 0). With weak measured stability, all
  labels are Low: treat every list as exploratory.

## Limitations

- BoPI is boundary risk, not competitive or mental pressure; it includes
  batter strength, spell form and boundary history. There is no pressure
  ground truth and no causal claim.
- Expected-runs models are on average optimistic (population mean of runs
  prevented -3.6 per 100 balls); read values relative to other bowlers.
- Scores for 2025-26 are computed with models frozen on 2022-24 data;
  period shifts after the training window are not re-learned.
- No role or opponent-strength adjustment beyond phase matching; cluster
  SEs can be optimistic at small samples; the runs-wickets exchange rate
  remains an exposed assumption.
- Team field is the latest observed bowling team in the data (club or country), not
  current contract, retention, nationality or auction eligibility.

## Notes

- Earlier estimator versions are kept for development history; their
  sections above describe what each one showed and where it failed.
- No external API key is required.
