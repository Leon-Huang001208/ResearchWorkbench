import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {randomBytes,randomUUID} from 'node:crypto';
import postgres from 'postgres';
import {migrate} from '../src/database.ts';
import {initializeIdentity,activateRuntime,pauseRuntime,withOwnerTransaction,claimTask} from '../src/control.ts';
import {openQueue,processOne} from '../src/queue.ts';
import {parseConfig} from '../src/config.ts';
import {collectionHandlers,scheduleCollection,seedPublicSources,acquireFeed,publicSources} from '../src/collection.ts';
import {grantWorker} from '../src/provision.ts';

test('durable inbox drains bounded batches, reuses versions and retains invalid raw without watermark',{timeout:20000},async()=>{
  const dir=resolve(import.meta.dirname,'../../../logs/hot-stage-zero');
  const receipt=JSON.parse(await readFile(join(dir,'receipt.json'),'utf8'));
  const password=await readFile(join(dir,'password'),'utf8');
  const db=postgres({host:'127.0.0.1',port:receipt.port,database:'hot_probe',username:'postgres',password,onnotice:()=>{}});
  const schema='hot_collect_'+randomBytes(5).toString('hex');
  let boss:Awaited<ReturnType<typeof openQueue>>|undefined;
  let workDb:ReturnType<typeof postgres>|undefined;
  try{
    await migrate(db,schema);const instance=randomUUID(),token=randomBytes(32).toString('hex');
    await initializeIdentity(db,schema,instance,token);boss=await openQueue(db,schema,true);
    await seedPublicSources(db,schema);await db`update ${db(schema)}.sources set enabled=(id='fed')`;
    const role='hot_collect_worker_'+randomBytes(5).toString('hex'),secret=randomBytes(32).toString('hex');
    try{await db.unsafe(`create role "${role}" login nosuperuser nocreatedb nocreaterole password '${secret}'`);}catch{throw Error('hot_fixture_role_failed');}
    await grantWorker(db,schema,role);
    workDb=postgres({host:'127.0.0.1',port:receipt.port,database:'hot_probe',username:role,password:secret,onnotice:()=>{}});
    await boss.stop();boss=await openQueue(workDb,schema);
    const owner=await activateRuntime(db,schema,instance,token,'native');
    const config=parseConfig({enabled:true,collection:{maxItems:3}});
    const raw=await readFile(join(dir,'fed.xml'),'utf8');
    let response=raw,calls=0;
    const fetcher:typeof fetch=async()=>{calls++;return new Response(response,{status:200});};
    const handlers=collectionHandlers(workDb,boss,schema,owner,config,fetcher);
    assert.equal(await scheduleCollection(workDb,boss,schema,owner,config),1);
    await db`update ${db(schema)}.sources set next_due_at=null where id='fed'`;
    assert.equal(await scheduleCollection(workDb,boss,schema,owner,config),0); // Queued collect blocks a new cycle even if overdue.
    assert.equal(await processOne(boss,workDb,schema,owner,'hot.collect',handlers['hot.collect']),'completed');
    const [pending]=await db`select count(*)::int n from ${db(schema)}.material_inbox where not processed`;
    assert.ok(pending.n>3);
    await db`update ${db(schema)}.sources set next_due_at=clock_timestamp()-interval '1 minute' where id='fed'`;
    assert.equal(await scheduleCollection(db,boss,schema,owner,config),0); // Pending entries block refetch.
    let previous=pending.n;
    for(let index=0;index<20;index++){
      const state=await processOne(boss,workDb,schema,owner,'hot.parse',handlers['hot.parse']);
      const [{n}]=await db`select count(*)::int n from ${db(schema)}.material_inbox where not processed`;
      assert.ok(previous-n<=3);previous=n;if(n===0)break;assert.equal(state,'completed');
    }
    assert.equal(previous,0);assert.equal(calls,1);
    assert.equal((await db`select count(*)::int n from ${db(schema)}.raw_pages`)[0].n,1);
    const [versions]=await db`select count(*)::int n from ${db(schema)}.material_versions`;
    assert.equal(versions.n,pending.n);
    assert.equal(await scheduleCollection(db,boss,schema,owner,config),1);
    await processOne(boss,workDb,schema,owner,'hot.collect',handlers['hot.collect']);
    for(let index=0;index<20;index++){await processOne(boss,workDb,schema,owner,'hot.parse',handlers['hot.parse']);
      if((await db`select count(*)::int n from ${db(schema)}.material_inbox where not processed`)[0].n===0)break;}
    assert.equal((await db`select count(*)::int n from ${db(schema)}.material_versions`)[0].n,versions.n);
    const [before]=await db`select last_success_at,cursor from ${db(schema)}.sources where id='fed'`;
    response='<rss>invalid';await db`update ${db(schema)}.sources set next_due_at=null where id='fed'`;
    await scheduleCollection(db,boss,schema,owner,config);
    await processOne(boss,workDb,schema,owner,'hot.collect',handlers['hot.collect']);
    const [after]=await db`select last_success_at,cursor,last_error_code from ${db(schema)}.sources where id='fed'`;
    assert.equal(after.last_success_at.toISOString(),before.last_success_at.toISOString());assert.deepEqual(after.cursor,before.cursor);
    assert.equal(after.last_error_code,'hot_source_parse_failed');
    assert.equal((await db`select coverage,body from ${db(schema)}.raw_pages order by acquired_at desc limit 1`)[0].coverage,'unknown');
    // An exception after publication rolls back the original and all pending records together.
    response=raw;
    const granted=await claimTask(db,schema,owner,randomUUID(),'hot.collect:fed:999',randomUUID());
    assert.equal(granted.state,'claimed');if(granted.state!=='claimed')throw Error('hot_fixture_claim_failed');
    const output=await handlers['hot.collect']({sourceId:'fed',sequence:'999'},new AbortController().signal,granted.claim);
    const [count]=await db`select count(*)::int n from ${db(schema)}.raw_pages`;
    await assert.rejects(withOwnerTransaction(db,schema,owner,async tx=>{await output.commit!(tx);throw Error('test_interruption');}),/test_interruption/);
    assert.equal((await db`select count(*)::int n from ${db(schema)}.raw_pages`)[0].n,count.n);
    await db`update ${db(schema)}.job_claims set lease_until=clock_timestamp()-interval '1 second' where input_key='hot.collect:fed:999'`;
    await scheduleCollection(workDb,boss,schema,owner,config);
    assert.equal((await db`select state,error_code from ${db(schema)}.collection_runs where input_key='hot.collect:fed:999'`)[0].error_code,'hot_collection_interrupted');
    const old=await claimTask(db,schema,owner,randomUUID(),'hot.collect:fed:1000',randomUUID());
    assert.equal(old.state,'claimed');if(old.state!=='claimed')throw Error('hot_fixture_claim_failed');
    await db`update ${db(schema)}.job_claims set lease_until=clock_timestamp()-interval '1 second' where input_key='hot.collect:fed:1000'`;
    const replacement=await claimTask(db,schema,owner,randomUUID(),'hot.collect:fed:1000',randomUUID());
    assert.equal(replacement.state,'claimed');if(replacement.state!=='claimed')throw Error('hot_fixture_claim_failed');
    const beforeLate=calls;
    await assert.rejects(handlers['hot.collect']({sourceId:'fed',sequence:'1000'},new AbortController().signal,old.claim),/hot_claim_stale/);
    assert.equal(calls,beforeLate);
    assert.equal((await db`select count(*)::int n from ${db(schema)}.collection_runs where input_key='hot.collect:fed:1000'`)[0].n,0);
    await pauseRuntime(db,schema,owner,token);
  }finally{if(boss)await boss.stop();if(workDb)await workDb.end({timeout:5});await db.end({timeout:5});}
});

test('public fetch bounds honor cancellation, no redirects and Retry-After',async()=>{
  const source=(await publicSources())[0];let redirects:RequestRedirect|undefined;
  const response=await acquireFeed(source,new AbortController().signal,async(_url,options)=>{
    redirects=options?.redirect;return new Response('',{status:429,headers:{'retry-after':'3600'}});
  });
  assert.equal(redirects,'error');assert.equal(response.code,'hot_source_rate_limited');assert.equal(response.retrySeconds,3600);
  const controller=new AbortController();controller.abort();
  const aborted=await acquireFeed(source,controller.signal,async()=>{throw Error('aborted');});
  assert.equal(aborted.code,'hot_source_cancelled');
  const invalid=await acquireFeed(source,new AbortController().signal,async()=>new Response(new Uint8Array([255,254,253])));
  assert.deepEqual(invalid.raw,Buffer.from([255,254,253]));assert.ok(invalid.code);
});
