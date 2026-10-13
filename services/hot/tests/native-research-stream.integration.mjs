/** Real pinned SDK, synthetic credential and offline SSE; no vendor request. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createNativeDsh} from '../src/native-dsh.mjs';
import {createResearchStream} from '../../../app/research_web/runtime/hot-model-stream.mjs';

test('real prepared SDK request fits admitted full-request bound and persists normalized SSE before output',async()=>{
  const source=process.env.RWB_HOT_TEST_DSH_SOURCE,python=process.env.RWB_HOT_TEST_PYTHON;
  assert.ok(source&&python,'explicit owned pinned DSH and Python required');
  const home=await mkdtemp(join(tmpdir(),'hot-sdk-stream-')),bridge=join(home,'bridge.py');
  await writeFile(bridge,"import json,sys\np=json.load(sys.stdin)\nassert p['op'] in ['describe','resolve']\nprint(json.dumps({'ok':True,'configured':True,'source':'system-keychain','writable':True,**({'value':'synthetic-offline-sdk-key'} if p['op']=='resolve' else {})}))\n",{mode:0o600});
  const fetch=globalThis.fetch;let context,requests=0,bound=0,saved=false,sentBytes=0;
  const event=(type,value)=>`event: ${type}\ndata: ${JSON.stringify({type,...value})}\n\n`;
  const sse=event('message_start',{message:{id:'synthetic-message',type:'message',role:'assistant',model:'deepseek-flash',content:[],usage:{input_tokens:30,output_tokens:0}}})+
    event('content_block_start',{index:0,content_block:{type:'text',text:''}})+event('content_block_delta',{index:0,delta:{type:'text_delta',text:'Offline SDK receipt proof'}})+event('content_block_stop',{index:0})+
    event('message_delta',{delta:{stop_reason:'end_turn',stop_sequence:null},usage:{output_tokens:10}})+event('message_stop',{});
  globalThis.fetch=async(url,options)=>{requests++;assert.equal(String(url),'https://api.deepseek.com/anthropic/v1/messages');sentBytes=Buffer.byteLength(options.body);assert.ok(sentBytes<=bound);return new Response(sse,{status:200,headers:{'Content-Type':'text/event-stream'}});};
  try{
    context=await createNativeDsh({source,credentials:{python,bridge,dataHome:home}});
    const ledger={reserve:async params=>{bound=params.inputTokenBound;return {state:'reserved',ticket:{id:'synthetic-ticket',token:'synthetic-token'}};},dispatch:async()=>{},unknown:async()=>{throw Error('unexpected unknown');},cancel:async()=>{},receipt:async(_bound,chunks)=>{assert.ok(chunks.some(c=>c.type==='usage'&&c.usage.inputTokens===30&&c.usage.outputTokens===10));saved=true;return {overrun:false};}};
    const stream=createResearchStream(context.runtime,ledger,{runId:'00000000-0000-0000-0000-000000000001',sessionId:'00000000-0000-0000-0000-000000000002'},{provider:'deepseek-official',model:'deepseek-flash',maxTokens:512,temperature:0,system:'Synthetic offline test',messages:[{id:'synthetic-input',role:'user',source:{kind:'user'},content:[{type:'text',text:'No real provider may be contacted.'}]}]});
    let text='';for await(const chunk of stream){assert.equal(saved,true);if(chunk.type==='text-delta')text+=chunk.text;}
    assert.equal(text,'Offline SDK receipt proof');assert.equal(requests,1);assert.ok(sentBytes>0);
  }finally{globalThis.fetch=fetch;if(context)await context.close();await rm(home,{recursive:true});}
});
