"""Inspect Cricsheet JSON ZIP/directory or explicitly mapped delivery CSV."""
import json, zipfile, pathlib, hashlib
import pandas as pd
CREDIT = {'bowled','caught','caught and bowled','lbw','stumped','hit wicket'}
ALIASES = {'match_id':['match_id','id'], 'date':['date','start_date'], 'season':['season','year'], 'innings':['innings','inning'], 'over':['over','overs'], 'batter':['batter','striker'], 'bowler':['bowler'], 'bat_runs':['bat_runs','runs_off_bat','batsman_runs'], 'total':['total','total_runs'], 'wides':['wides','wide_runs'], 'noballs':['noballs','noball_runs'], 'byes':['byes','bye_runs'], 'legbyes':['legbyes','legbye_runs'], 'wicket':['wicket','bowler_wicket'], 'dismissals':['dismissals','wickets_lost'], 'venue':['venue'], 'team':['team','bowling_team'], 'batting_team':['batting_team'], 'target':['target'], 'sequence':['sequence','delivery_sequence']}
def load(path, cfg):
    p=pathlib.Path(path); excluded=[]; rows=[]; coverage=[]
    if p.suffix.lower()=='.csv':
        df=pd.read_csv(p); mapping={k:next((a for a in v if a in df),None) for k,v in ALIASES.items()};print('CSV schema:',mapping,flush=True)
        need=[k for k in ALIASES if mapping[k] is None]
        if need: raise ValueError('Critical canonical CSV columns missing: '+', '.join(need)+'. Use Cricsheet JSON or map these columns; do not guess extras/wickets/sequence.')
        df=df.rename(columns={v:k for k,v in mapping.items()})
        if not pd.to_numeric(df.over,errors='coerce').dropna().astype(float).map(float.is_integer).all():raise ValueError('CSV over must be zero-based integer, not cricket decimal notation.')
        if df.over.min()<0 or df.over.max()>19:raise ValueError('CSV over must be zero-based 0..19.')
        if df.duplicated(['match_id','innings','sequence']).any():raise ValueError('Duplicate CSV delivery keys.')
        if df[list(ALIASES)].isna().any().any():raise ValueError('Missing values in critical canonical CSV fields.')
        df['date']=pd.to_datetime(df.date).dt.strftime('%Y-%m-%d');df['season']=df.season.astype(str).str[:4].astype(int)
        df=df[(df.season>=cfg['warmup_year'])&(df.season<=max(cfg['years']))].sort_values(['date','match_id','innings','sequence'])
        df['legal']=(df.wides.eq(0)&df.noballs.eq(0)).astype(int);df['boundary']=df.bat_runs.isin([4,6]).astype(int);df['importance']=.5
        df['charged']=df.bat_runs+df.wides+df.noballs
        return df,{'format':'CSV','mapping':mapping,'warnings':['CSV must represent prevalidated standard 20-over innings; use JSON for automatic match-condition checks.']}
    if p.is_dir(): files=[(str(f),f.read_bytes()) for f in p.glob('*.json')]
    else:
        z=zipfile.ZipFile(p);files=[(n,z.read(n)) for n in z.namelist() if n.endswith('.json')]
    for name,raw in files:
        x=json.loads(raw);i=x['info']; year=int(str(i['season'])[:4]);date=str(i['dates'][0]);mid=pathlib.Path(name).stem
        if not cfg['warmup_year']<=year<=max(cfg['years']):continue
        coverage.append({'match_id':mid,'season':year,'date':date,'venue':i['venue']})
        reason=None
        if i.get('gender')!='male' or i.get('match_type')!='T20':reason='not male T20'
        elif i.get('overs',20)!=20 or i.get('balls_per_over',6)!=6:reason='reduced/nonstandard innings'
        elif i.get('outcome',{}).get('method'):reason='revised target/method'
        elif len(x['innings'])<2:reason='missing innings'
        elif i.get('outcome',{}).get('result') in ['no result','abandoned']:reason='no result'
        elif any(a.get('target',{}).get('overs',20)!=20 for a in x['innings'][:2]):reason='reduced target overs'
        if reason:excluded.append({'match_id':mid,'season':year,'reason':reason});continue
        first_total=sum(d['runs']['total'] for o in x['innings'][0]['overs'] for d in o['deliveries'])
        for ino,a in enumerate(x['innings'][:2],1):
            if a.get('super_over'):continue
            batting=a['team']; bowling=next(t for t in i['teams'] if t!=batting);seq=0
            for o in a['overs']:
                for d in o['deliveries']:
                    e=d.get('extras',{});wk=d.get('wickets',[]);seq+=1
                    rows.append(dict(match_id=mid,date=date,season=year,innings=ino,sequence=seq,over=o['over'],batter=d['batter'],bowler=d['bowler'],bat_runs=d['runs']['batter'],total=d['runs']['total'],wides=e.get('wides',0),noballs=e.get('noballs',0),byes=e.get('byes',0),legbyes=e.get('legbyes',0),charged=d['runs']['batter']+e.get('wides',0)+e.get('noballs',0),legal=int(not(e.get('wides') or e.get('noballs'))),boundary=int(d['runs']['batter'] in [4,6] and not d['runs'].get('non_boundary',False)),wicket=sum(w['kind'] in CREDIT for w in wk),dismissals=sum(w['kind'] not in ['retired hurt','retired not out'] for w in wk),venue=i['venue'],team=bowling,batting_team=batting,target=a.get('target',{}).get('runs',first_total+1) if ino==2 else 0,importance=1. if i.get('event',{}).get('stage') else .5))
    df=pd.DataFrame(rows).sort_values(['date','match_id','innings','sequence']).reset_index(drop=True)
    audit={'format':'Cricsheet JSON','input_files':len(files),'source_seasons':pd.DataFrame(coverage).groupby('season').size().to_dict(),'included_seasons':df.groupby('season').match_id.nunique().to_dict(),'exclusions':excluded,'deliveries':len(df),'columns':df.columns.tolist(),'date_range':[df.date.min(),df.date.max()],'source_manifest':coverage,'sha256':hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None}
    print('SCHEMA',json.dumps({k:v for k,v in audit.items() if k not in ['source_manifest','exclusions']},default=str),flush=True)
    return df,audit
