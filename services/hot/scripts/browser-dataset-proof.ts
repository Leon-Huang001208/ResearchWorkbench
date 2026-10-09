/** Owned real-event browser fixture preparation; never creates a model quota or dispatches. */
import {readFile,writeFile,access} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {randomUUID} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import postgres from 'postgres';
import {migrate} from '../src/database.ts';
import {grantWorker,grantController} from '../src/provision.ts';
import {activateRuntime,pauseRuntime} from '../src/control.ts';
import {configureSource} from '../src/source-control.ts';
import {sha256} from '../src/material.ts';
import {assertNodeRuntime} from '../src/config.ts';
assertNodeRuntime();const chunks:Buffer[]=[];let bytes=0;
for await(const part of process.stdin){bytes+=part.length;if(bytes>65536)throw Error('hot_browser_input_limit');chunks.push(Buffer.from(part));}
const input=JSON.parse(Buffer.concat(chunks).toString('utf8'));
if(!['prepare','restore'].includes(input.action))throw Error('hot_browser_action_invalid');
const project=resolve(import.meta.dirname,'../../..'),dir=join(project,'logs/hot-stage-zero'),schema='hot_acceptance_model',scopeId='hot_events_goal_01a11684';
const proofId=input.proofId??'browser';
if(typeof proofId!=='string'||!/^[a-z][a-z0-9-]{0,47}$/.test(proofId))throw Error('hot_browser_proof_invalid');
const baselineFile=join(dir,proofId+'-source-baseline.json'),cleanupFile=join(dir,proofId+'-cleanup-receipt.json');
const baseline=JSON.parse(await readFile(join(dir,'receipt.json'),'utf8'));
const container=JSON.parse(execFileSync('docker',['inspect','rwb-hot-probe-6a5d3231'],{encoding:'utf8',timeout:5000}))[0];
if(input.projectRoot!==project||container.Config.Labels?.['rwb.hot.probe']!=='6a5d3231'||container.Config.Image!==baseline.image||
 container.NetworkSettings.Ports['5432/tcp'][0].HostIp!=='127.0.0.1'||Number(container.NetworkSettings.Ports['5432/tcp'][0].HostPort)!==baseline.port||
 !container.Mounts.some((m:any)=>m.Type==='volume'&&m.Name==='rwb-hot-probe-6a5d3231-data'))throw Error('hot_browser_probe_foreign');
