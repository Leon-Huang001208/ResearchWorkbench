/** One prepared DSH request: durable admission, complete receipt, then replay. */
import {createHash} from 'node:crypto';

const fields=new Set(['provider','model','messages','system','tools','toolHistory','temperature','maxTokens','stop','sessionId','purpose','reasoningEffort','signal']);
const hash=value=>createHash('sha256').update(value).digest('hex');
function freeze(value){if(value&&typeof value==='object'){Object.values(value).forEach(freeze);Object.freeze(value);}return value;}
function json(value){
  if(value===null||typeof value==='string'||typeof value==='boolean')return value;
  if(typeof value==='number'&&Number.isFinite(value))return value;
  if(Array.isArray(value))return value.map(json);
  if(value&&typeof value==='object'&&Object.getPrototypeOf(value)===Object.prototype)return Object.fromEntries(Object.entries(value).filter(([,v])=>v!==undefined).sort(([a],[b])=>a<b?-1:a>b?1:0).map(([k,v])=>[k,json(v)]));
  throw Error('hot_stream_request_invalid');
}
function attachment(value){return value&&typeof value==='object'&&(['image','file','audio'].includes(value.type)||Object.values(value).some(attachment));}
export function freezeResearchRequest(options){
  if(!options||typeof options!=='object'||Object.keys(options).some(k=>!fields.has(k))||options.provider!=='deepseek-official'||options.model!=='deepseek-flash'||!Array.isArray(options.messages))throw Error('hot_stream_request_invalid');
  if(attachment(options.messages))throw Error('hot_stream_text_only');
  const maximum=options.maxTokens??4096;
  if(!Number.isSafeInteger(maximum)||maximum<1||maximum>4096)throw Error('hot_stream_request_invalid');
  let request;try{request=json({...Object.fromEntries(Object.entries(options).filter(([k,v])=>k!=='signal'&&v!==undefined)),maxTokens:maximum});}catch{throw Error('hot_stream_request_invalid');}
  const bytes=Buffer.byteLength(JSON.stringify(request));
  if(bytes>65536)throw Error('hot_stream_request_limit');
  return {request:freeze(request),requestHash:hash(JSON.stringify(request)),inputTokenBound:bytes+2048};
}
function callId(runId,digest){const b=Buffer.from(hash(runId+':'+digest).slice(0,32),'hex');b[6]=(b[6]&15)|80;b[8]=(b[8]&63)|128;const h=b.toString('hex');return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20)}`;}
function complete(chunks){
  if(!Array.isArray(chunks)||chunks.length<2||chunks.length>8192||Buffer.byteLength(JSON.stringify({chunks}))>1048576)throw Error('hot_stream_receipt_invalid');
  if(chunks.filter(c=>c?.type==='finish').length!==1||chunks.filter(c=>c?.type==='usage').length!==1||chunks.at(-1)?.type!=='finish')throw Error('hot_stream_receipt_invalid');
  const usage=chunks.find(c=>c.type==='usage').usage;
  if(!usage||!Number.isSafeInteger(usage.inputTokens)||usage.inputTokens<0||!Number.isSafeInteger(usage.outputTokens)||usage.outputTokens<0)throw Error('hot_stream_receipt_invalid');
  if(!['stop','tool-calls','max-tokens','error','aborted'].includes(chunks.at(-1).reason?.kind))throw Error('hot_stream_receipt_invalid');
  return ['error','aborted'].includes(chunks.at(-1).reason.kind);
}

export async function* createResearchStream(runtime,ledger,run,options){
  options.signal?.throwIfAborted();
  const initial=freezeResearchRequest(options);
  const config=Object.fromEntries(['provider','model','maxTokens','temperature','reasoningEffort'].filter(k=>initial.request[k]!==undefined).map(k=>[k,initial.request[k]]));
  const prepared=await runtime.prepareCall(config,options.signal);
  options.signal?.throwIfAborted();
  if(prepared.retryPolicy?.mode!=='normal'||prepared.retryPolicy.maxRetries!==0)throw Error('hot_stream_retry_denied');
  if(prepared.config.provider!==config.provider||prepared.config.model!==config.model||prepared.config.maxTokens!==config.maxTokens)throw Error('hot_stream_prepared_config_invalid');
  const actual=freezeResearchRequest({...initial.request,...prepared.config});
  const params={runId:run.runId,sessionId:run.sessionId,callId:callId(run.runId,actual.requestHash),requestHash:actual.requestHash,provider:actual.request.provider,model:actual.request.model,inputTokenBound:actual.inputTokenBound,maxOutputTokens:actual.request.maxTokens};
  const admission=await ledger.reserve(params);
  if(admission.state==='reused'){
    options.signal?.throwIfAborted();
    const saved=admission.response;
    if(saved?.rejected||complete(saved?.chunks))throw Error('hot_stream_provider_failed');
    for(const chunk of saved.chunks){options.signal?.throwIfAborted();yield chunk;}
    return;
  }
  if(admission.state!=='reserved')throw Error('hot_stream_attempt_pending');
  const bound={runId:run.runId,sessionId:run.sessionId,callId:params.callId,ticket:admission.ticket};
  let dispatchAttempted=false,received=false;
  try{
    options.signal?.throwIfAborted();
    // After this await the dispatch response may be lost. Never refund that case.
    dispatchAttempted=true;await ledger.dispatch(bound);
    const request=Object.freeze({...actual.request,signal:options.signal});
    const chunks=[];let bytes=0;
    for await(const chunk of prepared.stream(request)){
      const copy=json(chunk);bytes+=Buffer.byteLength(JSON.stringify(copy))+1;
      if(bytes>1048500||chunks.length>=8192)throw Error('hot_stream_receipt_limit');
      chunks.push(copy);
    }
    const failed=complete(chunks);
    const receipt=await ledger.receipt(bound,chunks);received=true;
    options.signal?.throwIfAborted();
    if(receipt?.overrun)throw Error('hot_stream_budget_overrun');
    if(failed)throw Error('hot_stream_provider_failed');
    for(const chunk of chunks){options.signal?.throwIfAborted();yield chunk;}
  }catch(error){
    if(!received){
      if(dispatchAttempted){try{await ledger.unknown(bound);}catch{ledger.warn?.('hot_stream_unknown_unconfirmed');}}
      else {try{await ledger.cancel(bound);}catch{ledger.warn?.('hot_stream_cancel_unconfirmed');}}
      throw Error(dispatchAttempted?'hot_stream_outcome_unknown':'hot_stream_cancelled');
    }
    throw error;
  }
}
