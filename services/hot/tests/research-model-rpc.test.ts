import {test} from 'node:test';
import assert from 'node:assert/strict';
import {researchStreamReceipt} from '../src/research-model-rpc.ts';

const tariff={inputMicrosPerMillion:300000,cacheReadMicrosPerMillion:6000,cacheWriteMicrosPerMillion:300000,outputMicrosPerMillion:1200000};
test('research receipt accounts normalized usage and freezes the complete replay stream',()=>{
  const chunks=[{type:'text-delta',index:0,text:'evidence'},{type:'usage',usage:{inputTokens:100,cacheReadTokens:10,outputTokens:20,totalTokens:130}}, {type:'finish',reason:{kind:'stop'}}];
  const result=researchStreamReceipt(chunks,tariff);
  assert.equal(result.tokens,130);assert.equal(result.costMicros,55);assert.deepEqual(result.response,{chunks});
  chunks[0].text='mutated';assert.equal((result.response as any).chunks[0].text,'evidence');
});
test('incomplete and ambiguous streams cannot masquerade as saved successful results',()=>{
  const usage={type:'usage',usage:{inputTokens:10,outputTokens:2}};
  for(const chunks of [[],[usage], [{type:'finish',reason:{kind:'stop'}}], [usage,{type:'finish',reason:{kind:'stop'}},{type:'text-delta',text:'late'}], [usage,usage,{type:'finish',reason:{kind:'stop'}}]])assert.throws(()=>researchStreamReceipt(chunks,tariff),/hot_research_receipt_invalid/);
  assert.throws(()=>researchStreamReceipt([{type:'text-delta',text:'x'.repeat(1048576)},usage,{type:'finish',reason:{kind:'stop'}}],tariff),/hot_research_receipt_invalid/);
});
test('a provider failure with actual usage retains charges and a non-success replay marker',()=>{
  const result=researchStreamReceipt([{type:'usage',usage:{inputTokens:10,outputTokens:2}},{type:'finish',reason:{kind:'error',failure:{code:'FAILED'}}}],tariff);
  assert.equal((result.response as any).rejected,true);assert.equal(result.tokens,12);
});
