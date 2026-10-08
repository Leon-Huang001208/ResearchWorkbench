import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,mkdtemp,mkdir,writeFile,realpath,symlink} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {validatePricing,priceExists} from '../src/pricing.ts';
import {loadNativeModel} from '../src/native-model.ts';
import {parseConfig} from '../src/config.ts';
test('only current official conservative pricing is accepted',async()=>{
  const sample=JSON.parse(await readFile(new URL('../pricing.deepseek.2026-10-09.json',import.meta.url),'utf8'));
  assert.equal(validatePricing(sample,'2026-10-09').outputMicrosPerMillion,1200000);
  for(const value of [{...sample,verifiedOn:'2026-10-08'},{...sample,source:'https://evil.example'},{...sample,outputMicrosPerMillion:0},{...sample,secret:'unexpected'}])
    assert.throws(()=>validatePricing(value,'2026-10-09'),/hot_pricing_invalid/);
});
test('private catalog supports a new synthetic day and changed fingerprints block before calls',async()=>{
  if(process.platform!=='darwin')return;
  const home=await realpath(await mkdtemp('/tmp/rwb-pricing-'));await mkdir(join(home,'hot/pricing'),{recursive:true,mode:0o700});
  const price={...JSON.parse(await readFile(new URL('../pricing.deepseek.2026-10-09.json',import.meta.url),'utf8')),verifiedOn:'2026-10-10'};
  const id='00000000-0000-0000-0000-000000000001',path=join(home,'hot/pricing/2026-10-10.json');
  const envelope={version:1,instanceId:id,projectRoot:resolve(import.meta.dirname,'../../..'),pricing:price,verifiedBy:`os-uid:${process.getuid?.()}`,reason:'Synthetic date/catalog fixture'};
  await writeFile(path,JSON.stringify(envelope),{mode:0o600});
  let prepared=0;
  const db:any=(value:unknown)=>Array.isArray(value)?Promise.resolve([{authorization_hash:'a'.repeat(64),paused:false,max_calls:20,max_tokens:20000,max_cost_micros:1000000,
    daily_max_calls:20,daily_max_tokens:20000,daily_max_cost_micros:1000000,quota_timezone:'Asia/Shanghai'}]):'schema';
  const context:any={runtime:{listModels:async()=>[{id:'deepseek-v4-flash'}],prepareCall:()=>{prepared++;throw Error('must not prepare');}},safeOutput:()=>true,close:async()=>{}};
  const capability=await loadNativeModel(db,'hot',{instanceId:id,mode:'native',generation:'1'},parseConfig({model:{enabled:true},budget:{maxCallsPerDay:20,maxTokensPerDay:20000,maxCostPerDay:1}}),
    {source:'/unused',credentials:{python:'/unused',bridge:'/unused',dataHome:home}},async()=>context,'2026-10-10');
  assert.equal(capability.state,'ready');
  await writeFile(path,JSON.stringify({...envelope,pricing:{...price,outputMicrosPerMillion:2400000}}),{mode:0o600});
  assert.equal(capability.state,'blocked_model');assert.throws(()=>capability.groupingModel!.run({} as any,new AbortController().signal),/pricing_refresh_required/);
  assert.equal(prepared,0);await capability.close();
});
test('dangling catalog symlinks are existing records, never a fallback bypass',async()=>{
  const folder=await realpath(await mkdtemp('/tmp/rwb-pricing-link-')),path=join(folder,'price.json');
  await symlink(join(folder,'missing'),path);assert.equal(priceExists(path),true);
});
