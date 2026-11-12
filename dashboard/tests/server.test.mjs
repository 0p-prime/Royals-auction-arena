import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from '../server.mjs';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import os from 'node:os';import path from 'node:path';
async function running(dataPath,fn){const s=createServer({dataPath});await new Promise(r=>s.listen(0,'127.0.0.1',r));try{await fn(`http://127.0.0.1:${s.address().port}`);}finally{await new Promise(r=>s.close(r));}}
test('missing data produces explicit 404, not fake empty success',async()=>running('/absent/dataset.json',async url=>{const r=await fetch(url+'/api/dataset');assert.equal(r.status,404);assert.match((await r.json()).error,/No local dataset/);}));
test('only app allowlist and dataset endpoint are served',async()=>running('/absent',async url=>{for(const file of ['/private/dataset.json','/server.mjs','/package.json','/etc/passwd','/api/dataset/extra'])assert.equal((await fetch(url+file)).status,404);const r=await fetch(url);assert.equal(r.status,200);assert.match(r.headers.get('content-security-policy'),/connect-src 'self'/);assert.equal((await fetch(url,{method:'POST'})).status,405);}));
test('configured dataset is returned without mutation',async()=>{const dir=await mkdtemp(path.join(os.tmpdir(),'royals-test-'));try{const p=path.join(dir,'data.json');await writeFile(p,'{"test":1}');await running(p,async url=>{assert.deepEqual(await(await fetch(url+'/api/dataset')).json(),{test:1});});}finally{await rm(dir,{recursive:true});}});
