/** One Hot scheduler, one PG queue. Periodic briefs freeze existing evidence; no paid study or delivery. */
import type postgres from 'postgres';
import type {PgBoss} from 'pg-boss';
import {withOwnerTransaction,type RuntimeOwner,type Claim,type Tx} from './control.ts';
import {schemaName} from './config.ts';
import {publicationTime,sha256} from './material.ts';
import {canonicalGroupingInput} from './processing.ts';
import {eventsList} from './projections.ts';
import {enqueueTransaction,type JobOutput} from './queue.ts';
import {createBriefRequest,briefGet} from './brief-control.ts';
import {briefMarkdown,type BriefPayload} from './briefs.ts';
import type {PeriodicReportRenderer} from './periodic-report.ts';
import {logEvent} from './log.ts';
type Sql=ReturnType<typeof postgres>;
interface PeriodicConfig {name:string;channelId:string;enabled:boolean;firstRunAt:string;intervalSeconds:number;windowSeconds:number;maxEvents:number;timezone:string;sort:'importance'|'heat'|'recent'}
const uuid=/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i;
const fields=['name','channelId','enabled','firstRunAt','intervalSeconds','windowSeconds','maxEvents','timezone','sort'];
function plain(value:unknown):value is Record<string,unknown>{return value!==null&&typeof value==='object'&&!Array.isArray(value)&&Object.getPrototypeOf(value)===Object.prototype;}
function integer(value:unknown,min:number,max:number){return typeof value==='number'&&Number.isSafeInteger(value)&&value>=min&&value<=max;}
function json(value:unknown):postgres.JSONValue{return JSON.parse(JSON.stringify(value));}
async function assertClaim(tx:Tx,schema:string,claim:Claim,owner:RuntimeOwner){
  if(claim.owner.instanceId!==owner.instanceId||claim.owner.mode!==owner.mode||claim.owner.generation!==owner.generation)throw Error('hot_claim_stale');
  const rows=await tx`select input_key from ${tx(schema)}.job_claims where input_key=${claim.inputKey} and job_id=${claim.jobId}
    and worker_id=${claim.workerId} and lease_token=${claim.leaseToken} and generation=${owner.generation} and state='running' and lease_until>clock_timestamp()`;
  if(rows.length!==1)throw Error('hot_claim_stale');
}
function instant(value:unknown):Date|null {return typeof value==='string'&&/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?(?:Z|[+-]\d\d:\d\d)$/.test(value)?publicationTime(value,new Date(8640000000000000)):null;}
export function parsePeriodicConfig(value:unknown):PeriodicConfig{
  if(!plain(value)||Object.keys(value).some(key=>!fields.includes(key))||typeof value.name!=='string'||!value.name.trim()||value.name.length>120||typeof value.channelId!=='string'||!/^[a-z][a-z0-9_-]{0,47}$/.test(value.channelId)||typeof value.enabled!=='boolean'||
    !integer(value.intervalSeconds,60,604800)||!integer(value.windowSeconds,60,31622400)||!integer(value.maxEvents,1,20)||typeof value.timezone!=='string'||value.timezone.length>80||!['importance','heat','recent'].includes(String(value.sort)))throw Error('hot_periodic_config_invalid');
  const first=instant(value.firstRunAt);if(!first||typeof value.sort!=='string')throw Error('hot_periodic_config_invalid');
  try{new Intl.DateTimeFormat('zh-CN',{timeZone:value.timezone});}catch{throw Error('hot_periodic_config_invalid');}
  return {...value,firstRunAt:first.toISOString()} as unknown as PeriodicConfig;
}
export function nextPeriodicDue(due:Date,intervalSeconds:number,now:Date){
  if(!integer(intervalSeconds,60,604800)||!Number.isFinite(due.getTime())||!Number.isFinite(now.getTime())||now<due)throw Error('hot_periodic_due_invalid');
  const periods=Math.floor((now.getTime()-due.getTime())/(intervalSeconds*1000))+1,next=new Date(due.getTime()+periods*intervalSeconds*1000);
  if(!Number.isFinite(next.getTime()))throw Error('hot_periodic_due_invalid');return {next,missedPeriods:periods-1};
}
export function periodicIdentity(planId:string,version:number,due:string){
  if(!uuid.test(planId)||!integer(version,1,1000000)||!instant(due))throw Error('hot_periodic_due_invalid');
  const key=[planId.toLowerCase(),version,new Date(due).toISOString()].join(':');
  const id=(part:string)=>{const bytes=Buffer.from(sha256(key+':'+part).slice(0,32),'hex');bytes[6]=(bytes[6]&15)|80;bytes[8]=(bytes[8]&63)|128;const hex=bytes.toString('hex');return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;};
  return {runId:id('run'),briefId:id('brief'),requestId:id('request')};
}
export async function configurePeriodicPlan(db:Sql,schema:string,owner:RuntimeOwner,requestId:string,params:unknown){
  schemaName(schema);
  if(!uuid.test(requestId)||!plain(params)||Object.keys(params).some(key=>!['planId','expectedVersion','config','reason'].includes(key))||typeof params.planId!=='string'||!uuid.test(params.planId)||!integer(params.expectedVersion,0,999999)||typeof params.reason!=='string'||!params.reason.trim()||params.reason.length>1000)throw Error('hot_periodic_request_invalid');
  const id=params.planId.toLowerCase(),expected=Number(params.expectedVersion),config=parsePeriodicConfig(params.config);requestId=requestId.toLowerCase();
  if(expected===0&&config.enabled)throw Error('hot_periodic_enable_required');
  const reason=params.reason,value={planId:id,expectedVersion:expected,config,reason},hash=sha256(canonicalGroupingInput(value));
  try{
    const result=await withOwnerTransaction(db,schema,owner,async tx=>{
      const [permission]=await tx`select has_table_privilege(current_user,${schema+'.periodic_plan_requests'},'INSERT') allowed`;if(!permission.allowed)throw Error('hot_periodic_control_denied');
      const [cached]=await tx`select params_hash,after_state from ${tx(schema)}.periodic_plan_requests where request_id=${requestId}`;
      if(cached){if(cached.params_hash!==hash)throw Error('hot_periodic_request_conflict');return cached.after_state;}
      const [previous]=await tx`select p.current_version,v.config,p.next_due_at from ${tx(schema)}.periodic_plans p join ${tx(schema)}.periodic_plan_versions v on v.plan_id=p.id and v.version=p.current_version where p.id=${id} for update of p`;
      if((previous?.current_version??0)!==expected)throw Error('hot_periodic_version_conflict');
      if(!(await tx`select id from ${tx(schema)}.channels where id=${config.channelId}`).length)throw Error('hot_periodic_channel_invalid');
      if(!previous){const [size]=await tx`select count(*)::int count from ${tx(schema)}.periodic_plans`;if(size.count>=32)throw Error('hot_periodic_limit');}
      const reset=!previous||previous.config.firstRunAt!==config.firstRunAt||previous.config.intervalSeconds!==config.intervalSeconds;
      const due=reset?new Date(config.firstRunAt):previous.next_due_at;
      if(!previous)await tx`insert into ${tx(schema)}.periodic_plans(id,current_version,next_due_at) values(${id},${expected+1},${due})`;
      await tx`insert into ${tx(schema)}.periodic_plan_versions(plan_id,version,config) values(${id},${expected+1},${tx.json(json(config))})`;
      await tx`update ${tx(schema)}.periodic_plans set current_version=${expected+1},next_due_at=${due} where id=${id}`;
      const after={planId:id,version:expected+1,config,nextDueAt:due.toISOString(),requestId};
      await tx`insert into ${tx(schema)}.periodic_plan_requests(request_id,plan_id,params_hash,actor,reason,before_state,after_state)
        values(${requestId},${id},${hash},'local_host',${reason},${tx.json(json(previous??{}))},${tx.json(json(after))})`;
      return after;
    });logEvent('periodic_configured');return result;
  }catch(error){logEvent('periodic_failed');if(error instanceof Error&&/^hot_[a-z_]+$/.test(error.message))throw error;throw Error('hot_periodic_save_failed');}
}
export async function periodicPlans(db:Sql,schema:string,params:Record<string,postgres.JSONValue>){
  schemaName(schema);if(Object.keys(params).length)throw Error('hot_periodic_request_invalid');
  const [{cutoff}]=await db`select clock_timestamp() cutoff`;
  const rows=await db`select p.id,v.version,v.config,p.next_due_at from ${db(schema)}.periodic_plans p join ${db(schema)}.periodic_plan_versions v on v.plan_id=p.id and v.version=p.current_version order by p.id limit 32`;
  return json({cutoff,items:rows.map(row=>({planId:row.id,version:row.version,config:row.config,nextDueAt:row.next_due_at}))});
}
export async function periodicRuns(db:Sql,schema:string,params:Record<string,postgres.JSONValue>){
  schemaName(schema);if(Object.keys(params).some(key=>key!=='planId')||typeof params.planId!=='string'||!uuid.test(params.planId))throw Error('hot_periodic_request_invalid');
  const [{cutoff}]=await db`select clock_timestamp() cutoff`;
  const rows=await db`select r.*,e.execution_id,e.docx_hash,e.input_hash,octet_length(e.docx)::int report_bytes,
    (select j.state from ${db(schema)}.job j where j.name='hot.brief' and j.data->'payload'->>'runId'=r.id::text order by j.created_on desc limit 1) queue_state
    from ${db(schema)}.periodic_runs r left join ${db(schema)}.periodic_report_executions e on e.run_id=r.id
    where r.plan_id=${params.planId.toLowerCase()} order by r.due_at desc,r.id limit 50`;
  return json({cutoff,items:rows.map(row=>({runId:row.id,planId:row.plan_id,planVersion:row.plan_version,dueAt:row.due_at,missedPeriods:row.missed_periods,state:row.state,queueState:row.queue_state,errorCode:row.error_code,briefId:row.brief_version?row.brief_id:null,briefVersion:row.brief_version,contentHash:row.content_hash,createdAt:row.created_at,finishedAt:row.finished_at,
    report:row.execution_id?{state:'completed',executionId:row.execution_id,inputHash:row.input_hash,artifactHash:row.docx_hash,bytes:row.report_bytes}:null}))});
}
export async function schedulePeriodicBriefs(db:Sql,boss:PgBoss,schema:string,owner:RuntimeOwner){
  try{return await withOwnerTransaction(db,schema,owner,async tx=>{
    const [{now}]=await tx`select clock_timestamp() now`;
    const rows=await tx`select p.id,p.current_version,p.next_due_at,v.config from ${tx(schema)}.periodic_plans p join ${tx(schema)}.periodic_plan_versions v on v.plan_id=p.id and v.version=p.current_version
      where v.config->>'enabled'='true' and p.next_due_at<=${now} order by p.next_due_at,p.id for update of p skip locked limit 10`;
    for(const row of rows){
      const config=parsePeriodicConfig(row.config),due=row.next_due_at as Date,advance=nextPeriodicDue(due,config.intervalSeconds,now);
      const ids=periodicIdentity(row.id,row.current_version,due.toISOString());
      await tx`insert into ${tx(schema)}.periodic_runs(id,plan_id,plan_version,due_at,brief_id,request_id,config,missed_periods,state)
        values(${ids.runId},${row.id},${row.current_version},${due},${ids.briefId},${ids.requestId},${tx.json(json(config))},${advance.missedPeriods},'queued') on conflict(id) do nothing`;
      await enqueueTransaction(boss,tx,'hot.brief',ids.runId,{runId:ids.runId});
      await tx`update ${tx(schema)}.periodic_plans set next_due_at=${advance.next} where id=${row.id}`;
    }logEvent('periodic_scheduled',rows.length);return rows.length;
  });}catch(error){logEvent('periodic_failed');if(error instanceof Error&&/^hot_[a-z_]+$/.test(error.message))throw error;throw Error('hot_periodic_schedule_failed');}
}
export function periodicBriefHandler(db:Sql,schema:string,owner:RuntimeOwner,renderer?:PeriodicReportRenderer){
  const execute=async(payload:postgres.JSONValue,signal:AbortSignal,claim:Claim):Promise<JobOutput>=>{
    const input:unknown=payload;
    if(!plain(input)||Object.keys(input).some(key=>key!=='runId')||typeof input.runId!=='string'||!uuid.test(input.runId)||claim.inputKey!=='hot.brief:'+input.runId)throw Error('hot_periodic_request_invalid');
    const id=input.runId;
    const run=await withOwnerTransaction(db,schema,owner,async tx=>{
      await assertClaim(tx,schema,claim,owner);signal.throwIfAborted();
      const [row]=await tx`select r.*,p.current_version,v.config current_config from ${tx(schema)}.periodic_runs r join ${tx(schema)}.periodic_plans p on p.id=r.plan_id join ${tx(schema)}.periodic_plan_versions v on v.plan_id=p.id and v.version=p.current_version where r.id=${id}`;
      if(!row)throw Error('hot_periodic_run_invalid');
      if(row.state!=='queued')return row;
      if(row.current_version!==row.plan_version||!row.current_config.enabled){
        await tx`update ${tx(schema)}.periodic_runs set state='cancelled',finished_at=clock_timestamp(),error_code='hot_periodic_plan_changed' where id=${id}`;
        await assertClaim(tx,schema,claim,owner);signal.throwIfAborted();return {...row,state:'cancelled'};
      }
      return row;
    });
    if(run.state!=='queued')return {result:json({runId:id,state:run.state,briefId:run.brief_version?run.brief_id:null,version:run.brief_version})};
    const config=parsePeriodicConfig(run.config),cutoff=run.due_at.toISOString(),from=new Date(run.due_at.getTime()-config.windowSeconds*1000).toISOString();
    let selection=await withOwnerTransaction(db,schema,owner,async tx=>{
      await assertClaim(tx,schema,claim,owner);const [saved]=await tx`select selection from ${tx(schema)}.periodic_selections where run_id=${id}`;return saved?.selection;
    });
    if(!selection){
      const result=await eventsList(db,schema,{channelId:config.channelId,cutoff,from,to:cutoff,sort:config.sort,limit:config.maxEvents,offset:0}) as unknown as {items:{id:string}[]};
      const candidate={briefId:run.brief_id,expectedVersion:0,eventIds:result.items.map(row=>row.id),channelId:config.channelId,cutoff,from,to:cutoff,timezone:config.timezone};
      selection=await withOwnerTransaction(db,schema,owner,async tx=>{
        await assertClaim(tx,schema,claim,owner);signal.throwIfAborted();
        await tx`insert into ${tx(schema)}.periodic_selections(run_id,selection) values(${id},${tx.json(candidate)}) on conflict(run_id) do nothing`;
        const [saved]=await tx`select selection from ${tx(schema)}.periodic_selections where run_id=${id}`;
        await assertClaim(tx,schema,claim,owner);signal.throwIfAborted();return saved.selection;
      });
    }
    const fence=async(tx:Tx)=>{
      await assertClaim(tx,schema,claim,owner);signal.throwIfAborted();
      const [plan]=await tx`select p.current_version,v.config from ${tx(schema)}.periodic_plans p join ${tx(schema)}.periodic_plan_versions v on v.plan_id=p.id and v.version=p.current_version where p.id=${run.plan_id}`;
      if(!plan||plan.current_version!==run.plan_version||!plan.config.enabled)throw Error('hot_periodic_plan_changed');
    };
    if(!selection.eventIds.length){
      await withOwnerTransaction(db,schema,owner,async tx=>{await fence(tx);await tx`update ${tx(schema)}.periodic_runs set state='empty',error_code=null,finished_at=clock_timestamp() where id=${id}`;await fence(tx);});
      logEvent('periodic_completed');return {result:{runId:id,state:'empty',briefId:null}};
    }
    const saved=await createBriefRequest(db,schema,owner,run.request_id,selection,signal,{actor:'hot_scheduler',selection:{kind:'periodic',planId:run.plan_id,planVersion:run.plan_version,runId:id,missedPeriods:run.missed_periods},fence,
      saved:async(tx,result)=>{await tx`update ${tx(schema)}.periodic_runs set brief_version=${Number(result.version)},content_hash=${String(result.contentHash)} where id=${id}`;}});
    const meta=saved as Record<string,postgres.JSONValue>;
    const existing=await withOwnerTransaction(db,schema,owner,async tx=>{
      await fence(tx);const [row]=await tx`select execution_id,docx_hash,input_hash from ${tx(schema)}.periodic_report_executions where run_id=${id}`;return row;
    });
    let report=existing;
    if(!report){
      if(!renderer)throw Error('hot_periodic_report_unavailable');
      const frozen=await briefGet(db,schema,{briefId:String(meta.briefId),version:Number(meta.version)});
      const body=frozen as Record<string,postgres.JSONValue>;
      if(body.contentHash!==meta.contentHash)throw Error('hot_brief_integrity_invalid');
      const markdown=briefMarkdown({payload:body.payload as unknown as BriefPayload,contentHash:String(body.contentHash)});
      const data=await renderer(frozen,signal);signal.throwIfAborted();
      if(!Buffer.isBuffer(data)||data.length<1||data.length>5242880||Buffer.byteLength(markdown)>4000000)throw Error('hot_periodic_report_limit');
      const executionId=sha256('rwb-report-documents-v1:'+id+':'+String(meta.contentHash));
      report=await withOwnerTransaction(db,schema,owner,async tx=>{
        await fence(tx);
        await tx`insert into ${tx(schema)}.periodic_report_executions(run_id,execution_id,brief_id,brief_version,input_hash,renderer,markdown,markdown_hash,docx,docx_hash)
          values(${id},${executionId},${String(meta.briefId)},${Number(meta.version)},${String(meta.contentHash)},'rwb-report-documents-v1',${markdown},${sha256(markdown)},${data},${sha256(data)}) on conflict(run_id) do nothing`;
        const [row]=await tx`select execution_id,docx_hash,input_hash from ${tx(schema)}.periodic_report_executions where run_id=${id}`;
        await fence(tx);return row;
      });
    }
    if(report.input_hash!==meta.contentHash)throw Error('hot_periodic_report_conflict');
    return {result:json({runId:id,state:'completed',...JSON.parse(JSON.stringify(saved)),report:{executionId:report.execution_id,artifactHash:report.docx_hash,inputHash:report.input_hash,state:'completed'}}),
      commit:async tx=>{await fence(tx);await tx`update ${tx(schema)}.periodic_runs set state='completed',error_code=null,finished_at=clock_timestamp() where id=${id}`;await fence(tx);logEvent('periodic_completed');}};
  };
  return async(payload:postgres.JSONValue,signal:AbortSignal,claim:Claim):Promise<JobOutput>=>{
    try{return await execute(payload,signal,claim);}
    catch(error){
      logEvent('periodic_failed');
      if(error instanceof Error&&['hot_owner_stale','hot_claim_stale'].includes(error.message))throw error;
      const input:unknown=payload;
      if(plain(input)&&typeof input.runId==='string'&&uuid.test(input.runId)&&claim.inputKey==='hot.brief:'+input.runId){
        const id=input.runId,code=error instanceof Error&&/^hot_[a-z_]+$/.test(error.message)?error.message:'hot_periodic_brief_failed';
        await withOwnerTransaction(db,schema,owner,async tx=>{await assertClaim(tx,schema,claim,owner);await tx`update ${tx(schema)}.periodic_runs set error_code=${code} where id=${id} and state='queued'`;await assertClaim(tx,schema,claim,owner);});
      }
      throw error instanceof Error&&/^hot_[a-z_]+$/.test(error.message)?error:Error('hot_periodic_brief_failed');
    }
  };
}
