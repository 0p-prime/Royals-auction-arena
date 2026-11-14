import {TAGS,MODES,emptyState,addEntry,updateEntry,removeEntry,addAdjustment,removeAdjustment,setPurse,setTarget,setMode,compute,importRetained,exportJSON,exportCSV,restoreJSON,money} from './squad-core.js';
const $=id=>document.getElementById(id);
if(!$('squadSection'))throw new Error('squad section missing');
const KEY='royals-squad-planner-v1';
let state=load(),history=[],editingId=null,roleHints=new Map(),storageOk=true;
function load(){try{const raw=localStorage.getItem(KEY);if(raw){const r=restoreJSON(raw);if(r.state)return r.state;}}catch{}return emptyState();}
function save(){try{localStorage.setItem(KEY,exportJSON(state));storageOk=true;}catch{storageOk=false;}}
function commit(next){history.push(state);if(history.length>50)history.shift();state=next;save();render();}
function el(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;}
// Role tag checkboxes
const tagBox=$('sqTags');
for(const t of TAGS){const l=el('label','chip');const i=document.createElement('input');i.type='checkbox';i.value=t.id;i.name='sqTag';l.appendChild(i);l.appendChild(el('span',null,t.label));tagBox.appendChild(l);}
const checkedTags=()=>[...tagBox.querySelectorAll('input:checked')].map(i=>i.value);
const setTags=list=>{for(const i of tagBox.querySelectorAll('input'))i.checked=list.includes(i.value);};
// Names from the dataset for suggestions only. Nationality is never guessed.
fetch('./dataset.json').then(r=>r.ok?r.json():null).then(d=>{if(!d)return;const names=new Set();
 const bat=d.disciplines&&d.disciplines.batting&&d.disciplines.batting.players||[];for(const p of bat){names.add(p.name);if(p.role==='opener')roleHints.set(p.name,['top']);else if(p.role==='middle')roleHints.set(p.name,['middle']);else if(p.role==='finisher')roleHints.set(p.name,['finisher']);}
 const lists=d.disciplines&&d.disciplines.bowling&&d.disciplines.bowling.lists||{};for(const k of Object.keys(lists))for(const p of lists[k])names.add(p.name);
 const dl=$('sqNames');for(const n of [...names].sort().slice(0,2000)){const o=document.createElement('option');o.value=n;dl.appendChild(o);}}).catch(()=>{});
$('sqName').addEventListener('input',()=>{const n=$('sqName').value.trim();const h=roleHints.get(n);const hint=$('sqHint');
 if(h&&editingId===null){if(!checkedTags().length)setTags(h);hint.textContent='The dataset lists this batter as '+({top:'an opener (top order)',middle:'a middle-order batter',finisher:'a finisher'}[h[0]])+'. Change the roles if that is not right. Nationality and bowling type are not in the data, so choose them yourself.';}
 else hint.textContent='';});
