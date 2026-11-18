#!/usr/bin/env node
/**
 * generate-assistant-data.mjs
 *
 * Builds web/lib/players.json for the Pitch assistant from the site dataset
 * (the same excluded dataset.json the deployment serves, schemaVersion 2).
 *
 * players.json is derived summary data and is EXCLUDED from the repository
 * (see .gitignore), exactly like dataset.json. Regenerate it before every
 * deployment:
 *
 *   node scripts/generate-assistant-data.mjs [path/to/dataset.json]
 *
 * Default input: web/dataset.json (produced by scripts/build_final_dataset.py
 * from the verified final-list exports). The output path is always
 * web/lib/players.json; vercel.json's includeFiles bundles web/lib/** into
 * the serverless function at deploy time. web/lib/knowledge.json (committed)
 * stays methodology-only; this script verifies that and fails if any
 * player-data key is present in it.
 */
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const input = process.argv[2] || join(root, 'web', 'dataset.json');
const outPlayers = join(root, 'web', 'lib', 'players.json');
const outKnowledge = join(root, 'web', 'lib', 'knowledge.json');

if (!existsSync(input)) {
  console.error(`Dataset not found: ${input}\nRun scripts/build_final_dataset.py first, or pass a dataset.json path.`);
  process.exit(1);
}

const dataset = JSON.parse(readFileSync(input, 'utf8'));
if (dataset.schemaVersion !== 2) {
  console.error('Expected a schemaVersion 2 dataset (final pressure lists).');
  process.exit(1);
}

const r1 = x => (typeof x === 'number' && Number.isFinite(x)) ? Math.round(x * 10) / 10 : (x ?? null);

const players = [];
const lists = {};
for (const disc of ['batting', 'bowling']) {
  const rows = dataset.disciplines[disc].players;
  lists[disc] = {
    finalList: rows.map(p => p.name),
    finalTop10: rows.filter(p => p.top10).map(p => p.name)
  };
  for (const p of rows) {
    players.push({
      n: p.name, d: disc, place: p.rank, score: r1(p.score),
      ci80: [r1(p.ciLow), r1(p.ciHigh)], aValue: p.aValue ?? null,
      hpBalls: p.hpBalls, hpMatches: p.hpMatches, top10: !!p.top10
    });
  }
}

writeFileSync(outPlayers, JSON.stringify({ players, battingLists: lists.batting, bowlingLists: lists.bowling }, null, 2) + '\n');
console.log(`Wrote ${outPlayers}: ${players.length} players (${lists.batting.finalList.length} batting, ${lists.bowling.finalList.length} bowling).`);

// Guard: the committed knowledge.json must stay methodology-only.
if (existsSync(outKnowledge)) {
  const k = JSON.parse(readFileSync(outKnowledge, 'utf8'));
  const bad = [];
  if ('players' in k) bad.push('players');
  for (const disc of ['batting', 'bowling']) if (k[disc] && 'lists' in k[disc]) bad.push(`${disc}.lists`);
  if (bad.length) {
    console.error(`Refusing to continue: ${outKnowledge} contains player data (${bad.join(', ')}). It must stay methodology-only.`);
    process.exit(1);
  }
  console.log('knowledge.json check: methodology-only, OK.');
}
