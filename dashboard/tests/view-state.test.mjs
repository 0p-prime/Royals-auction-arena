import test from 'node:test';
import assert from 'node:assert/strict';
import {bowlingSelection,intervalFor} from '../web/core.js';
test('metric changes escape the pooled uplift view',()=>{
 assert.deepEqual(bowlingSelection('pressure','pooled'),{metric:'pressure',innings:'chase'});
 assert.deepEqual(bowlingSelection('overall','pooled'),{metric:'overall',innings:'pooled'});
 assert.deepEqual(bowlingSelection('pressure','pooled','innings'),{metric:'uplift',innings:'pooled'});
});
test('uncertainty is attached to the measure, not the discipline',()=>{
 assert.equal(intervalFor('bowling','uplift','pooled'),'95%');
 for(const metric of ['pressure','overall']) assert.equal(intervalFor('bowling',metric,'pooled'),null);
 assert.equal(intervalFor('bowling','uplift','chase'),null);
 assert.equal(intervalFor('batting','uplift','pooled'),'90%');
 assert.equal(intervalFor('batting','pressure','pooled'),null);
});
test('application module parses before deployment', async()=>{
 const {execFileSync}=await import('node:child_process');
 execFileSync(process.execPath,['--check',new URL('../web/app.js',import.meta.url).pathname]);
});
