import test from 'node:test';import assert from 'node:assert/strict';
import {emptyState,addEntry,updateEntry,removeEntry,addAdjustment,setPurse,setMode,setTarget,compute,parseImport,importRetained,exportJSON,restoreJSON,exportCSV} from '../web/squad-core.js';
const mk=(s,f)=>{const r=addEntry(s,f);assert.ok(!r.error,r.error);return r.state;};
test('after-retentions mode does not deduct retained prices',()=>{
 let s=setPurse(emptyState(),100).state;
 s=mk(s,{name:'A',status:'retained',price:18,origin:'indian',tags:['top']});
 s=mk(s,{name:'B',status:'bought',price:10,origin:'overseas',tags:['pacer']});
 const c=compute(s);assert.equal(c.remaining,90);assert.equal(c.retainedInfoTotal,18);assert.equal(c.countsRetained,false);
});
test('total-budget mode deducts retained prices once',()=>{
 let s=setMode(setPurse(emptyState(),100).state,'total');
 s=mk(s,{name:'A',status:'retained',price:18});s=mk(s,{name:'B',status:'bought',price:10});
 assert.equal(compute(s).remaining,72);
});
test('missing price is unknown, never zero, and marks the purse incomplete',()=>{
 let s=setPurse(emptyState(),50).state;s=mk(s,{name:'A',status:'bought',price:''});
 const c=compute(s);assert.equal(s.entries[0].price,null);assert.equal(c.incomplete,true);assert.equal(c.unpriced,1);assert.equal(c.remaining,50);
 s=mk(s,{name:'Z',status:'bought',price:0});assert.equal(s.entries[1].price,0);
});
test('unknown origin is counted separately',()=>{
 let s=emptyState();s=mk(s,{name:'A',status:'bought'});s=mk(s,{name:'B',status:'bought',origin:'overseas'});
 const c=compute(s);assert.deepEqual(c.origin,{indian:0,overseas:1,unknown:1});
});
test('multi-tag players count in each role',()=>{
 let s=emptyState();s=mk(s,{name:'A',status:'bought',tags:['keeper','finisher']});s=mk(s,{name:'B',status:'bought',tags:[]});
 const c=compute(s);assert.equal(c.tags.keeper,1);assert.equal(c.tags.finisher,1);assert.equal(c.untagged,1);
});
test('edit, remove and adjustments restore the purse',()=>{
 let s=setPurse(emptyState(),20).state;s=mk(s,{name:'A',status:'bought',price:5});
 s=updateEntry(s,1,{price:8}).state;assert.equal(compute(s).remaining,12);
 s=addAdjustment(s,-2,'fee').state;assert.equal(compute(s).remaining,10);
 s=removeEntry(s,1);assert.equal(compute(s).remaining,18);
});
test('same names are allowed: no duplicate blocking',()=>{
 let s=emptyState();s=mk(s,{name:'A',status:'bought'});s=mk(s,{name:'A',status:'bought'});assert.equal(s.entries.length,2);assert.notEqual(s.entries[0].id,s.entries[1].id);
});
test('retained import parses lines and reports errors',()=>{
 const r=importRetained(setPurse(emptyState(),100).state,'Virat, 21, Indian, top; keeper\n# comment\nTim, , overseas\nBad, abc\nSolo');
 assert.equal(r.imported,3);assert.equal(r.errors.length,1);assert.equal(r.state.entries[1].price,null);assert.equal(r.state.entries[2].origin,'unknown');
 assert.ok(r.state.entries.every(e=>e.status==='retained'));assert.deepEqual(r.state.entries[0].tags,['top','keeper']);
});
test('per-slot only with a target',()=>{
 let s=setPurse(emptyState(),30).state;assert.equal(compute(s).perSlot,null);s=setTarget(s,'6').state;s=mk(s,{name:'A',status:'bought',price:0});assert.equal(compute(s).perSlot,6);
});
test('backup restores state and rejects other files',()=>{
 let s=setPurse(emptyState(),77.5).state;s=mk(s,{name:'A',status:'retained',price:3,origin:'indian',tags:['spinner']});
 const r=restoreJSON(exportJSON(s));assert.deepEqual(compute(r.state),compute(s));
 assert.ok(restoreJSON('{"a":1}').error);assert.ok(restoreJSON('nope').error);assert.match(exportCSV(s),/"A","retained","3","indian","Spinner"/);
});
test('invalid input is refused',()=>{assert.ok(setPurse(emptyState(),'abc').error);assert.ok(addEntry(emptyState(),{name:'',status:'bought'}).error);assert.ok(addEntry(emptyState(),{name:'A',price:'-1'}).error);});
