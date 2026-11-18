# Royals Auction Arena

A pressure-aware player analysis platform for historical T20 batting and bowling performance. Royals Auction Arena measures every delivery against what the match situation demanded, isolates the highest-pressure states across 843 completed matches (2022-2026), and ranks the batters and bowlers who produced the best recorded performance in those states. It ships as three connected parts: a final-run analysis pipeline, an interactive analysis website and the Pitch assistant.

**Live site:** https://royals-auction-arena.vercel.app/
**Round 1 report:** [reports/Royals_Auction_Arena_Round1_Report.pdf](reports/Royals_Auction_Arena_Round1_Report.pdf)

## Highlights

- **Pressure defined before the ball.** Every delivery is scored from the match state before it begins: score, wickets, balls remaining, target, phase, venue, season and recent events. The pressure measure never sees the outcome of the ball it describes.
- **One shared pressure set.** The top 35% of all 199,211 deliveries (69,724 balls) form a single high-pressure set on one common scale across both innings and all 843 matches. Every player is measured over the same fixed states.
- **Situation-adjusted performance.** Three model families estimate the expected ball outcome, the run value of a position and changes in win probability, with held-out match evaluation: each match is scored by models trained on the other match groups.
- **A fair, pooled ranking.** Batting and bowling are ranked on A, wicket-aware adjusted run value, over the shared pressure set with both innings pooled, recency weighting and partial pooling across the role population.
- **A readable 0-100 score.** Estimated A is standardised against the role population and mapped through the standard Normal curve: 50 is the role average, higher is better.
- **Interactive website.** Final batting and bowling lists, side-by-side player comparison, SVG interval charts, CSV export and an officially sourced IPL 2027 retained-squad grid with available pressure scores, all as a static site with no database.
- **Pitch assistant.** Ask questions about the rankings and the factors behind them in plain language, answered from the site's methodology and player summaries.

## Results at a glance

Final top 10, ranked by the 0-100 pressure score over the shared 2022-2026 high-pressure states. The full final lists (14 batters, 16 bowlers) live in [reports/final_lists](reports/final_lists) and on the website.

| # | Batters | Score | 80% interval |
| --- | --- | --- | --- |
| 1 | TH David | 71.6 | 25 - 97 |
| 2 | Tilak Varma | 66.7 | 22 - 95 |
| 3 | SA Yadav | 57.5 | 15 - 92 |
| 4 | JC Buttler | 56.1 | 14 - 92 |
| 5 | N Pooran | 55.6 | 14 - 92 |
| 6 | RK Singh | 53.4 | 12 - 91 |
| 7 | SO Hetmyer | 52.1 | 12 - 91 |
| 8 | Ishan Kishan | 49.4 | 10 - 90 |
| 9 | S Dube | 48.4 | 10 - 89 |
| 10 | SS Iyer | 45.3 | 9 - 87 |

| # | Bowlers | Score | 80% interval |
| --- | --- | --- | --- |
| 1 | CV Varun | 70.5 | 25 - 96 |
| 2 | AR Patel | 67.9 | 22 - 95 |
| 3 | B Kumar | 67.4 | 21 - 96 |
| 4 | JJ Bumrah | 66.6 | 20 - 95 |
| 5 | Kuldeep Yadav | 65.0 | 19 - 95 |
| 6 | HV Patel | 63.5 | 19 - 94 |
| 7 | M Theekshana | 61.3 | 17 - 94 |
| 8 | JO Holder | 60.1 | 16 - 93 |
| 9 | YS Chahal | 59.2 | 16 - 93 |
| 10 | Arshdeep Singh | 51.3 | 11 - 90 |

## Repository layout

| Path | Contents |
| --- | --- |
| `analysis/final-run/` | The scripts behind the final 18 November 2026 run: pressure reblend, filtered row building, hyperfit, rating-mixture draws, posterior aggregation and score building |
| `dashboard/` | The website: static front end, local development server, dataset builder, Pitch assistant function and tests |
| `reports/` | The Round 1 report PDF and clean final-list CSVs |

## Methodology summary

1. **Read the match situation before the ball.**
2. **Select the highest-pressure deliveries across all matches.**
3. **Estimate the expected outcome, then measure the player's performance relative to that reference.**
4. **Rank eligible players on their pressure performance, separately for batting and bowling.**

### Pressure score

```
P = 0.30 x leverage + 0.25 x collapse risk + 0.25 x required-rate stress + 0.20 x match balance
```

Leverage is how much the next ball can change the win chance; collapse risk reads recent wickets; required-rate stress compares the chase demand with what is sustainable at the venue and stage; match balance rises the closer the match is. The weights are a declared starting choice. A delivery is high pressure when its pre-ball score reaches 0.507, which keeps the top 35% of deliveries (35,922 from first innings, 33,802 from second).

### Performance measure A

- **Batting:** A is wicket-aware adjusted run value: runs scored plus the change in expected remaining team runs, compared with what an average batter was expected to produce in the same situations and bowling contexts.
- **Bowling:** A is the reference expectation minus the batting run value conceded, using the same wicket-aware frame from the bowling side. Both innings are pooled.

High-pressure A sets the ranking. Player estimates use a 365-day half-life recency weighting, chosen in advance, and partial pooling combines individual evidence with the population pattern.

### The score

```
Score = 100 x Phi(z)
```

z compares estimated A with the role average in population standard deviations, and Phi is the standard Normal curve. A score of 50 represents average estimated ability on this scale; batting and bowling carry separate scales.

### Selection and uncertainty

Every identity in the modelled pool (838 batters, 572 bowlers) is scored. The final lists cover the 14 batters and 16 bowlers with substantial high-pressure evidence, and the report presents the top 10 of each discipline. Each score carries an 80% interval from the rating-mixture model, conditional on the fitted models, settings and reference mix. The intervals are wide (about 77 points for top-10 batters and 75 for top-10 bowlers), so the leaders are best read as a group. A separate strict consistency label combines above-reference ability, precision and exposure; it remains unmet across both final lists.

## Website

The site is static HTML, CSS and JavaScript with SVG charts and no build dependencies. See [dashboard/README.md](dashboard/README.md) for local development, the dataset contract and deployment.

## Data

Match data: 843 completed matches from the competition-supplied match list, 2022-2026. Ball-by-ball records were recovered for those fixtures. The competition inputs and the recovered ball-by-ball records are not redistributed in this repository; `analysis/final-run/README.md` describes the inputs each pipeline stage expects.

The analysis is historical reporting of recorded 2022-2026 performance under a stated pressure definition. The Squad page presents the official IPL 2027 retained core as of 18 November 2026, with separate batting and bowling pressure estimates from the wider modelled pool.
