import {test} from 'node:test';
import assert from 'node:assert/strict';
import {runDshText,type DshRuntime,type TextLedger} from '../src/dsh-text.ts';
import {sha256} from '../src/material.ts';
import {createDshGrouping} from '../src/dsh-grouping.ts';
const request={provider:'deepseek-official',model:'deepseek-v4-flash',promptVersion:'v1',system:'extract',text:'material',maxOutputTokens:128,inputTokenBound:3000,
  cacheIdentity:'input-v2' as const,legacyTariffHashes:[sha256('old tariff')]};
const tariff={versionHash:sha256('new tariff'),inputMicrosPerMillion:1,cacheReadMicrosPerMillion:1,cacheWriteMicrosPerMillion:1,outputMicrosPerMillion:1};
const config={provider:request.provider,model:request.model,maxTokens:128,temperature:0};
const oldKey=sha256(JSON.stringify({config,promptVersion:'v1',tariff:sha256('old tariff'),inputHash:sha256(JSON.stringify(['extract','material']))}));
const runtime:DshRuntime={listModels:async()=>[],prepareCall:async()=>({config,retryPolicy:{mode:'normal',maxRetries:0},async *stream(){throw Error('must not send');}})};
const forbidden=async():Promise<never>=>{throw Error('must not write/send');};
const writes={dispatch:forbidden,unknown:forbidden,save:forbidden,cancelUnsent:forbidden};

test('new date/rates reuse immutable legacy response without reservation or dispatch',async()=>{
  let reserved=0;const looked:string[]=[];
  const ledger:TextLedger={...writes,lookup:async spec=>{looked.push(spec.resultKey);return spec.resultKey===oldKey?{state:'reused',response:{text:'cached fact'}}:null;},
    reserve:async()=>{reserved++;throw Error('must not reserve');}};
  const result=await runDshText(runtime,ledger,request,tariff,()=>true,new AbortController().signal) as any;
  assert.equal(result.text,'cached fact');assert.equal(reserved,0);assert.ok(looked.includes(oldKey));
});

test('legacy unknown send prevents creating a second priced attempt',async()=>{
  let reserved=0;
  const ledger:TextLedger={...writes,lookup:async spec=>spec.resultKey===oldKey?{state:'busy',attemptId:'unknown'}:null,
    reserve:async()=>{reserved++;throw Error('must not reserve');}};
  await assert.rejects(runDshText(runtime,ledger,request,tariff,()=>true,new AbortController().signal),/hot_dsh_attempt_pending/);
  assert.equal(reserved,0);
});

test('input cache identity stays stable when tariff/date changes',async()=>{
  const keys:string[]=[];
  const ledger:TextLedger={...writes,lookup:async()=>null,reserve:async spec=>{keys.push(spec.resultKey);return {state:'reused',response:{text:'saved'}};}};
  await runDshText(runtime,ledger,request,tariff,()=>true,new AbortController().signal);
  await runDshText(runtime,ledger,request,{...tariff,versionHash:sha256('tomorrow'),outputMicrosPerMillion:2},()=>true,new AbortController().signal);
  assert.equal(keys[0],keys[1]);
});

test('atomic legacy admission propagates the actual receipt key to grouping publication',async()=>{
  const local:DshRuntime={listModels:async()=>[],prepareCall:async config=>({config,retryPolicy:{mode:'normal',maxRetries:0},async *stream(){throw Error('must not send');}})};
  const ledger:TextLedger={...writes,lookup:async()=>null,reserve:async spec=>{
    assert.ok(spec.legacySpecs?.length);return {state:'reused',resultKey:oldKey,response:{text:JSON.stringify({parts:[{relation:'different_event',candidateId:null,title:'Fact',reason:'Evidence'}]})}};
  }};
  const model=createDshGrouping(local,ledger,tariff,()=>true,{provider:request.provider,model:request.model,cacheIdentity:'input-v2',legacyTariffHashes:request.legacyTariffHashes});
  const result=await model.run({material:{id:'00000000-0000-0000-0000-000000000001',revision:1,title:'Fact',excerpt:'Evidence',url:'https://example.com/fact',publishedAt:null,acquiredAt:'2026-10-08T00:00:00Z',contentHash:sha256('fact'),partial:true},
    promptVersion:'fixture',candidates:[],candidateLimit:20,candidateSearch:'bounded_all_history'},new AbortController().signal);
  assert.equal(result.resultKey,oldKey);
});
