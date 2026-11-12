import {views,filterPlayers,sourcePlayers,sortedPlayers,fmt,signed,validateDataset} from './core.js';
const $=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let mdisc='batting',view='rankings',data,discipline='batting',visible=[],current=[],activePage='home';
const metric=()=>$('metric').value;
const isBowling=()=>discipline==='bowling';
const value=p=>p[metric()];
const signClass=v=>v>0?'positive':v<0?'negative':'';
const interval=p=>p.ciLow!==null&&p.ciHigh!==null?`${signed(p.ciLow)} to ${signed(p.ciHigh)}`:'Not available';
const hasInterval=()=>isBowling()||metric()==='uplift';
const listKey=()=>metric()==='overall'?'overall':`${$('innings').value==='first'?'firstInnings':'chase'}Pressure${metric()==='uplift'?'Uplift':'Level'}`;
// Light-only presentation. Clear the previous theme preference on upgrade.
document.documentElement.dataset.theme='light';
try{localStorage.removeItem('raa-theme');}catch(err){}
function chartColors(){const s=getComputedStyle(document.documentElement);const g=k=>s.getPropertyValue(k).trim();return{grid:g('--chart-grid'),tick:g('--chart-tick'),zero:g('--chart-zero'),name:g('--chart-name'),interval:g('--chart-interval'),dot:g('--chart-dot'),value:g('--chart-value')};}
function load(dataset){data=validateDataset(dataset);$('loadError').hidden=true;$('dashboard').hidden=false;reset();route();}
function reset(){
 if(!data.disciplines[discipline])discipline=Object.keys(data.disciplines)[0];
 document.querySelectorAll('[data-discipline]').forEach(b=>{b.disabled=!data.disciplines[b.dataset.discipline];b.classList.toggle('active',b.dataset.discipline===discipline);b.setAttribute('aria-pressed',String(b.dataset.discipline===discipline));});
 $('role').value='all';$('search').value='';$('minBalls').value=0;$('pool').value='top10';
 updateSource();
}
function updateSource(){
 const d=data.disciplines[discipline];
 $('inningsLabel').hidden=!isBowling()||metric()==='overall';$('sortLabel').hidden=!isBowling();
 $('minBalls').parentElement.firstChild.textContent=isBowling()?(metric()==='overall'?'Min. overall attempts':'Min. pressure attempts'):'Min. pressure balls';
 for(const option of $('pool').options){option.hidden=option.disabled=isBowling()&&['sample','shortlist','quota'].includes(option.value);if(option.value==='top10')option.textContent=isBowling()?'Source top 10':'Analysis top 10';if(option.value==='eligible')option.textContent=isBowling()?'All qualified in source list':'Active + sample-qualified';if(option.value==='all')option.textContent=isBowling()?'All in source list':'All exported players';}
 $('roleLabel').textContent=isBowling()?'Bowling style':'Batting role';
 if(isBowling()&&['sample','shortlist','quota'].includes($('pool').value))$('pool').value='eligible';
 $('period').textContent=d.seasons+' · '+(isBowling()?'Bowling model v5':'Batting analysis');
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
 $('methodology').innerHTML=d.method.map(([title,text])=>`<details><summary>${esc(title)}</summary><p>${esc(text)}</p></details>`).join('')+`<p class="caption">Source: ${esc(d.source)}</p>`;
 render();
}
function render(){
 const d=data.disciplines[discipline];
 const base=metric()==='overall'&&isBowling()?current.map(p=>({...p,pressureBalls:p.deliveries})):current;
 visible=sortedPlayers(filterPlayers(base,{role:$('role').value,search:$('search').value,pool:$('pool').value,minBalls:$('minBalls').value}),metric(),discipline,$('sort').value);
 const qualified=current.filter(p=>p.sampleQualified).length;
 const ciCount=visible.filter(p=>p.ciLow>0).length;
 const sum=current.reduce((s,p)=>s+(isBowling()?p.deliveries:p.pressureBalls),0);
 const cards=isBowling()?[
  ['Source cohort',current.length,'Qualified bowlers before filters'],['Delivery attempts',sum.toLocaleString(),'Includes wides and no-balls'],['Filtered players',visible.length,'Current pool, style and sample filters'],['Runs interval','~95%','Not a composite-rank interval']
 ]:[['Sample-qualified',qualified,'52 meet sample floors; 50 active'],['Pressure balls',sum.toLocaleString(),'Across all exported batsmen'],['Analysis top 10',current.filter(p=>p.top10).length,'Funnel + uplift ranking'],['Uplift interval','90%','Match-bootstrap, shrunk estimate']];
 $('stats').innerHTML=cards.map(([a,b,c])=>`<div class="stat"><small>${esc(a)}</small><strong>${esc(b)}</strong><span>${esc(c)}</span></div>`).join('');
 let note=isBowling()?`${views[metric()].label}: runs saved ${metric()==='uplift'?'under pressure minus own normal, within matched innings phases':'vs model expectation'}, per 100 delivery attempts. ${$('sort').value==='published'?'Order follows the source composite rank across wicket values, not the runs component alone.':'Custom runs-only ordering; not the source composite ranking.'} ${metric()==='overall'?'Both innings pooled overall.':$('innings').value==='first'?'First innings only.':'Chasing innings only.'} Sample rule: ${d.minimumBalls[listKey()]}.`:
 `${views[metric()].label}: ${metric()==='uplift'?'EB-shrunk pressure-minus-normal RAE100 (PPF_adj)':'recency-weighted '+(metric()==='pressure'?'pressure-bucket':'overall')+' runs above expectation per 100 legal balls'}. Higher is better; current filters are applied before ordering.`;
 $('measureNote').textContent=note;
 $('caveat').innerHTML=`<p>${isBowling()?'Runs saved and wickets above expectation are separate components. Source order combines them across wicket values 10-30.':'Uplift compares pressure performance with their own normal level. The displayed 90% interval describes the shrunk uplift estimate.'}</p>`+(!isBowling()&&$('pool').value==='quota'?'<p><strong>Role note:</strong> Rinku Singh and Stubbs fill the finisher slots in this role-balanced list; their uplift values sit below zero.</p>':'')+(isBowling()?'<p>~95% intervals describe the runs component. Rank ranges show sensitivity to wicket values.</p>':'');
 $('resultCount').textContent=`${visible.length} filtered players · ${hasInterval()?ciCount+' positive runs/uplift intervals':'level intervals not supplied'}`;
 $('chartTitle').textContent=isBowling()&&$('sort').value==='published'?'Composite leaders: runs component':'Leading players';
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
 $('chartCaption').textContent=`${isBowling()?'Runs saved per 100 delivery attempts':'Runs above expectation per 100 legal balls'}. ${hasInterval()?`${dInterval()} ${isBowling()?'runs-component':'uplift'} intervals shown.`:'No level interval supplied in this export.'} Full values are listed below.`;
}
const dInterval=()=>data.disciplines[discipline].interval;
new ResizeObserver(()=>{if(data)drawChart(visible.slice(0,10));}).observe($('chart'));
function table(){
 if(!visible.length){$('playerTable').innerHTML='<p class="empty">No matching players. Reduce the minimum sample or clear the search.</p>';return;}
 const rows=visible.map((p,i)=>`<tr><td>${i+1}</td><td class="player"><strong>${esc(p.name)}</strong><small>${esc(p.team)} · recorded team</small></td><td class="role">${esc(p.role)}</td><td class="number ${signClass(value(p))}">${signed(value(p))}</td><td class="number">${hasInterval()?interval(p):'Not supplied'}</td><td class="number">${isBowling()?signed(p.wickets,2):p.pressureBalls}</td><td class="number">${isBowling()?p.deliveries:p.normalBalls}</td><td class="number">${isBowling()?`${p.order} (${p.rankBest}-${p.rankWorst})`:esc(p.confidence)}</td></tr>`).join('');
 const cards=visible.map((p,i)=>`<article class="player-card"><h4>${i+1}. ${esc(p.name)}</h4><p class="meta">${esc(p.team)} · ${esc(p.role)} · recorded data</p><div class="card-values"><div><small>${esc(views[metric()].label)}</small><strong class="${signClass(value(p))}">${signed(value(p))}</strong></div><div><small>${hasInterval()?dInterval()+' runs/uplift interval':'Level interval'}</small><span>${hasInterval()?interval(p):'Not supplied'}</span></div><div><small>${isBowling()?'Wickets above expected /100':'Pressure legal balls'}</small>${isBowling()?signed(p.wickets,2):p.pressureBalls}</div><div><small>${isBowling()?'Delivery attempts':'Normal legal balls'}</small>${isBowling()?p.deliveries:p.normalBalls}</div></div><div class="card-bottom">${isBowling()?`Source order ${p.order} · Rank range ${p.rankBest}-${p.rankWorst} at wicket values 10-30`:`Sample confidence: ${esc(p.confidence)}${p.top10?' · Analysis top 10':''}`}</div></article>`).join('');
 $('playerTable').innerHTML=`<div class="desktop-table"><table><thead><tr><th>#</th><th>Player / recorded team</th><th>${isBowling()?'Bowling style':'Batting role'}</th><th class="number">${metric()==='uplift'?'Uplift':'Level'} /100</th><th class="number">${hasInterval()?dInterval()+' runs interval':'Level interval'}</th><th class="number">${isBowling()?'Wickets /100':'Pressure balls'}</th><th class="number">${isBowling()?'Attempts':'Normal balls'}</th><th class="number">${isBowling()?'Source order (range)':'Confidence'}</th></tr></thead><tbody>${rows}</tbody></table></div><div class="mobile-players">${cards}</div>`;
}
function compare(){
 const players=[$('compareA').value,$('compareB').value].map(id=>current.find(p=>p.id===id));
 $('comparison').innerHTML=players.map((p,i)=>{if(!p)return '<p>No player available.</p>';
 const metrics=isBowling()?[
  [views[metric()].label+' /100',signed(value(p))],['Runs-component interval ('+dInterval()+')',interval(p)],['Wickets above expectation /100',signed(p.wickets,2)],['Source composite order',p.order],['Rank range, wicket values 10-30',`${p.rankBest}-${p.rankWorst}`],['Delivery attempts',p.deliveries],...(metric()==='uplift'?[['Pressure / normal attempts',`${p.pressureBalls} / ${p.normalBalls}`],['Compared phases',p.phases]]:[])
 ]:[['Pressure RAE100',signed(p.pressure)],['Normal RAE100',signed(p.normal)],['Overall RAE100',signed(p.overall)],['Shrunk uplift (PPF_adj)',signed(p.uplift)],['90% uplift interval',interval(p)],['Pressure / normal legal balls',`${p.pressureBalls} / ${p.normalBalls}`],['Sample-qualified',p.sampleQualified?'Yes':'No'],['Source active eligibility',p.eligible?'Yes':'No'],['Analysis top 10',p.top10?'Yes':'No']];
 return `<article class="compare-card"><p class="eyebrow">PLAYER ${i?'B':'A'}</p><h3>${esc(p.name)}</h3><p class="team">${esc(p.team)} · ${esc(p.role)} · recorded data</p><div class="compare-score"><span>${esc(views[metric()].label)}</span><strong class="${signClass(value(p))}">${signed(value(p))}</strong><small>${isBowling()?'runs saved /100 attempts':'runs above expectation /100 legal balls'}</small></div><div class="compare-divider" aria-hidden="true"></div><dl>${metrics.map(([a,b])=>`<div><dt>${esc(a)}</dt><dd>${esc(b)}</dd></div>`).join('')}</dl><p class="caption">${isBowling()?'The interval covers runs only, not wickets or composite rank.':'Uplift is shrunk; it need not equal the displayed unshrunk pressure-minus-normal difference.'}</p></article>`;
 }).join('');
}
for(const b of document.querySelectorAll('[data-discipline]'))b.addEventListener('click',()=>{discipline=b.dataset.discipline;reset();});
for(const id of ['metric','innings'])$(id).addEventListener('change',updateSource);
for(const id of ['pool','role','sort'])$(id).addEventListener('change',render);
for(const id of ['search','minBalls'])$(id).addEventListener('input',render);
for(const id of ['compareA','compareB'])$(id).addEventListener('change',compare);
$('exportBtn').addEventListener('click',()=>{
 const columns=['name','team','role',metric(),'ciLow','ciHigh','pressureBalls','normalBalls',...(isBowling()?['wickets','deliveries','order','rankBest','rankWorst']:['sampleQualified','eligible','top10','quota'])];
 const safe=v=>{const s=String(v??'');return '"'+(/^[=+@\-\t\r]/.test(s)&&typeof v==='string'?"'"+s:s).replace(/"/g,'""')+'"';};
 const csv=[columns.join(','),...visible.map(p=>columns.map(k=>safe((!hasInterval()&&['ciLow','ciHigh'].includes(k))?null:p[k])).join(','))].join('\r\n');
 const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`royals-${discipline}-${isBowling()?listKey()+'-':''}${metric()}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
$('fileInput').addEventListener('change',async e=>{try{load(JSON.parse(await e.target.files[0].text()));}catch(err){$('errorText').textContent=err.message;}});
try{const response=await fetch('./dataset.json');if(!response.ok)throw new Error('The local dataset has not been imported.');load(await response.json());}
catch(err){$('dashboard').hidden=true;$('loadError').hidden=false;$('errorText').textContent=err.message;$('period').textContent='No dataset loaded';}

function route(){
 const hash=location.hash.slice(1);activePage=['home','batting','bowling','methodology'].includes(hash)?hash:'home';
 document.querySelector('.intro').hidden=activePage!=='home';$('homeContent').hidden=activePage!=='home';
 document.querySelectorAll('[data-page]').forEach(a=>{a.classList.toggle('selected',a.dataset.page===activePage);if(a.dataset.page===activePage)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
 if(!data)return;
 if(activePage==='home')$('period').textContent='IPL 2022-2026 · Batting + bowling';
 $('dashboard').hidden=activePage==='home';document.querySelector('.tabs').hidden=true;
 const method=activePage==='methodology';
 $('analysisHeading').hidden=method;
 $('analysisTitle').textContent=activePage==='bowling'?'The bowling arena.':'The batting arena.';
 $('analysisEyebrow').textContent=activePage==='bowling'?'CONTROL. BREAKTHROUGHS. CONTEXT.':'TIMING. IMPACT. CONTEXT.';
 $('analysisIntro').textContent=activePage==='bowling'?'Explore runs saved, wickets and phase-matched uplift across five distinct analysis views.':'See how players performed under pressure, how that compares with their normal level, and where they fit in the shortlist.';
 $('stats').hidden=method;document.querySelector('.subtabs').hidden=method;if(!method)setView('rankings');else{document.querySelector('.board').hidden=true;document.querySelector('.compare-section').hidden=true;}document.querySelector('.method-section').hidden=!method;
 if(method){renderMethod();}
 else if(false){$('methodology').innerHTML=Object.entries(data.disciplines).map(([key,d])=>`<div class="method-group"><h3>${key==='batting'?'Batting':'Bowling'}</h3><p class="method-scope">${esc(d.seasons)} · ${esc(d.source)}</p>${d.method.map(([title,text])=>`<details><summary>${esc(title)}</summary><p>${esc(text)}</p></details>`).join('')}<details><summary>Interpretation and validation</summary><p>${esc(d.caveat)}</p></details></div>`).join('');}
 else if(activePage==='batting'||activePage==='bowling'){discipline=activePage;reset();}
}
function renderMethod(){if(!data.disciplines[mdisc])mdisc=Object.keys(data.disciplines)[0];
 document.querySelectorAll('[data-mdisc]').forEach(b=>{b.disabled=!data.disciplines[b.dataset.mdisc];const on=b.dataset.mdisc===mdisc;b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on));});
 const d=data.disciplines[mdisc];
 $('methodology').innerHTML=`<div class="method-group"><h3>${mdisc==='batting'?'Batting':'Bowling'}</h3><p class="method-scope">${esc(d.seasons)} · ${esc(d.source)}</p>${d.method.map(([title,text])=>`<details><summary>${esc(title)}</summary><p>${esc(text)}</p></details>`).join('')}<details><summary>Interpretation and validation</summary><p>${esc(d.caveat)}</p></details></div>`;}
for(const b of document.querySelectorAll('[data-mdisc]'))b.addEventListener('click',()=>{mdisc=b.dataset.mdisc;renderMethod();});
function setView(v){view=v;document.querySelector('.board').hidden=v!=='rankings';document.querySelector('.compare-section').hidden=v!=='compare';document.querySelectorAll('[data-view]').forEach(b=>{const on=b.dataset.view===v;b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on));});}
for(const b of document.querySelectorAll('[data-view]'))b.addEventListener('click',()=>setView(b.dataset.view));
window.addEventListener('hashchange',route);
