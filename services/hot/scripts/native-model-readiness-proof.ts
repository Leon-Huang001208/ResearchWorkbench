/** Actual configured credential/catalog acceptance; never invokes grouping or model send. */
import {readFile,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {execFileSync} from 'node:child_process';
import postgres from 'postgres';
import {parseConfig,assertNodeRuntime} from '../src/config.ts';
import {loadNativeModel,type ModelCapability} from '../src/native-model.ts';
import type {GroupingPacket} from '../src/processing.ts';
assertNodeRuntime();
const chunks:Buffer[]=[];let size=0;
for await(const chunk of process.stdin){size+=chunk.length;if(size>65536)throw Error('hot_bootstrap_limit');chunks.push(Buffer.from(chunk));}
const input=JSON.parse(Buffer.concat(chunks).toString('utf8'));
const expected=input.expectedState??'ready';if(!['ready','blocked_model'].includes(expected))throw Error('hot_model_proof_invalid');
const project=resolve(import.meta.dirname,'../../..'),dir=join(project,'logs/hot-stage-zero');
const baseline=JSON.parse(await readFile(join(dir,'receipt.json'),'utf8'));
const container=JSON.parse(execFileSync('docker',['inspect','rwb-hot-probe-6a5d3231'],{encoding:'utf8',timeout:5000}))[0];
if(input.projectRoot!==project||container.Config.Labels?.['rwb.hot.probe']!=='6a5d3231'||container.Config.Image!==baseline.image||
  container.NetworkSettings.Ports['5432/tcp'][0].HostIp!=='127.0.0.1'||Number(container.NetworkSettings.Ports['5432/tcp'][0].HostPort)!==baseline.port||
  !container.Mounts.some((m:any)=>m.Type==='volume'&&m.Name==='rwb-hot-probe-6a5d3231-data'))throw Error('hot_model_probe_foreign');
const schema='hot_acceptance_model',scopeId='hot_events_goal_01a11684';
const db=postgres({host:'127.0.0.1',port:baseline.port,database:'hot_probe',username:'rwb_hot_acceptance_worker',password:input.workerPassword,
  onnotice:()=>{},connect_timeout:5,connection:{default_transaction_read_only:true,statement_timeout:15000}});
let capability:ModelCapability|undefined;const receipt:any={state:'FAIL',scopeId,schema,paidCalls:0,research:'NOT_RUN',proof:'normal_factory_credential_catalog_only'};
try{
  const [identity]=await db`select instance_id,mode,generation::text from ${db(schema)}.runtime_identity where singleton`;
  if(identity.instance_id!==input.instanceId)throw Error('hot_model_instance_mismatch');
  const budget=async()=>{const [r]=await db`select charged_calls,charged_tokens::text,charged_cost_micros::text,paused from ${db(schema)}.model_budgets where scope_id=${scopeId}`;return r;};
  const before=await budget();
  const config=parseConfig({enabled:true,model:{enabled:true,scopeId},budget:{maxCallsPerDay:20,maxTokensPerDay:20000,maxCostPerDay:1}});
  capability=await loadNativeModel(db,schema,{instanceId:identity.instance_id,mode:identity.mode,generation:identity.generation},config,input.nativeModel);
  if(capability.state==='ready'){
    const packets=await db`select i.packet,r.result_key from ${db(schema)}.processing_items i
      join ${db(schema)}.processing_results r using(material_id,material_revision,prompt_version)
      where i.state='applied' order by i.material_id limit 2`;
    if(packets.length!==2)throw Error('hot_model_cache_proof_inputs_missing');
    receipt.cacheReplays=0;
    for(const row of packets){
      // Read-only DB session makes a cache miss fail before any reserve/dispatch.
      const result=await capability.groupingModel!.run(row.packet as GroupingPacket,AbortSignal.timeout(10000));
      if(result.resultKey!==row.result_key)throw Error('hot_model_legacy_cache_mismatch');
      receipt.cacheReplays++;
    }
  }
  receipt.model=capability.state;receipt.code=capability.code;receipt.budget=await budget();
  if(JSON.stringify(before)!==JSON.stringify(receipt.budget))throw Error('hot_model_readiness_budget_changed');
  if(capability.state!==expected||(expected==='blocked_model'&&capability.code!=='hot_dsh_model_unconfigured'))throw Error('hot_model_readiness_unexpected');
  receipt.state='PASS';
}catch(error){receipt.code=error instanceof Error&&/^hot_[a-z_]+$/.test(error.message)?error.message:'hot_model_readiness_failed';process.exitCode=1;}
finally{
  try{if(capability)await capability.close();}catch{receipt.state='FAIL';receipt.code='hot_model_context_close_failed';process.exitCode=1;}
  await db.end({timeout:5});
  await writeFile(join(dir,expected==='ready'?'native-model-readiness-receipt.json':'native-model-missing-credential-receipt.json'),JSON.stringify(receipt,null,2),{mode:0o600});
  console.log(JSON.stringify(receipt));
}
