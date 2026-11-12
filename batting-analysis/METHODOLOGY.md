# Methodology

## Estimands
- Pressure (BPI): 100 x P(current legal ball is a dot or the striker is dismissed),
  from features available BEFORE the ball. Same-row alignment: features at ball d
  predict ball d. Non-striker dismissals do not count toward the batsman.
- RAE (centered form): runs_batter - E[runs] - wicket_penalty x
  (dismissal - E[dismissal]). wicket_penalty(over, wickets) = expected runs the
  INCOMING batsman adds from that state until his own dismissal or innings end
  (censoring inside the expectation), estimated leave-one-match-out; arrival at
  wkts+1; at 9 down the penalty is 0 (innings ends). Fallbacks: over-only, then global.
- PPF = RAE100_pressure - RAE100_normal with recency weights (2025-26: 1.0, 2022-24: 0.6).

## Validation policies (leakage controls)
- Features: all pre-ball (shift tests; zeroing a ball's own outcome leaves its features
  unchanged). Par scores and bowler threat use expanding windows over strictly earlier
  DATES; same-day matches never see each other.
- BPI stacker: nested grouped CV. Outer 5-fold by match_id; inside each outer fold,
  base models produce inner OOF predictions, the stacker trains on those only, then
  frozen base+stacker score the outer test fold. No ball is scored by a model that
  saw its match. Reported stack metrics come from these outer-OOF scores.
- Model-selection disclosure: the two binary keep/drop gates (keep interaction, keep
  LPI) were evaluated on the SAME nested outer-OOF scores that are reported. Both
  variants' metrics are reported in the logs; selection bias from two binary choices
  is negligible but disclosed here rather than hidden.
- Temporal diagnostic: ALL fitting restricted to 2022-24 - base models, stacker
  (train grouped-OOF), E[runs]/E[dismissal], wicket-penalty grid, and the bucket
  edges (train BPI quantiles). 2025-26 rows are scored frozen. Train-period RAE uses
  within-train grouped OOF predictions, not in-sample fits. Test-row features
  (par, bowler threat) use expanding history up to that row's date only - the same
  information a live system would have.
- Split-half: matches numbered by date order, alternate matches per half. Each half
  reuses the REPORTED full-data OOF RAE and nested-OOF BPI (models are NOT refit per
  half); half-specific PPF, within-half bootstrap variance (200 joint draws) and EB
  shrinkage are then recomputed to give PPF_adj per half. Spearman of PPF_adj across
  batsmen. Results: eligible 0.026 (n=52), all batsmen -0.195 (n=140).
- EB shrinkage: lambda_i = between/(between + within_i); between = max(eps,
  var(PPF) - mean(within)); within_i = variance of PPF over 1000 match-bootstrap
  resamples (resample each batsman's matches with replacement, recompute weighted
  RAE100 per bucket, difference). lambda is computed once on full data and NOT
  re-estimated per resample; CI on PPF_adj = lambda_i x the 5th/95th bootstrap
  percentiles of PPF. Fallback K-shrinkage n/(n+K) reported alongside; sensitivity
  K in {40, 60, 100}.
- p-values for stacker coefficients use match-clustered standard errors
  (statsmodels, cov_type=cluster by match_id); ball rows are not independent.

## Role-quota disclosure
The 3/4/3 quota (3 openers / 4 middle / 3 finishers) is feasible without backfill:
openers Jaiswal, Sai Sudharsan, Kohli; middle Samson, Klaasen, Dube, Patidar;
finishers Jadeja (+21), Rinku Singh (-30, 90% CI -88 to +28), Stubbs (-42,
CI -133 to +12). The quota list drops Pant and Abhishek Sharma from the
unconstrained top 10. Singh and Stubbs qualify via pressure RAE100 >= 0 but have
NEGATIVE PPF_adj - they are quota fillers, not pressure specialists.

## Implementation notes (2026-11-12)
- Bootstrap: ONE joint resample of matches per draw, both buckets from the same draw
  (covariance preserved). joint_bootstrap() is a tested function
  (tests/test_regressions.py).
- Batting position from first appearance as batter OR non-striker; an opener run out
  without facing still holds position 2. Role labels/quotas use this.
- Retired hurt/out (13 rows) no longer count as striker dismissals in any target or
  in E[dismissal].
- DLS chase innings (414 legal rows, 4 matches) excluded from the modeling frame:
  Cricsheet carries no revised target, so RRR would be false.
- Wicket penalty is a pure LOO (over, wkts+1) cell lookup - identical for dismissal
  and non-dismissal rows at the same state (test enforces this).
- Temporal diagnostic: train BPI from within-train NESTED OOF (not in-sample);
  test scored frozen; train RAE from within-train grouped OOF. Both PPF-vs-PPF
  (0.16) and PPF-vs-level (0.60) reported; the 0.60 is overall class, NOT evidence
  the pressure premium reproduces.
- Split-half uses the reported estimator: nested-OOF BPI + OOF RAE, PPF_adj per half
  (EB within half, 200 joint bootstrap draws), alternate matches by date order.
  Results: eligible batsmen Spearman 0.026 (n=52), all batsmen -0.195 (n=140).
- Bootstrap coverage: 370 of 139,000 joint draws (0.27%) skipped because a resample
  left a batsman's pressure or normal bucket empty (max 28 of 1000 for one batsman);
  CIs use the remaining draws.
- Wicket-penalty cells: 19% of (over, wickets) arrival cells have fewer than 5
  historical stints and are unsmoothed leave-one-match-out sample means; sparse
  cells carry larger sampling error. This sensitivity is disclosed rather than
  smoothed over; its net impact on final PPF_adj is not formally quantified.
- EB intervals: bootstrap CI is the sampling interval of OBSERVED PPF; the lambda-scaled
  interval on PPF_adj is a shrunk-estimate interval, not a posterior interval. EB
  assumes between-player variance is estimated without error and within-player
  bootstrap variance captures match-level sampling only.
- Eligibility thresholds read from config.yaml everywhere (no hardcoded 60/200).
- Reconciliation: 585 no-ball batter runs and 27 non-legal-ball dismissals (21 striker,
  15 stumpings) excluded by the legal-ball rule; dots_last12 divides by 12 from ball 1
  as the spec literally states (early-innings values read low); both disclosed, not changed.
- Model selection: full vs additive stack chosen on the same nested outer-OOF scores
  reported (full logloss 0.6327 vs additive 0.6331; AUC 0.6113 vs 0.6121 - additive is
  BETTER on AUC). Selection-on-evaluation risk is unquantified; both variants reported.

## Deviations from the written spec
1. Batter hand and bowler type omitted (absent from Cricsheet data).
2. RAE uses the centered dismissal residual (the uncentered formula does not
   satisfy the zero-mean residual check on out-of-fold predictions).
3. BPI decile monotonicity treated as a diagnostic, not a forced pass/fail.
   (Empirically the deciles were strictly monotone anyway: 24.9% -> 53.1%.)

## Confirmed limitations carried into the report
Situational (not psychological) pressure; batting position is a role/selection
proxy, settledness carries survivor effects, bowler threat is opponent skill;
BPI anti-predicts imminent dismissal within 6 balls (AUC 0.46-0.48, measured);
batsman identity is excluded from BPI features by design.
Split-half reliability ~0 -> list is indicative, per the spec's own gate.
