/** Research shares Hot's sole cumulative ledger. No provider dispatch occurs here. */
import type postgres from 'postgres';
import {withOwnerTransaction,type RuntimeOwner} from './control.ts';
import {reserveModelInTransaction,lookupModelInTransaction} from './model-budget.ts';
import {validatePricing} from './pricing.ts';
import {canonicalGroupingInput} from './processing.ts';
import {sha256} from './material.ts';
import {schemaName} from './config.ts';
import {logEvent} from './log.ts';
type Sql=ReturnType<typeof postgres>;
type Params=Record<string,postgres.JSONValue>;
const UUID=/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
export async function reserveResearchModelCall(db:Sql,schema:string,owner:RuntimeOwner,scopeId:string,price:unknown,today:string,params:Params){
  schemaName(schema);
  const keys=['runId','sessionId','callId','requestHash','provider','model','inputTokenBound','maxOutputTokens'];
  if(Object.keys(params).length!==keys.length||Object.keys(params).some(key=>!keys.includes(key))||
    ['runId','sessionId','callId'].some(key=>typeof params[key]!=='string'||!UUID.test(params[key] as string))||
    typeof params.requestHash!=='string'||!/^[a-f0-9]{64}$/.test(params.requestHash)||params.provider!=='deepseek-official'||
    typeof params.inputTokenBound!=='number'||!Number.isSafeInteger(params.inputTokenBound)||params.inputTokenBound<1||params.inputTokenBound>1000000||
    typeof params.maxOutputTokens!=='number'||!Number.isSafeInteger(params.maxOutputTokens)||params.maxOutputTokens<1||params.maxOutputTokens>4096)
    throw Error('hot_research_model_invalid');
  const inputTokenBound=params.inputTokenBound,maxOutputTokens=params.maxOutputTokens;
  params=Object.freeze({...params});
  const paramsHash=sha256(canonicalGroupingInput({scopeId,...params}));
  try{return await withOwnerTransaction(db,schema,owner,async tx=>{
    const [permission]=await tx`select has_table_privilege(current_user,${schema+'.research_model_calls'},'INSERT') allowed`;
    if(!permission.allowed)throw Error('hot_research_control_denied');
    const [run]=await tx`select i.session_id,r.state from ${tx(schema)}.research_inputs i join ${tx(schema)}.research_runs r on r.id=i.id where i.id=${params.runId as string}`;
    if(!run||run.session_id!==params.sessionId)throw Error('hot_research_session_invalid');
    const [prior]=await tx`select c.run_id,c.params_hash,c.attempt_id,a.result_key,a.spec_hash,a.scope_id,a.state attempt_state,r.attempt_id cache_attempt_id
      from ${tx(schema)}.research_model_calls c join ${tx(schema)}.model_attempts a on a.id=c.attempt_id
      left join ${tx(schema)}.model_results r on r.result_key=a.result_key where c.id=${params.callId as string}`;
    if(prior){
      if(prior.run_id!==params.runId||prior.params_hash!==paramsHash||prior.scope_id!==scopeId)throw Error('hot_research_request_conflict');
      if(prior.attempt_state==='cancelled'||prior.cache_attempt_id!==null&&prior.cache_attempt_id!==prior.attempt_id)throw Error('hot_research_model_attempt_changed');
      const saved=await lookupModelInTransaction(tx,schema,{resultKey:prior.result_key,specHash:prior.spec_hash});
      if(!saved||saved.state==='busy'&&saved.attemptId!==prior.attempt_id)throw Error('hot_research_model_attempt_changed');
      return saved;
    }
    if(!['execution_starting','running'].includes(run.state))throw Error('hot_research_execution_not_active');
    const tariff=validatePricing(price,today);
    if(params.model!==tariff.requestedModel||owner.mode!=='native')throw Error('hot_research_model_denied');
    const tariffHash=sha256(canonicalGroupingInput(tariff));
    const specHash=sha256(canonicalGroupingInput({stage:'hot-research-call-v1',scopeId,...params,tariffHash}));
    const maxTokens=inputTokenBound+maxOutputTokens;
    const numerator=BigInt(inputTokenBound)*BigInt(Math.max(tariff.inputMicrosPerMillion,tariff.cacheReadMicrosPerMillion,tariff.cacheWriteMicrosPerMillion))+
      BigInt(maxOutputTokens)*BigInt(tariff.outputMicrosPerMillion);
    const maxCostMicros=Number((numerator+999999n)/1000000n);
    const admission=await reserveModelInTransaction(tx,schema,owner,scopeId,{resultKey:specHash,specHash,maxTokens,maxCostMicros});
    if(admission.state!=='reserved')throw Error('hot_research_model_mapping_missing');
      await tx`insert into ${tx(schema)}.research_model_calls(id,run_id,attempt_id,params_hash,request_hash,provider,model,input_token_bound,max_output_tokens,tariff_hash,tariff)
        values(${params.callId as string},${params.runId as string},${admission.ticket.id},${paramsHash},${params.requestHash as string},${params.provider as string},${params.model as string},${params.inputTokenBound as number},${params.maxOutputTokens as number},${tariffHash},${tx.json(tariff)})`;
    logEvent('model_controlled');return admission;
  });}catch(error){logEvent('model_blocked');
    if(error instanceof Error&&/^hot_[a-z_]+$/.test(error.message))throw error;
    throw Error('hot_research_model_failed');
  }
}
