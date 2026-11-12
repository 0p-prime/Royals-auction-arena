# Verification record

Build checked on 12 November 2026. This record covers the website and aggregate import, not a new fit of the original analysis models.

## Automated checks

- 9 Node tests pass: combined filters, immutable ordering, distinct source lists, composite-vs-runs sorting, null metrics, numeric schema validation, explicit missing-data state, file allowlist/method restrictions and dataset route.
- 2 Python importer unit tests pass for finite numeric parsing and null handling.
- Aggregate integrity check passes for 202 batters and five bowling lists (118 overall, 59 chase pressure, 41 chase uplift, 96 first-innings pressure, 57 first-innings uplift). 4,213 numeric comparisons plus membership/order checks match their input exports.
- Browser checks pass with no JavaScript errors. Both the local server and a standalone static export were tested. The static export has no dependency on the development API.

## Interaction coverage

Batting top-10 count, 3/4/3 quota warning, empty search, pressure-level interval absence, all five bowling list leaders, innings switching, source composite order, player comparison and CSV download were checked. Sample-qualified and active eligibility counts reproduce as 52 and 50. Export filename and file creation were checked. Phone-width layouts at 390px and 320px have no page-level horizontal overflow.

Observed source leaders: Samson (batting analysis top 10); Bumrah (bowling overall); Umesh Yadav (chase pressure); Axar Patel (chase uplift); Starc (first-innings pressure); Ashwin (first-innings uplift). Bowling source order is composite, so a negative runs component can still appear first.

## Visual inspection

Actual pixels were inspected for desktop, 390px and 320px layouts, forest charts, mobile player cards, and comparison cards. The Royals-inspired revision uses pink/navy, original project branding and an original cricket-field graphic, without copying official logos or making affiliation claims. Chart values, interval bars, zero line and labels remain readable. The source cohort and filtered-player counts are labeled separately.

## Navigation revision

Home, Batting, Bowling and Methodology route isolation, direct hash navigation, rounded grid layout, original crest at desktop/mobile header sizes and both discipline methods were checked after the website navigation revision. 390px and 320px layouts remain within the viewport.

## Scope not verified by this record

Live hosting, public URL availability and account-level deployment settings must be checked after deployment. Auction rules/player availability and future pressure skill are outside the website's verified scope. Original pipeline test reports (18 batting, 61 bowling) are inherited evidence from the supplied verified artifacts, not new tests executed by this website build.
