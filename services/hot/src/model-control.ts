/** Explicit offline migration-owner controls, never a paid worker capability. */
import type postgres from 'postgres';
import {schemaName} from './config.ts';
import {sha256} from './material.ts';
import {canonicalGroupingInput} from './processing.ts';
import {logEvent} from './log.ts';
type Sql=ReturnType<typeof postgres>;
interface Identity {instanceId:string;controllerToken:string}
interface Request {requestId:string;operator:string;reason:string;operation:'authorize'|'terminate';parameters:unknown}
const UUID=/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i;
function object(value:unknown,keys:string[]):Record<string,any>{
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(k=>!keys.includes(k)))throw Error('hot_model_control_invalid');
  return value as Record<string,any>;
}
function amount(value:unknown,max:number):number{
  if(typeof value!=='number'||!Number.isSafeInteger(value)||value<0||value>max)throw Error('hot_model_control_invalid');return value;
}
function scope(value:unknown):string{if(typeof value!=='string'||!/^[a-z][a-z0-9_-]{0,63}$/.test(value))throw Error('hot_model_control_invalid');return value;}
function policy(value:unknown){
  const p=object(value,['scopeId','maxCalls','maxTokens','maxCostMicros','daily']);
  const d=object(p.daily,['maxCalls','maxTokens','maxCostMicros','timezone']);
  if(typeof d.timezone!=='string'||d.timezone.length>80)throw Error('hot_model_control_invalid');
  try{new Intl.DateTimeFormat('en',{timeZone:d.timezone});}catch{throw Error('hot_model_control_invalid');}
  return {scopeId:scope(p.scopeId),maxCalls:amount(p.maxCalls,10000),maxTokens:amount(p.maxTokens,10000000),maxCostMicros:amount(p.maxCostMicros,10000000000),
    daily:{maxCalls:amount(d.maxCalls,10000),maxTokens:amount(d.maxTokens,10000000),maxCostMicros:amount(d.maxCostMicros,10000000000),timezone:d.timezone}};
}
export async function modelControl(db:Sql,schema:string,identity:Identity,request:Request):Promise<Record<string,any>>{
  schemaName(schema);object(request,['requestId','operator','reason','operation','parameters']);
  if(!UUID.test(request.requestId)||!UUID.test(identity.instanceId)||!/^[A-Za-z0-9_-]{32,128}$/.test(identity.controllerToken)||
    typeof request.operator!=='string'||!request.operator.trim()||request.operator.length>200||
    typeof request.reason!=='string'||!request.reason.trim()||request.reason.length>2000||!['authorize','terminate'].includes(request.operation))throw Error('hot_model_control_invalid');
  const id=request.requestId.toLowerCase(),params=object(request.parameters,request.operation==='authorize'?['policy','authorizePaid']:['attemptId']);
  if(request.operation==='authorize'&&params.authorizePaid!==true)throw Error('hot_model_paid_authorization_required');
  const authorized=request.operation==='authorize'?policy(params.policy):undefined;
  if(request.operation==='terminate'&&(typeof params.attemptId!=='string'||!UUID.test(params.attemptId)))throw Error('hot_model_control_invalid');
  const normalized={operation:request.operation,operator:request.operator.trim(),reason:request.reason.trim(),parameters:authorized?{policy:authorized,authorizePaid:true}:{attemptId:params.attemptId.toLowerCase()}};
  const hash=sha256(canonicalGroupingInput(normalized));
  const response=await db.begin(async tx=>{
    await tx`select pg_advisory_xact_lock(hashtextextended(${schema},231501))`;
    const [permission]=await tx`select has_schema_privilege(current_user,${schema},'CREATE') allowed`;
    if(!permission.allowed)throw Error('hot_model_control_denied');
    const [installed]=await tx`select instance_id,controller_token_hash,paused,owner_until<=clock_timestamp() expired from ${tx(schema)}.runtime_identity where singleton`;
    if(!installed||installed.instance_id!==identity.instanceId||installed.controller_token_hash!==sha256(identity.controllerToken))throw Error('hot_model_control_instance_mismatch');
    if(!installed.paused&&!installed.expired)throw Error('hot_model_control_requires_stopped');
    const [replayed]=await tx`select input_hash,response from ${tx(schema)}.model_control_requests where request_id=${id}`;
    if(replayed){if(replayed.input_hash!==hash)throw Error('hot_model_control_request_conflict');return replayed.response;}
    let before:postgres.JSONValue=null,result:Record<string,any>;
    if(authorized){
      const [existing]=await tx`select * from ${tx(schema)}.model_budgets where scope_id=${authorized.scopeId}`;
      if(existing){
        if(existing.max_calls!==authorized.maxCalls||Number(existing.max_tokens)!==authorized.maxTokens||Number(existing.max_cost_micros)!==authorized.maxCostMicros||
          existing.daily_max_calls!==authorized.daily.maxCalls||Number(existing.daily_max_tokens)!==authorized.daily.maxTokens||
          Number(existing.daily_max_cost_micros)!==authorized.daily.maxCostMicros||existing.quota_timezone!==authorized.daily.timezone)throw Error('hot_model_authorization_conflict');
        before=JSON.parse(JSON.stringify(existing));
      }else await tx`insert into ${tx(schema)}.model_budgets(scope_id,authorization_hash,max_calls,max_tokens,max_cost_micros,daily_max_calls,daily_max_tokens,daily_max_cost_micros,quota_timezone)
        values(${authorized.scopeId},${hash},${authorized.maxCalls},${authorized.maxTokens},${authorized.maxCostMicros},${authorized.daily.maxCalls},${authorized.daily.maxTokens},${authorized.daily.maxCostMicros},${authorized.daily.timezone})`;
      const [current]=await tx`select authorization_hash,charged_calls,charged_tokens::text,charged_cost_micros::text,paused from ${tx(schema)}.model_budgets where scope_id=${authorized.scopeId}`;
      result={state:'authorized',requestId:id,scopeId:authorized.scopeId,policy:authorized,authorizationHash:current.authorization_hash,
        charged:{calls:current.charged_calls,tokens:current.charged_tokens,costMicros:current.charged_cost_micros},paused:current.paused};
    }else{
      const [attempt]=await tx`select id,scope_id,state,dispatched_at,max_tokens::text,max_cost_micros::text,
        exists(select 1 from ${tx(schema)}.model_receipts r where r.attempt_id=a.id) has_receipt
        from ${tx(schema)}.model_attempts a where id=${params.attemptId} for update`;
      if(!attempt||!['reserved','dispatching','outcome_unknown'].includes(attempt.state)||attempt.state==='reserved'&&(attempt.dispatched_at!==null||attempt.has_receipt))throw Error('hot_model_termination_invalid');
      before=JSON.parse(JSON.stringify(attempt));
      if(attempt.state==='reserved'){
        await tx`update ${tx(schema)}.model_attempts set state='cancelled',finished_at=clock_timestamp() where id=${attempt.id}`;
        await tx`update ${tx(schema)}.model_budgets set charged_calls=charged_calls-1,charged_tokens=charged_tokens-${attempt.max_tokens},charged_cost_micros=charged_cost_micros-${attempt.max_cost_micros} where scope_id=${attempt.scope_id}`;
        result={state:'cancelled',requestId:id,attemptId:attempt.id,scopeId:attempt.scope_id,chargesRetained:false,knownUnsent:true};
      }else{
        await tx`update ${tx(schema)}.model_attempts set state='abandoned',finished_at=clock_timestamp() where id=${attempt.id}`;
        result={state:'abandoned',requestId:id,attemptId:attempt.id,scopeId:attempt.scope_id,chargesRetained:true};
      }
    }
    await tx`insert into ${tx(schema)}.model_control_requests(request_id,operation,input_hash,operator,reason,before_state,after_state,response)
      values(${id},${request.operation},${hash},${normalized.operator},${normalized.reason},${tx.json(before)},${tx.json(result)},${tx.json(result)})`;
    return result;
  });
  logEvent('model_controlled');return JSON.parse(JSON.stringify(response));
}
export async function modelAttempts(db:Sql,schema:string,query:{scopeId?:string;limit?:number;offset?:number}={}){
  schemaName(schema);object(query,['scopeId','limit','offset']);
  const id=query.scopeId===undefined?null:scope(query.scopeId),limit=amount(query.limit??50,50),offset=amount(query.offset??0,10000);
  if(limit<1)throw Error('hot_model_control_invalid');
  const rows=await db`select a.id,a.scope_id,a.result_key,a.spec_hash,a.generation::text,a.state,a.max_tokens::text reserved_tokens,a.max_cost_micros::text reserved_cost_micros,
    a.created_at,a.dispatched_at,a.finished_at,r.tokens::text,r.cost_micros::text,r.provider_request_id,r.cost_basis,r.received_at,
    b.charged_calls,b.charged_tokens::text,b.charged_cost_micros::text,b.max_calls budget_max_calls,b.max_tokens::text budget_max_tokens,b.max_cost_micros::text budget_max_cost_micros,b.paused
    from ${db(schema)}.model_attempts a join ${db(schema)}.model_budgets b on b.scope_id=a.scope_id
    left join ${db(schema)}.model_receipts r on r.attempt_id=a.id where (${id}::text is null or a.scope_id=${id})
    order by a.created_at desc,a.id limit ${limit} offset ${offset}`;
  const budgets=await db`select scope_id,max_calls,max_tokens::text,max_cost_micros::text,charged_calls,charged_tokens::text,charged_cost_micros::text,
    daily_max_calls,daily_max_tokens::text,daily_max_cost_micros::text,quota_timezone,paused from ${db(schema)}.model_budgets
    where (${id}::text is null or scope_id=${id}) order by scope_id limit 50`;
  return {items:JSON.parse(JSON.stringify([...rows])) as Record<string,any>[],budgets:JSON.parse(JSON.stringify([...budgets])) as Record<string,any>[],scopeId:id,limit,offset};
}
