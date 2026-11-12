# Royals Auction Arena

IPL auction analytics project. Code is grouped by domain.

- `bowling-analysis/` - historical IPL bowling pressure analysis (2022-26):
  how bowlers performed vs model expectation, overall, under pressure and
  pressure uplift, for both innings. Code, methodology, tests and the frozen
  trained models. See `bowling-analysis/README.md`.
- `batting-analysis/` - batting pressure analysis (2022-26): performance
  under pressure vs each batsman's own normal level, with validation and
  tests. See `batting-analysis/README.md` and `METHODOLOGY.md`.
- `dashboard/` - the read-only analysis website (HTML/CSS/JS, SVG charts,
  JSON data). See `dashboard/README.md`.

Further domains land here as they are built.
