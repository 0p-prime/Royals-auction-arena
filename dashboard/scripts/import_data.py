#!/usr/bin/env python3
"""Convert verified aggregate analysis files into the local dashboard contract.
No model fitting and no raw delivery processing occurs here.
"""
import argparse, csv, hashlib, json, math
from pathlib import Path

def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None

def rows(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as file:
        return list(csv.DictReader(file))

def batting(directory):
    directory = Path(directory)
    memberships = {}
    for key, filename, name_column in [('shortlisted','shortlist_35.csv','batter'),('top10','top10_batsmen.csv','Batsman'),('quota','top10_role_quota.csv','Batsman')]:
        memberships[key] = {r[name_column] for r in rows(directory / filename)}
    players = []
    for r in rows(directory / 'batsman_ppf.csv'):
        name = r['batter']
        players.append(dict(id=name, name=name, team=r['team'], role=r['role'],
            pressure=number(r['RAE100_p']), normal=number(r['RAE100_n']), overall=number(r['RAE100_all']),
            uplift=number(r['PPF_adj']), ciLow=number(r['ci_low_adj']), ciHigh=number(r['ci_high_adj']),
            pressureBalls=int(r['balls_p']), normalBalls=int(r['balls_n']), eligible=r['eligible']=='True',
            sampleQualified=int(r['balls_p'])>=60 and int(r['balls_n'])>=200, active=r['active']=='True', confidence=r['confidence'], **{key:name in names for key,names in memberships.items()}))
    return dict(players=players, interval='90%', seasons='IPL 2022-2026',
        source='Verified batting aggregate outputs; Cricsheet IPL JSON, retrieved 2026-11-12.',
        caveat="Historical ordering is indicative. Only Samson's 90% uplift interval among the analysis top 10 excludes zero. Split-half correlation: 0.026 for eligible batsmen; temporal uplift correlation: 0.16. New and settled batsmen are combined, with no balls-faced adjustment.",
        method=[
          ['Pressure and performance','BPI = 100 × probability of a dot or striker dismissal on the current legal ball. Pre-ball MPI/LPI features use nested match-grouped out-of-fold models. RAE is batter runs minus expected runs, minus a state-specific wicket penalty times the centered dismissal residual. Pressure and normal are distinct BPI buckets.'],
          ['Uplift and uncertainty','PPF is recency-weighted pressure RAE100 minus normal RAE100. PPF_adj applies empirical-Bayes shrinkage. The displayed 90% uplift intervals are lambda-scaled match-bootstrap intervals, conditional on the fitted estimator, not posterior intervals. Pressure and overall levels have no intervals supplied in this export.'],
          ['Selection and quotas','Sample-qualified requires at least 60 pressure and 200 normal balls. The analysis top 10 additionally uses an active-player/shortlist/performance funnel; 52 meet the sample floors; 50 also meet the source active-season requirement. Sample-qualified is not the same pool. The 3 opener / 4 middle / 3 finisher quota list includes Rinku Singh and Stubbs despite negative uplift; they fill finisher slots, not the pressure-specialist criterion. Team labels are recorded data, not current retention or auction status.'],
          ['Validation and scope','Split-half 0.026 eligible (n=52), -0.195 all (n=140); temporal pressure-premium correlation 0.16. The reported 0.60 pressure-level correlation is not evidence that uplift reproduces. Baseline comparisons are in-sample. 69% of pressure balls occur within a batter\'s first six balls. Sparse wicket-penalty cells add unquantified uncertainty; 19% have fewer than five historical stints.'],
          ['Data exclusions','Legal balls only. 585 no-ball batter runs and 27 non-legal-ball dismissals are excluded. Retired hurt/out does not count as striker dismissal. 414 DLS chase rows are excluded because revised targets were unavailable.']])

def bowling(path):
    raw = json.loads(Path(path).read_text())
    if not str(raw['meta']['version']).startswith('v5 '):
        raise ValueError('The dashboard requires the verified v5 bowling export, not a mixed-version file.')
    lists={}
    for key, records in raw['lists'].items():
        metric = 'overall' if key=='overall' else 'uplift' if key.endswith('Uplift') else 'pressure'
        players=[]
        for r in records:
            p=dict(id=r['bowler'],name=r['bowler'],team=r['team'],role=r['type'].lower(),
                pressure=None,normal=None,overall=None,uplift=None,
                ciLow=r['runsSavedCiLow'],ciHigh=r['runsSavedCiHigh'],
                pressureBalls=r.get('pressureBalls',r['deliveries']) if metric!='overall' else 0,
                normalBalls=r.get('normalBalls'),deliveries=r['deliveries'],eligible=True,
                top10=r['order']<=10,shortlisted=False,quota=False,order=r['order'],
                wickets=r['wicketsAboveExpectedPer100'],rankMedian=r['rankMedian'],rankBest=r['rankBest'],rankWorst=r['rankWorst'],
                ranksByWicketValue=r['ranksByWicketValue'],phases=r.get('phasesUsed'),confidence=None)
            p[metric]=r['runsSavedPer100'];players.append(p)
        lists[key]=players
    meta=raw['meta']
    return dict(players=[],lists=lists,interval='about 95%',seasons=meta['seasons'],source='Verified v5 bowling aggregate export. Cricsheet IPL JSON; historical reporting metadata, not auction eligibility.',
        minimumBalls=meta['minimumBalls'],definitions=meta['definitions'],units=meta['units'],
        caveat='Pressure level and uplift repeat weakly. Wicket and combined ranks do not repeat. Lists are not validated for pressure-skill or auction selection. 2025-26 is development data, not a fresh test. Runs intervals do not quantify uncertainty in the composite ranks.',
        method=[['Pressure definitions',meta['definitions']['pressureChase']+' '+meta['definitions']['pressureFirstInnings']],['Performance and ordering',meta['units']['runsSavedPer100']+' '+meta['units']['wicketsAboveExpectedPer100']+' '+meta['units']['order']+' '+meta['units']['rankRange']],['Uplift and intervals',meta['units']['uplift']+' '+meta['units']['runsSavedCi']],['Expectation model',meta['definitions']['expectation']],['Validation and limits',meta['methodologyNote']],['Team and sample scope',meta['definitions']['team']+' All bowling denominators are delivery attempts, including wides and no-balls; batting denominators are legal balls.']])

def build(batting_dir, bowling_path):
    data=dict(schemaVersion=1,title='Royals pressure lab',disciplines={'batting':batting(batting_dir)})
    if bowling_path:data['disciplines']['bowling']=bowling(bowling_path)
    paths=list(Path(batting_dir).glob('*.csv'))+([Path(bowling_path)] if bowling_path else [])
    data['provenance']=[dict(filename=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(paths)]
    return data

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batting',required=True,type=Path,help='Batting outputs directory')
    parser.add_argument('--bowling',type=Path,help='Verified bowler_model_data_v5.json')
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'private/dataset.json')
    args=parser.parse_args()
    dataset=build(args.batting,args.bowling)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(dataset,allow_nan=False,indent=2)+'\n')
    print(f'Imported {len(dataset["disciplines"]["batting"]["players"])} batters; bowling included: {bool(args.bowling)}. Wrote {args.output}')
