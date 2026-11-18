# Release procedure

1. Run the test suite (`npm test`).
2. Rebuild `web/dataset.json` from the verified final-list exports and
   `web/lib/players.json` from the dataset; confirm the dataset passes contract
   validation and matches the report's top-10 lists (covered by the test suite).
3. Deploy the `web/` directory to the hosting project. Confirm the assistant function
   keeps its configured model key from the project environment.
4. Verify the actual public URL in a fresh browser: dataset loading, chart rendering,
   discipline switching, comparison, CSV export, the squad planner and a live Pitch
   answer. A successful build alone is not a completed deployment.
5. Keep repository publication separate from deployment. Stage only reviewed source
   paths and approved data assets. Do not commit organizer inputs, environment files,
   cached credentials, fitted models, logs or generated Python caches.
