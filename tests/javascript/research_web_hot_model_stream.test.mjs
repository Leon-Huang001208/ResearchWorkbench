import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,rm,realpath} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createServer} from 'node:http';
import {apply} from '../../app/research_web/runtime/hot-model.mjs';
import {createResearchStream,freezeResearchRequest} from '../../app/research_web/runtime/hot-model-stream.mjs';

const options={provider:'deepseek-official',model:'deepseek-flash',messages:[{role:'user',content:[{type:'text',text:'source evidence'}]}],maxTokens:512,sessionId:'native-session'};
const chunks=[{type:'text-delta',index:0,text:'answer'},{type:'usage',usage:{inputTokens:20,outputTokens:3}},{type:'finish',reason:{kind:'stop'}}];
function fixture(overrides={}){
  const order=[];let sends=0;
  const ledger={reserve:async()=>{order.push('reserve');return {state:'reserved',ticket:{id:'ticket',token:'private'}};},dispatch:async()=>{order.push('dispatch');},receipt:async(_,saved)=>{order.push('receipt');assert.deepEqual(saved,chunks);},unknown:async()=>{order.push('unknown');},cancel:async()=>{order.push('cancel');},...overrides};
  const runtime={prepareCall:async config=>({config,retryPolicy:{mode:'normal',maxRetries:0},stream:async function*(request){sends++;order.push('send');assert.ok(Object.isFrozen(request.messages));yield* chunks;}})};
  return {order,ledger,runtime,sends:()=>sends};
}
const run={runId:'00000000-0000-0000-0000-000000000001',sessionId:'00000000-0000-0000-0000-000000000002'};
test('actual full request is frozen and bounded before any reservation',()=>{
  const frozen=freezeResearchRequest(options);assert.ok(frozen.inputTokenBound>=Buffer.byteLength(JSON.stringify(frozen.request))+2048);assert.equal(frozen.requestHash.length,64);
  assert.throws(()=>freezeResearchRequest({...options,messages:[{type:'image',data:'secret'}]}),/text_only/);
  assert.throws(()=>freezeResearchRequest({...options,system:'x'.repeat(65537)}),/request_limit/);
  assert.throws(()=>freezeResearchRequest({...options,unsupported:'hidden request'}),/request_invalid/);
});
test('reservation precedes one prepared send and durable receipt precedes output',async()=>{
  const f=fixture();const stream=createResearchStream(f.runtime,f.ledger,run,options);
  const first=await stream.next();assert.equal(first.value.text,'answer');assert.deepEqual(f.order,['reserve','dispatch','send','receipt']);
  await stream.return();assert.equal(f.sends(),1);assert.ok(!f.order.includes('unknown'));
});
test('replay never sends and unknown admission never retries',async()=>{
  const f=fixture({reserve:async()=>({state:'reused',response:{chunks}})});
  assert.deepEqual(await Array.fromAsync(createResearchStream(f.runtime,f.ledger,run,options)),chunks);assert.equal(f.sends(),0);
  const busy=fixture({reserve:async()=>({state:'busy'})});await assert.rejects(Array.fromAsync(createResearchStream(busy.runtime,busy.ledger,run,options)),/pending/);assert.equal(busy.sends(),0);
});
test('ambiguous dispatch and incomplete streams retain unknown without refund or output',async()=>{
  const f=fixture({dispatch:async()=>{throw Error('lost dispatch reply');}});
  await assert.rejects(Array.fromAsync(createResearchStream(f.runtime,f.ledger,run,options)),/outcome_unknown/);assert.equal(f.sends(),0);assert.deepEqual(f.order,['reserve','unknown']);
  const g=fixture();g.runtime.prepareCall=async config=>({config,retryPolicy:{mode:'normal',maxRetries:0},stream:async function*(){yield chunks[0];}});
  await assert.rejects(Array.fromAsync(createResearchStream(g.runtime,g.ledger,run,options)),/outcome_unknown/);assert.ok(g.order.includes('unknown'));assert.ok(!g.order.includes('receipt'));
});
test('provider retry policy is rejected before quota and receipt loss publishes no result',async()=>{
  const f=fixture();f.runtime.prepareCall=async config=>({config,retryPolicy:{mode:'normal',maxRetries:2}});
  await assert.rejects(Array.fromAsync(createResearchStream(f.runtime,f.ledger,run,options)),/retry_denied/);assert.deepEqual(f.order,[]);
  const g=fixture({receipt:async()=>{throw Error('lost receipt reply');}});await assert.rejects(Array.fromAsync(createResearchStream(g.runtime,g.ledger,run,options)),/outcome_unknown/);assert.equal(g.sends(),1);assert.ok(g.order.includes('unknown'));
});
test('late cancellation retains the saved receipt but publishes neither new nor cached output',async()=>{
  const abort=new AbortController();let saved=false;
  const f=fixture({receipt:async()=>{saved=true;abort.abort();}});
  await assert.rejects(Array.fromAsync(createResearchStream(f.runtime,f.ledger,run,{...options,signal:abort.signal})),{name:'AbortError'});
  assert.equal(saved,true);assert.equal(f.sends(),1);assert.ok(!f.order.includes('unknown'));assert.ok(!f.order.includes('cancel'));
  const cachedAbort=new AbortController();const cached=fixture({reserve:async()=>{cachedAbort.abort();return {state:'reused',response:{chunks}};}});
  await assert.rejects(Array.fromAsync(createResearchStream(cached.runtime,cached.ledger,run,{...options,signal:cachedAbort.signal})),{name:'AbortError'});assert.equal(cached.sends(),0);
});
test('real private HTTP bridge charges one nested prepared stream and leaves ordinary external sessions alone',async()=>{
  const root=await realpath(await mkdtemp(join(tmpdir(),'hot-stream-')));const sid=run.sessionId,cwd=join(root,'sessions',sid),calls=[];
  await mkdir(join(cwd,'inputs'),{recursive:true});await writeFile(join(cwd,'inputs','hot-context.json'),'{}',{mode:0o600});
  await mkdir(join(root,'.control'),{mode:0o700});const key='synthetic-private-key-'.padEnd(48,'x');
  const server=createServer(async(req,res)=>{let text='';for await(const part of req)text+=part;const body=JSON.parse(text);assert.equal(req.headers['x-research-data-key'],key);calls.push(body.operation);const response=body.operation==='binding'?run:body.operation==='reserve'?{state:'reserved',ticket:{id:'ticket',token:'token'}}:{state:body.operation==='receipt'?'received':'dispatching'};res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify(response));});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));await writeFile(join(root,'.control','datahub.json'),JSON.stringify({url:`http://127.0.0.1:${server.address().port}`,token:key}),{mode:0o600});
  let middleware,sends=0;const rootSession={header:{id:sid,cwd}},child={header:{id:'native-child',cwd,parentSession:sid}},ordinary={header:{id:'normal',cwd:'/ordinary-workspace'}};
  const ctx={sessions:{get:id=>id===sid?rootSession:id==='native-child'?child:ordinary},logger:{warn(){}},on:(_event,fn)=>{middleware=fn;},llm:{prepareCall:async config=>({config,retryPolicy:{mode:'normal',maxRetries:0},stream:request=>middleware(request,async function*(){sends++;yield* chunks;})})}};
  try{apply(ctx,{researchRoot:root});assert.deepEqual(await Array.fromAsync(middleware({...options,sessionId:'native-child'},()=>{throw Error('unprepared send denied');})),chunks);assert.equal(sends,1);assert.deepEqual(calls,['binding','reserve','dispatch','receipt']);
    const before=calls.length;assert.deepEqual(await Array.fromAsync(middleware({...options,sessionId:'normal'},async function*(){yield {ordinary:true};})),[{ordinary:true}]);assert.equal(calls.length,before);
  }finally{await new Promise(resolve=>server.close(resolve));await rm(root,{recursive:true,force:true});}
});
