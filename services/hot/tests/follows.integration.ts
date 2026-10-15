import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {randomBytes,randomUUID} from 'node:crypto';
import postgres from 'postgres';
import {migrate,ingestPage} from '../src/database.ts';
import {initializeIdentity,activateRuntime,pauseRuntime} from '../src/control.ts';
import {configureChannel,saveAutomaticEvent,correctEvent,eventAt} from '../src/events.ts';
import {configureFollow,readFollows} from '../src/follows.ts';
import {openQueue} from '../src/queue.ts';
import {grantWorker,grantController} from '../src/provision.ts';
import {sha256} from '../src/material.ts';

test('PG follows retain revisions/audit/replay across restart, respect event aliases and reject worker writes',{timeout:20000},async()=>{
  const dir=process.env.RWB_HOT_PROOF_DIR?resolve(process.env.RWB_HOT_PROOF_DIR):resolve(import.meta.dirname,'../../../logs/hot-stage-zero');
  const receipt=JSON.parse(await readFile(join(dir,'receipt.json'),'utf8')),password=await readFile(join(dir,'password'),'utf8');
  const port=process.env.RWB_HOT_PROOF_PORT?Number(process.env.RWB_HOT_PROOF_PORT):receipt.port;
  assert.ok(Number.isSafeInteger(port)&&port>0&&port<65536);
  const db=postgres({host:'127.0.0.1',port,database:'hot_probe',username:'postgres',password,onnotice:()=>{}});
  const schema='hot_follows_'+randomBytes(5).toString('hex'),role=schema+'_worker',controllerRole=schema+'_control',rolePassword=randomBytes(32).toString('hex');
  const token=randomBytes(32).toString('hex'),instance=randomUUID();let worker,controller;
  let provisioned=false;const createdRoles:string[]=[];
  try{
    await migrate(db,schema);await initializeIdentity(db,schema,instance,token);provisioned=true;
    const boss=await openQueue(db,schema,true);await boss.stop();
    await db.unsafe(`create role "${role}" login password '${rolePassword}'`);createdRoles.push(role);
    await db.unsafe(`create role "${controllerRole}" login password '${rolePassword}'`);createdRoles.push(controllerRole);
    await grantWorker(db,schema,role);await grantController(db,schema,controllerRole);
    let owner=await activateRuntime(db,schema,instance,token,'native');
    await configureChannel(db,schema,owner,'macro',0,{name:'Macro',topics:[],sourceIds:[],importanceRules:[],rules:[]});
    const followId=randomUUID(),requestId=randomUUID(),params={followId,expectedVersion:0,config:{kind:'channel',target:'macro',name:'Macro watch',enabled:true},reason:'policy follow'};
    const saved=await configureFollow(db,schema,owner,requestId,params);
    assert.deepEqual(await configureFollow(db,schema,owner,requestId,params),saved);
    await assert.rejects(configureFollow(db,schema,owner,requestId,{...params,reason:'changed'}),/hot_follow_request_conflict/);
    await assert.rejects(configureFollow(db,schema,owner,randomUUID(),{...params,followId:randomUUID()}),/hot_follow_target_conflict/);
    const paused=await configureFollow(db,schema,owner,randomUUID(),{...params,expectedVersion:1,config:{...params.config,enabled:false},reason:'paused'});
    assert.equal(JSON.parse(JSON.stringify(paused)).version,2);
    await assert.rejects(configureFollow(db,schema,owner,randomUUID(),{...params,reason:'stale'}),/hot_follow_version_conflict/);
    await pauseRuntime(db,schema,owner,token);const stale=owner;owner=await activateRuntime(db,schema,instance,token,'native');
    await assert.rejects(configureFollow(db,schema,stale,randomUUID(),{...params,expectedVersion:2}),/hot_owner_stale/);
    const list=JSON.parse(JSON.stringify(await readFollows(db,schema,{})));assert.equal(list.items[0].config.enabled,false);assert.equal(list.items[0].version,2);
    assert.deepEqual(await configureFollow(db,schema,owner,requestId,params),saved);
    await db`insert into ${db(schema)}.sources(id,operator,config) values('source','Synthetic operator','{}'::jsonb)`;
    const now=new Date();const page=await ingestPage(db,{source:'source',raw:'synthetic follow alias fixture',acquiredAt:now,materials:[{url:'https://example.test/'+randomUUID(),title:'Policy',excerpt:'Policy statement',upstreamId:null,publishedRaw:now.toISOString(),publishedAt:now,updatedRaw:'',sourceUpdatedAt:null}],cursor:{}},schema);
    const oldEvent=randomUUID(),currentEvent=randomUUID();const proposal={title:'Policy',materials:[{id:page.materialIds[0],revision:1,relation:'same_occurrence' as const}],links:[]};
    await saveAutomaticEvent(db,schema,owner,oldEvent,0,proposal);await saveAutomaticEvent(db,schema,owner,currentEvent,0,proposal);
    await configureFollow(db,schema,owner,randomUUID(),{followId:randomUUID(),expectedVersion:0,config:{kind:'event',target:oldEvent,name:'Policy follow',enabled:true},reason:'track'});
    await correctEvent(db,schema,owner,randomUUID(),'duplicate',{type:'merge',id:oldEvent,expected:1,target:currentEvent,targetExpected:1});
    assert.equal((await eventAt(db,schema,oldEvent,new Date()))?.id,currentEvent);
    assert.ok(JSON.parse(JSON.stringify(await readFollows(db,schema,{}))).items.some((row:any)=>row.config.target===oldEvent));
    const audit=await db`select actor,reason,before_state,after_state from ${db(schema)}.follow_requests order by created_at`;assert.equal(audit.length,3);assert.equal(audit[1].before_state.version,1);assert.equal(audit[1].after_state.version,2);
    await assert.rejects(db`update ${db(schema)}.follow_versions set config='{}'::jsonb`,/hot_immutable_evidence/);
    worker=postgres({host:'127.0.0.1',port,database:'hot_probe',username:role,password:rolePassword,onnotice:()=>{}});
    assert.equal(JSON.parse(JSON.stringify(await readFollows(worker,schema,{}))).items.length,2);
    await assert.rejects(configureFollow(worker,schema,owner,randomUUID(),{...params,expectedVersion:2}),/hot_follow_control_denied/);
    controller=postgres({host:'127.0.0.1',port,database:'hot_probe',username:controllerRole,password:rolePassword,onnotice:()=>{}});
    const enabled=await configureFollow(controller,schema,owner,randomUUID(),{...params,expectedVersion:2,reason:'controller scoped role enables'});
    assert.equal(JSON.parse(JSON.stringify(enabled)).version,3);
    assert.ok(JSON.parse(JSON.stringify(await readFollows(worker,schema,{}))).items.some((row:any)=>row.followId===followId&&row.version===3&&row.config.enabled));
    const [{count}]=await db`select count(*)::int count from ${db(schema)}.model_attempts`;assert.equal(count,0);
    await pauseRuntime(db,schema,owner,token);
  }finally{
    await worker?.end({timeout:5});await controller?.end({timeout:5});
    try{
      if(provisioned){
        const [identity]=await db`select instance_id,controller_token_hash from ${db(schema)}.runtime_identity where singleton`;
        assert.equal(identity.instance_id,instance);assert.equal(identity.controller_token_hash,sha256(token));
        await db.unsafe(`drop schema "${schema}" cascade`);
        for(const ownedRole of createdRoles)await db.unsafe(`drop role "${ownedRole}"`);
      }
    }finally{await db.end({timeout:5});}
  }
});
