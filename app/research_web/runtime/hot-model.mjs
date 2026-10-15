/** Hot session scope uses the existing instance-private Host data channel. */
import {constants} from 'node:fs';
import {open,realpath} from 'node:fs/promises';
import {basename,join} from 'node:path';
import {trustedDirectory} from './research-tools.mjs';
import {privateControl} from './public-data.mjs';
import {createResearchStream} from './hot-model-stream.mjs';

export const inject=['llm','sessions'];
export async function callHotLedger(root,operation,params){
  const control=await privateControl(root);
  const body=JSON.stringify({operation,params});
  if(Buffer.byteLength(body)>1114112)throw Error('hot_stream_bridge_limit');
  const response=await fetch(control.url+'/api/research/internal/data/hot-model',{
    method:'POST',headers:{'Content-Type':'application/json','X-Research-Data-Key':control.token},body,
    redirect:'error',credentials:'omit',signal:AbortSignal.timeout(10000),
  });
  if(!response.body)throw Error('hot_stream_bridge_unavailable');
  const reader=response.body.getReader();let bytes=0,text='';const decoder=new TextDecoder('utf-8',{fatal:true});
  try{for(;;){const part=await reader.read();if(part.done)break;bytes+=part.value.byteLength;if(bytes>1114112)throw Error('hot_stream_bridge_limit');text+=decoder.decode(part.value,{stream:true});}text+=decoder.decode();const value=JSON.parse(text);if(!response.ok){const code=value?.error?.code;throw Error(typeof code==='string'&&/^hot_[a-z_]{1,100}$/.test(code)?code:'hot_stream_bridge_unavailable');}return value;}
  finally{await reader.cancel();}
}
async function binding(ctx,config,options){
  if(!options.sessionId)return null;
  const session=ctx.sessions.get(options.sessionId);
  if(!session)throw Error('hot_stream_session_unknown');
  const root=await realpath(config.researchRoot),seen=new Set();let cursor=session,managed=false;
  while(cursor){
    if(seen.size>=16||seen.has(cursor.header.id))throw Error('hot_stream_lineage_invalid');seen.add(cursor.header.id);
    const cwd=cursor.header.cwd;
    if(typeof cwd==='string'&&cwd===join(root,'sessions',basename(cwd)))managed=true;
    if(!cursor.header.parentSession)break;
    cursor=ctx.sessions.get(cursor.header.parentSession);if(!cursor)throw Error('hot_stream_lineage_invalid');
  }
  if(!managed)return null;
  const cwd=await trustedDirectory(ctx,{agent:{session}},config);
  let file;
  try{file=await open(join(cwd,'inputs','hot-context.json'),constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);}
  catch(error){if(error.code==='ENOENT')return null;throw Error('hot_stream_context_invalid');}
  try{const stat=await file.stat();if(!stat.isFile()||stat.nlink!==1||stat.uid!==process.getuid()||stat.mode&0o077||stat.size>65536)throw Error('hot_stream_context_invalid');}
  finally{await file.close();}
  // Presence only selects the private check; file content cannot authorize billing.
  const run=await callHotLedger(config.researchRoot,'binding',{sessionId:basename(cwd)});
  if(!run||run.sessionId!==basename(cwd)||typeof run.runId!=='string')throw Error('hot_stream_binding_invalid');
  return run;
}
export function apply(ctx,config){
  const nested=new WeakSet();
  ctx.on('llm/stream',async function*(options,next){
    if(nested.has(options)){yield* next();return;}
    const run=await binding(ctx,config,options);
    if(!run){yield* next();return;}
    const ledger=Object.fromEntries(['reserve','dispatch','unknown','cancel'].map(op=>[op,params=>callHotLedger(config.researchRoot,op,params)]));
    ledger.receipt=(params,chunks)=>callHotLedger(config.researchRoot,'receipt',{...params,chunks,providerRequestId:null});
    ledger.warn=event=>ctx.logger.warn(event);
    const runtime={prepareCall:async(...args)=>{
      const prepared=await ctx.llm.prepareCall(...args);
      return {...prepared,stream:async function*(request){nested.add(request);try{yield* prepared.stream(request);}finally{nested.delete(request);}}};
    }};
    try{yield* createResearchStream(runtime,ledger,run,options);}
    catch(error){ctx.logger.warn('hot_research_stream_failed');throw error;}
  },{global:true,prepend:true});
}
