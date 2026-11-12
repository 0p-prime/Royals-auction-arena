"""Strict pre-delivery state; prior-date player/venue profiles, never same-day outcomes."""
from collections import defaultdict,deque
import pandas as pd
import numpy as np
NUMERIC=['innings','over','wickets_in_hand','crr','rrr','chase_gap','first_projection_gap','phase_weight','recent_boundaries','set_batter','batter_sr','spell_runs','importance']
CATEGORICAL=['venue']
def build(df,cfg,metadata=None):
    if metadata is not None and 'valid_from' not in metadata:
        raise ValueError('Historical feature metadata needs valid_from (YYYY-MM-DD). Undated metadata is reporting-only.')
    meta={} if metadata is None else metadata.fillna('Unknown').set_index('player').to_dict('index')
    profiles=defaultdict(lambda:[0,0]);typeprofiles=defaultdict(lambda:[0,0]);pars=defaultdict(list);globalpar=[];out=[]
    for date,day in df.groupby('date',sort=True):
        updates=[];parupdates=[]
        for (mid,ino),g in day.groupby(['match_id','innings'],sort=False):
            runs=balls=lost=0;batterballs=defaultdict(int);recent=deque(maxlen=cfg['recent_window']);spells=defaultdict(lambda:deque(maxlen=cfg['recent_window']));last_over={}
            venue=g.iloc[0].venue
            hist=pars[venue] if len(pars[venue])>=cfg['min_par_matches'] else globalpar
            par=float(np.mean(hist)) if hist else cfg['fallback_par']
            for r in g.to_dict('records'):
                bm=meta.get(r['bowler'],{});am=meta.get(r['batter'],{})
                typ=bm.get('type','Unknown') if bm.get('valid_from','9999')<=date else 'Unknown'
                hand=am.get('hand','Unknown') if am.get('valid_from','9999')<=date else 'Unknown'
                pr=typeprofiles[(r['batter'],typ)] if typ!='Unknown' else profiles[r['batter']]
                if pr[1]<cfg['min_profile_balls']:pr=profiles[r['batter']]
                sr=100*pr[0]/pr[1] if pr[1]>=cfg['min_profile_balls'] else cfg['fallback_batter_sr']
                crr=6*runs/balls if balls else 0.;remaining=max(cfg['innings_balls']-balls,1);rrr=6*max(r['target']-runs,0)/remaining if ino==2 else 0.
                gap=(crr-rrr) if cfg['chase_mode']=='intent' else (rrr-crr)
                phase='powerplay' if r['over']<cfg['powerplay_end'] else ('death' if r['over']>=cfg['death_start']-1 else 'middle')
                # A new spell starts after this bowler misses their next alternating over.
                if r['bowler'] in last_over and r['over']-last_over[r['bowler']]>cfg['spell_max_over_gap']:spells[r['bowler']].clear()
                last_over[r['bowler']]=r['over']
                out.append(dict(r, wickets_in_hand=max(10-lost,0),crr=crr,rrr=rrr,chase_gap=float(np.clip(gap/cfg['rate_scale'],0,1)) if ino==2 else 0.,first_projection_gap=crr*(cfg['innings_balls']/6)-par if ino==1 else 0.,phase_weight=cfg['phase_weight'] if phase!='middle' else 1.,recent_boundaries=sum(recent)/cfg['recent_window'],set_batter=int(batterballs[r['batter']]>cfg['set_batter_balls']),batter_sr=sr,spell_runs=sum(spells[r['bowler']]),phase=phase,type=typ,hand=hand,pre_runs=runs,pre_balls=balls,par=par))
                runs+=r['total'];balls+=r['legal'];lost+=r['dismissals'];recent.append(r['boundary']);spells[r['bowler']].append(r['charged']);batterballs[r['batter']]+=int(not r['wides']);updates.append((r['batter'],typ,r['bat_runs'],int(not r['wides'])))
            if ino==1 and (balls>=cfg['innings_balls'] or lost>=10):parupdates.append((venue,runs))
        for batter,typ,r,b in updates:profiles[batter][0]+=r;profiles[batter][1]+=b;typeprofiles[(batter,typ)][0]+=r;typeprofiles[(batter,typ)][1]+=b
        for v,p in parupdates:pars[v].append(p);globalpar.append(p)
    return pd.DataFrame(out)