function num(v){return v===''?'':v;}
function render(){
 const c=compute(state);
 for(const r of document.querySelectorAll('input[name="sqMode"]'))r.checked=r.value===state.mode;
 if(document.activeElement!==$('sqStart'))$('sqStart').value=state.purse===null?'':state.purse;
 if(document.activeElement!==$('sqTarget'))$('sqTarget').value=state.target===null?'':state.target;
 $('sqModeNote').textContent=c.countsRetained?'Mode: total budget. Retained prices ARE deducted (once) from the figure below.':'Mode: auction purse after retentions. Retained prices are NOT deducted again.';
 $('sqRemainingLabel').textContent=(c.incomplete?'Remaining purse (at most)':'Remaining purse')+' · '+(c.countsRetained?'budget before retentions':'after retentions');
 $('sqRemaining').textContent=c.remaining===null?'Enter an amount':money(c.remaining);
 $('sqSpent').textContent=money(c.spent);
 $('sqWarn').textContent=c.incomplete?('At most '+money(c.remaining)+' left. '+c.unpriced+(c.unpriced===1?' counted player has':' counted players have')+' no price yet, so the real figure may be lower.'):'';
 const info=[];if(c.retainedCount&&!c.countsRetained)info.push('Retained players: '+c.retainedCount+', listed prices total '+money(c.retainedInfoTotal)+(c.retainedUnpriced?' ('+c.retainedUnpriced+' with unknown price)':'')+'. Information only.');
 if(c.perSlot!==null)info.push((c.incomplete?'At most ':'About ')+money(c.perSlot)+' per remaining slot ('+c.slots+' to reach the target of '+state.target+').');else if(c.slots!==null&&c.slots<=0)info.push('Squad target of '+state.target+' reached.');
 $('sqInfo').textContent=info.join(' ');
 const al=$('sqAdjList');al.textContent='';for(const a of state.adjustments){const li=el('li');li.appendChild(el('span',null,(a.amount>0?'+':'')+a.amount+' cr'+(a.note?' · '+a.note:'')));const b=el('button','link','Remove');b.type='button';b.addEventListener('click',()=>commit(removeAdjustment(state,a.id)));li.appendChild(b);al.appendChild(li);}
 $('sqUndo').disabled=!history.length;
 // counts
 const box=$('sqCounts');box.textContent='';
 const card=(label,value,sub)=>{const d=el('div','count-card');d.appendChild(el('small',null,label));d.appendChild(el('strong',null,String(value)));if(sub)d.appendChild(el('span',null,sub));box.appendChild(d);};
 card('Squad size',c.size,state.target?'target '+state.target:'');card('Indian',c.origin.indian);card('Overseas',c.origin.overseas);card('Nationality not set',c.origin.unknown,c.origin.unknown?'not counted as Indian or overseas':'');
 for(const t of TAGS)card(t.label,c.tags[t.id]);if(c.untagged)card('No role set',c.untagged);
 $('sqSquadCount').textContent=c.size?'('+c.size+')':'';
 // list
 const lists=$('sqLists');lists.textContent='';
 if(!state.entries.length){lists.appendChild(el('p','empty','No players yet. Add one above or import a retained squad.'));}
 for(const g of [['retained','Retained'],['bought','Bought at auction']]){const items=state.entries.filter(e=>e.status===g[0]);if(!items.length)continue;
  lists.appendChild(el('h3',null,g[1]+' ('+items.length+')'));const ul=el('ul','player-list');
  for(const e of items){const li=el('li');const main=el('div','p-main');main.appendChild(el('strong',null,e.name));
   const meta=el('div','p-meta');meta.appendChild(el('span','badge '+(e.origin==='unknown'?'unset':e.origin),e.origin==='indian'?'Indian':e.origin==='overseas'?'Overseas':'Nationality not set'));
   meta.appendChild(el('span','badge price'+(e.price===null?' unset':''),e.price===null?'Price unknown':money(e.price)+(g[0]==='retained'&&!c.countsRetained?' (info)':'')));
   for(const t of e.tags)meta.appendChild(el('span','badge role',TAGS.find(x=>x.id===t).label));if(!e.tags.length)meta.appendChild(el('span','badge unset','No role set'));
   main.appendChild(meta);li.appendChild(main);
   const act=el('div','p-actions');const ed=el('button','link','Edit');ed.type='button';ed.addEventListener('click',()=>startEdit(e.id));const rm=el('button','link','Remove');rm.type='button';rm.addEventListener('click',()=>{if(editingId===e.id)stopEdit();commit(removeEntry(state,e.id));});act.appendChild(ed);act.appendChild(rm);li.appendChild(act);ul.appendChild(li);}
  lists.appendChild(ul);}
 $('sqStorageNote').classList.toggle('bad',!storageOk);
 if(!storageOk)$('sqStorageNote').textContent='This browser is blocking saving, so your plan will be lost when you close the page. Download a backup now.';
}
function startEdit(id){const e=state.entries.find(x=>x.id===id);if(!e)return;editingId=id;$('sqName').value=e.name;$('sqStatus').value=e.status;$('sqPrice').value=e.price===null?'':e.price;$('sqOrigin').value=e.origin;setTags(e.tags);$('sqFormTitle').textContent='Edit player';$('sqSubmit').textContent='Save changes';$('sqCancel').hidden=false;$('sqForm').scrollIntoView({block:'center'});}
function stopEdit(){editingId=null;$('sqForm').reset();setTags([]);$('sqFormTitle').textContent='Add a player';$('sqSubmit').textContent='Add to squad';$('sqCancel').hidden=true;$('sqHint').textContent='';$('sqFormError').textContent='';}
$('sqCancel').addEventListener('click',stopEdit);
$('sqForm').addEventListener('submit',ev=>{ev.preventDefault();const f={name:$('sqName').value,status:$('sqStatus').value,price:$('sqPrice').value,origin:$('sqOrigin').value,tags:checkedTags()};
 const r=editingId===null?addEntry(state,f):updateEntry(state,editingId,f);if(r.error){$('sqFormError').textContent=r.error;return;}
 const status=f.status;stopEdit();$('sqStatus').value=status;commit(r.state);$('sqName').focus();});
