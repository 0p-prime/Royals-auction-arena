# Metric semantics

## Batting

- Pressure level: recency-weighted RAE100 in the pressure bucket, in runs above expectation per 100 legal balls.
- Normal level: the same RAE100 in the normal bucket.
- Overall level: RAE100 across all modeled legal balls, including intermediate pressure states. It is not an average of the two displayed buckets.
- Uplift: `PPF_adj`, an empirical-Bayes-shrunk pressure-minus-normal difference. It need not equal the difference of the two unshrunk displayed levels.
- Interval: the exported lambda-scaled 90% match-bootstrap interval for uplift. Level intervals are not available in this export; none are invented.
- Sample-qualified: at least 60 pressure and 200 normal balls, regardless of active-season membership (104 players).
- Source active eligibility: the same count floors plus the source's active-season flag (122 players).
- Shortlist/top10/quota: exact membership of the supplied source files. The 3/4/3 quota list fills role slots from the same funnel order; on the current data it matches the analysis top 10.

The model uses pre-ball features and nested match-grouped out-of-fold pressure scores. Batting BPI predicts a dot or striker dismissal on the current legal ball, not psychological pressure. New/settled players remain combined, with no balls-faced adjustment. Split-half uplift consistency across match samples is weak (-0.00 all batsmen, -0.02 eligible), so fine rank differences are approximate. See the supplied batting methodology for full exclusions, shrinkage and validation details.

## Bowling

The published ranking is the funnel list over both innings: eligibility floors, an overall-skill shortlist, then ordering by shrunk pressure-minus-normal uplift (BPF_adj). Five supplementary views sit alongside it: overall, chase pressure, chase uplift, first-innings pressure and first-innings uplift. First/chase views use the same BoPI buckets but are never pooled with each other.

- Runs saved: above the situation-model expectation per 100 legal balls; wides and no-balls add to the cost but not the ball count. Positive is better.
- Uplift (BPF_adj): pressure RAE100 minus normal RAE100, shrunk by pressure balls over pressure balls plus 60.
- Funnel order: the published list order follows BPF_adj through the funnel. Sorting by the raw runs value is a separate, explicitly labeled exploratory choice.
- Uplift interval: 95%, from 500 match-cluster bootstrap resamples conditional on the fitted models and cutoffs. It covers sampling noise, not model, cutoff or selection uncertainty. Per-innings views have no interval supplied; none are invented.

Pressure is the top 30% of predicted boundary risk (BoPI, 70th percentile) and normal the bottom 55% (55th percentile), with cutoffs fitted on the training window. These are design choices, not psychological pressure. Overall requires 200 legal balls; chase pressure level 60; first-innings pressure level 40. Chase uplift additionally requires 120 normal balls; first-innings uplift 100. Thresholds and definitions are shown on the site.

Measured consistency: the pooled BPF rank repeats weakly across match samples (0.05 alternate-match, -0.01 early/late); the overall runs-saved level repeats better. Exact placings depend on cutoffs, floors and selection rules.
