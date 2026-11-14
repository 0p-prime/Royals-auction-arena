#!/usr/bin/env python3
"""Check imported metrics and membership against original aggregate exports."""
import argparse,csv,json,math
from pathlib import Path

def csv_rows(path):
    with Path(path).open(newline='') as file:return list(csv.DictReader(file))
def same(a,b):
    if b in ('',None):return a is None
    try:return math.isclose(a,float(b),rel_tol=1e-12,abs_tol=1e-12)
    except (TypeError,ValueError):return False

def check(dataset,batting,bowling):
    data=json.loads(Path(dataset).read_text());players={p['id']:p for p in data['disciplines']['batting']['players']}
    raw=csv_rows(Path(batting)/'batsman_ppf.csv');assert len(players)==len(raw)
    checked=0
    mapping={'pressure':'RAE100_p','normal':'RAE100_n','overall':'RAE100_all','uplift':'PPF_adj','ciLow':'ci_low_adj','ciHigh':'ci_high_adj','pressureBalls':'balls_p','normalBalls':'balls_n'}
    for r in raw:
        p=players[r['batter']]
        for field,column in mapping.items():assert same(p[field],r[column]),(p['id'],field);checked+=1
        assert p['eligible']==(r['eligible']=='True')
        assert p['sampleQualified']==(int(r['balls_p'])>=60 and int(r['balls_n'])>=200)
    for field,file in [('top10','top10_batsmen.csv'),('quota','top10_role_quota.csv'),('shortlisted','shortlist_35.csv')]:
        assert {p['id'] for p in players.values() if p[field]}=={r['batter'] for r in csv_rows(Path(batting)/file)}
    bowling=Path(bowling)
    meta={r['Bowler']:r for r in csv_rows(bowling/'all_bowlers.csv')}
    top10=[r['Bowler'] for r in csv_rows(bowling/'top10.csv')]
    lists=data['disciplines']['bowling']['lists']
    pooled=lists['pooledUplift']
    assert [p['name'] for p in pooled[:10]]==top10,'pooled funnel order must match the official top 10'
    for p in pooled:
        r=meta[p['name']]
        for field,column in [('uplift','BPF_adj'),('ciLow','CI_low'),('ciHigh','CI_high'),('pressure','rae100_pressure'),('normal','rae100_normal'),('overall','rae100_overall'),('pressureBalls','pressure_balls'),('normalBalls','normal_balls')]:
            assert same(p[field],r[column]),('pooledUplift',p['id'],field);checked+=1
        assert p['eligible']==(r['eligible']=='True')
        assert p['top10']==(r['selected']=='True')
    for p in lists['overall']:
        r=meta[p['name']]
        for field,column in [('overall','rae100_overall'),('pressure','rae100_pressure'),('normal','rae100_normal')]:
            assert same(p[field],r[column]),('overall',p['id'],field);checked+=1
    for key in ['chasePressureLevel','firstInningsPressureLevel','chasePressureUplift','firstInningsPressureUplift']:
        for p in lists[key]:
            assert p['name'] in meta,(key,p['name']);checked+=1
    print(f'Integrity passed: {len(players)} batters, six bowling views, {checked} numeric comparisons plus membership/order checks.')
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dataset',required=True);p.add_argument('--batting',required=True);p.add_argument('--bowling',required=True);a=p.parse_args();check(a.dataset,a.batting,a.bowling)
