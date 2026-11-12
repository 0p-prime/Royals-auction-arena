export const views={uplift:{label:'Improvement over normal',unit:'runs / 100 balls',key:'uplift'},pressure:{label:'Performance under pressure',unit:'runs / 100 balls',key:'pressure'},overall:{label:'Overall performance',unit:'runs / 100 balls',key:'overall'}};
export function filterPlayers(players,{role='all',search='',pool='eligible',minBalls=0}={}){
 return players.filter(p=>(role==='all'||p.role===role)&&(pool==='all'||(pool==='sample'?p.sampleQualified:pool==='shortlist'?p.shortlisted:pool==='top10'?p.top10:pool==='quota'?p.quota:p.eligible))&&p.pressureBalls>=Number(minBalls)&&`${p.name} ${p.team||''}`.toLowerCase().includes(search.toLowerCase()));
}
export function rankPlayers(players,metric='uplift') {return [...players].filter(p=>Number.isFinite(p[metric])).sort((a,b)=>b[metric]-a[metric]||a.name.localeCompare(b.name));}
export const fmt=(v,d=1)=>Number.isFinite(v)?v.toFixed(d):'Not available';
export const signed=(v,d=1)=>Number.isFinite(v)?`${v>0?'+':''}${v.toFixed(d)}`:'Not available';
export function validateDataset(data){
 if(!data||data.schemaVersion!==1||!data.disciplines)throw new Error('Expected a schemaVersion 1 dashboard dataset.');
 for(const [key,d]of Object.entries(data.disciplines)){
  if(!['batting','bowling'].includes(key)||!Array.isArray(d.players))throw new Error('Invalid discipline.');
  const names=new Set();
  for(const p of [...d.players,...Object.values(d.lists||{}).flat()]){if(typeof p.id!=='string'||typeof p.name!=='string'||!Number.isFinite(p.pressureBalls))throw new Error('Invalid player.');names.add(p.id);for(const m of ['pressure','normal','overall','uplift','ciLow','ciHigh'])if(p[m]!==null&&!Number.isFinite(p[m]))throw new Error(`Invalid metric: ${m}`);}
 }
 return data;
}
export function sourcePlayers(dataset,discipline,metric,innings='chase'){
 const d=dataset.disciplines[discipline];if(!d)return [];
 if(discipline==='batting')return d.players;
 const key=metric==='overall'?'overall':`${innings==='first'?'firstInnings':'chase'}Pressure${metric==='uplift'?'Uplift':'Level'}`;
 return d.lists[key]||[];
}
export function sortedPlayers(players,metric,discipline,order='published'){
 return discipline==='bowling'&&order==='published'?[...players].sort((a,b)=>a.order-b.order):rankPlayers(players,metric);
}
