# Royals pressure lab

A read-only cricket analysis website for exploring the final pressure-performance rankings: 14 batters and 16 bowlers ranked on recorded high-pressure performance across 843 completed matches (2022-2026). The site presents the pressure score, its 80% conditional interval and the evidence behind each player, plus a squad and purse planner for auction tracking.

## Run locally

Requires Node.js 20+; no npm dependencies or database are required.

```sh
npm start
# http://127.0.0.1:3000
```

The populated distribution includes `web/dataset.json`. A code-only checkout intentionally shows an import screen until a verified dataset is provided. No synthetic sample results are used.

To rebuild the dataset from the verified final-list exports, Python 3 is sufficient:

```sh
python3 scripts/build_final_dataset.py \
  --batting /path/to/batting_Final_List_filtered.csv \
  --bowling /path/to/bowling_Final_List_filtered.csv \
  --out web/dataset.json
npm start
```

Regenerate the Pitch assistant's player summaries before every deployment:

```sh
node scripts/generate-assistant-data.mjs
```

## Tests

```sh
npm test
```

## Deployment

The production site deploys the `web/` directory as a static site with one serverless
function (`web/api/assistant.js`, the Pitch assistant). `web/dataset.json` and
`web/lib/players.json` are generated artifacts, excluded from the repository; build both
before deploying. The assistant reads its model key from the hosting project's
environment (`GEMINI_API_KEY`); no key lives in the repository.
