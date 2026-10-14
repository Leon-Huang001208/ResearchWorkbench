import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {randomBytes,randomUUID} from 'node:crypto';
import postgres from 'postgres';
import {migrate,ingestPage} from '../src/database.ts';
import {initializeIdentity,activateRuntime,pauseRuntime} from '../src/control.ts';
import {saveAutomaticEvent,configureChannel} from '../src/events.ts';
import {createBriefRequest} from '../src/brief-control.ts';
import {researchEvidence} from '../src/research-evidence.ts';
import {sha256} from '../src/material.ts';
import {openQueue} from '../src/queue.ts';
import {grantWorker,grantController} from '../src/provision.ts';
import {startService} from '../src/service.ts';
import {rpc,startTransport} from '../src/transport.ts';
import {researchModelHandlers} from '../src/research-model-rpc.ts';
import {spawn} from 'node:child_process';
import {reserveResearchModelCall} from '../src/research-model.ts';
import {provisionModelBudget,reserveModel,markModelDispatch,saveModelReceipt,cancelUnsentModel} from '../src/model-budget.ts';

async function hostRead(python:string,input:Record<string,unknown>){
  const script=`import sys,json,hashlib
from pathlib import Path
from unittest.mock import patch
from research_workbench_entrypoint.hot_manager import HotManager
from app.research_web.hot_service import HotWebService
from app.research_web.hot_routes import router
from app.research_web.service import ResearchService
from app.research_web.store import Store
from tests.research_web.test_hot_session_recovery import Native
from uuid import uuid4
import keyring
from fastapi import FastAPI
from fastapi.testclient import TestClient
from docx import Document
import tempfile,asyncio,io
from contextlib import redirect_stdout
p=json.load(sys.stdin)
with redirect_stdout(sys.stderr),tempfile.TemporaryDirectory() as temp:
 m=HotManager(Path.cwd(),Path(temp).resolve(),object())
 with patch.object(m,"_state",return_value={"port":p["port"],"owner":p["owner"]}),patch.object(m,"_secret",side_effect=lambda ref:p["readerToken"] if ref=="rpc-reader" else p["controllerToken"]):
  value=m.research_evidence(p["briefId"],1,p["materialIds"])
  bridge=HotWebService(Path.cwd(),m.home,manager_factory=lambda:m)
  keys={}
  keyring.get_password=lambda service,account:keys.get((service,account))
  keyring.set_password=lambda service,account,value:keys.__setitem__((service,account),value)
  keyring.delete_password=lambda service,account:keys.pop((service,account),None)
  native=Native();native.lose_reply=False
  research=ResearchService(native,Store(m.home),owned=True)
  app=FastAPI();app.include_router(router);app.state.hot=bridge;app.state.research=research
  with TestClient(app) as client:
   response=client.get("/api/research/hot/briefs/"+p["briefId"]+"/docx?version=1")
   assert response.status_code==200
   text="\\n".join(paragraph.text for paragraph in Document(io.BytesIO(response.content)).paragraphs)
   assert value["manifest"]["briefContentHash"] in text
   files=list((m.home/"hot"/"brief-artifacts").glob("*.docx"))
   assert len(files)==1 and files[0].read_bytes()==response.content
   docx={"status":response.status_code,"bytes":len(response.content),"retained":True,"parsed":True}
   args={"runId":str(uuid4()),"requestId":str(uuid4()),"briefId":p["briefId"],"version":1,"materialIds":p["materialIds"],"targetMode":"fingpt"}
   response=client.post("/api/research/hot/research/handoffs",json=args,headers={"X-Research-User-Action":"?1"})
   assert response.status_code==200,response.text
   handoff=response.json();assert handoff["state"]=="snapshot_ready" and handoff["executionStarted"] is False
   replay=client.post("/api/research/hot/research/handoffs",json=args,headers={"X-Research-User-Action":"?1"})
   assert replay.json()["sessionId"]==handoff["sessionId"] and replay.json()["datasetId"]==handoff["datasetId"]
   assert native.creations==1
   dataset=research.datahub.snapshots.detail(handoff["sessionId"],handoff["datasetId"])
   assert dataset["hot"]["manifestHash"]==value["manifestHash"]
   for item in value["manifest"]["objects"]:assert research.datahub.snapshots.read(handoff["sessionId"],handoff["datasetId"],item["filename"])==value["objects"][item["key"]]
   handoff_proof={"state":handoff["state"],"nativeCreations":native.creations,"nativeFixture":True,"snapshotCount":len(research.datahub.snapshots.ids(handoff["sessionId"])),"executionStarted":False}
  asyncio.run(bridge.close())
  asyncio.run(research.close())
print(json.dumps({"manifestHash":value["manifestHash"],"objects":{k:{"bytes":len(v),"hash":hashlib.sha256(v).hexdigest()} for k,v in value["objects"].items()},"docx":docx,"handoff":handoff_proof}))`;
  return new Promise<any>((resolveResult,reject)=>{
    const child=spawn(python,['-c',script],{cwd:resolve(import.meta.dirname,'../../..'),stdio:['pipe','pipe','pipe']});
    let output='',errors='';const timer=setTimeout(()=>{child.kill('SIGTERM');reject(Error('hot_test_host_timeout'));},25000);
    child.stdout.on('data',chunk=>{output+=chunk.toString();if(output.length>65536){child.kill('SIGTERM');reject(Error('hot_test_host_output_limit'));}});
    child.stderr.on('data',chunk=>{errors+=chunk.toString();if(errors.length>65536){child.kill('SIGTERM');reject(Error('hot_test_host_output_limit'));}});
    child.once('error',error=>{clearTimeout(timer);reject(error);});
    child.stdin.once('error',error=>{clearTimeout(timer);child.kill('SIGTERM');reject(error);});
    child.once('close',code=>{clearTimeout(timer);if(code!==0){reject(Error('hot_test_host_failed:'+errors.slice(-1000)));return;}try{resolveResult(JSON.parse(output));}catch{reject(Error('hot_test_host_json_invalid'));}});
    child.stdin.end(JSON.stringify(input));
  });
}

