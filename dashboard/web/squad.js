const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const roles=['All players','Batters','Wicket-keepers','All-rounders','Bowlers'];
const roleMap={'Batters':'Batter','Wicket-keepers':'Wicket-keeper','All-rounders':'All-rounder','Bowlers':'Bowler'};
let roster=[],role='All players';
const icons={bat:'<g transform="rotate(32 20 20)"><rect x="18" y="2" width="5" height="10" rx="2"/><path d="M15 12h11v19q0 7-5.5 7T15 31Z"/></g>',ball:'<circle cx="21" cy="21" r="15"/><path d="M11 12q9 11 20 18M12 11q11 9 18 20" stroke-dasharray="2 3"/>',keeper:'<path d="M10 33 5 20q-1-5 3-5l5 8V9q0-4 4-2l2 13V6q1-4 4 0l1 14 1-11q2-4 4 0l1 15 3-6q4-2 4 2l-5 13Z"/>',all:'<path d="M12 31 29 6l5 4-17 25Z"/><circle cx="30" cy="29" r="7"/>'};
function icon(key){return `<svg viewBox="0 0 42 42" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${icons[key]}</svg>`;}
function score(d,label){
 if(!d)return `<div class="ret-score ret-unavailable"><div><span>${label}</span><strong>Unavailable</strong></div><small>No observed pressure score in this dataset</small></div>`;
 return `<div class="ret-score ${label==='Bowling'?'ret-bowl':'ret-bat'}"><div><span>${label}</span><strong>${d.score.toFixed(1)}<i>/100</i></strong></div><div class="ret-meter" aria-hidden="true"><span data-value="${d.score}"></span><b></b></div><small>${d.balls.toLocaleString()} pressure balls${d.provisional?' <em>· Provisional</em>':''}</small></div>`;
}
function evidence(d,label){
 if(!d)return `<p><b>${label}:</b> no observed pressure score available.</p>`;
 return `<p><b>${label}:</b> ${d.score.toFixed(1)}/100 · 80% conditional interval ${d.low.toFixed(0)}-${d.high.toFixed(0)} · ${d.balls.toLocaleString()} legal pressure balls across ${d.matches} matches.<br><span>${d.provisional?'Provisional, below the model exposure threshold. ':''}${d.shortlist?'Meets the final-list pressure-ball floor.':'Below the final-list pressure-ball floor; shown as squad context, not a final-list rank.'}</span></p>`;
}
function render(){
 const term=$('retSearch').value.trim().toLowerCase();
 const list=roster.filter(p=>(role==='All players'||p.role===roleMap[role])&&`${p.name} ${p.modelName||''}`.toLowerCase().includes(term));
 $('retCount').textContent=`${list.length} of ${roster.length} players`;
 $('retPlayers').innerHTML=list.length?list.map((p,i)=>`<article class="ret-player ${p.status==='Traded in'?'ret-trade':''}"><div class="ret-card-top"><span class="ret-role-icon">${icon(p.role==='Batter'?'bat':p.role==='Bowler'?'ball':p.role==='Wicket-keeper'?'keeper':'all')}</span><span class="ret-status">${p.captain?'Captain · ':''}${p.status}</span></div><p class="ret-role">${esc(p.role)} <span>· ${esc(p.country)}</span></p><h3>${esc(p.name)}</h3><div class="ret-scores">${score(p.batting,'Batting')}${score(p.bowling,'Bowling')}</div><details class="ret-evidence"><summary>Score details <span aria-hidden="true">+</span></summary><div>${evidence(p.batting,'Batting')}${evidence(p.bowling,'Bowling')}${p.modelName?`<p class="ret-alias">Analysis name: ${esc(p.modelName)}</p>`:''}</div></details></article>`).join(''):'<p class="ret-empty">No player matches this search. Try a different name or role.</p>';
 $('retPlayers').querySelectorAll('[data-value]').forEach(e=>e.style.setProperty('--value',e.dataset.value+'%'));
 $('retReset').hidden=role==='All players'&&!term;
}
$('retFilters').innerHTML=roles.map(r=>`<button type="button" data-ret-role="${r}" aria-pressed="${r===role}" class="${r===role?'active':''}">${r}</button>`).join('');
$('retFilters').addEventListener('click',e=>{const b=e.target.closest('[data-ret-role]');if(!b)return;role=b.dataset.retRole;for(const x of $('retFilters').children){const on=x===b;x.classList.toggle('active',on);x.setAttribute('aria-pressed',String(on));}render();});
$('retSearch').addEventListener('input',render);
$('retReset').addEventListener('click',()=>{role='All players';$('retSearch').value='';for(const x of $('retFilters').children){const on=x.dataset.retRole===role;x.classList.toggle('active',on);x.setAttribute('aria-pressed',String(on));}render();});
try{const r=await fetch('./retained-squad.json');if(!r.ok)throw new Error('Roster request failed');const d=await r.json();roster=d.players;render();$('retCoverage').textContent=roster.filter(p=>p.batting||p.bowling).length;}
catch{$('retPlayers').innerHTML='<p class="ret-empty" role="alert">The squad could not load. Please reload this page.</p>';}
// Progressive hover depth, never a requirement for reading or operating a card.
const motion=window.matchMedia('(hover:hover) and (pointer:fine) and (prefers-reduced-motion:no-preference)');
$('retPlayers').addEventListener('pointermove',e=>{if(!motion.matches)return;const c=e.target.closest('.ret-player');if(!c)return;const b=c.getBoundingClientRect();c.style.setProperty('--ry',`${((e.clientX-b.left)/b.width-.5)*3}deg`);c.style.setProperty('--rx',`${(.5-(e.clientY-b.top)/b.height)*3}deg`);});
$('retPlayers').addEventListener('pointerout',e=>{const c=e.target.closest('.ret-player');if(c&&!c.contains(e.relatedTarget)){c.style.removeProperty('--rx');c.style.removeProperty('--ry');}});
