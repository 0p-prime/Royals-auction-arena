# Verification record

Build checked on 18 November 2026. This record covers the website and the final-list
dataset build, not a new fit of the analysis models.

## Automated checks

- Node tests pass: pool/sample/search filters, immutable ranking order with exposure
  tie-break, null-metric handling, schema-version-2 validation (including duplicate and
  non-finite rejection), and a contract check that the built dataset holds 14 batters
  and 16 bowlers whose top-10 names match the delivered report exactly, with every
  score inside its 80% interval.
- Parse checks cover the application modules and the assistant function before deployment.
- A copy check fails the build if retired comparison-view terminology returns to the
  application, the markup or the assistant.

## Dataset provenance

`web/dataset.json` is built directly from the verified final-list exports of the
18 November 2026 run (see `analysis/final-run/`). Scores, intervals, pressure-ball and
pressure-match counts are carried through unchanged.
