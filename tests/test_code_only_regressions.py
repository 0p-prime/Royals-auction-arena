"""Synthetic-only regression checks. No private data or generated outputs read."""
import importlib.util,json,sys,tempfile
from pathlib import Path
import pandas as pd
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'batting-analysis'))
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,ROOT/path); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
bat=module('bat_loader','batting-analysis/data_loader.py')
bf=module('bat_features','batting-analysis/features.py')
bowl=module('bowl_loader','bowling-analysis/core/data_loader.py')
bowf=module('bowl_features','bowling-analysis/core/features.py')
def match(revised=False,context=True):
 def ball(r=0):return dict(batter='A',non_striker='B',bowler='C',runs=dict(batter=r,extras=0,total=r))
 chase=[ball(),ball(1)]
 if context:
  for d,t,b in zip(chase,[61,49],[60,48]):d.update(target_in_force=t,innings_balls=b)
 return dict(info=dict(season=2023,dates=['2023-01-01'],teams=['X','Y'],venue='Synthetic',gender='male',match_type='T20',overs=20,outcome={'method':'D/L'} if revised else {}),innings=[dict(team='X',overs=[dict(over=0,deliveries=[ball(4),ball()])]),dict(team='Y',target=dict(runs=99,overs=10),overs=[dict(over=0,deliveries=chase)])])
def test_batting_context_and_preball(tmp_path):
 (tmp_path/'fake.json').write_text(json.dumps(match(True)))
 d=bat.build_deliveries(tmp_path,[2023]);f=bf.build_features(d,{})
 c=f[f.innings.eq(2)].reset_index(drop=True)
 assert c.target_score.tolist()==[61,49]
 assert c.balls_left.tolist()==[60,47]
 assert c.runs_before.tolist()==[0,0]
 assert c.rrr.iloc[0]==pytest.approx(6.1)
 assert c.rrr.iloc[1]==pytest.approx(49*6/47)
 assert c.dls_chase.all()
def test_batting_revised_without_context_fails(tmp_path):
 (tmp_path/'fake.json').write_text(json.dumps(match(True,False)))
 with pytest.raises(ValueError,match='per-delivery'):bat.build_deliveries(tmp_path,[2023])
def test_bowling_csv_alias_allotment_and_year_floor(tmp_path):
 rows=[]
 for year in [2019,2022,2023]:
  rows.append(dict(match_id=str(year),date=f'{year}-01-01',season=year,innings=2,over=0,batter='A',bowler='C',bat_runs=0,total=0,wides=0,noballs=0,byes=0,legbyes=0,wicket=0,dismissals=0,venue='Synthetic',team='X',batting_team='Y',target_in_force=61,innings_balls=60,sequence=1))
 p=tmp_path/'fake.csv';pd.DataFrame(rows).to_csv(p,index=False)
 cfg=json.loads((ROOT/'bowling-analysis/config.json').read_text());d,a=bowl.load(p,cfg);f=bowf.build(d,cfg)
 assert d.season.tolist()==[2022,2023]
 assert d.target.tolist()==[61,61]
 assert f.rrr.tolist()==pytest.approx([6.1,6.1])
def test_bowling_revised_json_fails_explicitly(tmp_path):
 (tmp_path/'fake.json').write_text(json.dumps(match(True)))
 with pytest.raises(ValueError,match='per-delivery'):bowl.load(tmp_path,dict(years=[2022,2023]))
def test_builder_overall_uses_all_legal_balls(tmp_path,monkeypatch):
 monkeypatch.setattr(sys,'argv',['build_dataset.py','--batting-dir',str(tmp_path),'--bowling-dir',str(tmp_path)])
 builder=module('synthetic_builder','dashboard/scripts/build_dataset.py')
 pd.DataFrame([dict(Bowler='Synthetic bowler',pressure_balls=60,normal_balls=100,rae100_pressure=3,rae100_normal=1,rae100_overall=2,BPF_adj=1,CI_low=0,CI_high=2,eligible=True,shortlist_rank=1,Team='X',Type='pace')]).to_csv(tmp_path/'all_bowlers.csv',index=False)
 pd.DataFrame({'Bowler':['Synthetic bowler']}).to_csv(tmp_path/'top10.csv',index=False)
 pd.DataFrame([dict(match_id='fake',innings=2,bowler='Synthetic bowler',legal=1,weight=1,rae=1,bucket=b) for b in ['pressure']*60+['normal']*100+['middle']*60]).to_csv(tmp_path/'delivery_scores.csv.gz',index=False)
 result=builder.bowling()['lists']['overall']
 assert len(result)==1
 assert result[0]['deliveries']==220
