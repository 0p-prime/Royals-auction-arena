import test from 'node:test';
import assert from 'node:assert/strict';
test('application modules parse before deployment',async()=>{
 const {execFileSync}=await import('node:child_process');
 for(const f of ['../web/app.js','../web/core.js','../web/squad.js','../web/squad-core.js','../web/assistant.js'])execFileSync(process.execPath,['--check',new URL(f,import.meta.url).pathname]);
});
test('assistant API module parses before deployment',async()=>{
 const {execFileSync}=await import('node:child_process');
 execFileSync(process.execPath,['--check',new URL('../web/api/assistant.js',import.meta.url).pathname]);
});
test('no retired comparison views remain in the application copy',async()=>{
 const {readFileSync}=await import('node:fs');
 for(const f of ['../web/app.js','../web/index.html','../web/api/assistant.js']){
  const s=readFileSync(new URL(f,import.meta.url),'utf8');
  for(const term of ['uplift','Improvement over normal','role quota','shortlist35'])assert.ok(!s.toLowerCase().includes(term.toLowerCase()),`${f} still mentions ${term}`);
 }
});
