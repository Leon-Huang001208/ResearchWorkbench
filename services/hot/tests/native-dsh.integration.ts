/** Real installed DSH registry, with a describe-only credential fixture; never dispatches. */
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,rm,readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createNativeDsh} from '../src/native-dsh.mjs';
import {loadNativeModel} from '../src/native-model.ts';
import {parseConfig} from '../src/config.ts';

test('current pinned build mounts the official route without resolving secrets or sending',async()=>{
  const source=process.env.RWB_HOT_TEST_DSH_SOURCE,python=process.env.RWB_HOT_TEST_PYTHON;
  assert.ok(source&&python,'explicit owned installed DSH and Python paths required');
  const directory=await mkdtemp(join(tmpdir(),'hot-native-catalog-'));
  const bridge=join(directory,'describe.py'),calls=join(directory,'calls.jsonl');
  await writeFile(bridge,`import json,sys,pathlib
p=json.load(sys.stdin)
with pathlib.Path(${JSON.stringify(calls)}).open('a') as f: f.write(json.dumps({'op':p['op'],'ref':p['ref']})+'\\n')
assert p['op']=='describe', 'credential resolution forbidden in catalog proof'
print(json.dumps({'ok':True,'configured':True,'source':'system-keychain','writable':True}))
`,{mode:0o600});
  let active:Awaited<ReturnType<typeof createNativeDsh>>|undefined;
  try{
    active=await createNativeDsh({source,credentials:{python,bridge,dataHome:directory}});
    const models=await active.runtime.listModels('deepseek-official');
    assert.ok(models.some(model=>model.id==='deepseek-flash'));
    const prepared=await active.runtime.prepareCall({provider:'deepseek-official',model:'deepseek-flash',maxTokens:512,temperature:0},new AbortController().signal);
    assert.equal(prepared.config.model,'deepseek-flash');
    assert.equal(prepared.retryPolicy.maxRetries,0);
    assert.equal(prepared.config.maxTokens,512);
    const db:any=(query:unknown)=>Array.isArray(query)?Promise.resolve([{authorization_hash:'a'.repeat(64),paused:false,max_calls:20,max_tokens:20000,max_cost_micros:1000000,
      daily_max_calls:20,daily_max_tokens:20000,daily_max_cost_micros:1000000,quota_timezone:'Asia/Shanghai'}]):'schema';
    const capability=await loadNativeModel(db,'hot',{instanceId:'00000000-0000-0000-0000-000000000001',mode:'native',generation:'1'},
      parseConfig({model:{enabled:true},budget:{maxCallsPerDay:20,maxTokensPerDay:20000,maxCostPerDay:1}}),
      {source,credentials:{python,bridge,dataHome:directory}},async()=>active!,'2026-10-12');
    assert.equal(capability.state,'ready');
    assert.ok(capability.groupingModel);
    assert.deepEqual((await readFile(calls,'utf8')).trim().split('\n').map(line=>JSON.parse(line).op),['describe']);
    assert.equal(active.safeOutput('No private material reflected'),false,'no resolved credential means no output can pass reflection checks');
  }finally{if(active)await active.close();await rm(directory,{recursive:true});}
});
