#!/usr/bin/env python3
"""Build the website dataset.json from the verified final pressure-list exports.

Inputs are the two final-list CSVs produced by the analysis pipeline
(analysis/final-run/scores_new.py). The final selection keeps players with
substantial high-pressure evidence: at least 550 legal high-pressure balls for
batting and at least 601 for bowling, giving 14 batters and 16 bowlers.

Usage:
    python3 scripts/build_final_dataset.py \
        --batting batting_Final_List_filtered.csv \
        --bowling bowling_Final_List_filtered.csv \
        --out web/dataset.json --csv-dir ../reports/final_lists
"""
import argparse, csv, json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--batting', required=True)
ap.add_argument('--bowling', required=True)
ap.add_argument('--out', default='web/dataset.json')
ap.add_argument('--csv-dir', default=None)
args = ap.parse_args()

FLOORS = {'batting': 550, 'bowling': 601}

def num(v):
    try:
        f = float(v)
        return f if f == f and f not in (float('inf'), float('-inf')) else None
    except (TypeError, ValueError):
        return None

def load(path, disc):
    rows = list(csv.DictReader(open(path, newline='', encoding='utf-8-sig')))
    sel = [r for r in rows if int(r['HP_legal_balls']) >= FLOORS[disc]]
    sel.sort(key=lambda r: -float(r['Score']))
    players = []
    for i, r in enumerate(sel, 1):
        players.append({
            'id': r['player_id'], 'name': r['player'],
            'score': num(r['Score']),
            'ciLow': num(r['Score80low_conditional_mixture']),
            'ciHigh': num(r['Score80high_conditional_mixture']),
            'aValue': num(r['A_common']),
            'hpBalls': int(r['HP_legal_balls']), 'hpMatches': int(r['HP_matches']),
            'rank': i, 'top10': i <= 10,
        })
    return players

SEASONS = '843 completed matches, 2022-2026'
SOURCE = ('Final 18 November 2026 historical pressure analysis of 843 completed matches '
          'from the competition-supplied match list (2022-2026). Ball-by-ball records were '
          'recovered for those fixtures.')

def method(disc):
    value = (
        ['Batting: value above expectation',
         'A batter earns credit for producing more than the situation demanded, including the cost of losing their wicket. '
         'A is wicket-aware adjusted run value: runs scored plus the change in expected remaining team runs, compared with what '
         'an average batter was expected to produce in the same situations and bowling contexts. High-pressure A sets the ranking. '
         'Strike rate and boundary rates remain style context, not ranking inputs.']
        if disc == 'batting' else
        ['Bowling: value saved',
         'A bowler earns credit for conceding less than expected and taking wickets that are theirs. A is the reference '
         'expectation minus the batting run value conceded, using the same wicket-aware frame from the bowling side. '
         'Both innings are pooled. High-pressure A sets the ranking. Economy and boundary rates remain style context, not ranking inputs.'])
    return [
        ['Pressure before the ball',
         'The pressure score combines leverage (30%), collapse risk (25%), required-rate stress (25%) and match balance (20%), '
         'all measured from information available before the ball. Leverage is how much the next ball can change the win chance; '
         'collapse risk reads recent wickets; required-rate stress compares the chase demand with what is sustainable at the venue '
         'and stage; match balance rises the closer the match is. The weights are a declared starting choice.'],
        ['One shared pressure set',
         'A delivery is high pressure when its pre-ball score reaches 0.507: the top 35% of all 199,211 deliveries, 69,724 balls '
         '(35,922 from first innings and 33,802 from second innings) on one common scale across all 843 matches. Every player is '
         'measured over the same fixed set of high-pressure states.'],
        ['Expected-performance models',
         'Three model families estimate the expected ball outcome, the run value of a position and changes in win probability. '
         'The 843 matches are split into fixed groups, and each match is evaluated using models trained on the other groups. '
         'Run expectancy values a wicket by the runs the batting side would still be expected to score, so early wickets cost more '
         'than late ones. Win probability comes from one smooth model calibrated on held-out matches.'],
        value,
        ['Recency and partial pooling',
         'Player estimates weigh recent matches more, with a 365-day half-life chosen in advance; the population-level fit treats '
         'all dates equally. Partial pooling combines individual evidence with the population pattern, giving players with fewer '
         'pressure balls a more balanced estimate.'],
        ['The 0-100 score',
         'Each player\'s estimated A is standardised against the whole role population and converted to a score from 0 to 100: '
         '100 times the standard Normal cumulative probability of the standardised estimate. A score of 50 is the role average. '
         'Batting and bowling use separate scales.'],
        ['Who receives a rank',
         'Every identity in the modelled pool (838 batters, 572 bowlers) is scored. The final lists cover the 14 batters and '
         '16 bowlers with substantial high-pressure evidence, and the report presents the top 10 of each discipline.'],
        ['Reading the intervals',
         'Each score carries an 80% interval from the rating-mixture model, conditional on the fitted models, settings and '
         'reference mix. The intervals are wide (about 77 points for top-10 batters and 75 for top-10 bowlers), so the leaders '
         'are best read as a group: small simulation variation can exchange near-equal neighbours. A separate strict consistency '
         'label combines above-reference ability, precision and exposure; it remains unmet across both final lists.'],
    ]

CAVEAT = ('Historical analysis of recorded 2022-2026 performance in the high-pressure situations defined by this method. '
          'The 80% intervals are conditional on the fitted models, settings and reference mix and omit model-form and '
          'calibration uncertainty, so treat close ranks as approximate.')

dataset = {
    'schemaVersion': 2,
    'generated': '2026-11-18',
    'disciplines': {
        disc: {'seasons': SEASONS, 'source': SOURCE, 'interval': '80%',
               'method': method(disc), 'caveat': CAVEAT,
               'players': load(getattr(args, disc), disc)}
        for disc in ('batting', 'bowling')
    },
}
out = Path(args.out)
out.write_text(json.dumps(dataset, indent=1) + '\n')
print(f'Wrote {out}: batting={len(dataset["disciplines"]["batting"]["players"])}, '
      f'bowling={len(dataset["disciplines"]["bowling"]["players"])}')

if args.csv_dir:
    d = Path(args.csv_dir)
    d.mkdir(parents=True, exist_ok=True)
    head = ['rank', 'player', 'score', 'interval80_low', 'interval80_high', 'pressure_balls', 'pressure_matches']
    for disc in ('batting', 'bowling'):
        with open(d / f'{disc}_final_list.csv', 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(head)
            for p in dataset['disciplines'][disc]['players']:
                w.writerow([p['rank'], p['name'], round(p['score'], 1), round(p['ciLow']), round(p['ciHigh']),
                            p['hpBalls'], p['hpMatches']])
        print('Wrote', d / f'{disc}_final_list.csv')
