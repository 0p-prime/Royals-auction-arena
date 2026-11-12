# Release procedure

1. Run source tests, import the verified aggregate exports and check numeric/list integrity.
2. Build the static export. Inspect `dist/` and confirm that only approved summary results and static assets are included.
3. Run standalone static HTTP browser checks, including mobile at 390px and 320px, no horizontal overflow, all five bowling sources and the batting quota warning.
4. Deploy the static directory to the intended free hosting project. Do not modify an unrelated portfolio project or buy a domain/upgrade.
5. Verify the actual public URL in a fresh browser, including dataset loading, chart rendering, discipline/innings switching, comparison and CSV export. A successful build alone is not a completed deployment.
6. Keep repository publication separate from deployment. Stage only reviewed source paths and approved data assets. Do not commit organizer inputs, environment files, cached credentials, fitted models, logs or generated Python caches. Respect the publication cadence established for the repository.

The root website source is designed to live in `dashboard/` inside a larger repository. The separate batting analysis source can live in `batting-analysis/`; it is not imported into visitor runtime. Existing `bowling-analysis/` is independent and must not be overwritten.
