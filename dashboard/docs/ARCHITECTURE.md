# Architecture

## Runtime

The production website is static. The browser fetches `./dataset.json`, validates its version and numeric fields, and renders the selected discipline and metric. Filters, comparison selection and CSV export are local browser operations. There is no visitor database, login, tracking service, outbound analysis API or transaction flow.

The four public views use hash-based navigation (`#home`, `#batting`, `#bowling`, `#methodology`), with isolated sections and no server rewrites required. The homepage uses rounded three-column feature cards on a twelve-column desktop grid, stacking on mobile.

`web/core.js` contains pure selection, source routing and ordering functions. `web/app.js` handles presentation and event binding. `web/style.css` defines responsive desktop tables and mobile cards from the same filtered data. Charts are SVG with readable text values and an accessible description.

`server.mjs` provides a dependency-free local development server bound to `127.0.0.1` by default. It serves an explicit file allowlist and a read-only dataset route; it is not the production backend. `PORT`, `HOST` and `DATA_PATH` can be set through the environment. Do not expose the local server to untrusted networks without reviewing its deployment configuration.

## Data flow

1. Verified aggregate analysis exports remain the numeric source of truth.
2. The Python importer maps numeric values, list membership and metadata into schema version 1, with SHA-256 provenance for the input files it consumes.
3. The static exporter validates and copies this dataset plus the website assets into `dist/`.
4. Hosting serves those files without a build/runtime model fit.

No interpolation, recalibration, smoothing or refitting occurs in the website. Batting metrics retain full exported precision until display formatting. Bowling uses the aggregate exports' reported precision. Missing metrics stay null and are never imputed as zero.

## Ordering

The batting analysis top 10 is a membership list from the verified selection funnel. The website may reorder those members when another measure is selected. An all-player or sample-qualified view is exploratory and is not a replacement for the funnel.

Bowling published order follows the selection funnel (shrunk uplift). Sorting by the raw runs value is a separate, explicitly labeled exploratory choice.

## Security boundary

Only summary aggregates are exported. The server never serves arbitrary filesystem paths. Public export does not copy raw inputs, Python source folders, models, logs, environment files or credentials. Untrusted text is HTML-escaped and CSV strings are guarded against spreadsheet-formula injection. Static assets include a restrictive Content Security Policy and MIME-sniffing protection.
