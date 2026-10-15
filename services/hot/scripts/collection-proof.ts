/** Two actual collection cycles on four official sources through the production worker. */
import {readFile,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {randomBytes,randomUUID} from 'node:crypto';
import postgres from 'postgres';
import {migrate} from '../src/database.ts';
import {initializeIdentity} from '../src/control.ts';
import {openQueue} from '../src/queue.ts';
import {seedPublicSources} from '../src/collection.ts';
import {grantWorker,grantController} from '../src/provision.ts';
import {startService} from '../src/service.ts';
import {setTimeout as delay} from 'node:timers/promises';
import {execFileSync} from 'node:child_process';
import {sha256} from '../src/material.ts';

const dir=resolve(import.meta.dirname,'../../../logs/hot-stage-zero');
const receipt=JSON.parse(await readFile(join(dir,'receipt.json'),'utf8'));
const container=JSON.parse(execFileSync('docker',['inspect','rwb-hot-probe-6a5d3231'],{encoding:'utf8',timeout:5000}))[0];
if(container.Config.Labels?.['rwb.hot.probe']!=='6a5d3231'||container.Config.Image!==receipt.image||
  container.NetworkSettings.Ports['5432/tcp'][0].HostIp!=='127.0.0.1'||Number(container.NetworkSettings.Ports['5432/tcp'][0].HostPort)!==receipt.port)throw Error('hot_probe_foreign');
const password=await readFile(join(dir,'password'),'utf8');
const db=postgres({host:'127.0.0.1',port:receipt.port,database:'hot_probe',username:'postgres',password,onnotice:()=>{}});
const schema='hot_live_'+randomBytes(5).toString('hex'),worker='hot_w_'+randomBytes(5).toString('hex'),controller='hot_c_'+randomBytes(5).toString('hex');
const workerPassword=randomBytes(32).toString('hex'),controllerPassword=randomBytes(32).toString('hex');
const instanceId=randomUUID(),controllerToken=randomBytes(32).toString('hex'),readerToken=randomBytes(32).toString('hex');
let service:Awaited<ReturnType<typeof startService>>|undefined;
const outcome:Record<string,unknown>={state:'FAIL',scope:'macos_native_worker_public_http',schema,model:'NOT_RUN',research:'NOT_RUN'};
outcome.codeHashes=Object.fromEntries(await Promise.all(['src/collection.ts','src/queue.ts','src/service.ts','src/database.ts','src/provision.ts','src/source-control.ts','migrations/0005-collection-inbox.sql','migrations/0006-source-control.sql']
  .map(async file=>[file,sha256(await readFile(resolve(import.meta.dirname,'..',file)))])));
try{
  await migrate(db,schema);await initializeIdentity(db,schema,instanceId,controllerToken);
  const boss=await openQueue(db,schema,true);await boss.stop();await seedPublicSources(db,schema);
  await db.unsafe(`create role "${worker}" login nosuperuser nocreatedb nocreaterole password '${workerPassword}'`);
  await db.unsafe(`create role "${controller}" login nosuperuser nocreatedb nocreaterole password '${controllerPassword}'`);
  await grantWorker(db,schema,worker);await grantController(db,schema,controller);
  service=await startService({config:{enabled:true,database:{mode:'external',tls:'disable',name:'hot_probe',schema,port:receipt.port,user:worker,controllerUser:controller},
    collection:{frequencySeconds:60,maxItems:100},worker:{concurrency:2}},instanceId,mode:'native',workerPassword,controllerUser:controller,controllerPassword,controllerToken,readerToken});
  const deadline=Date.now()+140000;let completed=false,last='';
  while(Date.now()<deadline){
    const [runtime]=await db`select paused from ${db(schema)}.runtime_identity where singleton`;
    if(runtime.paused)throw Error('hot_collection_worker_stopped');
    const rows=await db`select s.id,s.operator,s.last_error_code,
      (select count(*)::int from ${db(schema)}.collection_runs r where r.source_id=s.id and state='acquired') cycles,
      (select count(*)::int from ${db(schema)}.material_inbox i join ${db(schema)}.raw_pages p on p.id=i.page_id where p.source_id=s.id and not i.processed) pending
      from ${db(schema)}.sources s order by id`;
    const state=JSON.stringify(rows);
    if(state!==last){console.log(JSON.stringify({event:'collection_progress',sources:rows}));last=state;}
    if(rows.length===4&&rows.every(row=>row.cycles>=2&&row.pending===0)){completed=true;outcome.sources=rows;break;}
    await delay(1000);
  }
  if(!completed)throw Error('hot_collection_acceptance_incomplete');
  const [counts]=await db`select (select count(*)::int from ${db(schema)}.materials) materials,
    (select count(*)::int from ${db(schema)}.material_versions) versions,
    (select count(*)::int from ${db(schema)}.raw_pages) rawPages`;
  const [identity]=await db`select count(*)::int as duplicates from (select identity from ${db(schema)}.materials group by identity having count(*)>1) x`;
  if(identity.duplicates)throw Error('hot_collection_identity_duplicate');
  Object.assign(outcome,{state:'PASS',...counts,coverage:'latest_snapshot',cycles:2});
}catch(error){outcome.code=error instanceof Error&&/^hot_[a-z_]+$/.test(error.message)?error.message:'hot_collection_proof_failed';process.exitCode=1;}
finally{
  if(service)await service.close();await db.end({timeout:5});
  await writeFile(join(dir,'collection-live-receipt.json'),JSON.stringify(outcome,null,2),{mode:0o600});
  console.log(JSON.stringify(outcome));
}
