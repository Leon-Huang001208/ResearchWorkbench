/** Cumulative authorization and durable paid-attempt receipts. No provider dispatch here. */
import type postgres from 'postgres';
import {randomUUID,randomBytes} from 'node:crypto';
import {withOwnerTransaction,type RuntimeOwner,type Tx} from './control.ts';
import {schemaName} from './config.ts';
import {sha256} from './material.ts';
import {logEvent} from './log.ts';
type Sql=ReturnType<typeof postgres>;
export interface BudgetPolicy {scopeId:string;authorizationHash:string;maxCalls:number;maxTokens:number;maxCostMicros:number;
  daily?:{maxCalls:number;maxTokens:number;maxCostMicros:number;timezone:string}}
export interface ModelSpec {resultKey:string;specHash:string;maxTokens:number;maxCostMicros:number;
  legacySpecs?:Array<{resultKey:string;specHash:string}>}
export interface ModelTicket {id:string;token:string}
export type ModelReservation={state:'reserved';ticket:ModelTicket}|{state:'busy';attemptId:string}|{state:'reused';response:postgres.JSONValue;resultKey?:string};
function amount(value:number,maximum=10000000000){if(!Number.isSafeInteger(value)||value<0||value>maximum)throw Error('hot_model_budget_invalid');}
function hash(value:string){if(!/^[a-f0-9]{64}$/.test(value))throw Error('hot_model_spec_invalid');}
function scope(value:string){if(!/^[a-z][a-z0-9_-]{0,63}$/.test(value))throw Error('hot_model_scope_invalid');}
function ticket(value:ModelTicket){if(!/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(value.id)||!/^[a-f0-9]{64}$/.test(value.token))throw Error('hot_model_ticket_invalid');}
function responseText(value:postgres.JSONValue):string{
  const plain=JSON.parse(JSON.stringify(value));
  const canonical=(item:unknown):unknown=>Array.isArray(item)?item.map(canonical):item&&typeof item==='object'?
    Object.fromEntries(Object.entries(item).sort(([a],[b])=>a<b?-1:a>b?1:0).map(([key,part])=>[key,canonical(part)])):item;
  return JSON.stringify(canonical(plain));
}
export async function provisionModelBudget(db:Sql,schema:string,policy:BudgetPolicy):Promise<void>{
  schemaName(schema);scope(policy.scopeId);hash(policy.authorizationHash);
  amount(policy.maxCalls,10000);amount(policy.maxTokens,10000000);amount(policy.maxCostMicros);
  const daily=policy.daily??{maxCalls:policy.maxCalls,maxTokens:policy.maxTokens,maxCostMicros:policy.maxCostMicros,timezone:'Asia/Shanghai'};
  amount(daily.maxCalls,10000);amount(daily.maxTokens,10000000);amount(daily.maxCostMicros);
  try{new Intl.DateTimeFormat('en',{timeZone:daily.timezone});}catch{throw Error('hot_model_budget_invalid');}
  await db.begin(async tx=>{
    const [permission]=await tx`select has_schema_privilege(current_user,${schema},'CREATE') allowed`;
    if(!permission.allowed)throw Error('hot_model_authorization_denied');
    await tx`insert into ${tx(schema)}.model_budgets(scope_id,authorization_hash,max_calls,max_tokens,max_cost_micros,daily_max_calls,daily_max_tokens,daily_max_cost_micros,quota_timezone)
      values(${policy.scopeId},${policy.authorizationHash},${policy.maxCalls},${policy.maxTokens},${policy.maxCostMicros},${daily.maxCalls},${daily.maxTokens},${daily.maxCostMicros},${daily.timezone}) on conflict do nothing`;
    const [row]=await tx`select * from ${tx(schema)}.model_budgets where scope_id=${policy.scopeId}`;
    if(row.authorization_hash!==policy.authorizationHash||row.max_calls!==policy.maxCalls||Number(row.max_tokens)!==policy.maxTokens||Number(row.max_cost_micros)!==policy.maxCostMicros)throw Error('hot_model_authorization_conflict');
    if(row.daily_max_calls!==daily.maxCalls||Number(row.daily_max_tokens)!==daily.maxTokens||Number(row.daily_max_cost_micros)!==daily.maxCostMicros||row.quota_timezone!==daily.timezone)throw Error('hot_model_authorization_conflict');
  });
}
export async function reserveModel(db:Sql,schema:string,owner:RuntimeOwner,scopeId:string,spec:ModelSpec):Promise<ModelReservation>{
  return withOwnerTransaction(db,schema,owner,tx=>reserveModelInTransaction(tx,schema,owner,scopeId,spec));
}
/** Caller must already hold withOwnerTransaction's identity/generation fence. */
export async function reserveModelInTransaction(tx:Tx,schema:string,owner:RuntimeOwner,scopeId:string,spec:ModelSpec):Promise<ModelReservation>{
  schemaName(schema);scope(scopeId);hash(spec.resultKey);hash(spec.specHash);amount(spec.maxTokens,10000000);amount(spec.maxCostMicros);
  const legacy=spec.legacySpecs??[];
  if(!Array.isArray(legacy)||legacy.length>9)throw Error('hot_model_spec_invalid');
  for(const item of legacy){hash(item.resultKey);hash(item.specHash);}
  if(spec.maxTokens===0)throw Error('hot_model_budget_invalid');
    // Alias checks and fresh admission share saveModelReceipt's schema fence.
    // A late legacy receipt cannot land between cache miss and reservation.
    for(const compatible of [{resultKey:spec.resultKey,specHash:spec.specHash},...legacy]){
      const saved=await lookupUnlocked(tx,schema,compatible);
      if(saved)return saved;
    }
    const [policy]=await tx`select *,((clock_timestamp() at time zone quota_timezone)::date)::text as today from ${tx(schema)}.model_budgets where scope_id=${scopeId} for update`;
    if(!policy)throw Error('hot_model_budget_exhausted');
    const [used]=await tx`select count(*)::int calls,coalesce(sum(coalesce(r.tokens,a.max_tokens)),0)::text tokens,
      coalesce(sum(coalesce(r.cost_micros,a.max_cost_micros)),0)::text cost from ${tx(schema)}.model_attempts a
      left join ${tx(schema)}.model_receipts r on r.attempt_id=a.id where a.scope_id=${scopeId} and a.day_key=${policy.today} and a.state<>'cancelled'`;
    if(used.calls+1>policy.daily_max_calls||Number(used.tokens)+spec.maxTokens>Number(policy.daily_max_tokens)||Number(used.cost)+spec.maxCostMicros>Number(policy.daily_max_cost_micros))throw Error('hot_model_daily_budget_exhausted');
    const [budget]=await tx`update ${tx(schema)}.model_budgets set charged_calls=charged_calls+1,charged_tokens=charged_tokens+${spec.maxTokens},charged_cost_micros=charged_cost_micros+${spec.maxCostMicros}
      where scope_id=${scopeId} and not paused and charged_calls+1<=max_calls and charged_tokens+${spec.maxTokens}<=max_tokens
      and charged_cost_micros+${spec.maxCostMicros}<=max_cost_micros returning scope_id`;
    if(!budget)throw Error('hot_model_budget_exhausted');
    const id=randomUUID(),token=randomBytes(32).toString('hex');
    await tx`insert into ${tx(schema)}.model_attempts(id,scope_id,result_key,spec_hash,dispatch_token_hash,generation,max_tokens,max_cost_micros,state,day_key)
      values(${id},${scopeId},${spec.resultKey},${spec.specHash},${sha256(token)},${owner.generation},${spec.maxTokens},${spec.maxCostMicros},'reserved',${policy.today})`;
    logEvent('model_reserved');return {state:'reserved' as const,ticket:{id,token}};
}
/** Compatibility reads never create an attempt or mutate a quota. */
async function lookupUnlocked(db:Sql|postgres.TransactionSql,schema:string,spec:{resultKey:string;specHash:string}):Promise<
  {state:'reused';response:postgres.JSONValue;resultKey?:string}|{state:'busy';attemptId:string}|null>{
  schemaName(schema);hash(spec.resultKey);hash(spec.specHash);
  const [saved]=await db`select r.spec_hash,c.response from ${db(schema)}.model_results r
    join ${db(schema)}.model_receipts c on c.attempt_id=r.attempt_id where r.result_key=${spec.resultKey}`;
  if(saved){if(saved.spec_hash!==spec.specHash)throw Error('hot_model_spec_conflict');return {state:'reused',response:saved.response,resultKey:spec.resultKey};}
  const [pending]=await db`select id,spec_hash from ${db(schema)}.model_attempts where result_key=${spec.resultKey}
    and state in ('reserved','dispatching','outcome_unknown','abandoned')`;
  if(pending){if(pending.spec_hash!==spec.specHash)throw Error('hot_model_spec_conflict');return {state:'busy',attemptId:pending.id};}
  return null;
}
export async function lookupModel(db:Sql,schema:string,spec:{resultKey:string;specHash:string}){
  schemaName(schema);hash(spec.resultKey);hash(spec.specHash);
  return db.begin(async tx=>{
    await tx`select pg_advisory_xact_lock(hashtextextended(${schema},231501))`;
    return lookupUnlocked(tx,schema,spec);
  });
}
/** Read an existing result under a caller-held schema fence; never admits or refunds. */
export async function lookupModelInTransaction(tx:Tx,schema:string,spec:{resultKey:string;specHash:string}){
  return lookupUnlocked(tx,schema,spec);
}
export async function markModelDispatch(db:Sql,schema:string,owner:RuntimeOwner,value:ModelTicket):Promise<void>{
  ticket(value);
  await withOwnerTransaction(db,schema,owner,async tx=>{
    await markModelDispatchInTransaction(tx,schema,owner,value);
  });
}
/** Caller holds the owner fence, allowing research-state admission to be atomic. */
export async function markModelDispatchInTransaction(tx:Tx,schema:string,owner:RuntimeOwner,value:ModelTicket):Promise<void>{
    ticket(value);
    const [attempt]=await tx`select scope_id,max_tokens,max_cost_micros from ${tx(schema)}.model_attempts where id=${value.id}
      and dispatch_token_hash=${sha256(value.token)} and generation=${owner.generation} and state='reserved'`;
    if(!attempt)throw Error('hot_model_dispatch_denied');
    // This row lock serializes dispatch admission with late provider accounting.
    const [budget]=await tx`select *,((clock_timestamp() at time zone quota_timezone)::date)::text as today from ${tx(schema)}.model_budgets where scope_id=${attempt.scope_id} for update`;
    if(!budget||budget.paused||budget.charged_calls>budget.max_calls||Number(budget.charged_tokens)>Number(budget.max_tokens)||Number(budget.charged_cost_micros)>Number(budget.max_cost_micros))throw Error('hot_model_budget_exhausted');
    const [used]=await tx`select count(*)::int calls,coalesce(sum(coalesce(r.tokens,a.max_tokens)),0)::text tokens,
      coalesce(sum(coalesce(r.cost_micros,a.max_cost_micros)),0)::text cost from ${tx(schema)}.model_attempts a left join ${tx(schema)}.model_receipts r on r.attempt_id=a.id
      where a.scope_id=${attempt.scope_id} and a.day_key=${budget.today} and a.state<>'cancelled' and a.id<>${value.id}`;
    if(used.calls+1>budget.daily_max_calls||Number(used.tokens)+Number(attempt.max_tokens)>Number(budget.daily_max_tokens)||Number(used.cost)+Number(attempt.max_cost_micros)>Number(budget.daily_max_cost_micros))throw Error('hot_model_daily_budget_exhausted');
    const rows=await tx`update ${tx(schema)}.model_attempts set state='dispatching',dispatched_at=clock_timestamp(),day_key=${budget.today}
      where id=${value.id} and dispatch_token_hash=${sha256(value.token)} and generation=${owner.generation} and state='reserved' returning id`;
    if(rows.length!==1)throw Error('hot_model_dispatch_denied');
}
export async function markModelUnknown(db:Sql,schema:string,value:ModelTicket):Promise<void>{
  schemaName(schema);ticket(value);
  const rows=await db`update ${db(schema)}.model_attempts set state='outcome_unknown' where id=${value.id}
    and dispatch_token_hash=${sha256(value.token)} and state='dispatching' returning id`;
  if(rows.length!==1)throw Error('hot_model_attempt_state_conflict');
  logEvent('model_unknown');
}
export async function cancelUnsentModel(db:Sql,schema:string,owner:RuntimeOwner,id:string):Promise<void>{
  await withOwnerTransaction(db,schema,owner,async tx=>{
    const [row]=await tx`select * from ${tx(schema)}.model_attempts where id=${id} for update`;
    if(!row||row.state!=='reserved')throw Error('hot_model_cancel_denied');
    await tx`update ${tx(schema)}.model_attempts set state='cancelled',finished_at=clock_timestamp() where id=${id}`;
    await tx`update ${tx(schema)}.model_budgets set charged_calls=charged_calls-1,charged_tokens=charged_tokens-${row.max_tokens},charged_cost_micros=charged_cost_micros-${row.max_cost_micros} where scope_id=${row.scope_id}`;
  });
}
export async function saveModelReceipt(db:Sql,schema:string,value:ModelTicket,response:postgres.JSONValue,usage:{tokens:number;costMicros:number;providerRequestId:string|null;costBasis?:'provider'|'tariff-ceiling'|'synthetic'}):Promise<{overrun:boolean}>{
  schemaName(schema);ticket(value);amount(usage.tokens,10000000);amount(usage.costMicros);
  const basis=usage.costBasis??'provider';if(!['provider','tariff-ceiling','synthetic'].includes(basis))throw Error('hot_model_receipt_invalid');
  if((usage.providerRequestId!==null&&(typeof usage.providerRequestId!=='string'||usage.providerRequestId.length<1||usage.providerRequestId.length>256))||Buffer.byteLength(JSON.stringify(response))>1048576)throw Error('hot_model_receipt_invalid');
  return db.begin(async tx=>{
    // Share reservation's serialization fence without requiring the old runtime
    // generation to remain active. A cache miss cannot race a receipt becoming visible.
    await tx`select pg_advisory_xact_lock(hashtextextended(${schema},231501))`;
    // Receipt persistence survives a runtime lease loss. Business publication still
    // uses commitClaim; a late response cannot acknowledge a stale worker's task.
    const [attempt]=await tx`select * from ${tx(schema)}.model_attempts where id=${value.id} and dispatch_token_hash=${sha256(value.token)} for update`;
    if(!attempt)throw Error('hot_model_ticket_denied');
    const digest=sha256(responseText(response));
    const [saved]=await tx`select * from ${tx(schema)}.model_receipts where attempt_id=${value.id}`;
    if(saved){
      if(saved.response_hash!==digest||Number(saved.tokens)!==usage.tokens||Number(saved.cost_micros)!==usage.costMicros||saved.provider_request_id!==usage.providerRequestId||saved.cost_basis!==basis)throw Error('hot_model_receipt_conflict');
      return {overrun:usage.tokens>Number(attempt.max_tokens)||usage.costMicros>Number(attempt.max_cost_micros)};
    }
    if(!['dispatching','outcome_unknown','abandoned'].includes(attempt.state))throw Error('hot_model_attempt_state_conflict');
    const overrun=usage.tokens>Number(attempt.max_tokens)||usage.costMicros>Number(attempt.max_cost_micros);
    await tx`insert into ${tx(schema)}.model_receipts(attempt_id,response,response_hash,tokens,cost_micros,provider_request_id,cost_basis)
      values(${value.id},${tx.json(response)},${digest},${usage.tokens},${usage.costMicros},${usage.providerRequestId},${basis})`;
    await tx`update ${tx(schema)}.model_budgets set charged_tokens=charged_tokens-${attempt.max_tokens}+${usage.tokens},
      charged_cost_micros=charged_cost_micros-${attempt.max_cost_micros}+${usage.costMicros},paused=paused or ${overrun} where scope_id=${attempt.scope_id}`;
    await tx`update ${tx(schema)}.model_attempts set state='received',finished_at=clock_timestamp() where id=${value.id}`;
    await tx`insert into ${tx(schema)}.model_results(result_key,spec_hash,attempt_id) values(${attempt.result_key},${attempt.spec_hash},${value.id})`;
    logEvent('model_receipt_saved');return {overrun};
  }) as Promise<{overrun:boolean}>;
}
