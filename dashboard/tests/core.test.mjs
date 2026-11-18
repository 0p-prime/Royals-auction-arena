import test from 'node:test';
import assert from 'node:assert/strict';
import {filterPlayers,rankPlayers,validateDataset} from '../web/core.js';
const a={id:'A',name:'A One',score:71.6,ciLow:25.1,ciHigh:96.6,aValue:0.019,hpBalls:573,hpMatches:72,rank:1,top10:true};
const b={id:'B',name:'B Two',score:66.7,ciLow:21.5,ciHigh:95.2,aValue:0.012,hpBalls:1005,hpMatches:97,rank:2,top10:true};
const c={id:'C',name:'C Three',score:40.2,ciLow:5,ciHigh:83,aValue:0.001,hpBalls:780,hpMatches:80,rank:12,top10:false};
test('pool, minimum balls and case-insensitive search combine',()=>{
 assert.deepEqual(filterPlayers([a,b,c],{pool:'top10'}),[a,b]);
 assert.deepEqual(filterPlayers([a,b,c],{pool:'all',minBalls:800}),[b]);
 assert.deepEqual(filterPlayers([a,b,c],{pool:'all',search:'TWO'}),[b]);
});
test('ranking orders by score, then exposure, without mutating input',()=>{
 const input=[c,a,b];assert.deepEqual(rankPlayers(input),[a,b,c]);assert.deepEqual(input,[c,a,b]);
 const less={...a,id:'L',name:'L',hpBalls:60},more={...a,id:'M',name:'M',hpBalls:80};
 assert.equal(rankPlayers([less,more])[0].name,'M');
});
test('missing score never creates a fabricated value',()=>{assert.deepEqual(rankPlayers([{...a,score:null}]),[]);});
test('schema validates the final-list dataset shape',()=>{
 assert.throws(()=>validateDataset({}));
 assert.throws(()=>validateDataset({schemaVersion:1,disciplines:{batting:{players:[a]}}}));
 assert.throws(()=>validateDataset({schemaVersion:2,disciplines:{batting:{players:[{...a,ciLow:Infinity}]}}}));
 assert.throws(()=>validateDataset({schemaVersion:2,disciplines:{batting:{players:[a,a]}}}));
 assert.ok(validateDataset({schemaVersion:2,disciplines:{batting:{players:[a,b]},bowling:{players:[c]}}}));
});
test('the built site dataset passes validation and matches the report top 10',async()=>{
 const {readFileSync}=await import('node:fs');
 const d=validateDataset(JSON.parse(readFileSync(new URL('../web/dataset.json',import.meta.url),'utf8')));
 assert.equal(d.disciplines.batting.players.length,14);
 assert.equal(d.disciplines.bowling.players.length,16);
 assert.deepEqual(d.disciplines.batting.players.filter(p=>p.top10).map(p=>p.name),['TH David','Tilak Varma','SA Yadav','JC Buttler','N Pooran','RK Singh','SO Hetmyer','Ishan Kishan','S Dube','SS Iyer']);
 assert.deepEqual(d.disciplines.bowling.players.filter(p=>p.top10).map(p=>p.name),['CV Varun','AR Patel','B Kumar','JJ Bumrah','Kuldeep Yadav','HV Patel','M Theekshana','JO Holder','YS Chahal','Arshdeep Singh']);
 for(const disc of ['batting','bowling'])for(const p of d.disciplines[disc].players){assert.ok(p.hpBalls>0);assert.ok(p.ciLow<p.score&&p.score<p.ciHigh);}
});
