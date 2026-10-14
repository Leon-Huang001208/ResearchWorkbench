import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {randomUUID,randomBytes} from 'node:crypto';
import postgres from 'postgres';
import {migrate} from '../src/database.ts';
import {initializeIdentity} from '../src/control.ts';
import {openQueue} from '../src/queue.ts';
import {grantWorker,grantController} from '../src/provision.ts';
import {seedPublicSources} from '../src/collection.ts';
import {startService} from '../src/service.ts';
import {rpc} from '../src/transport.ts';
import {setTimeout as delay} from 'node:timers/promises';

test('signed source pause cancels in-flight HTTP without stopping worker or accepting late materials',{timeout:15000},async()=>{
  const dir=resolve(import.meta.dirname,'../../../logs/hot-stage-zero');
  const receipt=JSON.parse(await readFile(join(dir,'receipt.json'),'utf8')),password=await readFile(join(dir,'password'),'utf8');
  const db=postgres({host:'127.0.0.1',port:receipt.port,database:'hot_probe',username:'postgres',password,onnotice:()=>{}});
  const schema='hot_cancel_'+randomBytes(5).toString('hex'),worker='hot_cw_'+randomBytes(5).toString('hex'),controller='hot_cc_'+randomBytes(5).toString('hex');
  const workerPassword=randomBytes(32).toString('hex'),controllerPassword=randomBytes(32).toString('hex');
  const instanceId=randomUUID(),controllerToken=randomBytes(32).toString('hex'),readerToken=randomBytes(32).toString('hex');
  let service:Awaited<ReturnType<typeof startService>>|undefined;
  const originalFetch=globalThis.fetch;let calls=0,cancelled=false;
  let signalStarted:()=>void=()=>{};
  const started=new Promise<void>(resolveStarted=>{signalStarted=resolveStarted;});
  try{
    await migrate(db,schema);await initializeIdentity(db,schema,instanceId,controllerToken);
    const boss=await openQueue(db,schema,true);await boss.stop();await seedPublicSources(db,schema);
    await db`update ${db(schema)}.sources set enabled=(id='fed')`;
    try{
      await db.unsafe(`create role "${worker}" login nosuperuser nocreatedb nocreaterole password '${workerPassword}'`);
      await db.unsafe(`create role "${controller}" login nosuperuser nocreatedb nocreaterole password '${controllerPassword}'`);
    }catch{throw Error('hot_fixture_roles_failed');}
    await grantWorker(db,schema,worker);await grantController(db,schema,controller);
    // Simulated slow HTTP is intentional: this tests cancellation, not live-source acceptance.
    globalThis.fetch=async(_url,options)=>{
      calls++;signalStarted();
      return new Promise((_resolve,reject)=>{
        const abort=()=>{cancelled=true;reject(Error('cancelled'));};
        if(options?.signal?.aborted)abort();else options?.signal?.addEventListener('abort',abort,{once:true});
      });
    };
    service=await startService({config:{enabled:true,database:{mode:'external',tls:'disable',port:receipt.port,name:'hot_probe',schema,user:worker,controllerUser:controller}},
      instanceId,mode:'native',workerPassword,controllerUser:controller,controllerPassword,controllerToken,readerToken});
    await Promise.race([started,delay(5000).then(()=>{throw Error('hot_fixture_http_not_started');})]);
    const result=await rpc(service.port,service.owner,controllerToken,'source.configure',{sourceId:'fed',expectedRevision:'0',enabled:false}) as any;
    assert.equal(result.enabled,false);
    for(let i=0;i<30;i++){
      if((await db`select count(*)::int n from ${db(schema)}.job_claims where state='failed'`)[0].n>0)break;
      await delay(50);
    }
    assert.equal(cancelled,true);assert.equal(calls,1);
    assert.equal((await db`select count(*)::int n from ${db(schema)}.raw_pages`)[0].n,0);
    assert.equal((await db`select count(*)::int n from ${db(schema)}.material_versions`)[0].n,0);
    const status=await rpc(service.port,service.owner,readerToken,'status',{}) as any;
    assert.equal(status.worker,'running');
    const [source]=await db`select enabled,last_success_at from ${db(schema)}.sources where id='fed'`;
    assert.equal(source.enabled,false);assert.equal(source.last_success_at,null);
  }finally{if(service)await service.close();globalThis.fetch=originalFetch;await db.end({timeout:5});}
});
