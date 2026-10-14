/** PostgreSQL owns Hot handoff progress; native side effects use the reserved session identity. */
import type postgres from 'postgres';
import {randomUUID} from 'node:crypto';
import {schemaName} from './config.ts';
import {withOwnerTransaction,type RuntimeOwner} from './control.ts';
import {researchEvidence,parseEvidenceSelection} from './research-evidence.ts';
import {canonicalGroupingInput} from './processing.ts';
import {sha256} from './material.ts';
import {logEvent} from './log.ts';
type Sql=ReturnType<typeof postgres>;
type Params=Record<string,postgres.JSONValue>;
const UUID=/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i;
const transitions:Record<string,string[]>={prepared:['session_creating','abandoned'],session_creating:['session_ready','session_outcome_unknown'],
  session_outcome_unknown:['session_ready','abandoned'],session_ready:['snapshot_ready','abandoned'],snapshot_ready:['execution_starting','abandoned'],
  execution_starting:['running','execution_outcome_unknown','failed'],execution_outcome_unknown:['running','completed','failed','abandoned'],
  running:['completed','failed'],completed:[],failed:[],abandoned:[]};
export function validateRunTransition(from:string,to:string){if(!transitions[from]?.includes(to))throw Error('hot_research_transition_invalid');}
function uuid(value:unknown){if(typeof value!=='string'||!UUID.test(value))throw Error('hot_research_run_invalid');return value.toLowerCase();}
function only(params:Params,keys:string[]){if(Object.keys(params).some(key=>!keys.includes(key)))throw Error('hot_research_run_invalid');}
function json(value:unknown){return JSON.parse(JSON.stringify(value)) as postgres.JSONValue;}
function projection(row:Record<string,any>){return json({instanceId:JSON.parse(Buffer.from(row.manifest_body).toString()).instanceId,runId:row.id,requestId:row.request_id,sessionId:row.session_id,targetMode:row.target_mode,
  briefId:row.brief_id,version:row.brief_version,materialIds:row.material_ids,evidenceManifestHash:row.manifest_hash,
  revision:row.revision,state:row.state,datasetId:row.dataset_id,datasetManifestHash:row.dataset_manifest_hash,
  deliveryKey:row.delivery_key,reportRunId:row.report_run_id,errorCode:row.error_code,createdAt:row.created_at,updatedAt:row.updated_at});}