$('sqStart').addEventListener('change',()=>{const r=setPurse(state,$('sqStart').value);if(r.error){$('sqWarn').textContent=r.error;return;}commit(r.state);});
$('sqTarget').addEventListener('change',()=>{const r=setTarget(state,$('sqTarget').value);if(r.error){$('sqWarn').textContent=r.error;return;}commit(r.state);});
for(const r of document.querySelectorAll('input[name="sqMode"]'))r.addEventListener('change',()=>{if(r.checked&&r.value!==state.mode)commit(setMode(state,r.value));});
$('sqAdjForm').addEventListener('submit',ev=>{ev.preventDefault();const r=addAdjustment(state,$('sqAdjAmount').value,$('sqAdjNote').value);if(r.error){$('sqWarn').textContent=r.error;return;}$('sqAdjForm').reset();commit(r.state);});
$('sqUndo').addEventListener('click',()=>{if(!history.length)return;state=history.pop();save();stopEdit();render();});
$('sqImportBtn').addEventListener('click',()=>{const text=$('sqImportText').value;const r=importRetained(state,text);const out=$('sqImportResult');out.textContent='';
 if(!r.imported&&!r.errors.length){out.textContent='Nothing to import. Add one player per line.';return;}
 if(r.imported)commit(r.state);
 out.appendChild(el('p',null,r.imported+' retained '+(r.imported===1?'player':'players')+' imported.'+(r.errors.length?' '+r.errors.length+' '+(r.errors.length===1?'line was':'lines were')+' skipped:':'')));
 if(r.errors.length){const ul=el('ul');for(const e of r.errors.slice(0,10))ul.appendChild(el('li',null,'Line '+e.line+': '+e.reason+' ('+e.text.trim().slice(0,60)+')'));out.appendChild(ul);}
 if(r.imported&&!r.errors.length)$('sqImportText').value='';});
function download(name,text,type){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}
const stamp=()=>new Date().toISOString().slice(0,10);
$('sqDownload').addEventListener('click',()=>{download('squad-plan-'+stamp()+'.json',exportJSON(state),'application/json');$('sqBackupResult').textContent='Backup downloaded.';});
$('sqDownloadCsv').addEventListener('click',()=>{download('squad-'+stamp()+'.csv',exportCSV(state),'text/csv');$('sqBackupResult').textContent='CSV downloaded. Use the JSON backup to restore a plan.';});
$('sqRestore').addEventListener('change',async()=>{const f=$('sqRestore').files[0];if(!f)return;const r=restoreJSON(await f.text());$('sqRestore').value='';
 if(r.error){$('sqBackupResult').textContent=r.error;return;}
 if(state.entries.length&&!confirm('Replace the current plan with the backup?'))return;stopEdit();commit(r.state);$('sqBackupResult').textContent='Backup restored: '+r.state.entries.length+' players.';});
$('sqClear').addEventListener('click',()=>{if(!state.entries.length&&state.purse===null&&!state.adjustments.length)return;if(!confirm('Clear the whole plan? You can use Undo straight after.'))return;stopEdit();commit(emptyState());});
render();
