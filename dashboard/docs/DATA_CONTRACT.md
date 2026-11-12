# Data contract: schema version 1

Top level: `schemaVersion`, `title`, `disciplines`, `provenance`.

Each discipline has `seasons`, `source`, `interval`, `caveat`, `method` (title/text pairs), and `players`. Bowling additionally has `lists`, `minimumBalls`, `units` and `definitions`.

Player fields:

| Field | Meaning |
| --- | --- |
| id, name | Exact supplied analysis name; not a cross-discipline identity registry |
| team | Historical recorded team, never current eligibility |
| role | Batting position group, or bowling pace/spin/unknown reporting label |
| pressure, normal, overall, uplift | Numeric measure or null; never a placeholder zero |
| ciLow, ciHigh | Batting uplift interval; bowling selected-list runs-component interval |
| pressureBalls, normalBalls | Raw sample counts; bowling overall uses pressureBalls=0 because pressure count is not supplied |
| sampleQualified | Batting count floors without active-season restriction |
| eligible | Supplied batting active eligibility; bowling selected-list qualification |
| top10, shortlisted, quota | Supplied batting list membership; bowling top10 from source order <=10 |
| confidence | Source batting category, not inferred from arbitrary score thresholds |
| deliveries | Bowling attempts in selected source list |
| order, rankMedian, rankBest, rankWorst | Source bowling ordering and wicket-value sensitivity |
| wickets, ranksByWicketValue, phases | Bowling component and stratum context |

Bowling list keys: `overall`, `chasePressureLevel`, `chasePressureUplift`, `firstInningsPressureLevel`, `firstInningsPressureUplift`. The active list supplies the players; absent metrics remain null. The interface uses delivery attempts rather than the missing pressure count when applying an overall-view sample filter.

All non-finite CSV values are serialized as null. The importer rejects a bowling source whose metadata is not v5. Source hashes refer to aggregate files, not raw delivery files.
