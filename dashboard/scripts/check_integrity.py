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
    for field,file,column in [('top10','top10_batsmen.csv','Batsman'),('quota','top10_role_quota.csv','Batsman'),('shortlisted','shortlist_35.csv','batter')]:
        assert {p['id'] for p in players.values() if p[field]}=={r[column] for r in csv_rows(Path(batting)/file)}
    source=json.loads(Path(bowling).read_text())
    for key,rows in source['lists'].items():
        target=data['disciplines']['bowling']['lists'][key];assert len(target)==len(rows)
        metric='overall' if key=='overall' else 'uplift' if key.endswith('Uplift') else 'pressure'
        for p,r in zip(target,rows):
            assert p['id']==r['bowler'] and p['order']==r['order']
            for field,column in [(metric,'runsSavedPer100'),('ciLow','runsSavedCiLow'),('ciHigh','runsSavedCiHigh'),('wickets','wicketsAboveExpectedPer100'),('rankBest','rankBest'),('rankWorst','rankWorst'),('deliveries','deliveries')]:
                assert same(p[field],r[column]),(key,p['id'],field);checked+=1
            assert p['ranksByWicketValue']==r['ranksByWicketValue']
    print(f'Integrity passed: {len(players)} batters, five bowling lists, {checked} numeric comparisons plus membership/order checks.')
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dataset',required=True);p.add_argument('--batting',required=True);p.add_argument('--bowling',required=True);a=p.parse_args();check(a.dataset,a.batting,a.bowling)
