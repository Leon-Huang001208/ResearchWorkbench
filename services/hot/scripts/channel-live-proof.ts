/** Fixed-scope real-event rule acceptance, no model bootstrap or paid call. */
import {readFile,writeFile} from 'node:fs/promises';
import {join,resolve} from 'node:path';
import {execFileSync} from 'node:child_process';
import postgres from 'postgres';
import {assertNodeRuntime} from '../src/config.ts';
import {migrate} from '../src/database.ts';
import {activateRuntime,pauseRuntime} from '../src/control.ts';
import {grantWorker} from '../src/provision.ts';
import {seedPublicSources} from '../src/collection.ts';
import {configureChannel} from '../src/events.ts';
import {evaluateChannelRules,ruleEvidenceAt} from '../src/channel-rules.ts';
import {sha256} from '../src/material.ts';
import {canonicalGroupingInput} from '../src/processing.ts';
assertNodeRuntime();const parts:Buffer[]=[];let bytes=0;
for await(const chunk of process.stdin){bytes+=chunk.length;if(bytes>65536)throw Error('hot_channel_bootstrap_limit');parts.push(Buffer.from(chunk));}
const input=JSON.parse(Buffer.concat(parts).toString('utf8'));
const project=resolve(import.meta.dirname,'../../..'),dir=join(project,'logs/hot-stage-zero'),schema='hot_acceptance_model',scopeId='hot_events_goal_01a11684';
if(input.projectRoot!==project)throw Error('hot_channel_project_mismatch');
const baseline=JSON.parse(await readFile(join(dir,'receipt.json'),'utf8'));
const container=JSON.parse(execFileSync('docker',['inspect','rwb-hot-probe-6a5d3231'],{encoding:'utf8',timeout:5000}))[0];
if(container.Config.Labels?.['rwb.hot.probe']!=='6a5d3231'||container.Config.Image!==baseline.image||
  container.NetworkSettings.Ports['5432/tcp'][0].HostIp!=='127.0.0.1'||Number(container.NetworkSettings.Ports['5432/tcp'][0].HostPort)!==baseline.port||
  !container.Mounts.some((mount:any)=>mount.Type==='volume'&&mount.Name==='rwb-hot-probe-6a5d3231-data'&&mount.Destination==='/var/lib/postgresql/data'))throw Error('hot_channel_probe_foreign');
const options={host:'127.0.0.1',port:baseline.port,database:'hot_probe',onnotice:()=>{}};
const db=postgres({...options,username:'postgres',password:input.databasePassword});
let worker:ReturnType<typeof postgres>|undefined,owner:Awaited<ReturnType<typeof activateRuntime>>|undefined;
const outcome:any={state:'FAIL',schema,scopeId,paidCalls:0,coverage:'frozen_subset',outputs:[]};
try{
  const rows=await db`select instance_id,controller_token_hash from ${db(schema)}.runtime_identity where singleton`;
  if(rows.length!==1||rows[0].instance_id!==input.instanceId||rows[0].controller_token_hash!==sha256(input.controllerToken))throw Error('hot_channel_identity_mismatch');
  const [before]=await db`select charged_calls,charged_tokens::text,charged_cost_micros::text from ${db(schema)}.model_budgets where scope_id=${scopeId}`;
  await migrate(db,schema);await grantWorker(db,schema,'rwb_hot_acceptance_worker');await seedPublicSources(db,schema);
  worker=postgres({...options,username:'rwb_hot_acceptance_worker',password:input.workerPassword});
  owner=await activateRuntime(db,schema,input.instanceId,input.controllerToken,'native',300,true);
  const definitions=JSON.parse(await readFile(resolve(import.meta.dirname,'../channels.example.json'),'utf8'));
  for(const [id,config] of Object.entries(definitions.channels)){
    const [current]=await db`select cv.config from ${db(schema)}.channels c join ${db(schema)}.channel_versions cv on cv.channel_id=c.id and cv.version=c.current_version where c.id=${id}`;
    if(current){if(canonicalGroupingInput(current.config)!==canonicalGroupingInput(config))throw Error('hot_channel_acceptance_config_changed');}
    else await configureChannel(db,schema,owner,id,0,config as any);
  }
  const [check]=await db`select count(*)::int n from ${db(schema)}.events e where exists(select 1 from ${db(schema)}.processing_results r where e.id=any(r.event_ids))`;
  if(check.n!==2)throw Error('hot_channel_acceptance_events_changed');
  await evaluateChannelRules(worker,schema,owner,20);
  const [{cutoff}]=await db`select clock_timestamp() cutoff`;
  const events=await db`select e.id,v.snapshot->>'title' title from ${db(schema)}.events e join ${db(schema)}.event_versions v on v.event_id=e.id and v.revision=e.current_revision order by e.id`;
  for(const event of events)for(const channel of Object.keys(definitions.channels)){
    const evidence=await ruleEvidenceAt(worker,schema,event.id,channel,cutoff);
    if(!evidence?.evidence)throw Error('hot_channel_acceptance_evidence_missing');
    outcome.outputs.push({eventId:event.id,title:event.title,channel,...evidence});
  }
  const macro=outcome.outputs.find((row:any)=>row.channel==='macro'&&row.evidence.details.sourceIds.includes('fed'));
  const ai=outcome.outputs.find((row:any)=>row.channel==='ai'&&row.evidence.details.sourceIds.includes('openai'));
  const gold=outcome.outputs.find((row:any)=>row.channel==='gold'&&row.evidence.details.sourceIds.includes('fed'));
  if(!macro||!ai||!gold||macro.judgment.judgment.importance<80||ai.judgment.judgment.relevance<70||gold.judgment.judgment.relevance>=macro.judgment.judgment.relevance)throw Error('hot_channel_acceptance_rule_mismatch');
  const [after]=await db`select charged_calls,charged_tokens::text,charged_cost_micros::text from ${db(schema)}.model_budgets where scope_id=${scopeId}`;
  if(canonicalGroupingInput(before)!==canonicalGroupingInput(after))throw Error('hot_channel_acceptance_budget_changed');
  outcome.budget=after;outcome.state='PASS';
}catch(error){outcome.code=error instanceof Error&&/^hot_[a-z_]+$/.test(error.message)?error.message:'hot_channel_acceptance_failed';process.exitCode=1;}
finally{
  if(owner)await pauseRuntime(db,schema,owner,input.controllerToken);if(worker)await worker.end({timeout:5});await db.end({timeout:5});
  await writeFile(join(dir,'channel-live-receipt.json'),JSON.stringify(outcome,null,2),{mode:0o600});
  console.log(JSON.stringify({state:outcome.state,code:outcome.code,outputs:outcome.outputs.length,paidCalls:0,budget:outcome.budget}));
}
