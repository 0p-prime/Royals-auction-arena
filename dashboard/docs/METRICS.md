# Metric semantics

## Batting

- Pressure level: recency-weighted RAE100 in the pressure bucket, in runs above expectation per 100 legal balls.
- Normal level: the same RAE100 in the normal bucket.
- Overall level: RAE100 across all modeled legal balls, including intermediate pressure states. It is not an average of the two displayed buckets.
- Uplift: `PPF_adj`, an empirical-Bayes-shrunk pressure-minus-normal difference. It need not equal the difference of the two unshrunk displayed levels.
- Interval: the exported lambda-scaled 90% match-bootstrap interval for uplift. Level intervals are not available in this export; none are invented.
- Sample-qualified: at least 60 pressure and 200 normal balls, regardless of active-season membership (52 players).
- Source active eligibility: the same count floors plus the source's active-season flag (50 players). Warner and Dhawan meet count floors but are inactive under that rule.
- Shortlist/top10/quota: exact membership of the supplied source files. The 3/4/3 quota contains negative-uplift finishers Rinku Singh and Stubbs.

The model uses pre-ball features and nested match-grouped out-of-fold pressure scores. Batting BPI predicts a dot or striker dismissal on the current legal ball, not imminent wickets or psychological pressure. New/settled players remain combined, with no balls-faced adjustment; 69% of pressure balls are a batter's first six. Split-half and temporal uplift reliability are weak. See the supplied batting methodology for full exclusions, shrinkage and validation details.

## Bowling

Five independently supplied lists are retained: overall, chase pressure, chase uplift, first-innings pressure and first-innings uplift. First/chase pressure scales differ and must not be pooled.

- Runs saved: above the situation-model expectation per 100 delivery attempts, including wides and no-balls. Positive is better. Level shrinkage is toward the group average, not zero.
- Wickets above expectation: separate wickets-per-100-attempts component.
- Uplift: phase-matched pressure-minus-normal performance within innings. A synthetic normal level cannot be recovered by subtracting it from a separate pressure list; the samples and adjustment differ.
- Composite order: best median rank across wicket values 10,15,20,25,30, then mean rank, then name. Combined score within each value is runs saved + wicket value × wickets above expectation.
- Rank range: best/worst placement across those five wicket values, not a statistical interval.
- Runs interval: about 95%, based on match-clustered errors conditional on frozen models/shrinkage. It covers only the runs component, not wickets or composite rank.

The v5 pressure band is [0.6,0.9) on a calibration-adjusted state score, with near-decided tails below 0.05 or above 0.95 removed from both pools. These are design choices, not guaranteed probabilities. Overall requires 200 attempts; chase pressure level 60; first-innings pressure level 40. Chase uplift additionally requires 120 normal attempts; first-innings uplift 100; both require 3 matches and 10 attempts per phase stratum. Thresholds and definitions are supplied in the v5 metadata and shown on the site.

Overall runs level repeats moderately, pressure/uplift weakly, wickets/combined ranks do not. 2025-26 was used during development and is not a fresh test. No list is validated for pressure-skill or auction selection.