test('signed PG evidence copies old full originals, rejects foreign objects and survives content correction',{timeout:45000},async()=>{
  const dir=resolve(process.env.RWB_HOT_TEST_FIXTURE_DIR??resolve(import.meta.dirname,'../../../logs/hot-stage-zero'));
  const baseline=JSON.parse(await readFile(join(dir,'receipt.json'),'utf8'));
  const password=await readFile(join(dir,'password'),'utf8');
  const port=Number(process.env.RWB_HOT_TEST_PG_PORT??baseline.port);
  if(!Number.isInteger(port)||port<1||port>65535)throw Error('hot_test_port_invalid');
  const db=postgres({host:'127.0.0.1',port,database:'hot_probe',username:'postgres',password,onnotice:()=>{},connect_timeout:5,connection:{statement_timeout:5000}});
  const suffix=randomBytes(5).toString('hex'),schema='hot_research_'+suffix,worker='hr_worker_'+suffix,controller='hr_ctrl_'+suffix;
  const workerPassword=randomBytes(32).toString('hex'),controllerPassword=randomBytes(32).toString('hex');
  const instanceId=randomUUID(),controllerToken=randomBytes(32).toString('hex'),readerToken=randomBytes(32).toString('hex');
  let service:Awaited<ReturnType<typeof startService>>|undefined;
  let controllerDb:ReturnType<typeof postgres>|undefined;
  let modelRpc:Awaited<ReturnType<typeof startTransport>>|undefined;
  try{
    await migrate(db,schema);await initializeIdentity(db,schema,instanceId,controllerToken);
    const queue=await openQueue(db,schema,true);await queue.stop();
    for(const [role,secret] of [[worker,workerPassword],[controller,controllerPassword]])await db.unsafe(`create role "${role}" login nosuperuser nocreatedb nocreaterole password '${secret}'`);
    await grantWorker(db,schema,worker);await grantController(db,schema,controller);
    await db`insert into ${db(schema)}.sources(id,operator,config,enabled) values('official','Independent Official','{}'::jsonb,false)`;
    const now=new Date(),raw=Buffer.from('原始响应🙂\u0000'.repeat(7000)),url='https://example.com/'+randomUUID();
    // NUL is legal in bytea but not a material text; raw response deliberately tests binary fidelity.
    const item={url,title:'Original official title',excerpt:'完整正文🙂'.repeat(6000),upstreamId:null,publishedRaw:'',publishedAt:null,updatedRaw:'',sourceUpdatedAt:null};
    const stored=await ingestPage(db,{source:'official',raw:raw.toString('utf8'),acquiredAt:now,materials:[item],cursor:{}},schema);
    const initial=await activateRuntime(db,schema,instanceId,controllerToken,'native'),eventId=randomUUID();
    await saveAutomaticEvent(db,schema,initial,eventId,0,{title:'Original event',materials:[{id:stored.materialIds[0],revision:1,relation:'same_occurrence'}],links:[]});
    await configureChannel(db,schema,initial,'macro',0,{name:'Macro',topics:['official'],sourceIds:['official'],importanceRules:[]});
    const [{cutoff}]=await db`select clock_timestamp() cutoff`,briefId=randomUUID();
    await createBriefRequest(db,schema,initial,randomUUID(),{briefId,expectedVersion:0,eventIds:[eventId],channelId:'macro',cutoff:cutoff.toISOString()});
    const selection={briefId,version:1,materialIds:stored.materialIds};
    const before=await researchEvidence(db,schema,selection) as any;
    assert.equal(before.manifest.briefContext.events[0].reports[0].excerptIsPartial,true);
    assert.equal(before.manifest.objects.length,2);assert.equal(before.manifest.materials[0].revision,1);
    assert.equal(before.manifest.briefContext.events[0].reports[0].publishedAt,null);
    await assert.rejects(researchEvidence(db,schema,{...selection,materialIds:[randomUUID()]}),/material_not_selected/);
    await new Promise(resolve=>setTimeout(resolve,5));
    await ingestPage(db,{source:'official',raw:'later source response',acquiredAt:new Date(),materials:[{...item,excerpt:'Later correction'}],cursor:{}},schema);
    const after=await researchEvidence(db,schema,selection) as any;assert.equal(after.manifestHash,before.manifestHash);
    await pauseRuntime(db,schema,initial,controllerToken);
    service=await startService({config:{enabled:true,database:{mode:'external',tls:'disable',port,name:'hot_probe',schema,user:worker}},instanceId,mode:'native',workerPassword,controllerUser:controller,controllerPassword,controllerToken,readerToken});
    const read=(method:string,params:any)=>rpc(service!.port,service!.owner,readerToken,method,params) as Promise<any>;
    let manifestChunk=await read('research.evidence',selection);const manifestParts:Buffer[]=[];let manifestOffset=0;
    const manifestHash=manifestChunk.manifestHash;
    for(let i=0;i<23;i++){
      assert.equal(manifestChunk.offset,manifestOffset);assert.equal(manifestChunk.manifestHash,manifestHash);
      const part=Buffer.from(manifestChunk.dataBase64,'base64');manifestParts.push(part);manifestOffset+=part.length;
      if(manifestChunk.nextOffset===null)break;
      manifestChunk=await read('research.evidence',{...selection,offset:manifestOffset,manifestHash});
    }
    const manifestBytes=Buffer.concat(manifestParts);assert.equal(sha256(manifestBytes),manifestHash);
    const signed={manifest:JSON.parse(manifestBytes.toString('utf8')),manifestHash};assert.deepEqual(signed,before);
    await assert.rejects(read('research.evidence',{...selection,offset:1}),/offset_invalid/);
    const runId=randomUUID(),prepareId=randomUUID(),runParams={runId,...selection,targetMode:'fingpt'};
    const control=(method:string,params:any,requestId=randomUUID())=>rpc(service!.port,service!.owner,controllerToken,method,params,requestId) as Promise<any>;
    await assert.rejects(read('research.prepare',runParams),/denied/);
    let run=await control('research.prepare',runParams,prepareId);
    assert.equal(run.state,'prepared');assert.equal(run.evidenceManifestHash,signed.manifestHash);
    assert.match(run.sessionId,/^[a-f0-9-]{36}$/);const reserved=run.sessionId;
    assert.deepEqual(await control('research.prepare',runParams,prepareId),run);
    await assert.rejects(control('research.prepare',{...runParams,targetMode:'claw'},prepareId),/request_conflict/);
    const firstAdvance=randomUUID(),firstArgs={runId,expectedRevision:run.revision,state:'session_creating'};
    run=await control('research.advance',firstArgs,firstAdvance);
    assert.deepEqual(await control('research.advance',firstArgs,firstAdvance),run);
    await assert.rejects(control('research.advance',{...firstArgs,state:'session_ready'},firstAdvance),/request_conflict/);
    const advance=async(state:string,patch:any={})=>{run=await control('research.advance',{runId,expectedRevision:run.revision,state,...patch});};
    await advance('session_outcome_unknown');await advance('session_ready');
    await assert.rejects(control('research.advance',{runId,expectedRevision:run.revision,state:'snapshot_ready'}),/snapshot_required/);
    await advance('snapshot_ready',{datasetId:randomUUID(),datasetManifestHash:'a'.repeat(64)});
    await advance('execution_starting',{deliveryKey:'hot-run-'+runId});await advance('execution_outcome_unknown');
    await assert.rejects(control('research.advance',{runId,expectedRevision:run.revision,state:'execution_starting'}),/transition_invalid/);
    await advance('running');
    const price=JSON.parse(await readFile(new URL('../pricing.deepseek.2026-10-09.json',import.meta.url),'utf8'));
    const day=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
    price.verifiedOn=day;price.requestedModel='deepseek-flash';
    await provisionModelBudget(db,schema,{scopeId:'shared_goal',authorizationHash:sha256('synthetic-test-only'),maxCalls:2,maxTokens:2000,maxCostMicros:10000});
    controllerDb=postgres({host:'127.0.0.1',port,database:'hot_probe',username:controller,password:controllerPassword,onnotice:()=>{}});
    const call={runId,sessionId:run.sessionId,callId:randomUUID(),requestHash:'c'.repeat(64),provider:'deepseek-official',model:'deepseek-flash',inputTokenBound:400,maxOutputTokens:512};
    await db.unsafe(`create function "${schema}".fail_model_mapping() returns trigger language plpgsql as $$ begin raise exception 'synthetic insert interruption'; end $$`);
    await db.unsafe(`create trigger fail_model_mapping before insert on "${schema}".research_model_calls for each row execute function "${schema}".fail_model_mapping()`);
    await assert.rejects(reserveResearchModelCall(controllerDb,schema,service.owner,'shared_goal',price,day,call),/research_model_failed/);
    assert.equal((await db`select charged_calls from ${db(schema)}.model_budgets where scope_id='shared_goal'`)[0].charged_calls,0,'link failure rolls back quota and attempt atomically');
    await db.unsafe(`drop trigger fail_model_mapping on "${schema}".research_model_calls`);
    const pipeline=await reserveModel(controllerDb,schema,service.owner,'shared_goal',{resultKey:'f'.repeat(64),specHash:'f'.repeat(64),maxTokens:100,maxCostMicros:100});
    assert.equal(pipeline.state,'reserved');
    let activePrice:unknown=price;
    modelRpc=await startTransport({port:0,identity:service.owner,controllerToken,readerToken,
      handlers:new Map(researchModelHandlers(controllerDb,schema,service.owner,'shared_goal',()=>activePrice,()=>day)),guard:async()=>{}});
    const modelCall=(op:string,params:any,token=controllerToken)=>rpc(modelRpc!.port,service!.owner,token,'research.model.'+op,params) as Promise<any>;
    await assert.rejects(modelCall('reserve',call,readerToken),/denied/);
    const ticket=await modelCall('reserve',call);
    assert.equal(ticket.state,'reserved');
    const repeated=await reserveResearchModelCall(controllerDb!,schema,service.owner,'shared_goal',price,day,call);
    assert.equal(repeated.state,'busy');
    await assert.rejects(reserveResearchModelCall(controllerDb!,schema,service.owner,'shared_goal',price,day,{...call,requestHash:'d'.repeat(64)}),/request_conflict/);
    await assert.rejects(reserveResearchModelCall(controllerDb!,schema,service.owner,'shared_goal',price,day,{...call,callId:randomUUID(),sessionId:randomUUID()}),/session_invalid/);
    await assert.rejects(reserveResearchModelCall(controllerDb!,schema,service.owner,'shared_goal',price,day,{...call,callId:randomUUID()}),/budget_exhausted/);
    const [used]=await db`select charged_calls,charged_tokens::text from ${db(schema)}.model_budgets where scope_id='shared_goal'`;
    assert.equal(used.charged_calls,2);assert.equal(used.charged_tokens,'1012');
    await assert.rejects(db`update ${db(schema)}.research_model_calls set request_hash=${'d'.repeat(64)}`,/immutable_evidence/);
    if(ticket.state!=='reserved')throw Error('hot_fixture_ticket_invalid');
    const bound={runId,sessionId:run.sessionId,callId:call.callId,ticket:ticket.ticket};
    for(const op of ['dispatch','unknown','cancel','receipt'])await assert.rejects(modelCall(op,bound,readerToken),/denied/);
    await assert.rejects(modelCall('dispatch',{...bound,sessionId:randomUUID()}),/binding_denied/);
    await assert.rejects(modelCall('dispatch',{...bound,ticket:{...ticket.ticket,token:'a'.repeat(64)}}),/binding_denied/);
    activePrice={...price,outputMicrosPerMillion:2400000};
    await assert.rejects(modelCall('dispatch',bound),/model_denied/);
    activePrice=price;
    assert.equal((await modelCall('dispatch',bound)).state,'dispatching');
    await assert.rejects(modelCall('dispatch',bound),/dispatch_denied/);
    assert.equal((await modelCall('unknown',bound)).state,'outcome_unknown');
    assert.equal((await modelCall('unknown',bound)).state,'outcome_unknown');
    // Synthetic provider usage; token-fragmented output exercises a >64KiB signed receipt.
    const chunks=[...Array.from({length:1500},()=>({type:'text-delta',index:0,text:'x'})), {type:'usage',usage:{inputTokens:30,outputTokens:20,totalTokens:50}}, {type:'finish',reason:{kind:'stop'}}];
    const receipt={...bound,chunks,providerRequestId:null};
    await assert.rejects(modelCall('receipt',{...receipt,costMicros:0}),/invalid/);
    assert.equal((await modelCall('receipt',receipt)).state,'received');
    assert.equal((await modelCall('receipt',receipt)).state,'received');
    assert.equal((await modelCall('unknown',bound)).state,'received');
    await assert.rejects(modelCall('receipt',{...receipt,chunks:[{...chunks[0],text:'changed'},...chunks.slice(1)]}),/receipt_conflict/);
    activePrice=null;
    assert.equal((await modelCall('reserve',call)).state,'reused');
    activePrice=price;
    assert.equal((await reserveResearchModelCall(controllerDb,schema,service.owner,'shared_goal',price,day,call)).state,'reused');
    if(pipeline.state!=='reserved')throw Error('hot_fixture_ticket_invalid');
    await cancelUnsentModel(controllerDb,schema,service.owner,pipeline.ticket.id);
    const cancelledCall={...call,callId:randomUUID()};
    const cancelled=await reserveResearchModelCall(controllerDb,schema,service.owner,'shared_goal',price,day,cancelledCall);
    if(cancelled.state!=='reserved')throw Error('hot_fixture_ticket_invalid');
    await cancelUnsentModel(controllerDb,schema,service.owner,cancelled.ticket.id);
    await assert.rejects(reserveResearchModelCall(controllerDb,schema,service.owner,'shared_goal',price,day,cancelledCall),/attempt_changed/);
    assert.equal((await db`select charged_calls from ${db(schema)}.model_budgets where scope_id='shared_goal'`)[0].charged_calls,1);
    const racedCall={...call,callId:randomUUID()};
    const raced=await modelCall('reserve',racedCall);assert.equal(raced.state,'reserved');
    let reached!:()=>void,release!:()=>void;
    const beforeFence=new Promise<void>(resolve=>{reached=resolve;}),resumeFence=new Promise<void>(resolve=>{release=resolve;});
    const delayed=new Proxy(controllerDb,{get(target,key,receiver){if(key!=='begin')return Reflect.get(target,key,receiver);return async(fn:any)=>{reached();await resumeFence;return target.begin(fn);};}});
    const handler=new Map(researchModelHandlers(delayed,schema,service.owner,'shared_goal',()=>price,()=>day)).get('research.model.dispatch')!;
    const racedBound={runId,sessionId:run.sessionId,callId:racedCall.callId,ticket:raced.ticket};
    const dispatching=handler.run(racedBound,randomUUID(),new AbortController().signal);
    await beforeFence;await advance('completed');release();
    await assert.rejects(dispatching,/model_denied/,'terminal transition before the owner fence forbids dispatch');
    assert.equal((await db`select state from ${db(schema)}.model_attempts where id=${raced.ticket.id}`)[0].state,'reserved');
    await modelCall('cancel',racedBound);
    assert.equal((await reserveResearchModelCall(controllerDb,schema,service.owner,'shared_goal',undefined,'2026-10-13',call)).state,'reused','saved result replays in terminal run across dates without current pricing or new admission');
    await assert.rejects(reserveResearchModelCall(controllerDb!,schema,service.owner,'shared_goal',price,day,{...call,callId:randomUUID()}),/execution_not_active/);
    assert.equal((await read('research.run',{runId})).sessionId,reserved);
    const workerDb=postgres({host:'127.0.0.1',port,database:'hot_probe',username:worker,password:workerPassword,onnotice:()=>{}});
    await assert.rejects(reserveResearchModelCall(workerDb,schema,service.owner,'shared_goal',price,day,{...call,callId:randomUUID()}),/control_denied/);
    try{await assert.rejects(workerDb`update ${workerDb(schema)}.research_runs set state='prepared' where id=${runId}`,/permission denied/);}finally{await workerDb.end({timeout:5});}
    await assert.rejects(db`update ${db(schema)}.research_inputs set session_id=${randomUUID()} where id=${runId}`,/immutable_evidence/);
    if(process.env.RWB_HOT_TEST_PYTHON){
      const host=await hostRead(process.env.RWB_HOT_TEST_PYTHON,{...selection,port:service.port,owner:service.owner,readerToken,controllerToken});
      assert.equal(host.manifestHash,signed.manifestHash);
      for(const object of signed.manifest.objects)assert.deepEqual(host.objects[object.key],{bytes:object.bytes,hash:object.contentHash});
      assert.equal(host.docx.status,200);assert.equal(host.docx.retained,true);assert.equal(host.docx.parsed,true);
      assert.equal(host.handoff.state,'snapshot_ready');assert.equal(host.handoff.nativeCreations,1);assert.equal(host.handoff.snapshotCount,1);assert.equal(host.handoff.executionStarted,false);
    }
    for(const object of signed.manifest.objects){
      let offset=0;const parts:Buffer[]=[];
      for(let i=0;i<300;i++){
        const chunk=await read('research.original',{...selection,objectKey:object.key,manifestHash:signed.manifestHash,offset});
        assert.equal(chunk.offset,offset);assert.equal(chunk.contentHash,object.contentHash);
        const bytes=Buffer.from(chunk.dataBase64,'base64');parts.push(bytes);offset+=bytes.length;
        if(chunk.nextOffset===null)break;assert.equal(chunk.nextOffset,offset);
      }
      const bytes=Buffer.concat(parts);assert.equal(bytes.length,object.bytes);assert.equal(sha256(bytes),object.contentHash);
      if(object.key.startsWith('raw:'))assert.deepEqual(bytes,raw);
      else {const full=JSON.parse(bytes.toString());assert.equal(full.excerpt,item.excerpt);assert.equal(full.publishedAt,null);assert.equal(full.revision,1);}
    }
    await assert.rejects(read('research.original',{...selection,objectKey:'raw:'+randomUUID(),manifestHash:signed.manifestHash,offset:0}),/not_selected/);
    await assert.rejects(read('research.original',{...selection,objectKey:signed.manifest.objects[0].key,manifestHash:'0'.repeat(64),offset:0}),/manifest_changed/);
    await assert.rejects(rpc(service.port,{...service.owner,generation:String(Number(service.owner.generation)+1)},readerToken,'research.evidence',selection),/untrusted|owner_stale|identity|scope/);
    await assert.rejects(db`update ${db(schema)}.raw_pages set body=${Buffer.from('tampered')} where source_id='official'`,/immutable_evidence/);
  }finally{
    if(modelRpc)await modelRpc.close();
    if(controllerDb)await controllerDb.end({timeout:5});
    if(service)await service.close();
    await db.unsafe(`drop schema if exists "${schema}" cascade`);
    for(const role of [worker,controller])await db.unsafe(`drop role if exists "${role}"`);
    await db.end({timeout:5});
  }
});
