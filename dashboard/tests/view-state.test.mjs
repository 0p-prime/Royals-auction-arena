import test from 'node:test';
import assert from 'node:assert/strict';
import {bowlingSelection,intervalFor} from '../web/core.js';
test('pressure always pools both bowling innings',()=>{
 assert.deepEqual(bowlingSelection('pressure','pooled'),{metric:'pressure',innings:'pooled'});
 assert.deepEqual(bowlingSelection('pressure','chase'),{metric:'pressure',innings:'pooled'});
 assert.deepEqual(bowlingSelection('uplift','first'),{metric:'uplift',innings:'first'});
});
test('uncertainty is attached to the measure, not the discipline',()=>{
 assert.equal(intervalFor('bowling','uplift','pooled'),'95%');
 assert.equal(intervalFor('bowling','overall','pooled'),null);
 assert.equal(intervalFor('bowling','uplift','chase'),null);
 assert.equal(intervalFor('batting','uplift','pooled'),'90%');
 for(const t of ['batting','bowling']) assert.equal(intervalFor(t,'pressure','pooled'),'80%');
});
test('application module parses before deployment', async()=>{
 const {execFileSync}=await import('node:child_process');
 execFileSync(process.execPath,['--check',new URL('../web/app.js',import.meta.url).pathname]);
});
