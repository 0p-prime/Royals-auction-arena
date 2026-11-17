import {views,filterPlayers,sourcePlayers,sortedPlayers,fmt,signed,validateDataset,bowlingSelection,intervalFor} from './core.js';
const $=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let mdisc='batting',view='rankings',data,discipline='batting',visible=[],current=[],activePage='home';
const metric=()=>$('metric').value;
const isBowling=()=>discipline==='bowling';
const value=p=>p[metric()];
const signClass=v=>v>0?'positive':v<0?'negative':'';
const interval=p=>p.ciLow!==null&&p.ciHigh!==null?`${signed(p.ciLow)} to ${signed(p.ciHigh)}`:'Not available';
const hasInterval=()=>Boolean(intervalFor(discipline,metric(),$('innings').value));
const listKey=()=>metric()==='pressure'?'pooledPressure':metric()==='overall'?'overall':$('innings').value==='pooled'?'pooledUplift':`${$('innings').value==='first'?'firstInnings':'chase'}Pressure${metric()==='uplift'?'Uplift':'Level'}`;
// Light-only presentation. Clear the previous theme preference on upgrade.
document.documentElement.dataset.theme='light';
try{localStorage.removeItem('raa-theme');}catch(err){}
function chartColors(){const s=getComputedStyle(document.documentElement);const g=k=>s.getPropertyValue(k).trim();return{grid:g('--chart-grid'),tick:g('--chart-tick'),zero:g('--chart-zero'),name:g('--chart-name'),interval:g('--chart-interval'),dot:g('--chart-dot'),value:g('--chart-value')};}
function load(dataset){data=validateDataset(dataset);{const b=data.disciplines.batting,w=data.disciplines.bowling;const nb=b?.lists?.pooledPressure?.length||b?.players?.length||0,nw=w&&w.lists?Object.keys(w.lists).length:0;if($('statBatters'))$('statBatters').textContent=nb?nb.toLocaleString('en-IN'):'–';if($('statBowlViews'))$('statBowlViews').textContent=nw||'–';}$('loadError').hidden=true;$('dashboard').hidden=false;reset();route();}
function reset(){
 if(!data.disciplines[discipline])discipline=Object.keys(data.disciplines)[0];
 document.querySelectorAll('[data-discipline]').forEach(b=>{b.disabled=!data.disciplines[b.dataset.discipline];b.classList.toggle('active',b.dataset.discipline===discipline);b.setAttribute('aria-pressed',String(b.dataset.discipline===discipline));});
 $('metric').value='pressure';$('innings').value='pooled';$('sort').value='published';
 $('role').value='all';$('search').value='';$('minBalls').value=0;$('pool').value='top10';
 updateSource();
}
function updateSource(event){
 if(isBowling()){
  const next=bowlingSelection(metric(),$('innings').value,event?.target?.id==='innings'?'innings':'metric');
  $('metric').value=next.metric;$('innings').value=next.innings;
 }
 const d=data.disciplines[discipline];
 $('inningsLabel').hidden=!isBowling()||metric()!=='uplift';$('sortLabel').hidden=!isBowling()||metric()==='pressure';
 $('minBalls').parentElement.firstChild.textContent=isBowling()?(metric()==='overall'?'Min. overall legal balls':'Min. pressure legal balls'):'Min. pressure balls';
 for(const option of $('pool').options){option.hidden=option.disabled=(isBowling()||metric()==='pressure')&&['sample','shortlist','quota'].includes(option.value);if(option.value==='top10')option.textContent='Analysis top 10';if(option.value==='eligible')option.textContent=metric()==='pressure'?'Pressure sample qualified':isBowling()?'Eligible bowlers':'Active + sample-qualified';if(option.value==='all')option.textContent=isBowling()?'All exported bowlers':'All exported players';}
 $('roleLabel').textContent=isBowling()?'Bowling style':'Batting role';
 if((isBowling()||metric()==='pressure')&&['sample','shortlist','quota'].includes($('pool').value))$('pool').value='eligible';
 $('period').textContent=d.seasons+' · '+(isBowling()?'Bowling analysis':'Batting analysis');
 current=sourcePlayers(data,discipline,metric(),$('innings').value);
 const selected=$('role').value;
 $('role').innerHTML='<option value="all">All roles</option>'+[...new Set(current.map(p=>p.role))].sort().map(r=>`<option value="${esc(r)}">${esc(r[0].toUpperCase()+r.slice(1))}</option>`).join('');
 if([...$('role').options].some(o=>o.value===selected))$('role').value=selected;
 const options=current.slice().sort((a,b)=>a.name.localeCompare(b.name)).map(p=>`<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
 const oldA=$('compareA').value,oldB=$('compareB').value;
 $('compareA').innerHTML=options;$('compareB').innerHTML=options;
 const preferred=current.filter(p=>p.top10);
 const ranked=sortedPlayers(preferred.length?preferred:current,metric(),discipline,$('sort').value);
 $('compareA').value=current.some(p=>p.id===oldA)?oldA:ranked[0]?.id||'';
 $('compareB').value=current.some(p=>p.id===oldB)?oldB:ranked[1]?.id||ranked[0]?.id||'';
 $('methodology').innerHTML=d.method.map(([title,text])=>`<details><summary>${esc(title)}</summary><p>${esc(text.replaceAll('per-match BPI','delivery BPI'))}</p></details>`).join('')+`<p class="caption">Source: ${esc(d.source)}</p>`;
 render();
}
function render(){
 const d=data.disciplines[discipline];
 const base=metric()==='overall'&&isBowling()?current.map(p=>({...p,pressureBalls:p.deliveries})):current;
 visible=sortedPlayers(filterPlayers(base,{role:$('role').value,search:$('search').value,pool:$('pool').value,minBalls:$('minBalls').value}),metric(),discipline,$('sort').value);
 const qualified=current.filter(p=>p.sampleQualified).length;
 const ciCount=visible.filter(p=>p.ciLow>0).length;
 const sum=current.reduce((s,p)=>s+(isBowling()&&metric()==='overall'?p.deliveries:p.pressureBalls),0);
 const cards=metric()==='pressure'?[['Eligible players',qualified,'Consistent selection standard'],['Pressure balls',sum.toLocaleString(),'Both innings across the complete cohort'],['Final top 10',current.filter(p=>p.top10).length,'Pressure performance only'],['Calculation','17 Nov 2026','New offline performance run']]:isBowling()?[
  ['Source cohort',current.length,'Qualified bowlers before filters'],[metric()==='overall'?'Sample rule':'Pressure legal balls',metric()==='overall'?d.minimumBalls.overall:sum.toLocaleString(),metric()==='overall'?'Published cohort preserved':'Across the source cohort before filters'],['Filtered players',visible.length,'Current pool, style and sample filters'],['Uplift interval',dInterval()||'Not supplied',hasInterval()?'Match-bootstrap, shrunk uplift':'No interval supplied for this view']
 ]:[['Sample-qualified',qualified,d.sampleFloorsText],['Pressure balls',sum.toLocaleString(),'Across all exported batsmen'],['Analysis top 10',current.filter(p=>p.top10).length,'Funnel + uplift ranking'],['Uplift interval','90%','Match-bootstrap, shrunk estimate']];
 $('stats').innerHTML=cards.map(([a,b,c])=>`<div class="stat"><small>${esc(a)}</small><strong>${esc(b)}</strong><span>${esc(c)}</span></div>`).join('');
 let note=isBowling()?`${views[metric()].label}: runs saved ${metric()==='uplift'?'under pressure minus own normal':'vs model expectation'}, per 100 legal balls. ${$('sort').value==='published'?'Order follows the analysis funnel for this view.':'Custom runs-only ordering.'} ${metric()==='overall'?'Both innings pooled overall.':$('innings').value==='pooled'?'Both innings pooled; the published final-list funnel (eligibility floors, overall-skill shortlist, uplift ranking).':$('innings').value==='first'?'First innings only.':'Chasing innings only.'} Sample rule: ${d.minimumBalls[listKey()]}.`:
 `${views[metric()].label}: ${metric()==='uplift'?'EB-shrunk pressure-minus-normal RAE100 (PPF_adj)':'recency-weighted '+(metric()==='pressure'?'pressure-bucket':'overall')+' runs above expectation per 100 legal balls'}. Higher is better; current filters are applied before ordering.`;
 if(metric()==='pressure')note='Pressure RAE100: recency-weighted runs above expectation per 100 legal pressure balls. Both innings pooled; substantial pressure exposure for consistency in selection; no activity filter, normal floor or old shortlist. New 17 November offline calculation from the saved reconstructed checkpoint. Matches the final report.';
 else note+=' Preserved earlier comparison export; this is not the new final pressure-only run.';
 $('measureNote').textContent=note;
 $('caveat').innerHTML=`<p>${isBowling()?'Scores include runs saved against model expectation and 20 runs per credited wicket. The final pooled order follows shrunk pressure-minus-normal uplift through the selection funnel.':'Uplift compares pressure performance with their own normal level. The displayed 90% interval describes the shrunk uplift estimate.'}</p>`+(!isBowling()&&$('pool').value==='quota'?'<p><strong>Role note:</strong> role-balanced quotas can include batters whose uplift sits below zero when a role needs representation.</p>':'')+(isBowling()?`<p>${hasInterval()?'The 95% match-bootstrap interval describes shrunk pooled uplift, conditional on fitted models and cutoffs.':'No interval is supplied for this bowling view.'}</p>`:'');
 if(metric()==='pressure')$('caveat').innerHTML='<p>The final list ranks pressure performance itself. The first-innings and chase contributions are combined before calculating the rate. Scores are run-equivalent units, not percentages.</p>';
 $('resultCount').textContent=`${visible.length} filtered players · ${hasInterval()?ciCount+' positive runs/uplift intervals':'level intervals not supplied'}`;
 $('chartTitle').textContent=isBowling()&&$('sort').value==='published'?'Leading players':'Leading players';
 drawChart(visible.slice(0,10));table();compare();
}
function drawChart(players){
 const col=chartColors();
 if(!players.length){$('chart').innerHTML='<p class="empty">No players match these filters.</p>';$('chartCaption').textContent='Try another role, sample threshold or player pool.';return;}
 const width=Math.max(270,$('chart').clientWidth),left=width<450?112:150,right=width<450?48:65,height=players.length*36+42;
 let range=[0,...players.flatMap(p=>hasInterval()&&p.ciLow!==null&&p.ciHigh!==null?[value(p),p.ciLow,p.ciHigh]:[value(p)])].filter(Number.isFinite);
 let min=Math.min(...range),max=Math.max(...range);if(max===min){min-=1;max+=1;}
 const pad=(max-min)*.07;min-=pad;max+=pad;
 const x=v=>left+(v-min)/(max-min)*(width-left-right);
 let svg=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="forestTitle forestDesc"><title id="forestTitle">${esc(views[metric()].label)}</title><desc id="forestDesc">${esc(players.map(p=>`${p.name}: ${signed(value(p))}${hasInterval()?', interval '+interval(p):''}`).join('; '))}</desc>`;
 for(let i=0;i<5;i++){const tick=min+(max-min)*i/4;svg+=`<line x1="${x(tick)}" x2="${x(tick)}" y1="6" y2="${height-28}" stroke="${col.grid}"/><text x="${x(tick)}" y="${height-8}" text-anchor="middle" font-size="10" fill="${col.tick}">${Math.round(tick)}</text>`;}
 svg+=`<line x1="${x(0)}" x2="${x(0)}" y1="6" y2="${height-28}" stroke="${col.zero}" stroke-dasharray="3 4"/>`;
 players.forEach((p,i)=>{const y=i*36+22;svg+=`<text x="${left-13}" y="${y+4}" text-anchor="end" font-size="12" fill="${col.name}" font-weight="600">${esc(p.name)}</text>`;
 if(hasInterval()&&p.ciLow!==null&&p.ciHigh!==null)svg+=`<line x1="${x(p.ciLow)}" x2="${x(p.ciHigh)}" y1="${y}" y2="${y}" stroke="${col.interval}" stroke-width="2"/><line x1="${x(p.ciLow)}" x2="${x(p.ciLow)}" y1="${y-4}" y2="${y+4}" stroke="${col.interval}"/><line x1="${x(p.ciHigh)}" x2="${x(p.ciHigh)}" y1="${y-4}" y2="${y+4}" stroke="${col.interval}"/>`;
 svg+=`<circle cx="${x(value(p))}" cy="${y}" r="4" fill="${col.dot}"/><text x="${width-3}" y="${y+4}" text-anchor="end" font-size="12" fill="${col.value}">${signed(value(p))}</text>`;});
 $('chart').innerHTML=svg+'</svg>';
 $('chartCaption').textContent=`${isBowling()?'Runs saved per 100 legal balls':'Runs above expectation per 100 legal balls'}. ${hasInterval()?`${dInterval()} uplift intervals shown.`:'No level interval supplied in this export.'} Full values are listed below.`;
}
const dInterval=()=>intervalFor(discipline,metric(),$('innings').value);
new ResizeObserver(()=>{if(data)drawChart(visible.slice(0,10));}).observe($('chart'));
function table(){
 if(!visible.length){$('playerTable').innerHTML='<p class="empty">No matching players. Reduce the minimum sample or clear the search.</p>';return;}
 const rows=visible.map((p,i)=>`<tr><td>${i+1}</td><td class="player"><strong>${esc(p.name)}</strong><small>${esc(p.team)} · recorded team</small></td><td class="role">${esc(p.role)}</td><td class="number ${signClass(value(p))}">${signed(value(p))}</td><td class="number">${hasInterval()?interval(p):'Not supplied'}</td><td class="number">${p.pressureBalls}</td><td class="number">${p.normalBalls}</td><td class="number">${metric()==='pressure'?`${p.firstInningsPressureBalls} / ${p.chasePressureBalls}`:isBowling()?`${p.pressureBalls} / ${p.normalBalls}`:esc(p.confidence)}</td></tr>`).join('');
 const cards=visible.map((p,i)=>`<article class="player-card"><h4>${i+1}. ${esc(p.name)}</h4><p class="meta">${esc(p.team)} · ${esc(p.role)} · recorded data</p><div class="card-values"><div><small>${esc(views[metric()].label)}</small><strong class="${signClass(value(p))}">${signed(value(p))}</strong></div><div><small>${hasInterval()?dInterval()+' runs/uplift interval':'Level interval'}</small><span>${hasInterval()?interval(p):'Not supplied'}</span></div><div><small>Pressure legal balls</small>${p.pressureBalls}</div><div><small>Normal legal balls</small>${p.normalBalls}</div></div><div class="card-bottom">${isBowling()?`${p.pressureBalls} pressure / ${p.normalBalls} normal legal balls`:`Sample confidence: ${esc(p.confidence)}${p.top10?' · Analysis top 10':''}`}</div></article>`).join('');
 $('playerTable').innerHTML=`<div class="desktop-table"><table><thead><tr><th>#</th><th>Player / recorded team</th><th>${isBowling()?'Bowling style':'Batting role'}</th><th class="number">${metric()==='uplift'?'Uplift':'Level'} /100</th><th class="number">${hasInterval()?dInterval()+' runs interval':'Level interval'}</th><th class="number">Pressure balls</th><th class="number">Normal balls</th><th class="number">${metric()==='pressure'?'First / chase':isBowling()?'Pressure / normal':'Confidence'}</th></tr></thead><tbody>${rows}</tbody></table></div><div class="mobile-players">${cards}</div>`;
}
function compare(){
 const players=[$('compareA').value,$('compareB').value].map(id=>current.find(p=>p.id===id));
 $('comparison').innerHTML=players.map((p,i)=>{if(!p)return '<p>No player available.</p>';
 const metrics=metric()==='pressure'?[["Pressure RAE100",signed(p.pressure)],["Pressure legal balls",p.pressureBalls],["First innings / chase",`${p.firstInningsPressureBalls} / ${p.chasePressureBalls}`],["Meets sample standard",p.eligible?'Yes':'No'],["Final top 10",p.top10?'Yes':'No']]:isBowling()?[
  [views[metric()].label+' /100',signed(value(p))],['Uplift interval',hasInterval()?dInterval()+': '+interval(p):'Not supplied for this view'],['Pressure / normal legal balls',`${p.pressureBalls} / ${p.normalBalls}`]
 ]:[['Pressure RAE100',signed(p.pressure)],['Normal RAE100',signed(p.normal)],['Overall RAE100',signed(p.overall)],['Shrunk uplift (PPF_adj)',signed(p.uplift)],['90% uplift interval',interval(p)],['Pressure / normal legal balls',`${p.pressureBalls} / ${p.normalBalls}`],['Sample-qualified',p.sampleQualified?'Yes':'No'],['Current-view eligibility',p.eligible?'Yes':'No'],['Analysis top 10',p.top10?'Yes':'No']];
 return `<article class="compare-card"><p class="eyebrow">PLAYER ${i?'B':'A'}</p><h3>${esc(p.name)}</h3><p class="team">${esc(p.team)} · ${esc(p.role)} · recorded data</p><div class="compare-score"><span>${esc(views[metric()].label)}</span><strong class="${signClass(value(p))}">${signed(value(p))}</strong><small>${isBowling()?'runs saved /100 legal balls':'runs above expectation /100 legal balls'}</small></div><div class="compare-divider" aria-hidden="true"></div><dl>${metrics.map(([a,b])=>`<div><dt>${esc(a)}</dt><dd>${esc(b)}</dd></div>`).join('')}</dl><p class="caption">${metric()==='pressure'?'New 17 November offline performance run. Both innings pooled.':isBowling()?(hasInterval()?'The interval describes shrunk uplift, conditional on the fitted models and cutoffs.':'No interval is supplied for this view.'):'Uplift is shrunk; it need not equal the displayed unshrunk pressure-minus-normal difference.'}</p></article>`;
 }).join('');
}
for(const b of document.querySelectorAll('[data-discipline]'))b.addEventListener('click',()=>{discipline=b.dataset.discipline;reset();});
for(const id of ['metric','innings'])$(id).addEventListener('change',updateSource);
for(const id of ['pool','role','sort'])$(id).addEventListener('change',render);
for(const id of ['search','minBalls'])$(id).addEventListener('input',render);
for(const id of ['compareA','compareB'])$(id).addEventListener('change',compare);
$('exportBtn').addEventListener('click',()=>{
 const columns=['name','team','role',metric(),'ciLow','ciHigh','pressureBalls','normalBalls',...(isBowling()?['eligible','top10']:['sampleQualified','eligible','top10','quota'])];
 const safe=v=>{const s=String(v??'');return '"'+(/^[=+@\-\t\r]/.test(s)&&typeof v==='string'?"'"+s:s).replace(/"/g,'""')+'"';};
 const csv=[columns.join(','),...visible.map(p=>columns.map(k=>safe((!hasInterval()&&['ciLow','ciHigh'].includes(k))?null:p[k])).join(','))].join('\r\n');
 const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`royals-${discipline}-${isBowling()?listKey()+'-':''}${metric()}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
$('fileInput').addEventListener('change',async e=>{try{load(JSON.parse(await e.target.files[0].text()));}catch(err){$('errorText').textContent=err.message;}});
try{const response=await fetch('./dataset.json');if(!response.ok)throw new Error('The local dataset has not been imported.');load(await response.json());}
catch(err){$('dashboard').hidden=true;$('loadError').hidden=false;$('errorText').textContent=err.message;$('period').textContent='No dataset loaded';}

function route(){
 const hash=location.hash.slice(1);activePage=['home','batting','bowling','squad','methodology'].includes(hash)?hash:'home';
 document.querySelector('.intro').hidden=activePage!=='home';$('homeContent').hidden=activePage!=='home';const sq=activePage==='squad';$('squadSection').hidden=!sq;
 document.querySelectorAll('[data-page]').forEach(a=>{a.classList.toggle('selected',a.dataset.page===activePage);if(a.dataset.page===activePage)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
 if(!data)return;
 if(activePage==='home')$('period').textContent='IPL, T20I and Asia Cup 2022-2026 · Batting + bowling';
 $('dashboard').hidden=activePage==='home'||sq;document.querySelector('.tabs').hidden=true;
 const method=activePage==='methodology';
 $('analysisHeading').hidden=method;
 $('analysisTitle').textContent=activePage==='bowling'?'The bowling arena.':'The batting arena.';
 $('analysisEyebrow').textContent=activePage==='bowling'?'CONTROL. BREAKTHROUGHS. CONTEXT.':'TIMING. IMPACT. CONTEXT.';
 $('analysisIntro').textContent=activePage==='bowling'?'Explore the final pooled pressure-performance list, plus the preserved overall and uplift comparisons.':'Explore the final pressure-performance list, plus the preserved overall and uplift comparisons.';
 $('stats').hidden=method;document.querySelector('.subtabs').hidden=method;if(!method)setView('rankings');else{document.querySelector('.board').hidden=true;document.querySelector('.compare-section').hidden=true;}document.querySelector('.method-section').hidden=!method;
 if(method){renderMethod();}
 else if(false){$('methodology').innerHTML=Object.entries(data.disciplines).map(([key,d])=>`<div class="method-group"><h3>${key==='batting'?'Batting':'Bowling'}</h3><p class="method-scope">${esc(d.seasons)} · ${esc(d.source)}</p>${d.method.map(([title,text])=>`<details><summary>${esc(title)}</summary><p>${esc(text.replaceAll('per-match BPI','delivery BPI'))}</p></details>`).join('')}<details><summary>Interpretation and validation</summary><p>${esc(d.caveat)}</p></details></div>`).join('');}
 else if(activePage==='batting'||activePage==='bowling'){discipline=activePage;reset();}
}
function renderMethod(){if(!data.disciplines[mdisc])mdisc=Object.keys(data.disciplines)[0];
 document.querySelectorAll('[data-mdisc]').forEach(b=>{b.disabled=!data.disciplines[b.dataset.mdisc];const on=b.dataset.mdisc===mdisc;b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on));});
 const d=data.disciplines[mdisc];
 $('methodology').innerHTML=`<div class="method-group"><h3>${mdisc==='batting'?'Batting':'Bowling'}</h3><p class="method-scope">${esc(d.seasons)} · ${esc(d.source)}</p>${d.method.map(([title,text])=>`<details><summary>${esc(title)}</summary><p>${esc(text.replaceAll('per-match BPI','delivery BPI'))}</p></details>`).join('')}<details><summary>Interpretation and validation</summary><p>${esc(d.caveat)}</p></details><details><summary>How the final 10 are selected</summary><p>For consistency in selection, assess players over a substantial sample of pressure situations. Pool both innings and rank pressure RAE100 from highest to lowest. No activity filter, normal-ball minimum, overall-skill shortlist or uplift ordering applies to the final pressure list. The earlier comparison views preserve their original rules.</p></details><details><summary>Calculation provenance</summary><p>The final pressure list uses the 17 November 2026 offline expectation-model run on the saved reconstructed pressure checkpoint. Overall and shrunk-uplift views preserve earlier comparison exports and their own intervals. No old uplift interval is used for pressure level.</p></details></div>`;}
for(const b of document.querySelectorAll('[data-mdisc]'))b.addEventListener('click',()=>{mdisc=b.dataset.mdisc;renderMethod();});
function setView(v){view=v;document.querySelector('.board').hidden=v!=='rankings';document.querySelector('.compare-section').hidden=v!=='compare';document.querySelectorAll('[data-view]').forEach(b=>{const on=b.dataset.view===v;b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on));});}
for(const b of document.querySelectorAll('[data-view]'))b.addEventListener('click',()=>setView(b.dataset.view));
window.addEventListener('hashchange',route);
