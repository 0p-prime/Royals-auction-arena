import {measure,filterPlayers,rankPlayers,fmt,validateDataset} from './core.js';
const $=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let mdisc='batting',view='rankings',data,discipline='batting',visible=[],current=[],activePage='home';
const isBowling=()=>discipline==='bowling';
const interval=p=>p.ciLow!==null&&p.ciHigh!==null?`${fmt(p.ciLow,0)} to ${fmt(p.ciHigh,0)}`:'Not available';
// Light-only presentation. Clear the previous theme preference on upgrade.
document.documentElement.dataset.theme='light';
try{localStorage.removeItem('raa-theme');}catch(err){}
function chartColors(){const s=getComputedStyle(document.documentElement);const g=k=>s.getPropertyValue(k).trim();return{grid:g('--chart-grid'),tick:g('--chart-tick'),zero:g('--chart-zero'),name:g('--chart-name'),interval:g('--chart-interval'),dot:g('--chart-dot'),value:g('--chart-value')};}
function load(dataset){data=validateDataset(dataset);if($('statBatters'))$('statBatters').textContent=data.disciplines.batting.players.length;if($('statBowlers'))$('statBowlers').textContent=data.disciplines.bowling.players.length;$('loadError').hidden=true;$('dashboard').hidden=false;reset();route();}
function reset(){
 if(!data.disciplines[discipline])discipline=Object.keys(data.disciplines)[0];
 document.querySelectorAll('[data-discipline]').forEach(b=>{b.disabled=!data.disciplines[b.dataset.discipline];b.classList.toggle('active',b.dataset.discipline===discipline);b.setAttribute('aria-pressed',String(b.dataset.discipline===discipline));});
 $('pool').value='top10';$('search').value='';$('minBalls').value=0;
 updateSource();
}
function updateSource(){
 const d=data.disciplines[discipline];
 $('period').textContent=d.seasons+' · '+(isBowling()?'Bowling analysis':'Batting analysis');
 current=rankPlayers(d.players);
 for(const option of $('pool').options)option.textContent=option.value==='top10'?'Final top 10':`Full final list (${current.length})`;
 const options=current.map(p=>`<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
 const oldA=$('compareA').value,oldB=$('compareB').value;
 $('compareA').innerHTML=options;$('compareB').innerHTML=options;
 const preferred=current.filter(p=>p.top10);
 $('compareA').value=current.some(p=>p.id===oldA)?oldA:preferred[0]?.id||current[0]?.id||'';
 $('compareB').value=current.some(p=>p.id===oldB)?oldB:preferred[1]?.id||preferred[0]?.id||'';
 render();
}
function render(){
 const d=data.disciplines[discipline];
 visible=filterPlayers(current,{search:$('search').value,pool:$('pool').value,minBalls:$('minBalls').value});
 const sum=current.reduce((s,p)=>s+p.hpBalls,0);
 const cards=[['Final rank list',current.length,'Ranked on pressure performance'],['Pressure balls',sum.toLocaleString(),'Legal high-pressure balls across the list'],['Final top 10',current.filter(p=>p.top10).length,'Pressure performance only'],['Calculation','18 Nov 2026','Final historical run, 843 matches']];
 $('stats').innerHTML=cards.map(([a,b,c])=>`<div class="stat"><small>${esc(a)}</small><strong>${esc(b)}</strong><span>${esc(c)}</span></div>`).join('');
 $('measureNote').textContent='Pressure score: 100 x the Normal cumulative probability of the standardized historical pressure-performance estimate. 50 is the role population mean; higher is better. Both innings pooled over 843 completed matches (2022-2026), with recency weighting. Final 18 November 2026 analysis; matches the delivered report.';
 $('caveat').innerHTML=`<p>The final list ranks performance under pressure itself; the score is an index, not a success probability. The 80% conditional score intervals are wide (about ${isBowling()?'75':'77'} points on average for the top 10), so treat close ranks as approximate; they omit model-form and calibration uncertainty.</p>`;
 $('resultCount').textContent=`${visible.length} players shown · 80% conditional score intervals`;
 drawChart(visible.slice(0,10));table();compare();
}
function drawChart(players){
 const col=chartColors();
 if(!players.length){$('chart').innerHTML='<p class="empty">No players match these filters.</p>';$('chartCaption').textContent='Try another sample threshold or clear the search.';return;}
 const width=Math.max(270,$('chart').clientWidth),left=width<450?112:150,right=width<450?48:65,height=players.length*36+42;
 let range=[0,...players.flatMap(p=>p.ciLow!==null&&p.ciHigh!==null?[p.score,p.ciLow,p.ciHigh]:[p.score])].filter(Number.isFinite);
 let min=Math.min(...range),max=Math.max(...range);if(max===min){min-=1;max+=1;}
 const pad=(max-min)*.07;min=Math.max(0,min-pad);max=Math.min(100,max+pad);
 const x=v=>left+(v-min)/(max-min)*(width-left-right);
 let svg=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="forestTitle forestDesc"><title id="forestTitle">${esc(measure.label)}</title><desc id="forestDesc">${esc(players.map(p=>`${p.name}: ${fmt(p.score)}, interval ${interval(p)}`).join('; '))}</desc>`;
 for(let i=0;i<5;i++){const tick=min+(max-min)*i/4;svg+=`<line x1="${x(tick)}" x2="${x(tick)}" y1="6" y2="${height-28}" stroke="${col.grid}"/><text x="${x(tick)}" y="${height-8}" text-anchor="middle" font-size="10" fill="${col.tick}">${Math.round(tick)}</text>`;}
 players.forEach((p,i)=>{const y=i*36+22;svg+=`<text x="${left-13}" y="${y+4}" text-anchor="end" font-size="12" fill="${col.name}" font-weight="600">${esc(p.name)}</text>`;
 if(p.ciLow!==null&&p.ciHigh!==null)svg+=`<line x1="${x(p.ciLow)}" x2="${x(p.ciHigh)}" y1="${y}" y2="${y}" stroke="${col.interval}" stroke-width="2"/><line x1="${x(p.ciLow)}" x2="${x(p.ciLow)}" y1="${y-4}" y2="${y+4}" stroke="${col.interval}"/><line x1="${x(p.ciHigh)}" x2="${x(p.ciHigh)}" y1="${y-4}" y2="${y+4}" stroke="${col.interval}"/>`;
 svg+=`<circle cx="${x(p.score)}" cy="${y}" r="4" fill="${col.dot}"/><text x="${width-3}" y="${y+4}" text-anchor="end" font-size="12" fill="${col.value}">${fmt(p.score)}</text>`;});
 $('chart').innerHTML=svg+'</svg>';
 $('chartCaption').textContent='Pressure score index; 50 is the role population mean. 80% conditional score intervals shown. Full values are listed below.';
}
new ResizeObserver(()=>{if(data)drawChart(visible.slice(0,10));}).observe($('chart'));
function table(){
 if(!visible.length){$('playerTable').innerHTML='<p class="empty">No matching players. Reduce the minimum sample or clear the search.</p>';return;}
 const rows=visible.map(p=>`<tr><td>${p.rank}</td><td class="player"><strong>${esc(p.name)}</strong></td><td class="number">${fmt(p.score)}</td><td class="number">${interval(p)}</td><td class="number">${p.hpBalls}</td><td class="number">${p.hpMatches}</td></tr>`).join('');
 const cards=visible.map(p=>`<article class="player-card"><h4>${p.rank}. ${esc(p.name)}</h4><p class="meta">Recorded high-pressure performance, 2022-2026</p><div class="card-values"><div><small>${esc(measure.label)}</small><strong>${fmt(p.score)}</strong></div><div><small>80% score interval</small><span>${interval(p)}</span></div><div><small>Pressure legal balls</small>${p.hpBalls}</div><div><small>High-pressure matches</small>${p.hpMatches}</div></div><div class="card-bottom">Score index${p.top10?' · Final top 10':''}</div></article>`).join('');
 $('playerTable').innerHTML=`<div class="desktop-table"><table><thead><tr><th>#</th><th>Player</th><th class="number">Score /100</th><th class="number">80% score interval</th><th class="number">Pressure balls</th><th class="number">HP matches</th></tr></thead><tbody>${rows}</tbody></table></div><div class="mobile-players">${cards}</div>`;
}
function compare(){
 const players=[$('compareA').value,$('compareB').value].map(id=>current.find(p=>p.id===id));
 $('comparison').innerHTML=players.map((p,i)=>{if(!p)return '<p>No player available.</p>';
 const metrics=[['Pressure score /100',fmt(p.score)],['80% conditional score interval',interval(p)],['Estimated A (model units)',fmt(p.aValue,4)],['Legal high-pressure balls',p.hpBalls],['High-pressure matches',p.hpMatches],['Final list rank',`#${p.rank}`],['Final top 10',p.top10?'Yes':'No']];
 return `<article class="compare-card"><p class="eyebrow">PLAYER ${i?'B':'A'}</p><h3>${esc(p.name)}</h3><p class="team">Recorded high-pressure performance, 2022-2026</p><div class="compare-score"><span>${esc(measure.label)}</span><strong>${fmt(p.score)}</strong><small>score index (50 = role average)</small></div><div class="compare-divider" aria-hidden="true"></div><dl>${metrics.map(([a,b])=>`<div><dt>${esc(a)}</dt><dd>${esc(b)}</dd></div>`).join('')}</dl><p class="caption">Final 18 November 2026 historical run. Both innings pooled.</p></article>`;
 }).join('');
}
for(const b of document.querySelectorAll('[data-discipline]'))b.addEventListener('click',()=>{discipline=b.dataset.discipline;reset();});
$('pool').addEventListener('change',render);
for(const id of ['search','minBalls'])$(id).addEventListener('input',render);
for(const id of ['compareA','compareB'])$(id).addEventListener('change',compare);
$('exportBtn').addEventListener('click',()=>{
 const columns=['rank','name','score','ciLow','ciHigh','hpBalls','hpMatches','top10'];
 const safe=v=>{const s=String(v??'');return '"'+(/^[=+@\-\t\r]/.test(s)&&typeof v==='string'?"'"+s:s).replace(/"/g,'""')+'"';};
 const csv=[columns.join(','),...visible.map(p=>columns.map(k=>safe(p[k])).join(','))].join('\r\n');
 const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`royals-${discipline}-pressure.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
$('fileInput').addEventListener('change',async e=>{try{load(JSON.parse(await e.target.files[0].text()));}catch(err){$('errorText').textContent=err.message;}});
try{const response=await fetch('./dataset.json');if(!response.ok)throw new Error('The local dataset has not been imported.');load(await response.json());}
catch(err){$('dashboard').hidden=true;$('loadError').hidden=false;$('errorText').textContent=err.message;$('period').textContent='No dataset loaded';}

function route(){
 const hash=location.hash.slice(1);activePage=['home','batting','bowling','squad','methodology'].includes(hash)?hash:'home';
 document.querySelector('.intro').hidden=activePage!=='home';$('homeContent').hidden=activePage!=='home';const sq=activePage==='squad';$('squadSection').hidden=!sq;
 document.querySelectorAll('[data-page]').forEach(a=>{a.classList.toggle('selected',a.dataset.page===activePage);if(a.dataset.page===activePage)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
 if(!data)return;
 if(activePage==='home')$('period').textContent='843 completed matches, 2022-2026 · Batting + bowling';
 $('dashboard').hidden=activePage==='home'||sq;document.querySelector('.tabs').hidden=true;
 const method=activePage==='methodology';
 $('analysisHeading').hidden=method;
 $('analysisTitle').textContent=activePage==='bowling'?'The bowling arena.':'The batting arena.';
 $('analysisEyebrow').textContent=activePage==='bowling'?'CONTROL. BREAKTHROUGHS. CONTEXT.':'TIMING. IMPACT. CONTEXT.';
 $('analysisIntro').textContent='Explore the final pressure-performance list, ranked on recorded high-pressure performance alone.';
 $('stats').hidden=method;document.querySelector('.subtabs').hidden=method;if(!method)setView('rankings');else{document.querySelector('.board').hidden=true;document.querySelector('.compare-section').hidden=true;}document.querySelector('.method-section').hidden=!method;
 if(method)renderMethod();
 else if(activePage==='batting'||activePage==='bowling'){discipline=activePage;reset();}
}
function renderMethod(){if(!data.disciplines[mdisc])mdisc=Object.keys(data.disciplines)[0];
 document.querySelectorAll('[data-mdisc]').forEach(b=>{b.disabled=!data.disciplines[b.dataset.mdisc];const on=b.dataset.mdisc===mdisc;b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on));});
 const d=data.disciplines[mdisc];
 $('methodology').innerHTML=`<div class="method-group"><h3>${mdisc==='batting'?'Batting':'Bowling'}</h3><p class="method-scope">${esc(d.seasons)} · ${esc(d.source)}</p>${d.method.map(([title,text])=>`<details><summary>${esc(title)}</summary><p>${esc(text)}</p></details>`).join('')}<details><summary>Interpretation and scope</summary><p>${esc(d.caveat)}</p></details><details><summary>Data</summary><p>Match data: 843 completed matches from the competition-supplied match list, 2022-2026. Ball-by-ball records were recovered for those fixtures. Of 199,211 deliveries, the 69,724 highest-pressure deliveries (35.0%) form the shared pressure set. The modelled pool contains 838 batting identities and 572 bowling identities, and every player estimate uses the same shared set of high-pressure deliveries.</p></details></div>`;}
for(const b of document.querySelectorAll('[data-mdisc]'))b.addEventListener('click',()=>{mdisc=b.dataset.mdisc;renderMethod();});
function setView(v){view=v;document.querySelector('.board').hidden=v!=='rankings';document.querySelector('.compare-section').hidden=v!=='compare';document.querySelectorAll('[data-view]').forEach(b=>{const on=b.dataset.view===v;b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on));});}
for(const b of document.querySelectorAll('[data-view]'))b.addEventListener('click',()=>setView(b.dataset.view));
window.addEventListener('hashchange',route);
