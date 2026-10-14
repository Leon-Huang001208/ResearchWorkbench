import {test} from 'node:test';import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';import{resolve,join}from'node:path';import{randomBytes,randomUUID}from'node:crypto';
import postgres from 'postgres';import{migrate,ingestPage}from'../src/database.ts';import{initializeIdentity,activateRuntime,pauseRuntime}from'../src/control.ts';
import{seedPublicSources,scheduleCollection}from'../src/collection.ts';import{configureSource}from'../src/source-control.ts';import{grantWorker,grantController}from'../src/provision.ts';import{openQueue}from'../src/queue.ts';import{parseConfig}from'../src/config.ts';import{sha256}from'../src/material.ts';
test('explicit catalog activation preserves old evidence, audits/replays and becomes schedulable only under controller ownership',{timeout:20000},async()=>{
 const dir=resolve(process.env.RWB_HOT_PROOF_DIR??new URL('../../../logs/hot-stage-zero',import.meta.url).pathname),proof=JSON.parse(await readFile(join(dir,'receipt.json'),'utf8')),password=await readFile(join(dir,'password'),'utf8');
 const port=Number(process.env.RWB_HOT_PROOF_PORT??proof.port);assert.ok(Number.isSafeInteger(port)&&port>0&&port<65536);
 const options={host:'127.0.0.1',port,database:'hot_probe',onnotice:()=>{}},db=postgres({...options,username:'postgres',password}),suffix=randomBytes(5).toString('hex'),schema='hot_catalog_'+suffix,worker='hot_cw_'+suffix,control='hot_cc_'+suffix,instance=randomUUID(),token=randomBytes(32).toString('hex');
 let ordinary:ReturnType<typeof postgres>|undefined,controller:ReturnType<typeof postgres>|undefined,boss:Awaited<ReturnType<typeof openQueue>>|undefined,initialized=false;const roles:string[]=[];
 try{
  await migrate(db,schema);await initializeIdentity(db,schema,instance,token);initialized=true;boss=await openQueue(db,schema,true);await seedPublicSources(db,schema);
  await db`update ${db(schema)}.sources set enabled=(id='fed'),config=jsonb_build_object('adapter','frozen_acceptance_subset','originalMarker','preserved','largeMarker',9007199254740993::bigint),next_due_at=null where id='fed'`;
  await db`update ${db(schema)}.sources set enabled=false where id<>'fed'`;
  const workerPassword=randomBytes(32).toString('hex'),controlPassword=randomBytes(32).toString('hex');
  for(const [role,key] of [[worker,workerPassword],[control,controlPassword]]){await db.unsafe(`create role "${role}" login nosuperuser nocreatedb nocreaterole password '${key}'`);roles.push(role);}
  await grantWorker(db,schema,worker);await grantController(db,schema,control);ordinary=postgres({...options,username:worker,password:workerPassword});controller=postgres({...options,username:control,password:controlPassword});await boss.stop();boss=await openQueue(ordinary,schema);
  const owner=await activateRuntime(controller,schema,instance,token,'native'),config=parseConfig({enabled:true});
  const now=new Date();await ingestPage(db,{source:'fed',raw:'original frozen bytes',acquiredAt:now,materials:[{url:'https://www.federalreserve.gov/example',title:'Original frozen material',excerpt:'Original frozen material',upstreamId:null,publishedRaw:now.toISOString(),publishedAt:now,updatedRaw:'',sourceUpdatedAt:null}],cursor:{}},schema);
  const originals=await db`select to_jsonb(v) row from ${db(schema)}.material_versions v`;
  assert.equal(await scheduleCollection(ordinary,boss,schema,owner,config),0);
  const params={sourceId:'fed',expectedRevision:'0',useCatalog:true,reason:'Explicit continuation of verified public feed'},id=randomUUID();
  await assert.rejects(configureSource(ordinary,schema,owner,id,params));
  const first=await configureSource(controller,schema,owner,id,params) as any;assert.equal(first.catalogActivation.adapter,'public_feed');assert.equal(first.revision,'1');
  assert.deepEqual(await configureSource(controller,schema,owner,id,params),first);
  assert.deepEqual(await configureSource(controller,schema,owner,id,params,600,async()=>{throw Error('catalog unavailable');}),first);
  const [row]=await db`select config,config::text config_text,config->>'largeMarker' marker from ${db(schema)}.sources where id='fed'`;assert.equal(row.config.originalMarker,'preserved');assert.equal(row.config.catalogId,'fed');assert.equal(row.marker,'9007199254740993');
  assert.equal(first.catalogActivation.configSha256,sha256(row.config_text));
  assert.deepEqual(await db`select to_jsonb(v) row from ${db(schema)}.material_versions v`,originals);
  assert.equal((await db`select count(*)::int n from ${db(schema)}.source_control_requests`)[0].n,1);
  await assert.rejects(configureSource(controller,schema,owner,id,{...params,reason:'different'}),/request_conflict/);
  await assert.rejects(configureSource(controller,schema,owner,randomUUID(),params),/revision_conflict/);
  assert.equal(await scheduleCollection(ordinary,boss,schema,owner,config),1);
  await db`update ${db(schema)}.sources set operator='foreign' where id='openai'`;
  await assert.rejects(configureSource(controller,schema,owner,randomUUID(),{...params,sourceId:'openai'}),/config_invalid/);
  await pauseRuntime(controller,schema,owner,token);
  await assert.rejects(configureSource(controller,schema,owner,randomUUID(),{...params,expectedRevision:'1'}),/owner_stale/);
  assert.equal((await db`select count(*)::int n from ${db(schema)}.model_attempts`)[0].n,0);
 }finally{
  await boss?.stop();await ordinary?.end({timeout:5});await controller?.end({timeout:5});
  try{if(initialized){const [identity]=await db`select instance_id,controller_token_hash from ${db(schema)}.runtime_identity where singleton`;assert.equal(identity.instance_id,instance);assert.equal(identity.controller_token_hash,sha256(token));await db.unsafe(`drop schema "${schema}" cascade`);}for(const role of roles)await db.unsafe(`drop role "${role}"`);}
  finally{await db.end({timeout:5});}
 }
});
