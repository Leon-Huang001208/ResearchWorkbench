import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {join,resolve} from 'node:path';
import {randomUUID,randomBytes} from 'node:crypto';
import postgres from 'postgres';
import {migrate} from '../src/database.ts';
import {initializeIdentity,activateRuntime,pauseRuntime,claimTask,withOwnerTransaction} from '../src/control.ts';
import {openQueue,processOne} from '../src/queue.ts';
import {seedPublicSources,collectionHandlers,scheduleCollection} from '../src/collection.ts';
import {configureSource} from '../src/source-control.ts';
import {grantWorker,grantController} from '../src/provision.ts';
import {parseConfig} from '../src/config.ts';

test('conditional source changes audit once, reject worker and preserve paused inbox for resume',{timeout:20000},async()=>{
  const dir=resolve(import.meta.dirname,'../../../logs/hot-stage-zero');
  const receipt=JSON.parse(await readFile(join(dir,'receipt.json'),'utf8')),password=await readFile(join(dir,'password'),'utf8');
  const options={host:'127.0.0.1',port:receipt.port,database:'hot_probe',onnotice:()=>{}};
  const db=postgres({...options,username:'postgres',password});
  const schema='hot_source_'+randomBytes(5).toString('hex'),worker='hot_sw_'+randomBytes(5).toString('hex'),control='hot_sc_'+randomBytes(5).toString('hex');
  const workerPassword=randomBytes(32).toString('hex'),controlPassword=randomBytes(32).toString('hex');
  let ordinary:ReturnType<typeof postgres>|undefined,controller:ReturnType<typeof postgres>|undefined,boss:Awaited<ReturnType<typeof openQueue>>|undefined;
  try{
    await migrate(db,schema);const instance=randomUUID(),token=randomBytes(32).toString('hex');
    await initializeIdentity(db,schema,instance,token);boss=await openQueue(db,schema,true);
    await seedPublicSources(db,schema);await db`update ${db(schema)}.sources set enabled=(id='fed')`;
    try{
      await db.unsafe(`create role "${worker}" login nosuperuser nocreatedb nocreaterole password '${workerPassword}'`);
      await db.unsafe(`create role "${control}" login nosuperuser nocreatedb nocreaterole password '${controlPassword}'`);
    }catch{throw Error('hot_fixture_roles_failed');}
    await grantWorker(db,schema,worker);await grantController(db,schema,control);
    ordinary=postgres({...options,username:worker,password:workerPassword});controller=postgres({...options,username:control,password:controlPassword});
    await boss.stop();boss=await openQueue(ordinary,schema);
    const owner=await activateRuntime(controller,schema,instance,token,'native');
    const request=randomUUID(),params={sourceId:'fed',expectedRevision:'0',frequencySeconds:60};
    await assert.rejects(configureSource(ordinary,schema,owner,request,params));
    const first=await configureSource(controller,schema,owner,request,params) as any;
    assert.equal(first.revision,'1');assert.equal(first.frequencySeconds,60);
    assert.deepEqual(await configureSource(controller,schema,owner,request,params),first);
    assert.equal((await db`select count(*)::int n from ${db(schema)}.source_control_requests`)[0].n,1);
    await assert.rejects(configureSource(controller,schema,owner,request,{...params,frequencySeconds:120}),/request_conflict/);
    await assert.rejects(configureSource(controller,schema,owner,randomUUID(),{...params,expectedRevision:'0'}),/revision_conflict/);
    await assert.rejects(db`update ${db(schema)}.source_control_requests set actor='local_host'`);
    await db`update ${db(schema)}.sources set next_due_at=null where id='fed'`;
    const config=parseConfig({enabled:true,collection:{frequencySeconds:600,maxItems:3}});
    const raw=await readFile(join(dir,'fed.xml'),'utf8');let calls=0;
    const controllers=new Map<string,AbortController>();
    const handlers=collectionHandlers(ordinary,boss,schema,owner,config,async()=>{calls++;return new Response(raw);},controllers);
    await scheduleCollection(ordinary,boss,schema,owner,config);
    const [due]=await db`select extract(epoch from next_due_at-clock_timestamp())::int seconds from ${db(schema)}.sources where id='fed'`;
    assert.ok(due.seconds>50&&due.seconds<=60);
    await processOne(boss,ordinary,schema,owner,'hot.collect',handlers['hot.collect']);
    const [page]=await db`select id from ${db(schema)}.raw_pages limit 1`;
    const output=await handlers['hot.parse']({pageId:page.id},new AbortController().signal);
    await configureSource(controller,schema,owner,randomUUID(),{sourceId:'fed',expectedRevision:'1',enabled:false});
    await assert.rejects(withOwnerTransaction(ordinary,schema,owner,tx=>output.commit!(tx)),/source_paused/);
    assert.equal((await db`select count(*)::int n from ${db(schema)}.material_versions`)[0].n,0);
    assert.equal(await scheduleCollection(ordinary,boss,schema,owner,config),0);
    await configureSource(controller,schema,owner,randomUUID(),{sourceId:'fed',expectedRevision:'2',enabled:true,frequencySeconds:null});
    await scheduleCollection(ordinary,boss,schema,owner,config);
    for(let i=0;i<20;i++){
      await processOne(boss,ordinary,schema,owner,'hot.parse',handlers['hot.parse']);
      if((await db`select count(*)::int n from ${db(schema)}.material_inbox where not processed`)[0].n===0)break;
    }
    assert.equal(calls,1);
    assert.equal((await db`select count(*)::int n from ${db(schema)}.material_inbox where not processed`)[0].n,0);
    const granted=await claimTask(ordinary,schema,owner,randomUUID(),'hot.collect:fed:2000',randomUUID());
    assert.equal(granted.state,'claimed');if(granted.state!=='claimed')throw Error('hot_fixture_claim_failed');
    // Deterministic boundary: pause after the real preflight transaction commits,
    // before its Promise returns to the handler. The abort registration must already exist.
    const proxy=new Proxy(ordinary,{
      get(target,key,receiver){
        if(key==='begin')return async(operation:(tx:postgres.TransactionSql)=>Promise<unknown>)=>{
          const result=await target.begin(operation);
          await configureSource(controller!,schema,owner,randomUUID(),{sourceId:'fed',expectedRevision:'3',enabled:false});
          assert.ok(controllers.get('fed'));controllers.get('fed')!.abort();
          return result;
        };
        return Reflect.get(target,key,receiver);
      }
    });
    const guarded=collectionHandlers(proxy,boss,schema,owner,config,async()=>{calls++;return new Response(raw);},controllers);
    await assert.rejects(guarded['hot.collect']({sourceId:'fed',sequence:'2000'},new AbortController().signal,granted.claim));
    assert.equal(calls,1);assert.equal(controllers.size,0);
    await pauseRuntime(controller,schema,owner,token);
  }finally{if(boss)await boss.stop();if(ordinary)await ordinary.end({timeout:5});if(controller)await controller.end({timeout:5});await db.end({timeout:5});}
});
