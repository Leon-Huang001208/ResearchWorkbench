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
import {rpc} from '../src/transport.ts';
import {spawn} from 'node:child_process';

async function hostRead(python:string,input:Record<string,unknown>){
  const script=`import sys,json,hashlib
from pathlib import Path
from unittest.mock import patch
from research_workbench_entrypoint.hot_manager import HotManager
from app.research_web.hot_service import HotWebService
from app.research_web.hot_routes import router
from fastapi import FastAPI
from fastapi.testclient import TestClient
from docx import Document
import tempfile,asyncio,io
from contextlib import redirect_stdout
p=json.load(sys.stdin)
with redirect_stdout(sys.stderr),tempfile.TemporaryDirectory() as temp:
 m=HotManager(Path.cwd(),Path(temp).resolve(),object())
 with patch.object(m,"_state",return_value={"port":p["port"],"owner":p["owner"]}),patch.object(m,"_secret",return_value=p["readerToken"]):
  value=m.research_evidence(p["briefId"],1,p["materialIds"])
  bridge=HotWebService(Path.cwd(),m.home,manager_factory=lambda:m)
  app=FastAPI();app.include_router(router);app.state.hot=bridge
  with TestClient(app) as client:
   response=client.get("/api/research/hot/briefs/"+p["briefId"]+"/docx?version=1")
   assert response.status_code==200
   text="\\n".join(paragraph.text for paragraph in Document(io.BytesIO(response.content)).paragraphs)
   assert value["manifest"]["briefContentHash"] in text
   files=list((m.home/"hot"/"brief-artifacts").glob("*.docx"))
   assert len(files)==1 and files[0].read_bytes()==response.content
   docx={"status":response.status_code,"bytes":len(response.content),"retained":True,"parsed":True}
  asyncio.run(bridge.close())
print(json.dumps({"manifestHash":value["manifestHash"],"objects":{k:{"bytes":len(v),"hash":hashlib.sha256(v).hexdigest()} for k,v in value["objects"].items()},"docx":docx}))`;
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
    if(process.env.RWB_HOT_TEST_PYTHON){
      const host=await hostRead(process.env.RWB_HOT_TEST_PYTHON,{...selection,port:service.port,owner:service.owner,readerToken});
      assert.equal(host.manifestHash,signed.manifestHash);
      for(const object of signed.manifest.objects)assert.deepEqual(host.objects[object.key],{bytes:object.bytes,hash:object.contentHash});
      assert.equal(host.docx.status,200);assert.equal(host.docx.retained,true);assert.equal(host.docx.parsed,true);
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
    if(service)await service.close();
    await db.unsafe(`drop schema if exists "${schema}" cascade`);
    for(const role of [worker,controller])await db.unsafe(`drop role if exists "${role}"`);
    await db.end({timeout:5});
  }
});