const db=postgres({host:'127.0.0.1',port:baseline.port,database:'hot_probe',username:'postgres',password:input.databasePassword,onnotice:()=>{},connect_timeout:5});
let owner:Awaited<ReturnType<typeof activateRuntime>>|undefined;
let createdRole=false;
let restoreRoleBound=false;
let restoreBaseline:{instanceId:string;controllerRole:string;budget:unknown;sources:{id:string;enabled:boolean;frequency_seconds:number|null}[]}|undefined;
let restoreReceipt:Record<string,unknown>|undefined;
try{
 const [identity]=await db`select instance_id,controller_token_hash from ${db(schema)}.runtime_identity where singleton`;
 if(identity.instance_id!==input.instanceId||identity.controller_token_hash!==sha256(input.controllerToken))throw Error('hot_browser_identity_mismatch');
 if(input.action==='restore'){
  restoreBaseline=JSON.parse(await readFile(baselineFile,'utf8'));
  if(!restoreBaseline||restoreBaseline.instanceId!==input.instanceId)throw Error('hot_browser_baseline_foreign');
  if(!/^rwb_hot_browser_[a-f0-9]{10}$/.test(input.controllerRole)||restoreBaseline.controllerRole!==input.controllerRole)throw Error('hot_browser_role_invalid');
  restoreRoleBound=true;
 }
 const budget=async()=>{const [r]=await db`select charged_calls,charged_tokens::text,charged_cost_micros::text,max_calls,max_tokens::text,max_cost_micros::text from ${db(schema)}.model_budgets where scope_id=${scopeId}`;return r;};
 const before=await budget();if(before.max_calls!==20||before.max_tokens!=='20000'||before.max_cost_micros!=='1000000')throw Error('hot_browser_budget_mismatch');
 if(input.action==='prepare'){
  // Fail before migration/role changes when this exact proof already has a baseline.
  try{await access(baselineFile);throw Error('hot_browser_baseline_exists');}catch(error){if((error as NodeJS.ErrnoException).code!=='ENOENT')throw error;}
  await migrate(db,schema);
  if(!/^rwb_hot_browser_[a-f0-9]{10}$/.test(input.controllerRole)||!/^[a-f0-9]{64}$/.test(input.controllerPassword))throw Error('hot_browser_role_invalid');
  const [existing]=await db`select oid from pg_roles where rolname=${input.controllerRole}`;
  if(existing)throw Error('hot_browser_role_exists');
  try{await db.unsafe(`create role "${input.controllerRole}" login nosuperuser nocreatedb nocreaterole password '${input.controllerPassword}'`);createdRole=true;}catch{throw Error('hot_browser_role_failed');}
  await grantWorker(db,schema,'rwb_hot_acceptance_worker');await grantController(db,schema,input.controllerRole);
  const sources=JSON.parse(JSON.stringify(await db`select id,enabled,frequency_seconds from ${db(schema)}.sources order by id`));
  await writeFile(baselineFile,JSON.stringify({instanceId:input.instanceId,controllerRole:input.controllerRole,budget:before,sources},null,2),{mode:0o600,flag:'wx'});
  owner=await activateRuntime(db,schema,input.instanceId,input.controllerToken,'native',300,true);
  for(const source of sources){
   const [current]=await db`select config_revision::text from ${db(schema)}.sources where id=${source.id}`;
   if(source.enabled)await configureSource(db,schema,owner,randomUUID(),{sourceId:source.id,expectedRevision:current.config_revision,enabled:false});
  }
  const [events]=await db`select count(*)::int n from ${db(schema)}.events`;
  if(events.n!==2)throw Error('hot_browser_event_count_mismatch');
  console.log(JSON.stringify({state:'prepared',schema,port:baseline.port,events:events.n,budget:await budget()}));
 }else{
  const saved=restoreBaseline!;
  owner=await activateRuntime(db,schema,input.instanceId,input.controllerToken,'native',300,true);
  for(const source of saved.sources){
   const [current]=await db`select enabled,frequency_seconds,config_revision::text from ${db(schema)}.sources where id=${source.id}`;
   if(current.enabled!==source.enabled||current.frequency_seconds!==source.frequency_seconds)await configureSource(db,schema,owner,randomUUID(),
    {sourceId:source.id,expectedRevision:current.config_revision,enabled:source.enabled,frequencySeconds:source.frequency_seconds});
  }
  const after=await budget();if(JSON.stringify(after)!==JSON.stringify(saved.budget))throw Error('hot_browser_budget_changed');
  restoreReceipt={budget:after,sourcesRestored:true};
  console.log(JSON.stringify({state:'restored',budget:after}));
 }
}catch(error){console.log(JSON.stringify({state:'FAIL',code:error instanceof Error&&/^hot_[a-z_]+$/.test(error.message)?error.message:'hot_browser_prepare_failed'}));process.exitCode=1;}
finally{
 let runtimePaused:boolean|null=null,temporaryRoleNoLogin=false;
 if(owner)try{await pauseRuntime(db,schema,owner,input.controllerToken);runtimePaused=true;}catch{console.log(JSON.stringify({state:'FAIL',code:'hot_browser_pause_failed'}));process.exitCode=1;runtimePaused=false;}
 if((createdRole&&process.exitCode===1)||restoreRoleBound)try{await db.unsafe(`alter role "${input.controllerRole}" nologin`);temporaryRoleNoLogin=true;}catch{console.log(JSON.stringify({state:'FAIL',code:'hot_browser_role_cleanup_failed'}));process.exitCode=1;}
 try{await db.end({timeout:5});}catch{console.log(JSON.stringify({state:'FAIL',code:'hot_browser_close_failed'}));process.exitCode=1;}
 if(restoreRoleBound)try{await writeFile(cleanupFile,JSON.stringify({state:process.exitCode===1?'FAIL':'PASS',...restoreReceipt,
   restorationAudited:!!restoreReceipt,runtimePaused,temporaryRoleNoLogin},null,2),{mode:0o600});}catch{console.log(JSON.stringify({state:'FAIL',code:'hot_browser_receipt_failed'}));process.exitCode=1;}
}
