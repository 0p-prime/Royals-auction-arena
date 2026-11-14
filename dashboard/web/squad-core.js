// Pure squad and purse logic. No rules, caps or purse values are built in:
// every number comes from the selector. Amounts are in rupees crore.
export const TAGS=[
 {id:'top',label:'Top order',group:'Batters'},
 {id:'middle',label:'Middle order',group:'Batters'},
 {id:'finisher',label:'Finisher',group:'Batters'},
 {id:'spinner',label:'Spinner',group:'Bowlers'},
 {id:'pacer',label:'Pacer',group:'Bowlers'},
 {id:'keeper',label:'Wicketkeeper',group:'Other'},
 {id:'allrounder',label:'All-rounder',group:'Other'}
];
export const MODES={after:'Auction purse at start (after retentions)',total:'Total budget before retentions'};
const TAG_IDS=new Set(TAGS.map(t=>t.id));
const ALIASES={top:'top','top order':'top',opener:'top',middle:'middle','middle order':'middle',finisher:'finisher',spinner:'spinner',spin:'spinner',pacer:'pacer',pace:'pacer',seam:'pacer',keeper:'keeper',wk:'keeper',wicketkeeper:'keeper',allrounder:'allrounder','all-rounder':'allrounder','all rounder':'allrounder',ar:'allrounder'};
export const STORAGE_VERSION=1;
export function emptyState(){return {version:STORAGE_VERSION,mode:'after',purse:null,target:null,adjustments:[],entries:[],nextId:1};}
export function num(v){if(v===null||v===undefined)return null;const t=String(v).trim().replace(/,/g,'');if(t==='')return null;const n=Number(t);return Number.isFinite(n)?n:NaN;}
export function cleanTags(list){const out=[];for(const t of list||[]){const id=ALIASES[String(t).trim().toLowerCase()]||(TAG_IDS.has(t)?t:null);if(id&&!out.includes(id))out.push(id);}return out;}
export function cleanOrigin(v){const t=String(v||'').trim().toLowerCase();if(['indian','india','ind'].includes(t))return 'indian';if(['overseas','foreign','os'].includes(t))return 'overseas';return 'unknown';}
// status: 'retained' | 'bought'. price: number or null (unknown, never zero by default).
export function makeEntry(state,{name,status,price,origin,tags}){
 const n=String(name||'').trim().slice(0,60);if(!n)return {error:'Enter a player name.'};
 const p=num(price);if(Number.isNaN(p)||(p!==null&&p<0))return {error:'Price must be a number of crore, or left blank if unknown.'};
 return {entry:{id:state.nextId,name:n,status:status==='retained'?'retained':'bought',price:p,origin:cleanOrigin(origin),tags:cleanTags(tags)}};
}
export function addEntry(state,fields){const r=makeEntry(state,fields);if(r.error)return {state,error:r.error};return {state:{...state,entries:[...state.entries,r.entry],nextId:state.nextId+1}};}
export function updateEntry(state,id,fields){const old=state.entries.find(e=>e.id===id);if(!old)return {state,error:'Player not found.'};const r=makeEntry(state,{...old,...fields});if(r.error)return {state,error:r.error};return {state:{...state,entries:state.entries.map(e=>e.id===id?{...r.entry,id}:e)}};}
export function removeEntry(state,id){return {...state,entries:state.entries.filter(e=>e.id!==id)};}
export function addAdjustment(state,amount,note){const a=num(amount);if(a===null||Number.isNaN(a)||a===0)return {state,error:'Enter an adjustment amount, positive or negative.'};return {state:{...state,adjustments:[...state.adjustments,{id:state.nextId,amount:a,note:String(note||'').trim().slice(0,80)}],nextId:state.nextId+1}};}
export function removeAdjustment(state,id){return {...state,adjustments:state.adjustments.filter(a=>a.id!==id)};}
export function setPurse(state,v){const n=num(v);if(Number.isNaN(n)||(n!==null&&n<0))return {state,error:'Purse must be a number of crore.'};return {state:{...state,purse:n}};}
export function setTarget(state,v){const n=num(v);if(Number.isNaN(n)||(n!==null&&(n<1||!Number.isInteger(n))))return {state,error:'Squad target must be a whole number.'};return {state:{...state,target:n}};}
export function setMode(state,mode){return {...state,mode:mode==='total'?'total':'after'};}
// Retained prices are counted ONLY when the input is the total budget before retentions.
export function compute(state){
 const countsRetained=state.mode==='total';
 const counted=state.entries.filter(e=>e.status==='bought'||(countsRetained&&e.status==='retained'));
 const spent=counted.reduce((s,e)=>s+(e.price??0),0);
 const unpriced=counted.filter(e=>e.price===null).length;
 const adj=state.adjustments.reduce((s,a)=>s+a.amount,0);
 const retained=state.entries.filter(e=>e.status==='retained');
 const retainedPriced=retained.filter(e=>e.price!==null);
 const remaining=state.purse===null?null:round(state.purse-spent+adj);
 const size=state.entries.length;
 const slots=state.target?state.target-size:null;
 const perSlot=(remaining!==null&&slots>0)?round(remaining/slots):null;
 const origin={indian:0,overseas:0,unknown:0};for(const e of state.entries)origin[e.origin]++;
 const tags={};for(const t of TAGS)tags[t.id]=0;let untagged=0;for(const e of state.entries){if(!e.tags.length)untagged++;for(const t of e.tags)tags[t]++;}
 return {mode:state.mode,countsRetained,spent:round(spent),unpriced,adjustment:round(adj),remaining,incomplete:unpriced>0,size,slots,perSlot,origin,tags,untagged,
  retainedCount:retained.length,retainedInfoTotal:round(retainedPriced.reduce((s,e)=>s+e.price,0)),retainedUnpriced:retained.length-retainedPriced.length,
  boughtCount:size-retained.length};
}
export function round(n){return Math.round(n*100)/100;}
export function money(n){return n===null||n===undefined?'unknown':'₹'+String(round(n))+' cr';}
// One player per line: name, price, Indian|Overseas, tags separated by ; or /. Only the name is required.
export function parseImport(text){
 const rows=[],errors=[];const lines=String(text||'').split(/\r?\n/);
 lines.forEach((raw,i)=>{const line=raw.trim();if(!line||line.startsWith('#'))return;
  const parts=line.split(/[,\t|]/).map(s=>s.trim());
  const name=parts[0];if(!name){errors.push({line:i+1,text:raw,reason:'No name'});return;}
  let price=null,origin='unknown',tags=[];let bad=null;
  for(const p of parts.slice(1)){if(p==='')continue;
   const n=num(p.replace(/^₹/,'').replace(/\s*cr(ore)?$/i,''));
   if(n!==null&&!Number.isNaN(n)){if(n<0)bad='Negative price';else price=n;continue;}
   const o=cleanOrigin(p);if(o!=='unknown'){origin=o;continue;}
   const tl=cleanTags(p.split(/[;/]/));if(tl.length){tags=tags.concat(tl);continue;}
   bad='Could not read "'+p+'"';}
  if(bad){errors.push({line:i+1,text:raw,reason:bad});return;}
  rows.push({name,status:'retained',price,origin,tags:cleanTags(tags)});});
 return {rows,errors};
}
export function importRetained(state,text){
 const {rows,errors}=parseImport(text);let s=state;
 for(const r of rows){const res=addEntry(s,r);if(!res.error)s=res.state;}
 return {state:s,imported:rows.length,errors};
}
// Backup: JSON file that restores the whole plan.
export function exportJSON(state){return JSON.stringify({app:'royals-squad-planner',...state},null,1);}
export function restoreJSON(text){
 let d;try{d=JSON.parse(text);}catch{return {error:'This is not a valid backup file.'};}
 if(!d||d.app!=='royals-squad-planner'||!Array.isArray(d.entries)||!Array.isArray(d.adjustments))return {error:'This file is not a squad planner backup.'};
 const s=emptyState();s.mode=d.mode==='total'?'total':'after';s.purse=typeof d.purse==='number'&&d.purse>=0?d.purse:null;s.target=Number.isInteger(d.target)&&d.target>0?d.target:null;
 let id=1;
 for(const e of d.entries){const r=makeEntry({nextId:id},{name:e.name,status:e.status,price:e.price,origin:e.origin,tags:e.tags});if(r.entry){s.entries.push(r.entry);id++;}}
 for(const a of d.adjustments){const v=num(a.amount);if(v&&!Number.isNaN(v)){s.adjustments.push({id,amount:v,note:String(a.note||'').slice(0,80)});id++;}}
 s.nextId=id;return {state:s};
}
export function exportCSV(state){
 const q=v=>'"'+String(v).replace(/"/g,'""')+'"';const rows=[['Player','Status','Price (crore)','Origin','Roles']];
 for(const e of state.entries)rows.push([e.name,e.status,e.price===null?'unknown':e.price,e.origin,e.tags.map(t=>TAGS.find(x=>x.id===t).label).join('; ')]);
 return rows.map(r=>r.map(q).join(',')).join('\n');
}
