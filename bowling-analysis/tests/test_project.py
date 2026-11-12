import copy,json
from pathlib import Path
import numpy as np
import pandas as pd
from features import build
from bpf import aggregate,add_scores,bootstrap
from selector import select
from data_loader import load,CREDIT
CFG=json.loads((Path(__file__).resolve().parents[1]/'config.json').read_text())
def rows():
    base=dict(match_id='a',date='2022-01-01',season=2022,innings=2,over=0,batter='A',bowler='B',bat_runs=0,total=0,wides=0,noballs=0,byes=0,legbyes=0,charged=0,legal=1,boundary=0,wicket=0,dismissals=0,venue='V',team='BT',batting_team='AT',target=121,importance=.5,type='Unknown',phase='powerplay')
    return pd.DataFrame([dict(base,sequence=i+1) for i in range(5)])
def test_preball_clock_and_extras():
    d=rows();d.loc[0,['wides','total','charged','legal']]=[1,1,1,0];d.loc[1,['noballs','total','charged','legal']]=[1,1,1,0];f=build(d,CFG)
    assert f.pre_balls.tolist()==[0,0,0,1,2]
    assert f.pre_runs.tolist()==[0,1,2,2,2]
    assert f.rrr.iloc[0]==6.05
    assert f.spell_runs.tolist()==[0,1,2,2,2]
def test_own_and_future_outcomes_cannot_change_earlier_features():
    d=rows();a=build(d,CFG);d.loc[3,['bat_runs','total','charged','boundary','wicket','dismissals']]=[6,6,6,1,1,1];b=build(d,CFG)
    cols=['crr','rrr','chase_gap','batter_sr','spell_runs','recent_boundaries','wickets_in_hand','set_batter','par','pre_runs','pre_balls']
    pd.testing.assert_frame_equal(a.loc[:3,cols],b.loc[:3,cols]);assert b.wickets_in_hand.iloc[4]==9

def test_same_date_profile_is_frozen():
    d=rows();other=d.copy();other['match_id']='b';other['bat_runs']=6;other['charged']=6;other['total']=6
    c=dict(CFG,min_profile_balls=1);a=build(pd.concat([d,other]),c);assert a.batter_sr.nunique()==1

def test_later_match_profile_uses_prior_match_only():
    d=rows();d['bat_runs']=1;d['charged']=1;d['total']=1
    other=d.copy();other['match_id']='b';other['date']='2022-01-02';c=dict(CFG,min_profile_balls=1)
    a=build(pd.concat([d,other]),c);assert a.batter_sr.iloc[0]==130.;assert a.batter_sr.iloc[-1]==100.

def test_legal_byeball_changes_score_not_charge():
    d=rows();d.loc[0,['byes','total']]=[4,4];a=build(d,CFG);assert a.pre_runs.iloc[1]==4;assert a.spell_runs.iloc[1]==0

def test_wicket_credit():
    assert 'run out' not in CREDIT;assert 'retired hurt' not in CREDIT;assert 'obstructing the field' not in CREDIT;assert 'hit the ball twice' not in CREDIT;assert 'bowled' in CREDIT

def test_spell_resets_after_break():
    d=rows();d['charged']=2;d.loc[2:,'over']=5;a=build(d,CFG);assert a.spell_runs.iloc[2]==0;assert a.spell_runs.iloc[3]==2

def test_boundaries_prior_only():
    d=rows();d.loc[0,'boundary']=1;a=build(d,CFG);assert a.recent_boundaries.iloc[0]==0;assert a.recent_boundaries.iloc[1]==1/12

def test_thresholds_inclusive_and_middle_dropped_only_for_comparison():
    d=rows();d['bopi']=[10,20,30,15,25];d['er']=1;d['ew']=.1;s=add_scores(d,CFG,[15,25]);assert s.bucket.tolist()==['normal','middle','pressure','normal','pressure'];t=aggregate(s,CFG);assert t.normal_balls.iloc[0]==2;assert t.pressure_balls.iloc[0]==2

