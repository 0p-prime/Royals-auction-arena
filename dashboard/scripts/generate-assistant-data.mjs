#!/usr/bin/env node
/**
 * generate-assistant-data.mjs
 *
 * Builds web/lib/players.json for the Pitch assistant from the derived site
 * dataset (the same excluded dataset.json the deployment serves).
 *
 * players.json is derived summary data and is EXCLUDED from the repository
 * (see .gitignore), exactly like dataset.json. Regenerate it before every
 * deployment:
 *
 *   node scripts/generate-assistant-data.mjs [path/to/dataset.json]
 *
 * Default input: web/dataset.json (produced by the data importer / static
 * exporter from the verified analysis outputs). The output path is always
 * web/lib/players.json; vercel.json's includeFiles bundles web/lib/** into
 * the serverless function at deploy time. web/lib/knowledge.json (committed)
 * stays methodology-only; this script verifies that and fails if any
 * player-data key is present in it.
 */
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const input = process.argv[2] || join(root, 'web', 'dataset.json');
const outPlayers = join(root, 'web', 'lib', 'players.json');
const outKnowledge = join(root, 'web', 'lib', 'knowledge.json');

if (!existsSync(input)) {
  console.error(`Dataset not found: ${input}\nRun the data importer / static exporter first, or pass a dataset.json path.`);
  process.exit(1);
}

const dataset = JSON.parse(readFileSync(input, 'utf8'));
const bat = dataset.disciplines.batting;
const bowl = dataset.disciplines.bowling;

const LIST_ORDER = ['pooledUplift', 'overall', 'chasePressureLevel', 'chasePressureUplift', 'firstInningsPressureLevel', 'firstInningsPressureUplift'];
const LEVEL_FIELD = { pooledUplift: 'uplift', overall: 'overall', chasePressureLevel: 'pressure', chasePressureUplift: 'uplift', firstInningsPressureLevel: 'pressure', firstInningsPressureUplift: 'uplift' };

const r1 = x => (typeof x === 'number' && Number.isFinite(x)) ? Math.round(x * 10) / 10 : (x ?? null);

const finalRow = r => ({
  place: r.order ?? null, score: r1(r.pressure), ci80: [r1(r.ciLow), r1(r.ciHigh)],
  hpBalls: r.pressureBalls, hpMatches: r.hpMatches ?? null, eligible: !!r.eligible, top10: !!r.top10
});

const players = [];
const batPressure = new Map((bat.lists?.pooledPressure || []).map(p => [p.id, p]));
for (const p of bat.players) {
  const row = {
    n: p.name, d: 'batting', team: p.team, role: p.role,
    pressure: r1(p.pressure), normal: r1(p.normal), overall: r1(p.overall), uplift: r1(p.uplift),
    ci90: [r1(p.ciLow), r1(p.ciHigh)],
    pressureBalls: p.pressureBalls, normalBalls: p.normalBalls,
    confidence: p.confidence, eligible: p.eligible, sampleQualified: p.sampleQualified,
    shortlisted: p.shortlisted, analysisTop10: p.top10, roleQuota: p.quota
  };
  const fp = batPressure.get(p.id);
  if (fp) { row.finalPressure = finalRow(fp); batPressure.delete(p.id); }
  players.push(row);
}
for (const fp of batPressure.values()) {
  players.push({ n: fp.name, d: 'batting', team: fp.team, role: fp.role, finalPressure: finalRow(fp) });
}

const bowlers = new Map(); // id -> aggregated row, first-appearance order
for (const listName of LIST_ORDER) {
  for (const r of bowl.lists[listName] || []) {
    if (!bowlers.has(r.id)) bowlers.set(r.id, { n: r.name, d: 'bowling', team: r.team, role: r.role, lists: {} });
    bowlers.get(r.id).lists[listName] = {
      place: r.order,
      level: r1(r[LEVEL_FIELD[listName]]),
      ci95: [r1(r.ciLow), r1(r.ciHigh)],
      deliveries: r.deliveries ?? null,
      wicketsAboveExpectedPer100: r.wickets ?? null,
      rankMedian: r1(r.rankMedian),
      rankRange: [r.rankBest ?? null, r.rankWorst ?? null],
      top10: !!r.top10,
      phases: r.phases ?? null
    };
  }
}
for (const r of bowl.lists?.pooledPressure || []) {
  if (!bowlers.has(r.id)) bowlers.set(r.id, { n: r.name, d: 'bowling', team: r.team, role: r.role, lists: {} });
  bowlers.get(r.id).lists.finalPressure = finalRow(r);
}
players.push(...bowlers.values());

const battingLists = {
  finalPressureTop10: (bat.lists?.pooledPressure || []).filter(p => p.top10).map(p => p.name),
  analysisTop10: bat.players.filter(p => p.top10).map(p => p.name),
  shortlist35: bat.players.filter(p => p.shortlisted).map(p => p.name),
  roleQuota: bat.players.filter(p => p.quota).map(p => p.name)
};
const bowlingLists = {};
for (const listName of LIST_ORDER) {
  bowlingLists[listName] = (bowl.lists[listName] || []).slice(0, 10).map(r => r.name);
}
bowlingLists.pooledPressure = (bowl.lists?.pooledPressure || []).filter(r => r.top10).map(r => r.name);

const out = { players, battingLists, bowlingLists };
writeFileSync(outPlayers, JSON.stringify(out, null, 2) + '\n');
console.log(`Wrote ${outPlayers}: ${players.length} players (${bat.players.length} batting, ${bowlers.size} bowling).`);

// Guard: the committed knowledge.json must stay methodology-only.
if (existsSync(outKnowledge)) {
  const k = JSON.parse(readFileSync(outKnowledge, 'utf8'));
  const bad = [];
  if ('players' in k) bad.push('players');
  for (const key of ['analysisTop10', 'shortlist35', 'roleQuota']) if (k.batting && key in k.batting) bad.push(`batting.${key}`);
  if (k.bowling && 'lists' in k.bowling) bad.push('bowling.lists');
  if (bad.length) {
    console.error(`Refusing to continue: ${outKnowledge} contains player data (${bad.join(', ')}). It must stay methodology-only.`);
    process.exit(1);
  }
  console.log('knowledge.json check: methodology-only, OK.');
}
