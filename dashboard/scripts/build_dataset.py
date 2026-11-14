#!/usr/bin/env python3
"""Build the dashboard dataset.json from the analysis outputs (supplied-CSV universe).
Batting: batsman_ppf.csv + shortlist_35.csv + top10_batsmen.csv + top10_role_quota.csv.
Bowling: all_bowlers.csv (pooled official aggregates) + delivery_scores.csv.gz
(per-innings splits = direct aggregation of the same scored rows; no refitting).

Usage:
    python3 scripts/build_dataset.py --batting-dir /path/to/batting/outputs \
        --bowling-dir /path/to/bowling/outputs --out web/dataset.json
"""
import argparse, csv, json, hashlib, math, sys
from pathlib import Path
import pandas as pd

_ap = argparse.ArgumentParser()
_ap.add_argument('--batting-dir', required=True)
_ap.add_argument('--bowling-dir', required=True)
_ap.add_argument('--out', default='web/dataset.json')
_args = _ap.parse_args()
BAT = Path(_args.batting_dir)
BOWL = Path(_args.bowling_dir)

def number(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (ValueError, TypeError):
        return None

def rows(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

# ---------- batting ----------
def batting():
    memberships = {}
    for key, fn, col in [('shortlisted','shortlist_35.csv','batter'),('top10','top10_batsmen.csv','batter'),('quota','top10_role_quota.csv','batter')]:
        memberships[key] = {r[col] for r in rows(BAT / fn)}
    players = []
    ppf = rows(BAT / 'batsman_ppf.csv')
    for r in ppf:
        name = r['batter']
        players.append(dict(id=name, name=name, team=r['team'], role=r['role'],
            pressure=number(r['RAE100_p']), normal=number(r['RAE100_n']), overall=number(r['RAE100_all']),
            uplift=number(r['PPF_adj']), ciLow=number(r['ci_low_adj']), ciHigh=number(r['ci_high_adj']),
            pressureBalls=int(r['balls_p']), normalBalls=int(r['balls_n']), eligible=r['eligible']=='True',
            sampleQualified=int(r['balls_p'])>=60 and int(r['balls_n'])>=200, active=r['active']=='True',
            confidence=r['confidence'], **{k: name in ns for k, ns in memberships.items()}))
    qual = sum(1 for p in players if p['sampleQualified'])
    act = sum(1 for p in players if p['sampleQualified'] and p['active'])
    return dict(players=players, interval='90%', seasons='IPL + T20I + Asia Cups 2022-2026',
        sampleFloorsText=f"{qual} meet sample floors; {act} active",
        source='Verified batting aggregate outputs from the supplied CSV match data (867 playable fixtures: IPL, T20I and Asia Cup tournaments, 2022-2026).',
        caveat=("Rankings compare how players actually performed on past matches in the supplied data under the model-defined pressure measure. "
                "Exact placings depend on the method's pressure cutoffs, sample floors and selection rules, so treat fine rank differences as approximate. "
                "The displayed 90% intervals describe the shrunk uplift estimate, not overall uncertainty."),
        method=[
          ['Pressure and performance','BPI = 100 x probability of a dot or striker dismissal on the current legal ball. Pre-ball MPI/LPI features use nested match-grouped out-of-fold models. RAE is batter runs minus expected runs, minus a state-specific wicket penalty times the centered dismissal residual. Pressure = top 30% of per-match BPI (70th percentile); normal = bottom 55% (55th percentile); the middle 15% is left out. Cutoffs are quantiles over all supplied 2022-26 matches.'],
          ['Uplift and uncertainty','PPF is recency-weighted pressure RAE100 minus normal RAE100. PPF_adj applies empirical-Bayes shrinkage. The displayed 90% uplift intervals are lambda-scaled match-bootstrap intervals, conditional on the fitted estimator, not posterior intervals. Pressure and overall levels have no intervals supplied in this export.'],
          ['Selection and quotas','Sample-qualified requires at least 60 pressure and 200 normal balls. The analysis top 10 additionally uses an active-player/shortlist/performance funnel. The 3 opener / 4 middle / 3 finisher quota list fills role slots from the same funnel order. Team labels are the latest observed team in the data (club or country), not current retention or auction status.'],
          ['Scope and checks','This is a data-analysis project: rankings describe observed performance on the supplied matches under the defined pressure measure. Internal consistency check: split-half correlation across match samples is -0.00 for all batsmen and -0.02 for eligible batsmen, so fine rank differences are approximate. Baseline comparisons are in-sample. Sparse wicket-penalty cells add unquantified uncertainty.'],
          ['Data exclusions','200,964 delivery rows in scope, 192,415 legal. No-ball batter runs and non-legal-ball dismissals are excluded. Retired hurt/out does not count as striker dismissal. 1,347 DLS-affected chase rows are excluded because revised targets were unavailable.']])

# ---------- bowling ----------
def rate(g, col):
    den = (g.legal * g.weight).sum()
    return (g[col] * g.weight).sum() / den if den else float('nan')

def bowling():
    allb = pd.read_csv(BOWL / 'all_bowlers.csv')
    top10_names = set(pd.read_csv(BOWL / 'top10.csv')['Bowler'])
    meta = allb.set_index('Bowler')
    d = pd.read_csv(BOWL / 'delivery_scores.csv.gz',
                    usecols=['match_id','innings','bowler','legal','weight','rae','bucket'])
    d = d[d.bucket.isin(['pressure','normal'])]

    def agg(sub):
        out = {}
        for b, g in sub.groupby('bowler'):
            p = g[g.bucket == 'pressure']; n = g[g.bucket == 'normal']
            out[b] = dict(
                pb=int(p.legal.sum()), nb=int(n.legal.sum()),
                deliveries=int(g.legal.sum()),
                pressure=number(100 * rate(p, 'rae')) if len(p) else None,
                normal=number(100 * rate(n, 'rae')) if len(n) else None,
                overall=number(100 * rate(g, 'rae')))
        return out

    pooled = {r['Bowler']: dict(pb=int(r['pressure_balls']), nb=int(r['normal_balls']),
                                deliveries=int(r['pressure_balls'] + r['normal_balls']),
                                pressure=number(r['rae100_pressure']), normal=number(r['rae100_normal']),
                                overall=number(r['rae100_overall']), uplift=number(r['BPF_adj']),
                                ciLow=number(r['CI_low']), ciHigh=number(r['CI_high']))
              for _, r in allb.iterrows()}
    by_inn = {2: agg(d[d.innings == 2]), 1: agg(d[d.innings == 1])}

    def mklist(source, metric, floors, order_by):
        pb_min, nb_min = floors
        out = []
        for b, a in source.items():
            if a['pb'] < pb_min or a['nb'] < nb_min:
                continue
            v = a.get(order_by)
            if v is None or not math.isfinite(v):
                continue
            m = meta.loc[b] if b in meta.index else None
            p = dict(id=b, name=b,
                team=str(m['Team']) if m is not None else '',
                role=str(m['Type']).lower() if m is not None else 'unknown',
                pressure=a['pressure'], normal=a['normal'], overall=a['overall'],
                uplift=a.get('uplift'),
                ciLow=a.get('ciLow') if order_by != 'overall' else None,
                ciHigh=a.get('ciHigh') if order_by != 'overall' else None,
                pressureBalls=a['pb'], normalBalls=a['nb'], deliveries=a['deliveries'],
                eligible=True, top10=b in top10_names, shortlisted=False, quota=False,
                wickets=None, rankMedian=None, rankBest=None, rankWorst=None,
                ranksByWicketValue=None, phases=None, confidence=None)
            p[metric] = v
            out.append(p)
        out.sort(key=lambda p: (-p[metric], p['name']))
        for i, p in enumerate(out):
            p['order'] = i + 1
        return out

    lists = {}
    lists['overall'] = mklist(pooled, 'overall', (0, 200), 'overall')
    funnel_pool = {b: a for b, a in pooled.items()
                   if b in meta.index and bool(meta.loc[b, 'eligible'])
                   and pd.notna(meta.loc[b, 'shortlist_rank'])
                   and number(meta.loc[b, 'rae100_pressure']) is not None and meta.loc[b, 'rae100_pressure'] >= 0}
    lists['pooledUplift'] = mklist(funnel_pool, 'uplift', (60, 200), 'uplift')
    lists['chasePressureLevel'] = mklist(by_inn[2], 'pressure', (60, 0), 'pressure')
    lists['firstInningsPressureLevel'] = mklist(by_inn[1], 'pressure', (40, 0), 'pressure')
    # uplift splits: pressure minus normal within the innings
    for inn, key, floors in [(2, 'chasePressureUplift', (60, 120)), (1, 'firstInningsPressureUplift', (40, 100))]:
        src = by_inn[inn]
        for b, a in src.items():
            u = (a['pressure'] - a['normal']) if (a['pressure'] is not None and a['normal'] is not None) else None
            a['uplift'] = number(u)
            a['ciLow'] = None; a['ciHigh'] = None
        lists[key] = mklist(src, 'uplift', floors, 'uplift')

    return dict(players=[], lists=lists, interval=None,
        seasons='IPL + T20I + Asia Cups; 2023-26 scored, 2022 season training-only',
        source='Verified bowling aggregate outputs from the supplied CSV match data (867 playable fixtures: IPL, T20I and Asia Cup tournaments, 2022-2026).',
        minimumBalls={'overall': 'at least 200 legal balls',
                      'pooledUplift': 'at least 60 pressure and 200 normal legal balls',
                      'chasePressureLevel': 'at least 60 pressure legal balls',
                      'chasePressureUplift': 'at least 60 pressure and 120 normal legal balls',
                      'firstInningsPressureLevel': 'at least 40 pressure legal balls',
                      'firstInningsPressureUplift': 'at least 40 pressure and 100 normal legal balls'},
        definitions={
          'pressureChase': 'Pressure balls are the highest-BoPI (boundary-risk) 30% of deliveries; normal balls are the lowest 55%.',
          'pressureFirstInnings': 'The same BoPI buckets apply in both innings; first-innings lists use first-innings deliveries only.',
          'team': 'Team is the latest observed team in the data (club or country), not current auction availability.',
          'expectation': 'BoPI = 100 x predicted boundary chance from a model trained on earlier in-sample seasons only.'},
        units={
          'order': 'Order follows the displayed metric value, then name.',
          'runsSavedPer100': 'Runs saved vs model expectation per 100 legal balls (wides and no-balls add to the cost but not the ball count). Positive = saved runs.',
          'runsSavedCi': 'The 95% interval on the pooled uplift (BPF_adj) comes from match-cluster bootstrap resampling; per-innings views have no interval supplied.',
          'uplift': 'Uplift = pressure runs saved per 100 legal balls minus the bowler\'s own normal-balls rate. The pooled headline ranking uses BPF_adj, which shrinks uplift toward zero for small pressure samples.',
          'wicketsAboveExpectedPer100': 'Credited wickets (bowled, caught, caught & bowled, lbw, stumped, hit wicket) count 20 runs each in RAE; no run-outs.',
          'rankRange': 'Not used in this version: a single wicket value of 20 is fixed.'},
        caveat=("Rankings compare how bowlers actually performed on past matches in the supplied data under the model-defined pressure measure. "
                "Exact placings depend on the pressure cutoffs, the wicket value of 20 and the selection floors, so treat fine rank differences as approximate. "
                "The pooled uplift interval covers sampling noise only."),
        method=[
          ['Pressure definitions','BoPI = 100 x predicted chance the ball goes for a genuine boundary, from facts known before the ball. Pressure = top 30% BoPI (70th percentile); normal = bottom 55% (55th percentile). Cutoffs are quantiles of training-season deliveries.'],
          ['Performance and ordering','RAE = expected charged runs - actual charged runs + 20 per credited wicket. Lists show runs saved vs expectation per 100 legal balls.'],
          ['Uplift and intervals','BPF = pressure RAE100 - normal RAE100; BPF_adj = BPF x pressure_balls / (pressure_balls + 60). The final pooled ranking orders by BPF_adj.'],
          ['Expectation model','Season-ordered out-of-sample scoring: 2022 matches train the expectations only and carry no scores; 2023-26 matches are scored.'],
          ['Consistency and limits','This is a data-analysis project: lists describe observed performance on the supplied matches. Internal consistency check: alternate-match BPF rank correlation 0.05, so fine placings are approximate. Boundary risk is a proxy for pressure.'],
          ['Team and sample scope','Rates are per 100 legal balls; wides and no-balls add to the cost but not the ball count. 158,496 scored delivery attempts across 687 fixtures (2023-26).']])

def main():
    data = dict(schemaVersion=1, title='Royals pressure lab',
                disciplines={'batting': batting(), 'bowling': bowling()})
    paths = sorted(BAT.glob('*.csv')) + [BOWL / 'all_bowlers.csv', BOWL / 'top10.csv']
    data['provenance'] = [dict(filename=p.name, sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths]
    out = Path(_args.out)
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(data, allow_nan=False, indent=2) + '\n')
    b = data['disciplines']['batting']; w = data['disciplines']['bowling']
    print('batters:', len(b['players']), '| qualified:', sum(p['sampleQualified'] for p in b['players']),
          '| qualified+active:', sum(p['sampleQualified'] and p['active'] for p in b['players']))
    for k, l in w['lists'].items():
        print(f'bowling {k}: {len(l)} bowlers; #1 {l[0]["name"] if l else "-"}')
    print('wrote', out)

if __name__ == '__main__':
    main()
