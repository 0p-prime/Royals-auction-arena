# Royals pressure lab

A read-only cricket analysis website for exploring historical batting and bowling performance across the supplied 2022-26 matches (IPL, T20I and Asia Cup tournaments). It keeps performance under pressure separate from improvement over a player's own normal level. The published analysis lists are preserved; custom filters are explicitly exploratory.

## Run locally

Requires Node.js 20+; no npm dependencies or database are required.

```sh
npm start
# http://127.0.0.1:3000
```

The populated distribution includes `private/dataset.json`. A code-only checkout intentionally shows an import screen until a verified dataset is provided. No synthetic sample results are used.

To build the dataset from the analysis aggregate exports, Python 3 with pandas is sufficient:

```sh
python3 scripts/build_dataset.py \
  --batting-dir /path/to/batting/outputs \
  --bowling-dir /path/to/bowling/outputs \
  --out private/dataset.json
npm start
```

The builder does not fit models. Batting requires `batsman_ppf.csv`, `shortlist_35.csv`, `top10_batsmen.csv` and `top10_role_quota.csv`. Bowling requires `all_bowlers.csv`, `top10.csv` and `delivery_scores.csv.gz`; the innings-specific views are direct aggregations of the same scored deliveries. If you have the populated distribution, no build step is needed.

## Build the public website

```sh
npm run build
```

This writes `dist/` with HTML, CSS, JavaScript, derived summary JSON, attribution and Vercel configuration. No server-side runtime is needed on the hosted site. Deploy `dist/` as the static project root with no install or build command. Alternatively, configure a source deployment to run `npm run build` and use `dist` as output, but the build must first have an approved dataset available.

The entire `dist/` directory becomes public. Inspect `dataset.json` before deployment. It contains player-level aggregate results and their source-file hashes, not original organizer CSVs, delivery rows, fitted models or credentials. Public disclosure and repository publication are separate release decisions; `private/` and `dist/` stay gitignored by default.

## Website navigation

Home, Batting, Bowling and Methodology are separate hash-routed views. Navigation works with browser back/forward, direct links and keyboard controls. Homepage columns, player summaries and comparisons share a twelve-column desktop grid that stacks on phones. Technical validation and scope details live in Methodology; charts retain their metric and interval labels.

## Features

- Batting: analysis top 10, role-balanced 3/4/3 list, shortlist, sample-qualified pool, active eligible pool and all exported players.
- Bowling: the published funnel list (both innings), overall, chase pressure, chase uplift, first-innings pressure and first-innings uplift. The funnel list is the published ranking; the innings views are supplementary lenses on the same delivery scores.
- Role/style, name/team and minimum-sample filters; side-by-side player comparison; CSV export of the current filter.
- Responsive forest charts and phone-sized player cards, with accessible text equivalents and keyboard controls.
- Published funnel order for each bowling view, with optional runs-only ordering.

## Interpretation

This is descriptive historical analysis of the supplied matches. Team labels are historical records, not retention status or auction eligibility. Batting legal-ball counts and bowling legal-ball counts are different denominators; do not compare score magnitudes across disciplines.

Measured consistency across match samples is weak (split-half uplift correlation -0.00 for all batsmen and -0.02 for eligible batsmen; bowling alternate-match rank correlation 0.05), so exact placings are approximate and depend on the method's cutoffs, floors and selection rules. Among the batting analysis top 10, only TH David's 90% uplift interval excludes zero. Role-balanced quotas can include batters whose uplift sits below zero when a role needs representation. Full definitions and limitations are visible on the website and in [docs/METRICS.md](docs/METRICS.md).

## Tests

```sh
npm test
python3 -m unittest discover -s tests -p 'test_import.py'
```

For optional browser checks, install Playwright in the development environment and run:

```sh
npm install --no-save --package-lock=false playwright
CHROME_PATH=/usr/bin/google-chrome node tests/browser.mjs
```

Browser checks require the populated dataset. They start and stop their own local server. Screenshots are written to `test-artifacts/`, which is excluded from Git. The production website has no Playwright dependency.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md), [docs/VERIFICATION.md](docs/VERIFICATION.md), and [docs/RELEASE.md](docs/RELEASE.md).

## Data attribution

Ball-by-ball source: supplied CSV export of [Cricsheet](https://cricsheet.org/downloads/) matches (IPL, T20I and Asia Cup tournaments, 2022-26), under the Open Data Commons Attribution License. Bowling historical team/style reporting metadata is sourced from [aadi-jn/indian-premier-league](https://github.com/aadi-jn/indian-premier-league/blob/main/docs/data_dictionary.md) as recorded in the supplied analysis provenance. These labels are not current player availability. The data attribution notice is included with static exports.

## Pitch assistant

Pitch is the optional on-site Q&A assistant: `web/assistant.js` (UI) and `web/api/assistant.js` (Vercel serverless function). It answers questions about the rankings and every factor behind them, using only the site's methodology text and player summary rows, with off-topic and prompt-injection guards.

Environment (set in the hosting project only, never committed):

- `GEMINI_API_KEY` (required): key for the Gemini gateway. The project assumes a free Google AI Studio key; that tier needs no billing account or card. In Vercel: Project Settings -> Environment Variables, Production scope.
- `ASSISTANT_MODELS` (optional): comma-separated fallback model list.
- `ASSISTANT_DAILY_CAP` (optional, default 400): soft daily answer cap. Rate limits are per warm serverless instance (plus 8 requests/minute per client IP), not one global counter.

Player data: committed `web/lib/knowledge.json` carries site and methodology text only. Player summary rows and ranked lists live in `web/lib/players.json`, which is excluded from the repository like other derived data. Regenerate it from the derived site dataset before deployment:

    node scripts/generate-assistant-data.mjs [path/to/dataset.json]

`vercel.json` bundles `web/lib/**` into the function at deploy time. Without `players.json` the site is unaffected and Pitch answers methodology questions only.
