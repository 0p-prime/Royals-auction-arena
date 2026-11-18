export const measure={label:'Performance under pressure',unit:'score index (50 = role average)'};
export function filterPlayers(players,{search='',pool='all',minBalls=0}={}){
 return players.filter(p=>(pool!=='top10'||p.top10)&&p.hpBalls>=Number(minBalls)&&p.name.toLowerCase().includes(String(search).toLowerCase()));
}
export function rankPlayers(players){
 return [...players].filter(p=>Number.isFinite(p.score)).sort((a,b)=>b.score-a.score||b.hpBalls-a.hpBalls||a.name.localeCompare(b.name));
}
export const fmt=(v,d=1)=>Number.isFinite(v)?v.toFixed(d):'Not available';
export function validateDataset(data){
 if(!data||data.schemaVersion!==2||!data.disciplines)throw new Error('Expected a schemaVersion 2 dashboard dataset.');
 for(const [key,d]of Object.entries(data.disciplines)){
  if(!['batting','bowling'].includes(key)||!Array.isArray(d.players))throw new Error('Invalid discipline.');
  const ids=new Set();
  for(const p of d.players){
   if(typeof p.id!=='string'||typeof p.name!=='string'||!Number.isFinite(p.score)||!Number.isFinite(p.hpBalls)||!Number.isFinite(p.hpMatches)||!Number.isFinite(p.rank))throw new Error('Invalid player.');
   if(ids.has(p.id))throw new Error('Duplicate player.');
   ids.add(p.id);
   for(const m of ['ciLow','ciHigh','aValue'])if(p[m]!==null&&!Number.isFinite(p[m]))throw new Error(`Invalid metric: ${m}`);
  }
 }
 return data;
}
