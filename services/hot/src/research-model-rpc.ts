/** Private Host-only research ledger operations. Never sends a provider request. */
import type postgres from 'postgres';
import {withOwnerTransaction,type RuntimeOwner} from './control.ts';
import type {RpcHandler} from './transport.ts';
import {reserveResearchModelCall} from './research-model.ts';
import {markModelDispatchInTransaction,markModelUnknown,cancelUnsentModel,saveModelReceipt,type ModelTicket} from './model-budget.ts';
import {textUsage} from './dsh-text.ts';
import {sha256} from './material.ts';
import {canonicalGroupingInput} from './processing.ts';
import {logEvent} from './log.ts';
type Params=Record<string,postgres.JSONValue>;
const UUID=/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;

export function researchStreamReceipt(value:unknown,tariff:Record<string,any>){
  const invalid=()=>{throw Error('hot_research_receipt_invalid');};
  if(!Array.isArray(value)||value.length<2||value.length>8192||Buffer.byteLength(JSON.stringify(value))>1048576)invalid();
  const chunks=JSON.parse(JSON.stringify(value)) as Record<string,any>[];
  const types=new Set(['block-start','text-delta','reasoning-delta','tool-call-delta','block-end','usage','finish']);
  if(chunks.some(c=>!c||typeof c!=='object'||Array.isArray(c)||!types.has(c.type))||chunks.filter(c=>c.type==='usage').length!==1||chunks.filter(c=>c.type==='finish').length!==1)invalid();
  const finish=chunks.at(-1)!;
  if(finish.type!=='finish'||!['stop','tool-calls','max-tokens','error','aborted'].includes(finish.reason?.kind))invalid();
  let usage;try{usage=textUsage(chunks.find(c=>c.type==='usage')!.usage);}catch{invalid();}
  const u=usage!;
  const numerator=BigInt(u.inputTokens)*BigInt(tariff.inputMicrosPerMillion)+BigInt(u.cacheReadTokens)*BigInt(tariff.cacheReadMicrosPerMillion)+BigInt(u.cacheWriteTokens)*BigInt(tariff.cacheWriteMicrosPerMillion)+BigInt(u.outputTokens)*BigInt(tariff.outputMicrosPerMillion);
  const response:postgres.JSONValue={chunks,...(['error','aborted'].includes(finish.reason.kind)?{rejected:true}:{})};
  return {response,tokens:u.totalTokens,costMicros:Number((numerator+999999n)/1000000n)};
}

export function researchModelHandlers(db:postgres.Sql,schema:string,owner:RuntimeOwner,scopeId:string,
  currentPrice:()=>unknown,today:()=>string):Array<[string,RpcHandler]>{
  const guarded=(run:(params:Params)=>Promise<postgres.JSONValue>):RpcHandler=>({permission:'control',run:async params=>{
    try{return await run(params);}catch(error){logEvent('model_blocked');if(error instanceof Error&&/^hot_[a-z_]+$/.test(error.message))throw error;throw Error('hot_research_model_failed');}
  }});
  const binding=async(params:Params,extras:string[]=[],reader=db)=>{
    const keys=['runId','sessionId','callId','ticket',...extras];
    if(Object.keys(params).length!==keys.length||Object.keys(params).some(k=>!keys.includes(k))||['runId','sessionId','callId'].some(k=>typeof params[k]!=='string'||!UUID.test(params[k] as string)))throw Error('hot_research_model_invalid');
    const t=params.ticket as unknown as ModelTicket;
    if(!t||typeof t!=='object'||Array.isArray(t)||Object.keys(t).sort().join(',')!=='id,token'||!UUID.test(t.id)||typeof t.token!=='string'||!/^[a-f0-9]{64}$/.test(t.token))throw Error('hot_model_ticket_invalid');
    const [row]=await reader`select c.tariff,a.state,a.generation::text,a.scope_id,i.session_id,r.state run_state
      from ${reader(schema)}.research_model_calls c join ${reader(schema)}.research_inputs i on i.id=c.run_id
      join ${reader(schema)}.research_runs r on r.id=i.id join ${reader(schema)}.model_attempts a on a.id=c.attempt_id
      where c.id=${params.callId as string} and c.run_id=${params.runId as string} and c.attempt_id=${t.id} and a.dispatch_token_hash=${sha256(t.token)}`;
    if(!row||row.session_id!==params.sessionId||row.scope_id!==scopeId)throw Error('hot_research_model_binding_denied');
    return {ticket:t,row};
  };
  return [
    ['research.model.reserve',guarded(params=>reserveResearchModelCall(db,schema,owner,scopeId,currentPrice(),today(),params) as Promise<postgres.JSONValue>)],
    ['research.model.dispatch',guarded(async params=>withOwnerTransaction(db,schema,owner,async tx=>{
      const {ticket,row}=await binding(params,[],tx as unknown as postgres.Sql);
      // A stale tariff or terminal run cannot start a new provider send.
      const price=currentPrice() as Record<string,any>|null;
      if(!price||row.tariff.verifiedOn!==today()||price.verifiedOn!==today()||canonicalGroupingInput(price)!==canonicalGroupingInput(row.tariff)||!['execution_starting','running'].includes(row.run_state))throw Error('hot_research_model_denied');
      await markModelDispatchInTransaction(tx,schema,owner,ticket);return {state:'dispatching'};
    }))],
    ['research.model.unknown',guarded(async params=>{const {ticket,row}=await binding(params);if(['outcome_unknown','received'].includes(row.state))return {state:row.state};await markModelUnknown(db,schema,ticket);return {state:'outcome_unknown'};})],
    ['research.model.cancel',guarded(async params=>{const {ticket,row}=await binding(params);if(row.state!=='cancelled')await cancelUnsentModel(db,schema,owner,ticket.id);return {state:'cancelled'};})],
    ['research.model.receipt',guarded(async params=>{
      const {ticket,row}=await binding(params,['chunks','providerRequestId']);
      if(params.providerRequestId!==null&&(typeof params.providerRequestId!=='string'||params.providerRequestId.length<1||params.providerRequestId.length>256))throw Error('hot_research_receipt_invalid');
      const receipt=researchStreamReceipt(params.chunks,row.tariff);
      const result=await saveModelReceipt(db,schema,ticket,receipt.response,{tokens:receipt.tokens,costMicros:receipt.costMicros,providerRequestId:params.providerRequestId as string|null,costBasis:'tariff-ceiling'});
      return {state:'received',...result};
    })],
  ];
}
