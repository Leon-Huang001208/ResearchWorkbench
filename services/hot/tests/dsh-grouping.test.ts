import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createDshGrouping,GROUP_MODEL_PROMPT_VERSION} from '../src/dsh-grouping.ts';
import {canonicalGroupingInput,GROUP_PROMPT_VERSION,type GroupingPacket} from '../src/processing.ts';
import type {DshRuntime,TextLedger} from '../src/dsh-text.ts';
import {sha256} from '../src/material.ts';

test('grouping DSH input stays canonical after JSONB reload and reuses the persisted receipt',async()=>{
  let sends=0,key='',response:any;
  const decision={parts:[{relation:'different_event',candidateId:null,title:'事件',reason:'Synthetic fixture'}]};
  const runtime:DshRuntime={listModels:async()=>[],prepareCall:async config=>({config,retryPolicy:{mode:'normal',maxRetries:0},async *stream(options){
    sends++;assert.equal('tools' in options,false);assert.equal('sessionId' in options,false);
    yield {type:'text-delta',text:JSON.stringify(decision)};
    yield {type:'usage',usage:{inputTokens:1,outputTokens:1,totalTokens:2}};yield {type:'finish',reason:{kind:'stop'}};
  }})};
  const ledger:TextLedger={reserve:async spec=>{if(response){assert.equal(spec.resultKey,key);return {state:'reused',response};}key=spec.resultKey;return {state:'reserved',ticket:{id:'test',token:'test'}};},
    dispatch:async()=>{},unknown:async()=>{},cancelUnsent:async()=>{},save:async(_t,r)=>{response=r;assert.equal((r as {promptVersion:string}).promptVersion,GROUP_MODEL_PROMPT_VERSION);return {overrun:false};}};
  const model=createDshGrouping(runtime,ledger,{versionHash:sha256('synthetic'),inputMicrosPerMillion:0,outputMicrosPerMillion:0,cacheReadMicrosPerMillion:0,cacheWriteMicrosPerMillion:0},()=>true,{provider:'deepseek-official',model:'deepseek-v4-flash'});
  const packet:GroupingPacket={promptVersion:GROUP_PROMPT_VERSION,material:{id:'test',revision:1,title:'Official announcement',excerpt:'Public fragment',url:'https://example.com',publishedAt:null,acquiredAt:'2026-10-08T00:00:00Z',contentHash:sha256('input'),partial:false},candidates:[],candidateLimit:20,candidateSearch:'bounded_all_history'};
  const first=await model.run(packet,new AbortController().signal);
  const reloaded=JSON.parse(canonicalGroupingInput(packet));
  assert.deepEqual(await model.run(reloaded,new AbortController().signal),first);assert.equal(sends,1);
});
