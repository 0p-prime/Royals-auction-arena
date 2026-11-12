# Royals pressure lab

A read-only cricket analysis website for exploring historical batting and bowling performance in IPL 2022-2026. It keeps performance under pressure separate from improvement over a player's own normal level. The published analysis lists are preserved; custom filters are explicitly exploratory.

## Run locally

Requires Node.js 20+; no npm dependencies or database are required.

```sh
npm start
# http://127.0.0.1:3000
```

The populated distribution includes `private/dataset.json`. A code-only checkout intentionally shows an import screen until a verified dataset is provided. No synthetic sample results are used.

To import the original aggregate exports, Python 3 is sufficient:

```sh
python3 scripts/import_data.py \
  --batting /path/to/batting/outputs \
  --bowling /path/to/bowling/outputs/bowler_model_data_v5.json
npm start
```

The importer does not fit models or process delivery-level data. Batting requires `batsman_ppf.csv`, `shortlist_35.csv`, `top10_batsmen.csv` and `top10_role_quota.csv`. Bowling requires the verified v5 JSON, not v3/v4 artifacts. If you have the populated distribution, no import step is needed.

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
- Bowling: overall, chase pressure, chase uplift, first-innings pressure and first-innings uplift. Innings-specific lists are never combined.
- Role/style, name/team and minimum-sample filters; side-by-side player comparison; CSV export of the current filter.
- Responsive forest charts and phone-sized player cards, with accessible text equivalents and keyboard controls.
- Bowling composite source order and optional runs-component ordering. Rank ranges across wicket values remain visible.

## Interpretation

This is descriptive historical analysis, not a future-performance model, psychological-pressure measure or auction simulator. Team labels are historical records, not retention status or auction eligibility. Batting legal-ball counts and bowling delivery-attempt counts are different denominators. Do not compare score magnitudes across disciplines.

Only Samson's 90% uplift interval among the batting analysis top 10 excludes zero. The role-balanced list includes negative-uplift Rinku Singh and Stubbs to fill finisher slots. Batting new/settled players are combined without a balls-faced adjustment. Bowling intervals cover the runs component only, not wickets or composite rank. Full definitions and limitations are visible on the website and in [docs/METRICS.md](docs/METRICS.md).

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

Ball-by-ball source: [Cricsheet IPL JSON](https://cricsheet.org/downloads/), under the Open Data Commons Attribution License. Bowling historical team/style reporting metadata is sourced from [aadi-jn/indian-premier-league](https://github.com/aadi-jn/indian-premier-league/blob/main/docs/data_dictionary.md) as recorded in the supplied analysis provenance. These labels are not current player availability. The data attribution notice is included with static exports.

## Pitch assistant

Pitch is the optional on-site Q&A assistant: `web/assistant.js` (UI) and `web/api/assistant.js` (Vercel serverless function). It answers questions about the rankings and every factor behind them, using only the site's methodology text and player summary rows, with off-topic and prompt-injection guards.

Environment (set in the hosting project only, never committed):

- `GEMINI_API_KEY` (required): key for the Gemini gateway. The project assumes a free Google AI Studio key; that tier needs no billing account or card. In Vercel: Project Settings -> Environment Variables, Production scope.
- `ASSISTANT_MODELS` (optional): comma-separated fallback model list.
- `ASSISTANT_DAILY_CAP` (optional, default 400): soft daily answer cap. Rate limits are per warm serverless instance (plus 8 requests/minute per client IP), not one global counter.

Player data: committed `web/lib/knowledge.json` carries site and methodology text only. Player summary rows and ranked lists live in `web/lib/players.json`, which is excluded from the repository like other derived data. Regenerate it from the derived site dataset before deployment:

    node scripts/generate-assistant-data.mjs [path/to/dataset.json]

`vercel.json` bundles `web/lib/**` into the function at deploy time. Without `players.json` the site is unaffected and Pitch answers methodology questions only.
