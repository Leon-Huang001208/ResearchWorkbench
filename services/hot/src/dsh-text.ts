/** Session-free adapter for the pinned DSH prepared-call API. Never resolves/copies API keys. */
import {randomUUID} from 'node:crypto';
import {sha256} from './material.ts';
import type {ModelSpec,ModelTicket} from './model-budget.ts';
import type postgres from 'postgres';

interface CallConfig {provider:string;model:string;maxTokens:number;temperature:number;reasoningEffort?:string}
interface CallOptions extends CallConfig {system:string;messages:Array<{id:string;role:'user';source:{kind:'user'};content:Array<{type:'text';text:string}>}>;signal:AbortSignal}
export interface DshRuntime {
  listModels(provider:string):Promise<Array<{provider:string;id:string;name:string}>>;
  prepareCall(config:CallConfig,signal:AbortSignal):Promise<{config:CallConfig;retryPolicy:{mode:string;maxRetries?:number};stream(options:CallOptions):AsyncIterable<Record<string,unknown>>}>;
}
export interface TextLedger {
  reserve(spec:ModelSpec):Promise<{state:'reserved';ticket:ModelTicket}|{state:'busy';attemptId:string}|{state:'reused';response:postgres.JSONValue}>;
  dispatch(ticket:ModelTicket):Promise<void>;
  unknown(ticket:ModelTicket):Promise<void>;
  save(ticket:ModelTicket,response:postgres.JSONValue,usage:{tokens:number;costMicros:number;providerRequestId:string|null;costBasis:'tariff-ceiling'}):Promise<{overrun:boolean}>;
  cancelUnsent(ticket:ModelTicket):Promise<void>;
}
export interface TextTariff {
  versionHash:string;
  inputMicrosPerMillion:number;cacheReadMicrosPerMillion:number;cacheWriteMicrosPerMillion:number;outputMicrosPerMillion:number;
}
export interface TextUsage {inputTokens:number;outputTokens:number;cacheReadTokens:number;cacheWriteTokens:number;totalTokens:number}
export interface TextRequest {provider:string;model:string;promptVersion:string;system:string;text:string;maxOutputTokens:number;inputTokenBound:number}
function cost(tariff:TextTariff,input:number,read:number,write:number,output:number):number{
  const numerator=BigInt(input)*BigInt(tariff.inputMicrosPerMillion)+BigInt(read)*BigInt(tariff.cacheReadMicrosPerMillion)+
    BigInt(write)*BigInt(tariff.cacheWriteMicrosPerMillion)+BigInt(output)*BigInt(tariff.outputMicrosPerMillion);
  return integer(Number((numerator+999999n)/1000000n),10000000000);
}
function integer(value:unknown,maximum=10000000):number{
  if(typeof value!=='number'||!Number.isSafeInteger(value)||value<0||value>maximum)throw Error('hot_dsh_usage_invalid');return value;
}
export function textUsage(value:unknown):TextUsage{
  if(!value||typeof value!=='object'||Array.isArray(value))throw Error('hot_dsh_usage_invalid');
  const row=value as Record<string,unknown>;
  const inputTokens=integer(row.inputTokens),outputTokens=integer(row.outputTokens),cacheReadTokens=integer(row.cacheReadTokens??0),cacheWriteTokens=integer(row.cacheWriteTokens??0);
  const total=inputTokens+outputTokens+cacheReadTokens+cacheWriteTokens;
  if(inputTokens+cacheReadTokens+cacheWriteTokens===0||total>10000000||(row.totalTokens!==undefined&&integer(row.totalTokens)!==total))throw Error('hot_dsh_usage_invalid');
  // reasoningTokens is a subset of output, not a second charge.
  if(row.reasoningTokens!==undefined&&integer(row.reasoningTokens)>outputTokens)throw Error('hot_dsh_usage_invalid');
  return {inputTokens,outputTokens,cacheReadTokens,cacheWriteTokens,totalTokens:total};
}
export async function discoverTextModels(runtime:DshRuntime,provider:string){
  if(!/^[a-z][a-z0-9-]{0,63}$/.test(provider))throw Error('hot_dsh_route_invalid');
  return (await runtime.listModels(provider)).map(row=>({provider:row.provider,id:row.id,name:row.name}));
}
export async function runDshText(runtime:DshRuntime,ledger:TextLedger,request:TextRequest,tariff:TextTariff,
  safeOutput:(text:string)=>boolean,signal:AbortSignal):Promise<postgres.JSONValue>{
  if(!/^[a-z][a-z0-9-]{0,63}$/.test(request.provider)||!/^[A-Za-z0-9_.:-]{1,128}$/.test(request.model)||
    typeof request.system!=='string'||typeof request.text!=='string'||typeof request.promptVersion!=='string'||
    request.promptVersion.length>128||!/^[a-f0-9]{64}$/.test(tariff.versionHash))throw Error('hot_dsh_request_invalid');
  integer(request.maxOutputTokens,4096);integer(request.inputTokenBound);
  const textBytes=Buffer.byteLength(request.system)+Buffer.byteLength(request.text);
  if(!request.maxOutputTokens||request.inputTokenBound<textBytes+2048||textBytes>65536)throw Error('hot_dsh_request_invalid');
  for(const rate of [tariff.inputMicrosPerMillion,tariff.cacheReadMicrosPerMillion,tariff.cacheWriteMicrosPerMillion,tariff.outputMicrosPerMillion])integer(rate,10000000000);
  signal.throwIfAborted();
  const config={provider:request.provider,model:request.model,maxTokens:request.maxOutputTokens,temperature:0};
  const prepared=await runtime.prepareCall(config,signal);
  if(prepared.retryPolicy.mode!=='normal'||prepared.retryPolicy.maxRetries!==0)throw Error('hot_dsh_retry_denied');
  if(prepared.config.provider!==config.provider||prepared.config.model!==config.model||prepared.config.maxTokens!==config.maxTokens||prepared.config.temperature!==0)throw Error('hot_dsh_prepared_config_invalid');
  const specHash=sha256(JSON.stringify({config:prepared.config,promptVersion:request.promptVersion,tariff:tariff.versionHash,
    inputHash:sha256(JSON.stringify([request.system,request.text]))}));
  const maximumRate=Math.max(tariff.inputMicrosPerMillion,tariff.cacheReadMicrosPerMillion,tariff.cacheWriteMicrosPerMillion);
  const maxCostMicros=cost({...tariff,inputMicrosPerMillion:maximumRate},request.inputTokenBound,0,0,request.maxOutputTokens);
  const admitted=await ledger.reserve({resultKey:specHash,specHash,maxTokens:request.inputTokenBound+request.maxOutputTokens,maxCostMicros});
  if(admitted.state==='reused'){
    if(admitted.response&&typeof admitted.response==='object'&&'rejected'in admitted.response&&admitted.response.rejected===true)throw Error('hot_dsh_output_rejected');
    return admitted.response;
  }
  if(admitted.state==='busy')throw Error('hot_dsh_attempt_pending');
  let dispatched=false,saved=false;
  try{
    signal.throwIfAborted();await ledger.dispatch(admitted.ticket);dispatched=true;
    let output='',usage:TextUsage|undefined,finished=false,finishKind='',unsupported=false;
    for await(const chunk of prepared.stream({...prepared.config,system:request.system,messages:[{id:randomUUID(),role:'user',source:{kind:'user'},content:[{type:'text',text:request.text}]}],signal})){
      if(finished)throw Error('hot_dsh_stream_invalid');
      if(chunk.type==='text-delta'){
        if(typeof chunk.text!=='string')throw Error('hot_dsh_stream_invalid');output+=chunk.text;
        if(Buffer.byteLength(output)>65536)throw Error('hot_dsh_output_limit');
      }else if(chunk.type==='usage')usage=textUsage(chunk.usage);
      else if(chunk.type==='tool-call-delta')unsupported=true;
      else if(chunk.type==='reasoning-delta'){/* Not persisted or published; usage includes billed reasoning. */}
      else if(chunk.type==='finish'){
        const reason=chunk.reason as {kind?:string}|undefined;
        if(!reason?.kind||!['stop','max-tokens','tool-calls','aborted','error'].includes(reason.kind))throw Error('hot_dsh_finish_invalid');
        finishKind=reason.kind;finished=true;
      }else if(!['block-start','block-end'].includes(String(chunk.type)))throw Error('hot_dsh_stream_invalid');
    }
    if(!finished||!usage)throw Error('hot_dsh_receipt_incomplete');
    // The pinned successful stream does not expose a provider request id. Keep
    // it unknown, never substitute the local attempt/message UUID.
    // Only a synchronous credential-safety check belongs before persistence.
    // Domain/JSON validation must happen AFTER this receipt is durable.
    let valid=false;try{valid=!unsupported&&finishKind==='stop'&&output.length>0&&usage.outputTokens>0&&safeOutput(output)===true;}catch{valid=false;}
    const response:postgres.JSONValue=valid?{provider:request.provider,requestedModel:request.model,text:output,usage:{...usage}}:
      {provider:request.provider,requestedModel:request.model,rejected:true,code:'hot_dsh_output_rejected',finishKind,usage:{...usage}};
    const result=await ledger.save(admitted.ticket,response,{tokens:usage.totalTokens,costMicros:cost(tariff,usage.inputTokens,usage.cacheReadTokens,usage.cacheWriteTokens,usage.outputTokens),providerRequestId:null,costBasis:'tariff-ceiling'});
    saved=true;
    if(result.overrun)throw Error('hot_dsh_budget_overrun');
    if(signal.aborted)throw Error('hot_dsh_call_cancelled');
    if(!valid)throw Error('hot_dsh_output_rejected');
    return response;
  }catch(error){
    if(!saved){
      if(dispatched)await ledger.unknown(admitted.ticket);else await ledger.cancelUnsent(admitted.ticket);
    }
    if(error instanceof Error&&/^hot_dsh_[a-z_]+$/.test(error.message))throw error;
    throw Error('hot_dsh_call_failed');
  }
}
