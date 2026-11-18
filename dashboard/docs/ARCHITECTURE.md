# Architecture

## Runtime

The production website is static. The browser fetches `./dataset.json`, validates its
schema version and numeric fields, and renders the selected discipline. Filters,
comparison selection and CSV export are local browser operations. There is no visitor
database, login, tracking service or transaction flow.

The five public views use hash-based navigation (`#home`, `#batting`, `#bowling`,
`#squad`, `#methodology`), with isolated sections and no server rewrites required. The
homepage uses rounded three-column feature cards on a twelve-column desktop grid,
stacking on mobile.

`web/core.js` contains pure filtering, ordering and validation functions. `web/app.js`
handles presentation and event binding. `web/style.css` defines responsive desktop
tables and mobile cards from the same filtered data. Charts are SVG with readable text
values and an accessible description. `web/squad.js` and `web/squad-core.js` implement
the squad and purse planner; its data lives only in the visitor's browser.

`server.mjs` provides a dependency-free local development server bound to `127.0.0.1`
by default. It serves an explicit file allowlist and a read-only dataset route; it is
not the production backend. `PORT`, `HOST` and `DATA_PATH` can be set through the
environment.

## Pitch assistant

`web/api/assistant.js` is a single serverless function. It answers from the committed
methodology summary (`web/lib/knowledge.json`) and the generated player summaries
(`web/lib/players.json`, built from the same dataset the site serves), with per-IP rate
limits and a daily cap. The model key comes from the hosting project's environment.

## Data flow

1. The verified final-list exports from the analysis pipeline remain the numeric source of truth.
2. `scripts/build_final_dataset.py` turns them into `web/dataset.json` (schema version 2).
3. `scripts/generate-assistant-data.mjs` derives `web/lib/players.json` from the same dataset.
4. Both generated artifacts are excluded from the repository and rebuilt before every deployment.
