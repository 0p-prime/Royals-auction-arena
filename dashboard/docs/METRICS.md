# Metric semantics

One measure drives the site: recorded performance under pressure.

- **Pressure score**: `100 x Phi(z)`, where z is the player's estimated high-pressure A standardised against the role population. 50 is the role average; higher is better. Batting and bowling use separate scales and are read within their own discipline.
- **A (adjusted run value)**: batting A is runs scored plus the change in expected remaining team runs, relative to the average-batter expectation for the same situations and bowling contexts, including the cost of losing the wicket. Bowling A is the reference expectation minus the batting run value conceded, on the same wicket-aware frame, both innings pooled.
- **80% score interval**: the conditional interval from the 32-draw rating-mixture model, with fitted outcome and win models, hyperparameters and reference mix held fixed. It omits model-form and calibration uncertainty, so close ranks are approximate.
- **Pressure balls / pressure matches**: legal high-pressure deliveries and the number of matches in which the player faced or bowled high-pressure deliveries. High-pressure means a pre-ball pressure score of at least 0.507: the top 35% of all 199,211 deliveries, one shared set across both innings and all 843 matches.
- **Final lists**: the 14 batters and 16 bowlers with substantial high-pressure evidence, ranked by the pressure score. The report presents the top 10 of each discipline; the website shows the full final lists.
- **Recency**: player estimates weigh matches with a 365-day half-life, chosen in advance; the population-level fit treats all dates equally.
- **Consistency label**: a separate strict tag combining above-reference ability, precision and exposure. It remains unmet across both final lists and never changes the ranking.
