import {test} from 'node:test';
import assert from 'node:assert/strict';
import {runDshText,type DshRuntime,type TextLedger} from '../src/dsh-text.ts';
import {sha256} from '../src/material.ts';

const request={provider:'deepseek-official',model:'deepseek-v4-flash',promptVersion:'v1',system:'extract',text:'material',maxOutputTokens:128,inputTokenBound:3000};
const tariff={versionHash:sha256('synthetic tariff'),inputMicrosPerMillion:1000000,cacheReadMicrosPerMillion:500000,cacheWriteMicrosPerMillion:1000000,outputMicrosPerMillion:2000000};
function fixture(cancel=false,finishKind='stop'){
  const controller=new AbortController(),events:string[]=[];let response:any;
  const runtime:DshRuntime={listModels:async()=>[],prepareCall:async config=>({config,retryPolicy:{mode:'normal',maxRetries:0},
    async *stream(){yield {type:'text-delta',text:'answer'};if(cancel)controller.abort();
      yield {type:'usage',usage:{inputTokens:10,cacheReadTokens:4,outputTokens:2,totalTokens:16}};yield {type:'finish',reason:{kind:finishKind}};}})};
  const ledger:TextLedger={reserve:async()=>({state:'reserved',ticket:{id:'id',token:'token'}}),dispatch:async()=>{events.push('dispatch');},
    unknown:async()=>{events.push('unknown');},cancelUnsent:async()=>{events.push('cancel');},
    save:async(_ticket,value,usage)=>{events.push('save');response=value;assert.equal(usage.costMicros,16);return {overrun:false};}};
  return {runtime,ledger,controller,events,get response(){return response;}};
}
test('failed safety check retains usage in a sanitized rejected receipt',async()=>{
  const f=fixture();await assert.rejects(runDshText(f.runtime,f.ledger,request,tariff,()=>{throw Error('validator failure');},f.controller.signal),/output_rejected/);
  assert.deepEqual(f.events,['dispatch','save']);assert.equal(f.response.rejected,true);assert.equal('text'in f.response,false);
});
test('truncated complete response is charged before its business output is rejected',async()=>{
  const f=fixture(false,'max-tokens');
  await assert.rejects(runDshText(f.runtime,f.ledger,request,tariff,()=>true,f.controller.signal),/output_rejected/);
  assert.deepEqual(f.events,['dispatch','save']);assert.equal(f.response.finishKind,'max-tokens');
  const cached={...f.ledger,reserve:async()=>({state:'reused' as const,response:f.response})};
  await assert.rejects(runDshText(f.runtime,cached,request,tariff,()=>true,new AbortController().signal),/output_rejected/);
  assert.deepEqual(f.events,['dispatch','save']);
});
test('late complete usage is saved after cancellation while business output is denied',async()=>{
  const f=fixture(true);
  await assert.rejects(runDshText(f.runtime,f.ledger,request,tariff,()=>true,f.controller.signal),/call_cancelled/);
  assert.deepEqual(f.events,['dispatch','save']);assert.equal(f.response.usage.totalTokens,16);
});
