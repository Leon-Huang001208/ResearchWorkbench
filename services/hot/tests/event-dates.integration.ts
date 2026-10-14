import {test} from 'node:test';import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';import{resolve,join}from'node:path';import{randomBytes,randomUUID}from'node:crypto';
import postgres from 'postgres';import{migrate,ingestPage}from'../src/database.ts';import{initializeIdentity,activateRuntime,pauseRuntime,claimTask,withOwnerTransaction}from'../src/control.ts';
import{saveAutomaticEvent,correctEvent,eventAt}from'../src/events.ts';
import{seedPublicSources,scheduleCollection,collectionHandlers}from'../src/collection.ts';import{grantWorker}from'../src/provision.ts';import{openQueue,processOne}from'../src/queue.ts';import{parseConfig}from'../src/config.ts';import{sha256}from'../src/material.ts';
test('date source evidence is immutable, scoped, audited and preserved on automatic rerun',{timeout:20000},async()=>{
 const dir=resolve(process.env.RWB_HOT_PROOF_DIR??new URL('../../../logs/hot-stage-zero',import.meta.url).pathname),proof=JSON.parse(await readFile(join(dir,'receipt.json'),'utf8')),password=await readFile(join(dir,'password'),'utf8');
 const port=Number(process.env.RWB_HOT_PROOF_PORT??proof.port);assert.ok(Number.isSafeInteger(port)&&port>0&&port<65536);
 const options={host:'127.0.0.1',port,database:'hot_probe',onnotice:()=>{}},db=postgres({...options,username:'postgres',password}),suffix=randomBytes(5).toString('hex'),schema='hot_pages_'+suffix,role='hot_pw_'+suffix,instance=randomUUID(),token=randomBytes(32).toString('hex');
 let ordinary:ReturnType<typeof postgres>|undefined,boss:Awaited<ReturnType<typeof openQueue>>|undefined,initialized=false,createdRole=false;
 try{
  await migrate(db,schema);await initializeIdentity(db,schema,instance,token);initialized=true;boss=await openQueue(db,schema,true);await seedPublicSources(db,schema);
  await db`update ${db(schema)}.sources set enabled=(id='fed')`;
  const key=randomBytes(32).toString('hex');await db.unsafe(`create role "${role}" login nosuperuser nocreatedb nocreaterole password '${key}'`);createdRole=true;
  await grantWorker(db,schema,role);ordinary=postgres({...options,username:role,password:key});await boss.stop();boss=await openQueue(ordinary,schema);
  const owner=await activateRuntime(db,schema,instance,token,'native');
  const now=new Date(),quote='The policy announced on 17 February takes effect on 17 March 2026.';
  const stored=await ingestPage(db,{source:'fed',raw:quote,acquiredAt:now,materials:[{url:'https://www.federalreserve.gov/date-fixture',title:'Test policy',excerpt:quote,upstreamId:null,publishedRaw:'2026-02-17T12:00:00Z',publishedAt:new Date('2026-02-17T12:00:00Z'),updatedRaw:'',sourceUpdatedAt:null}],cursor:{}},schema);
  const ref={id:stored.materialIds[0],revision:1,relation:'same_occurrence' as const},id=randomUUID();
  await saveAutomaticEvent(ordinary,schema,owner,id,0,{title:'Test policy',materials:[ref],links:[]});
  const [{cutoff}]=await db`select clock_timestamp() cutoff`;
  const claim={value:'2026-03-17',precision:'day' as const,timezone:'Europe/London',evidence:{id:ref.id,revision:1,quote}};
  const change={type:'times' as const,id,expected:1,occurred:null,effective:claim},request=randomUUID();
  await assert.rejects(correctEvent(ordinary,schema,owner,request,'Test source review',change),/control_denied/);
  const first=await correctEvent(db,schema,owner,request,'Test source review',change) as any;assert.equal(first.source.snapshot.effectiveAt,'2026-03-17');
  assert.deepEqual(await correctEvent(db,schema,owner,request,'Test source review',change),first);
  assert.equal((await eventAt(db,schema,id,cutoff))!.snapshot.effectiveAt,null);
  const automatic=await saveAutomaticEvent(ordinary,schema,owner,id,2,{title:'Test policy',materials:[ref],links:[]});assert.deepEqual(automatic.snapshot.dateEvidence?.effective,claim);assert.equal(automatic.snapshot.manual.times,true);
  await assert.rejects(saveAutomaticEvent(ordinary,schema,owner,id,3,{title:'Test policy',materials:[],links:[]}),/time_evidence_invalid/);
  await assert.rejects(correctEvent(db,schema,owner,randomUUID(),'Test source review',{...change,expected:3,effective:{...claim,evidence:{...claim.evidence,quote:'not in the source'}}}),/time_evidence_invalid/);
  assert.equal((await db`select current_revision from ${db(schema)}.events where id=${id}`)[0].current_revision,3);
  assert.equal((await db`select count(*)::int n from ${db(schema)}.event_corrections`)[0].n,1);
  const cleared=await correctEvent(db,schema,owner,randomUUID(),'Withdraw unsupported date',{...change,expected:3,effective:null}) as any;assert.equal(cleared.source.snapshot.effectiveAt,null);
  assert.equal((await eventAt(db,schema,id,new Date(Date.now()+1000)))!.snapshot.effectiveAt,null);
  const unlocked=await saveAutomaticEvent(ordinary,schema,owner,id,4,{title:'Test policy',materials:[],links:[]});assert.equal(unlocked.revision,5);assert.equal(unlocked.snapshot.effectiveAt,null);
  await pauseRuntime(db,schema,owner,token);
 }finally{
  await boss?.stop();await ordinary?.end({timeout:5});
  try{if(initialized){const [identity]=await db`select instance_id,controller_token_hash from ${db(schema)}.runtime_identity where singleton`;assert.equal(identity.instance_id,instance);assert.equal(identity.controller_token_hash,sha256(token));await db.unsafe(`drop schema "${schema}" cascade`);}if(createdRole)await db.unsafe(`drop role "${role}"`);}
  finally{await db.end({timeout:5});}
 }
});