def test_shrinkage_recency_and_rates():
    d=rows();d['bucket']=['pressure','normal','normal','middle','middle'];d['weight']=.6;d['rae']=2.;t=aggregate(d,CFG);assert np.isclose(t.rae100_pressure.iloc[0],200);assert t.BPF_adj.iloc[0]==0

def test_bootstrap_clusters_reproducible():
    d=rows();d['bucket']=['pressure','normal','normal','middle','middle'];d['weight']=1.;d['rae']=2.;a=bootstrap(d,dict(CFG,bootstrap=20));b=bootstrap(d,dict(CFG,bootstrap=20));pd.testing.assert_frame_equal(a,b);assert a.CI_low.iloc[0]==0

def test_final_rank_not_overall_skill_and_filters():
    t=pd.DataFrame({'Bowler':['A','B','C'],'pressure_balls':[60,61,59],'normal_balls':[200,200,300],'active':[True]*3,'rae100_normal':[0,1,2],'rae100_overall':[100,0,200],'rae100_pressure':[0,1,2],'BPF_adj':[20,30,100],'role':['death']*3})
    all_,top=select(t,CFG);assert top.Bowler.tolist()==['B','A'];assert top.selected.all();assert not all_.loc[2,'eligible']

def test_optional_quota_no_silent_backfill():
    t=pd.DataFrame({'Bowler':['A','B'],'pressure_balls':[60,61],'normal_balls':[200,200],'active':[True]*2,'rae100_normal':[0,1],'rae100_overall':[100,0],'rae100_pressure':[0,1],'BPF_adj':[20,30],'role':['death']*2})
    _,top=select(t,dict(CFG,use_role_quota=True,roles={'death':1}));assert len(top)==1;assert top.Bowler.iloc[0]=='B'

def test_outputs_are_oos_and_no_fake_confidence():
    out=Path(__file__).resolve().parents[1]/'outputs';d=pd.read_csv(out/'delivery_scores.csv.gz');assert d.pre_balls.between(0,119).all();assert d.wickets_in_hand.between(1,10).all();assert d.bopi.between(0,100).all()
    t=pd.read_csv(out/'top10.csv');assert len(t)<=10;assert (t.pressure_balls>=60).all();assert(t.normal_balls>=200).all();assert (t.rae100_pressure>=0).all();assert (t.Confidence=='Low').all();assert t.selected.all()
    v=json.loads((out/'validation.json').read_text());assert v['alternate_match_bpf_rank']['rho']<.2;assert v['chosen_model']=='logistic'

def test_csv_critical_columns_fail_loudly(tmp_path):
    p=tmp_path/'x.csv';pd.DataFrame({'bowler':['B'],'batsman_runs':[4]}).to_csv(p,index=False)
    import pytest
    with pytest.raises(ValueError,match='Critical canonical CSV'):load(p,CFG)

def test_undated_metadata_not_used_as_historical_fact():
    import pytest
    with pytest.raises(ValueError,match='valid_from'):build(rows(),CFG,pd.DataFrame({'player':['B'],'type':['Pace']}))

def test_dated_metadata_only_after_date():
    meta=pd.DataFrame({'player':['B','A'],'type':['Pace','Unknown'],'hand':['Unknown','Left'],'valid_from':['2023-01-01','2023-01-01']})
    a=build(rows(),CFG,meta);assert a.type.eq('Unknown').all();assert a.hand.eq('Unknown').all()

def test_training_registry_exact_time_split():
    folds=json.loads((Path(__file__).resolve().parents[1]/'outputs/model_training_registry.json').read_text())
    for f in folds:
        assert max(f['training_seasons'])<f['predicted_season']
        assert not(set(f['training_match_ids'])&set(f['prediction_match_ids']))
        if f['predicted_season']>=2025:assert f['training_seasons']==[2022,2023,2024]

def test_undefined_correlation_is_none_not_zero():
    from validate import correlate
    a=pd.DataFrame({'Bowler':['A','B','C'],'BPF_adj':[1,1,1]});assert correlate(a,a)['rho'] is None
