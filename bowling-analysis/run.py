"""Reproduce audit, temporal predictions, diagnostics, selection and plots."""
import os
os.environ.setdefault('OMP_NUM_THREADS','2');os.environ.setdefault('OPENBLAS_NUM_THREADS','2')
import argparse,json,logging,joblib
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.calibration import calibration_curve
from sklearn.metrics import mean_absolute_error,mean_squared_error
from core.data_loader import load
from core.features import build,NUMERIC,CATEGORICAL
from core.bopi_model import model,target,metrics
from core.expected_runs import fit as fit_expected
from core.bpf import add_scores,aggregate,bootstrap
from core.selector import select
from core.validate import stability
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
def savejson(p,obj):p.write_text(json.dumps(obj,indent=2,default=str,allow_nan=False))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data',default='data/ipl_json.zip');ap.add_argument('--config',default='config.json');ap.add_argument('--metadata');ap.add_argument('--out',default='outputs');args=ap.parse_args();cfg=json.loads(Path(args.config).read_text());out=Path(args.out);out.mkdir(exist_ok=True,parents=True)
    
    if cfg.get('exclude_near_decided'):raise ValueError('No qualified near-decided exclusion model supplied. Leave exclude_near_decided=false.')
    raw,audit=load(args.data,cfg);savejson(out/'schema_audit.json',audit)
    if 'source_manifest' in audit:pd.DataFrame(audit['source_manifest']).to_csv(out/'source_match_manifest.csv',index=False)
    pd.DataFrame(audit.get('exclusions',[])).to_csv(out/'excluded_matches.csv',index=False)
    meta=pd.read_csv(args.metadata) if args.metadata else None
    logging.info('Building pre-ball features and prior-date profiles');d=build(raw,cfg,meta)
    players=sorted(set(raw.bowler)|set(raw.batter));pd.DataFrame({'player':players,'type':'Unknown','hand':'Unknown'}).to_csv(out/'metadata_template.csv',index=False)
    missing={'type_unknown_deliveries':int(d.type.eq('Unknown').sum()),'hand_unknown_deliveries':int(d.hand.eq('Unknown').sum()),'dew':'omitted, no sourced data','ground_size':'omitted, no sourced data','type_specific_sr':'fallback to prior-match overall batter SR when type unavailable','2026_present':bool((d.season==2026).any())};savejson(out/'missingness.json',missing)
    # 2024 is development. Select boundary estimator here, before opening 2025-26 metrics.
    devtrain=d[(d.season>=min(cfg['years']))&(d.season<=2023)];dev=d[d.season==2024];devmetrics={};models={}
    for k in ['logistic','xgboost']:
        logging.info('Development model %s',k);m=model(cfg,k);m.fit(devtrain,target(devtrain));devmetrics[k]=metrics(target(dev),m.predict_proba(dev)[:,1])
    chosen=min(devmetrics,key=lambda k:devmetrics[k]['brier']);logging.info('Frozen choice from 2024 Brier: %s',chosen)
    # Direction comparison is developmental only. Intent remains semantic default.
    literal=d.copy();literal['chase_gap']=np.where(literal.innings==2,np.clip((literal.rrr-literal.crr)/cfg['rate_scale'],0,1),0.)
    lm=model(cfg,chosen);literal_train=literal[(literal.season>=min(cfg['years']))&(literal.season<=2023)];lm.fit(literal_train,target(literal_train));direction={'configured_mode':cfg['chase_mode'],'literal_2024':metrics(target(dev),lm.predict_proba(literal[literal.season==2024])[:,1]),'configured_2024':devmetrics[chosen],'interpretation':'Direction diagnostic, not pressure-validity proof. Intent chosen from stated meaning, not test winner.'}
    # Expanding-year out-of-sample scores for 2022-24. Frozen 2022-24 model for 2025-26.
    scored=[];held={};preds={};fold_audit=[]
    for yr in cfg['years']:
        tr=d[d.season<yr] if yr==min(cfg['years']) else d[(d.season>=min(cfg['years']))&(d.season<yr)&(d.season<=cfg['train_end'])];te=d[d.season==yr]
        if te.empty:continue
        fold_audit.append({'predicted_season':yr,'training_seasons':sorted(tr.season.unique().tolist()),'training_match_ids':sorted(tr.match_id.unique().tolist()),'prediction_match_ids':sorted(te.match_id.unique().tolist())})
        logging.info('Predict season %s, train matches %s, rows %s',yr,tr.match_id.nunique(),len(tr))
        bm=model(cfg,chosen);bm.fit(tr,target(tr));er,ew=fit_expected(tr,cfg);a=te.copy();a['bopi']=100*bm.predict_proba(a)[:,1];a['er']=er.predict(a);a['ew']=ew.predict_proba(a)[:,1];scored.append(a)
        if yr==cfg['test_start']:joblib.dump({'bopi':bm,'expected_runs':er,'expected_wickets':ew,'config':cfg},out/'frozen_models.joblib')
    savejson(out/'model_training_registry.json',fold_audit)
    s=pd.concat(scored,ignore_index=True);train=d[(d.season>=min(cfg['years']))&(d.season<=cfg['train_end'])];test=d[d.season>=cfg['test_start']]
    for targetname in ['boundary','two_or_extra']:
        for k in ['logistic','xgboost']:
            logging.info('Held-out comparison %s %s',targetname,k);m=model(cfg,k);m.fit(train,target(train,targetname));p=m.predict_proba(test)[:,1];held[targetname+'_'+k]=metrics(target(test,targetname),p);preds[targetname+'_'+k]=p
    cutoffs=list(np.quantile(s.loc[s.season<=cfg['train_end'],'bopi'],[cfg['normal_quantile'],cfg['pressure_quantile']]))
    s=add_scores(s,cfg,cutoffs);table=aggregate(s,cfg)
    reporting=Path('data/reporting_metadata.csv')
    if reporting.exists():
        tags=pd.read_csv(reporting).set_index('player')['type'];table['Type']=table.Bowler.map(tags).fillna(table.Type)
    ci=bootstrap(s,cfg);table=table.merge(ci,on='Bowler')
    table['Confidence']='Low'
    table.loc[(table.matches>=cfg['confidence_med_matches'])&(table.pressure_balls>=cfg['confidence_med_pressure_balls'])&(table.CI_low>0),'Confidence']='Med'
    table.loc[(table.matches>=cfg['confidence_high_matches'])&(table.pressure_balls>=cfg['confidence_high_pressure_balls'])&(table.CI_low>0),'Confidence']='High'
    table['CI']=table.apply(lambda r:f"[{r.CI_low:.1f}, {r.CI_high:.1f}]" if pd.notna(r.CI_low) else 'not estimable',axis=1)
    val=stability(s,cfg);rho=val['alternate_match_bpf_rank']['rho'];noisy=rho is None or rho<cfg['stability_warning']
    if noisy:table['Confidence']='Low'
    missing['report_type_unknown_bowlers']=int(table.Type.eq('Unknown').sum());missing['report_type_total_bowlers']=len(table);savejson(out/'missingness.json',missing)
    table,top=select(table,cfg);table.sort_values('BPF_adj',ascending=False).to_csv(out/'all_bowlers.csv',index=False);top.to_csv(out/'top10.csv',index=False)
    for typ in ['Pace','Spin']:
        view=table[table.Type.str.lower().eq(typ.lower())];_,v=select(view,cfg);v.to_csv(out/f'top10_{typ.lower()}.csv',index=False)
    early=aggregate(s[s.season<=cfg['train_end']],cfg);late=aggregate(s[s.season>=cfg['test_start']],cfg);early.to_csv(out/'early_bpf.csv',index=False);late.to_csv(out/'late_bpf.csv',index=False)
    # Match-level contributions are sufficient to independently reproduce rates and bootstrap.
    s.to_csv(out/'delivery_scores.csv.gz',index=False,compression='gzip')
    sensitivities=[]
    for w in cfg['wicket_value_sensitivity']:
        cc=dict(cfg,wicket_value=w);ss=add_scores(s,cc,cutoffs);tt=aggregate(ss,cc);_,tp=select(tt,cc);sensitivities.append({'wicket_value':w,'top_names':tp.Bowler.tolist()});tp.to_csv(out/f'sensitivity_wicket_{int(w)}.csv',index=False)
    val.update({'chosen_model':chosen,'selection_rule':'2024 lowest Brier, both fit on seasons <=2023','development':devmetrics,'heldout_2025_2026':held,'chase_direction':direction,'cutoffs':{'normal_max':cutoffs[0],'pressure_min':cutoffs[1]},'expected_runs_holdout_mae':float(mean_absolute_error(s.loc[s.season>=cfg['test_start'],'charged'],s.loc[s.season>=cfg['test_start'],'er'])),'expected_wicket_holdout_brier':float(np.mean((s.loc[s.season>=cfg['test_start'],'ew']-s.loc[s.season>=cfg['test_start'],'wicket'])**2)),'stability_warning':noisy,'selected':len(top),'eligible':int(table.eligible.sum()),'wicket_value_sensitivity':sensitivities,'bootstrap':str(cfg['bootstrap'])+' match-cluster resamples per bowler; conditional on fixed fitted models and cutoffs, not full model uncertainty'})
    val['baseline_boundary_holdout']=metrics(target(test),np.full(len(test),target(train).mean()))
    val['baseline_alternative_holdout']=metrics(target(test,'two_or_extra'),np.full(len(test),target(train,'two_or_extra').mean()))
    # Requested RAE adds raw wickets. This centered diagnostic uses the otherwise unused E[W].
    centered=s.copy();centered['rae']=centered.rae-cfg['wicket_value']*centered.ew
    ct=aggregate(centered,cfg);ct.to_csv(out/'diagnostic_centered_wickets.csv',index=False);val['centered_wickets_stability']=stability(centered,cfg)
    # Bounded continuous revision (approved 2026-11-11): all-ball per-bowler
    # RAE-on-BoPI slopes with centered wickets and shrinkage. Reuses 2025-26 as
    # development evidence, not fresh validation. Original bucket BPF untouched.
    from bpf_continuous import run_continuous
    logging.info('Continuous pressure-response stage');cfull,cval=run_continuous(s,cfg)
    cfull.to_csv(out/'continuous_slopes.csv',index=False)
    (out/'validation_continuous.json').write_text(json.dumps(cval,indent=2,default=str))
    # Support sensitivity is diagnostic only, never used to suppress the mandatory warning.
    aa=aggregate(s[s.season<=cfg['train_end']],cfg);bb=aggregate(s[s.season>=cfg['test_start']],cfg)
    from validate import correlate
    aa=aa[(aa.pressure_balls>=cfg['sensitivity_min_cohort_balls'])&(aa.normal_balls>=cfg['sensitivity_min_cohort_balls'])];bb=bb[(bb.pressure_balls>=cfg['sensitivity_min_cohort_balls'])&(bb.normal_balls>=cfg['sensitivity_min_cohort_balls'])]
    val['time_bpf_support_sensitivity']=correlate(aa,bb)
    savejson(out/'validation.json',val)
    plt.rcParams.update({'figure.dpi':140,'axes.spines.top':False,'axes.spines.right':False,'font.size':10})
    fig,ax=plt.subplots(figsize=(8,4));ax.hist(s.bopi,bins=35,color='#236b8e');ax.axvline(cutoffs[0],color='#cf8134',label='Normal cutoff');ax.axvline(cutoffs[1],color='#b73244',label='Pressure cutoff');ax.set(xlabel='BoPI: predicted boundary risk (%)',ylabel='Delivery attempts',title='Boundary risk, not proven psychological pressure');ax.legend();fig.tight_layout();fig.savefig(out/'bopi_distribution.png');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for ax,tname in zip(axes,['boundary','two_or_extra']):
        for k in ['logistic','xgboost']:
            actual,pred=calibration_curve(target(test,tname),preds[tname+'_'+k],n_bins=cfg['calibration_bins'],strategy='quantile');ax.plot(pred,actual,'o-',label=k)
        ax.plot([0,1],[0,1],':',color='gray');ax.set(xlabel='Predicted event probability',ylabel='Observed frequency',title=tname+' | 2025-26');ax.legend()
    fig.tight_layout();fig.savefig(out/'calibration.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,5));t=top.sort_values('BPF_adj');ax.barh(t.Bowler,t.BPF_adj,color='#236b8e');ax.errorbar(t.BPF_adj,np.arange(len(t)),xerr=[np.maximum(t.BPF_adj-t.CI_low,0),np.maximum(t.CI_high-t.BPF_adj,0)],fmt='none',color='#b73244',capsize=3);ax.axvline(0,color='gray');ax.set(xlabel='BPF adjusted (runs-equivalent / 100 legal balls)',title='Conditional ranking | match-bootstrap 95% intervals');fig.tight_layout();fig.savefig(out/'top10.png');plt.close(fig)
    lines=[f"1. Audited {s.match_id.nunique()} usable IPL matches in 2022-26 ({len(s):,} delivery attempts); exclusions are logged.",f"2. {chosen} selected on 2024 development Brier; held-out boundary AUC {held['boundary_'+chosen]['auc']:.3f}, Brier {held['boundary_'+chosen]['brier']:.3f}.",f"3. {len(top)} bowlers selected from {int(table.eligible.sum())} eligible; final order uses BPF_adj, not overall skill.",f"4. Alternate-match BPF rank correlation {str(round(rho,3)) if rho is not None else 'undefined'}; time BPF rank correlation {str(round(val['time_bpf_rank']['rho'],3)) if val['time_bpf_rank']['rho'] is not None else 'undefined'}. "+('WARNING: BPF is noisy and indicative.' if noisy else 'Stability is descriptive, not future-performance proof.'),"5. Boundary risk is a proxy; wicket value=20 is assumed; missing historical type/hand/dew metadata and conditional bootstrap limit interpretation; team means latest observed IPL team, not current auction availability.",f"6. Continuous revision (all-ball slope, centered wickets, shrunk): alternate-match rho {cval['alternate_match_slope_rank']['rho']} (matched bucket baseline {cval['matched_cohort_bucket_bpf_baseline']['alternate_match']['rho']}), time rho {cval['time_slope_rank']['rho']} (baseline {cval['matched_cohort_bucket_bpf_baseline']['time']['rho']}). Exploratory interval labels in continuous_slopes.csv; see validation_continuous.json caveats."]
    (out/'SUMMARY.md').write_text('\n\n'.join(lines)+'\n');print('\n'.join(lines),flush=True)
if __name__=='__main__':main()