async function get(db:Sql,schema:string,id:string){
  const [row]=await db`select i.*,r.revision,r.state,r.dataset_id,r.dataset_manifest_hash,r.delivery_key,r.report_run_id,r.error_code,r.updated_at
    from ${db(schema)}.research_inputs i join ${db(schema)}.research_runs r on r.id=i.id where i.id=${id}`;
  if(!row)throw Error('hot_research_run_unknown');
  if(sha256(Buffer.from(row.manifest_body))!==row.manifest_hash)throw Error('hot_research_input_integrity_invalid');return row;
}
export async function readResearchRun(db:Sql,schema:string,params:Params){schemaName(schema);only(params,['runId']);return projection(await get(db,schema,uuid(params.runId)));}
export async function prepareResearchRun(db:Sql,schema:string,owner:RuntimeOwner,requestId:string,params:Params,signal?:AbortSignal){
  schemaName(schema);requestId=uuid(requestId);only(params,['runId','briefId','version','materialIds','targetMode']);
  const id=uuid(params.runId),selection=parseEvidenceSelection({briefId:params.briefId,version:params.version,materialIds:params.materialIds});
  if(params.targetMode!=='fingpt'&&params.targetMode!=='claw')throw Error('hot_research_run_invalid');
  const hash=sha256(canonicalGroupingInput({runId:id,...selection,targetMode:params.targetMode}));
  try{
    const [permission]=await db`select has_table_privilege(current_user,${schema+'.research_inputs'},'INSERT') allowed`;
    if(!permission.allowed)throw Error('hot_research_control_denied');
    const cached=async(reader:Sql)=>{
      const rows=await reader`select id,request_id,params_hash from ${reader(schema)}.research_inputs where id=${id} or request_id=${requestId}`;
      if(rows.length){if(rows.length!==1||rows[0].id!==id||rows[0].request_id!==requestId||rows[0].params_hash!==hash)throw Error('hot_research_request_conflict');return get(reader,schema,id);}
      return null;
    };
    const before=await cached(db);signal?.throwIfAborted();
    if(before)return withOwnerTransaction(db,schema,owner,async tx=>projection(await get(tx as unknown as Sql,schema,id)));
    const frozen=await researchEvidence(db,schema,selection,signal) as unknown as {manifest:Record<string,any>;manifestHash:string};
    if(frozen.manifest.instanceId!==owner.instanceId)throw Error('hot_research_instance_invalid');
    const body=Buffer.from(canonicalGroupingInput(frozen.manifest));
    const result=await withOwnerTransaction(db,schema,owner,async tx=>{
      signal?.throwIfAborted();const prior=await cached(tx as unknown as Sql);if(prior)return projection(prior);
      await tx`insert into ${tx(schema)}.research_inputs(id,request_id,params_hash,brief_id,brief_version,material_ids,target_mode,session_id,manifest_body,manifest_hash,actor)
        values(${id},${requestId},${hash},${selection.briefId},${selection.version},${tx.json(selection.materialIds)},${params.targetMode as string},${randomUUID()},${body},${frozen.manifestHash},'local_host')`;
      await tx`insert into ${tx(schema)}.research_runs(id) values(${id})`;
      return projection(await get(tx as unknown as Sql,schema,id));
    });
    logEvent('research_run_prepared');return result;
  }catch(error){logEvent('research_run_failed');if(error instanceof Error&&/^hot_[a-z_]+$/.test(error.message))throw error;
    if(signal?.aborted)throw Error('hot_research_cancelled');throw Error('hot_research_run_failed');}
}
export async function advanceResearchRun(db:Sql,schema:string,owner:RuntimeOwner,requestId:string,params:Params,signal?:AbortSignal){
  schemaName(schema);requestId=uuid(requestId);only(params,['runId','expectedRevision','state','datasetId','datasetManifestHash','deliveryKey','reportRunId','errorCode']);
  const id=uuid(params.runId),revision=params.expectedRevision;
  if(typeof revision!=='number'||!Number.isSafeInteger(revision)||revision<1||revision>1000000||typeof params.state!=='string'||!transitions[params.state])throw Error('hot_research_run_invalid');
  if(params.datasetId!==undefined)uuid(params.datasetId);
  if(params.datasetManifestHash!==undefined&&(typeof params.datasetManifestHash!=='string'||!/^[a-f0-9]{64}$/.test(params.datasetManifestHash)))throw Error('hot_research_run_invalid');
  if((params.datasetId===undefined)!==(params.datasetManifestHash===undefined))throw Error('hot_research_run_invalid');
  if(params.deliveryKey!==undefined&&(typeof params.deliveryKey!=='string'||!/^[A-Za-z0-9_.:-]{8,128}$/.test(params.deliveryKey)))throw Error('hot_research_run_invalid');
  if(params.reportRunId!==undefined&&(typeof params.reportRunId!=='string'||!/^[A-Za-z0-9_.:-]{1,128}$/.test(params.reportRunId)))throw Error('hot_research_run_invalid');
  if(params.errorCode!==undefined&&(typeof params.errorCode!=='string'||!/^[a-z][a-z0-9_]{0,99}$/.test(params.errorCode)))throw Error('hot_research_run_invalid');
  if(params.datasetId!==undefined&&params.state!=='snapshot_ready'||params.deliveryKey!==undefined&&params.state!=='execution_starting'||params.reportRunId!==undefined&&!['running','completed','failed'].includes(params.state))throw Error('hot_research_run_invalid');
  params={...params,runId:id,...(params.datasetId===undefined?{}:{datasetId:uuid(params.datasetId)})};
  const hash=sha256(canonicalGroupingInput(params));
  try{
    const [permission]=await db`select has_table_privilege(current_user,${schema+'.research_operations'},'INSERT')
      and has_column_privilege(current_user,${schema+'.research_runs'},'state','UPDATE') allowed`;
    if(!permission.allowed)throw Error('hot_research_control_denied');
    return await withOwnerTransaction(db,schema,owner,async tx=>{
    signal?.throwIfAborted();
    const [prior]=await tx`select run_id,params_hash,result from ${tx(schema)}.research_operations where request_id=${requestId}`;
    if(prior){if(prior.run_id!==id||prior.params_hash!==hash)throw Error('hot_research_request_conflict');return prior.result;}
    const row=await get(tx as unknown as Sql,schema,id);
    if(row.revision!==revision)throw Error('hot_research_revision_conflict');
    validateRunTransition(row.state,params.state as string);
    for(const [key,column] of [['datasetId','dataset_id'],['datasetManifestHash','dataset_manifest_hash'],['deliveryKey','delivery_key'],['reportRunId','report_run_id']] as const)
      if(params[key]!==undefined&&row[column]!==null&&params[key]!==row[column])throw Error('hot_research_mapping_conflict');
    const dataset=(params.datasetId??row.dataset_id) as string|null,datasetHash=(params.datasetManifestHash??row.dataset_manifest_hash) as string|null,delivery=(params.deliveryKey??row.delivery_key) as string|null;
    if(['snapshot_ready','execution_starting','execution_outcome_unknown','running','completed'].includes(params.state as string)&&(!dataset||!datasetHash))throw Error('hot_research_snapshot_required');
    if(['execution_starting','execution_outcome_unknown','running','completed'].includes(params.state as string)&&!delivery)throw Error('hot_research_delivery_required');
    const updated=await tx`update ${tx(schema)}.research_runs set revision=revision+1,state=${params.state as string},dataset_id=${dataset},dataset_manifest_hash=${datasetHash},
      delivery_key=${delivery},report_run_id=${(params.reportRunId??row.report_run_id) as string|null},error_code=${(params.errorCode??null) as string|null},updated_at=clock_timestamp()
      where id=${id} and revision=${revision} returning id`;
    if(updated.length!==1)throw Error('hot_research_revision_conflict');
    const result=projection(await get(tx as unknown as Sql,schema,id));
    await tx`insert into ${tx(schema)}.research_operations(request_id,run_id,params_hash,before_state,after_state,result,actor,generation)
      values(${requestId},${id},${hash},${row.state},${params.state as string},${tx.json(result)},'local_host',${owner.generation})`;
    logEvent('research_run_advanced');return result;
  });}catch(error){logEvent('research_run_failed');if(error instanceof Error&&/^hot_[a-z_]+$/.test(error.message))throw error;
    if(signal?.aborted)throw Error('hot_research_cancelled');throw Error('hot_research_run_failed');}
}
