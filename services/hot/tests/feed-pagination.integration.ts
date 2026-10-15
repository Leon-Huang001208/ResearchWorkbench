import {test} from 'node:test';import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';import{resolve,join}from'node:path';import{randomBytes,randomUUID}from'node:crypto';
import postgres from 'postgres';import{migrate}from'../src/database.ts';import{initializeIdentity,activateRuntime,pauseRuntime,claimTask,withOwnerTransaction}from'../src/control.ts';
import{seedPublicSources,scheduleCollection,collectionHandlers}from'../src/collection.ts';import{grantWorker}from'../src/provision.ts';import{openQueue,processOne}from'../src/queue.ts';import{parseConfig}from'../src/config.ts';import{sha256}from'../src/material.ts';
test('partial network failure preserves first raw/inbox without watermark; retry drains two ordered pages and reuses material versions',{timeout:20000},async()=>{
 const dir=resolve(process.env.RWB_HOT_PROOF_DIR??new URL('../../../logs/hot-stage-zero',import.meta.url).pathname),proof=JSON.parse(await readFile(join(dir,'receipt.json'),'utf8')),password=await readFile(join(dir,'password'),'utf8');
 const port=Number(process.env.RWB_HOT_PROOF_PORT??proof.port);assert.ok(Number.isSafeInteger(port)&&port>0&&port<65536);
 const options={host:'127.0.0.1',port,database:'hot_probe',onnotice:()=>{}},db=postgres({...options,username:'postgres',password}),suffix=randomBytes(5).toString('hex'),schema='hot_pages_'+suffix,role='hot_pw_'+suffix,instance=randomUUID(),token=randomBytes(32).toString('hex');
 let ordinary:ReturnType<typeof postgres>|undefined,boss:Awaited<ReturnType<typeof openQueue>>|undefined,initialized=false,createdRole=false;
 try{
  await migrate(db,schema);await initializeIdentity(db,schema,instance,token);initialized=true;boss=await openQueue(db,schema,true);await seedPublicSources(db,schema);
  await db`update ${db(schema)}.sources set enabled=(id='fed')`;
  const key=randomBytes(32).toString('hex');await db.unsafe(`create role "${role}" login nosuperuser nocreatedb nocreaterole password '${key}'`);createdRole=true;
  await grantWorker(db,schema,role);ordinary=postgres({...options,username:role,password:key});await boss.stop();boss=await openQueue(ordinary,schema);
  const owner=await activateRuntime(db,schema,instance,token,'native'),config=parseConfig({enabled:true,collection:{maxItems:1}});
  const first='<feed><link rel="next" href="/page2"/><entry><title>First</title><link href="https://www.federalreserve.gov/article1"/></entry></feed>',second='<feed><entry><title>Second</title><link href="https://www.federalreserve.gov/article2"/></entry></feed>';
  let fail=true;const calls:string[]=[];const handlers=collectionHandlers(ordinary,boss,schema,owner,config,async url=>{calls.push(String(url));return new Response(String(url).endsWith('/page2')?(fail?'':second):first,{status:String(url).endsWith('/page2')&&fail?503:200});});
  assert.equal(await scheduleCollection(ordinary,boss,schema,owner,config),1);assert.equal(await processOne(boss,ordinary,schema,owner,'hot.collect',handlers['hot.collect']),'completed');
  const [failed]=await db`select last_success_at,last_error_code from ${db(schema)}.sources where id='fed'`;assert.equal(failed.last_success_at,null);assert.equal(failed.last_error_code,'hot_source_http_failed');
  const [raw]=await db`select body,body_hash,gap from ${db(schema)}.raw_pages`;assert.equal(raw.body.toString(),first);assert.equal(raw.body_hash,sha256(first));assert.equal(raw.gap.code,'hot_source_http_failed');
  assert.equal(await processOne(boss,ordinary,schema,owner,'hot.parse',handlers['hot.parse']),'completed');assert.equal((await db`select last_success_at,last_error_code from ${db(schema)}.sources where id='fed'`)[0].last_error_code,'hot_source_http_failed');
  assert.equal((await db`select last_success_at from ${db(schema)}.sources where id='fed'`)[0].last_success_at,null);
  fail=false;await db`update ${db(schema)}.sources set next_due_at=null where id='fed'`;assert.equal(await scheduleCollection(ordinary,boss,schema,owner,config),1);
  assert.equal(await processOne(boss,ordinary,schema,owner,'hot.collect',handlers['hot.collect']),'completed');
  const [before]=await db`select last_success_at,cursor from ${db(schema)}.sources where id='fed'`;assert.equal(before.cursor.pageIds.length,2);
  for(let index=0;index<2;index++)assert.equal(await processOne(boss,ordinary,schema,owner,'hot.parse',handlers['hot.parse']),'completed');
  assert.equal((await db`select count(*)::int n from ${db(schema)}.material_versions`)[0].n,2);assert.equal((await db`select count(*)::int n from ${db(schema)}.material_inbox where not processed`)[0].n,0);
  const [after]=await db`select last_success_at,cursor from ${db(schema)}.sources where id='fed'`;assert.equal(after.last_success_at.toISOString(),before.last_success_at.toISOString());assert.equal(after.cursor.stage,'parsed');assert.equal(after.cursor.pageIds.length,2);assert.equal(calls.length,4);
  const granted=await claimTask(ordinary,schema,owner,randomUUID(),'hot.collect:fed:999',randomUUID());assert.equal(granted.state,'claimed');if(granted.state!=='claimed')throw Error('hot_fixture_claim_failed');
  const output=await handlers['hot.collect']({sourceId:'fed',sequence:'999'},new AbortController().signal,granted.claim);
  const [count]=await db`select count(*)::int n from ${db(schema)}.raw_pages`;
  await assert.rejects(withOwnerTransaction(ordinary,schema,owner,async tx=>{await output.commit!(tx);throw Error('test_interruption');}),/test_interruption/);
  assert.equal((await db`select count(*)::int n from ${db(schema)}.raw_pages`)[0].n,count.n);
  assert.deepEqual((await db`select last_success_at,cursor from ${db(schema)}.sources where id='fed'`)[0],after);
  await pauseRuntime(db,schema,owner,token);
 }finally{
  await boss?.stop();await ordinary?.end({timeout:5});
  try{if(initialized){const [identity]=await db`select instance_id,controller_token_hash from ${db(schema)}.runtime_identity where singleton`;assert.equal(identity.instance_id,instance);assert.equal(identity.controller_token_hash,sha256(token));await db.unsafe(`drop schema "${schema}" cascade`);}if(createdRole)await db.unsafe(`drop role "${role}"`);}
  finally{await db.end({timeout:5});}
 }
});
