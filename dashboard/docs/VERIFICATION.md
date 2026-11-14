# Verification record

Build checked on 14 November 2026. This record covers the website and aggregate dataset build, not a new fit of the original analysis models.

## Automated checks

- 9 Node tests pass: combined filters, immutable ordering, distinct source lists, ordering options, null metrics, numeric schema validation, explicit missing-data state, file allowlist/method restrictions and dataset route.
- 2 Python unit tests pass for finite numeric parsing and null handling.
- Aggregate integrity check passes for 649 batters and six bowling views (123 overall, 35 funnel, 108 chase pressure, 36 chase uplift, 156 first-innings pressure, 63 first-innings uplift). 6,204 numeric comparisons plus membership/order checks match their input exports. The pooled funnel view reproduces the official bowling top 10 exactly.
- The dataset passes the site's own contract validation before serving.

## Interaction coverage

Batting top-10 count, quota pool, empty search, pressure-level interval absence, all six bowling view leaders, innings switching including the both-innings funnel view, published funnel order, player comparison and CSV download were checked against the built dataset. Sample-qualified and active eligibility counts reproduce as 130 and 122.

Observed leaders in this build: TH David (batting analysis top 10); Sufiyan Muqeem (bowling overall); Haris Rauf (first-innings pressure); AM Ghazanfar (chase pressure); M Pathirana (first-innings uplift and the pooled funnel list); G Motie (chase uplift).

## Visual inspection

Desktop and phone layouts, forest charts, mobile player cards and comparison cards were inspected on the previous design revision; no layout code changed in this update. The live deployed site is re-checked visually after each deployment.

## Scope not verified by this record

Live hosting, public URL availability and account-level deployment settings must be checked after deployment. Auction rules and player availability are outside the website's verified scope. Original pipeline test reports are inherited evidence from the supplied verified artifacts, not new tests executed by this website build.
