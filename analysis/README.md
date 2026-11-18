# Analysis: final run

The final 18 November 2026 pressure-performance ranking was produced by the scripts in
[`final-run/`](final-run/), in this order:

1. **`newmethod_reblend.py`** builds the delivery-level pressure score from the per-fold
   calibrated references: leverage ECDF percentile (30%), match balance from win
   probability (20%), required-rate stress (25%) and collapse risk (25%). First-innings
   raw scores are quantile-mapped onto the second-innings scale, and the pooled 65th
   percentile cut marks the top 35% of deliveries as high pressure.
2. **`build_filtered_rows.py`** + **`raw_match_design_filtered.py`** keep only the
   high-pressure deliveries and build the per-player, per-match aggregated design rows
   (adjusted run value A, win-probability component K, event covariance, exposure and
   recency weights).
3. **`fit_filtered.py`** fits the shared role-population hyperparameters on those rows.
4. **`draws_new.py`** generates the 32 shared rating draws per fold with a gamma-quantile
   coupling, and **`mixture_new.py`** + **`weighted_summary_posterior_filtered.py`**
   aggregate each player's posterior under every draw.
5. **`combine_new.py`** pools the 32 draws into the rating-mixture posterior
   (within-draw plus between-draw covariance).
6. **`scores_new.py`** standardises each player's posterior mean A against the role
   population, converts it to the 0-100 score, derives the conditional 80% and 95%
   intervals, and writes the historical-score and final-list exports.

The website dataset is then built from the final-list exports with
[`../dashboard/scripts/build_final_dataset.py`](../dashboard/scripts/build_final_dataset.py).

## Inputs

The scripts expect the fitted expectation-model artifacts and the scored delivery table
from the analysis environment (held-out run-expectancy and win-probability model
coefficients, calibrated references and per-delivery utilities). Those artifacts and the
competition-supplied match data are not redistributed in this repository, so the scripts
document the computation rather than run standalone from a fresh checkout.

## Outputs

- `reports/final_lists/batting_final_list.csv` and `bowling_final_list.csv`: the 14
  batters and 16 bowlers of the final selection, with score, 80% interval, pressure
  balls and pressure matches.
- The Round 1 report: `reports/Royals_Auction_Arena_Round1_Report.pdf`.
