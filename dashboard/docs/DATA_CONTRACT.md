# Data contract: schema version 2

Top level: `schemaVersion` (2), `generated`, `disciplines`.

Each discipline (`batting`, `bowling`) has `seasons`, `source`, `interval` (`"80%"`),
`caveat`, `method` (title/text pairs) and `players`, the final rank list in rank order.

Player fields:

| Field | Meaning |
| --- | --- |
| id | Stable player identifier from the analysis pipeline |
| name | Display name |
| score | 0-100 pressure score; 50 is the role average |
| ciLow, ciHigh | 80% conditional score interval |
| aValue | Estimated high-pressure A in model units (per 100 opportunities) |
| hpBalls | Legal high-pressure balls |
| hpMatches | Matches with at least one high-pressure ball |
| rank | Final list rank, 1-based |
| top10 | True for the report top 10 |

Numeric fields are numbers or null; a missing value is never a placeholder zero. The
validator in `web/core.js` rejects unknown disciplines, duplicate players and
non-finite values before the site renders anything.
