import {test} from 'node:test';
import assert from 'node:assert/strict';
import {runDshText,textUsage,type DshRuntime,type TextLedger} from '../src/dsh-text.ts';
import {sha256} from '../src/material.ts';

test('DSH usage includes disjoint cache counters without double counting reasoning',()=>{
  assert.equal(textUsage({inputTokens:10,cacheReadTokens:20,cacheWriteTokens:5,outputTokens:7,reasoningTokens:3,totalTokens:42}).totalTokens,42);
  assert.throws(()=>textUsage({inputTokens:10,outputTokens:7,totalTokens:20}),/usage_invalid/);
});

test('prepared DSH text dispatch is session-free, reserved first and receipt saved before return',async()=>{
  const events:string[]=[];let generated:any;
  const runtime:DshRuntime={listModels:async()=>[],prepareCall:async config=>({config,retryPolicy:{mode:'normal',maxRetries:0},
    async *stream(options){events.push('stream');generated=options;yield {type:'text-delta',text:'answer'};
      yield {type:'usage',usage:{inputTokens:10,cacheReadTokens:5,outputTokens:2,totalTokens:17}};yield {type:'finish',reason:{kind:'stop'}};}})};
  const ledger:TextLedger={reserve:async()=>{events.push('reserve');return {state:'reserved',ticket:{id:'id',token:'token'}};},
    dispatch:async()=>{events.push('dispatch');},unknown:async()=>{events.push('unknown');},cancelUnsent:async()=>{events.push('cancel');},
    save:async(_ticket,_response,usage)=>{events.push('save');assert.equal(usage.tokens,17);assert.equal(usage.providerRequestId,null);return {overrun:false};}};
  const result=await runDshText(runtime,ledger,{provider:'deepseek-official',model:'deepseek-v4-flash',promptVersion:'test-v1',system:'extract',text:'material',maxOutputTokens:128,inputTokenBound:3000},
    {versionHash:sha256('synthetic tariff'),inputMicrosPerMillion:1000000,cacheReadMicrosPerMillion:1000000,cacheWriteMicrosPerMillion:1000000,outputMicrosPerMillion:1000000},()=>true,new AbortController().signal) as any;
  assert.equal(result.text,'answer');assert.deepEqual(events,['reserve','dispatch','stream','save']);
  assert.equal('sessionId'in generated,false);assert.equal('tools'in generated,false);
});

test('retry-enabled DSH route fails before reservation or send',async()=>{
  let reserved=false;
  const runtime:DshRuntime={listModels:async()=>[],prepareCall:async config=>({config,retryPolicy:{mode:'always'},async *stream(){throw Error('must not send');}})};
  const ledger={reserve:async()=>{reserved=true;throw Error('must not reserve');}} as unknown as TextLedger;
  await assert.rejects(runDshText(runtime,ledger,{provider:'deepseek-official',model:'deepseek-v4-flash',promptVersion:'v1',system:'extract',text:'material',maxOutputTokens:128,inputTokenBound:3000},
    {versionHash:sha256('synthetic'),inputMicrosPerMillion:1,cacheReadMicrosPerMillion:1,cacheWriteMicrosPerMillion:1,outputMicrosPerMillion:1},()=>true,new AbortController().signal),/retry_denied/);
  assert.equal(reserved,false);
});
