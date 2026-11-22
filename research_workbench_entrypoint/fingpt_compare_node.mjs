// Test-only model seam and budget observer. Original prompts, agent and tool results stay intact.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { registerHooks } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';

const SLOT = Symbol.for('rwb.comparison.private');
const sha = value => crypto.createHash('sha256').update(value).digest('hex');
function metric(filename, data) {
  fs.appendFileSync(filename, JSON.stringify({at:Date.now(), ...data})+'\n', {mode:0o600});
}

export function createBudget(write) {
  let tools=0, searches=0;
  return {
    before(name) {
      const search=['search_news_notices','get_news_flash','web_search'].includes(name) || name.startsWith('datahub_search_');
      if(tools>=48 || search && searches>=6) {
        write({event:'tool_denied',name});throw Error('comparison_tool_budget_exhausted');
      }
      if(name==='subagent') {write({event:'tool_denied',name});throw Error('comparison_subagent_denied');}
      tools++;if(search) searches++;
      write({event:'tool_admitted',name,ordinal:tools,searches});
    },
    result(name,ok) {write({event:'tool_result',name,ok});},
  };
}

// The A provider remains the original native provider; this plugin adds only the
// agreed search/subagent limits and numeric observability, never prompt content.
export function apply(ctx, config) {
  const write=value=>metric(config.metrics,value);
  const budget=createBudget(write);
  ctx.on('tools/pre-execute',async(exec,next)=>{
    const decision=await next();
    if(!['deny','cancel'].includes(decision.kind)) {
      try{budget.before(exec.name);}catch{return {kind:'deny',reason:'comparison_tool_budget_exhausted'};}
    }else write({event:'tool_denied',name:exec.name});
    return decision;
  },{global:true,prepend:true});
  ctx.on('tools/result',(exec,result)=>write({event:'tool_result',name:exec.name,ok:result.isError===false}),{global:true});
  ctx.on('llm/stream',async function*(options,next){
    write({event:'model_request',provider:options.provider,model:options.model});
    let seen=false;
    for await(const chunk of next()) {
      if(!seen && ['text-delta','text_delta','text'].includes(chunk.type)) {seen=true;write({event:'first_model_text'});}
      if(chunk.usage) {
        const usage=Object.fromEntries(Object.entries(chunk.usage).filter(([,v])=>Number.isFinite(v)));
        write({event:'usage',usage});
      }
      yield chunk;
    }
    write({event:'model_end'});
  },{global:true,prepend:true});
}

export function replaceTiers(source) {
  const start=source.indexOf('export function getTiers() {');
  const end=source.indexOf('\nexport function publicTiers()',start);
  if(start<0 || end<0)throw Error('comparison_llm_seam_unknown');
  return source.slice(0,start)+`export function getTiers() { return globalThis[Symbol.for('rwb.comparison.private')].tiers; }\n`+source.slice(end);
}

export function wrapTools(source) {
  const needle='export async function runTool(name, args, { signal } = {}) {';
  if(source.split(needle).length!==2)throw Error('comparison_tool_seam_unknown');
  return source.replace(needle,'async function comparisonOriginalTool(name, args, { signal } = {}) {')+`
export async function runTool(name,args,options={}) {
  const state=globalThis[Symbol.for('rwb.comparison.private')];
  state.budget.before(name);
  try {const result=await comparisonOriginalTool(name,args,options);state.budget.result(name,true);return result;}
  catch(error){state.budget.result(name,false);throw error;}
}
`;
}

export function createTiers(group,lite,key) {
  if(!['B','C'].includes(group) || typeof key!=='string' || !key || /[\r\n]/.test(key))throw Error('comparison_model_binding_invalid');
  const tiers=Object.fromEntries(['lite','ultra','frontier','kimi'].map(name=>[name,{label:name,key:'',model:''}]));
  const tier=group==='B'?'frontier':'lite';
  tiers[tier]=group==='B'?{label:'DeepSeek Flash（对照适配）',base:'https://api.deepseek.com',auth:'bearer',model:'deepseek-flash',key}
    :{label:'Lite · 小米 MiMo',base:lite.base_url,auth:'api-key',model:lite.model,key};
  return tiers;
}

async function main() {
  const root=process.env.RWB_COMPARE_ROOT,group=process.env.RWB_COMPARE_GROUP;
  if(!root || !['B','C'].includes(group))throw Error('comparison_scope_invalid');
  const read=name=>JSON.parse(fs.readFileSync(path.join(root,name),'utf8'));
  const prepared=read('prepared.json'), experiment=read('experiment.json');
  const engine=path.join(root,'sources/original/app/research_web/fingpt/engine');
  const metrics=path.join(root,'groups',group,'logs/metrics.jsonl');
  const write=value=>metric(metrics,value);
  const result=spawnSync(prepared.python,[path.join(path.dirname(fileURLToPath(import.meta.url)),'fingpt_compare_worker.py'),
    'node-credential','--root',root,'--group',group],{encoding:'utf8',stdio:['ignore','pipe','pipe'],maxBuffer:16384,timeout:25000});
  if(result.status!==0)throw Error('comparison_credential_unavailable');
  let key;
  try {key=JSON.parse(result.stdout).value;}catch{throw Error('comparison_credential_unavailable');}
  if(typeof key!=='string' || !key || key.length>1024)throw Error('comparison_credential_unavailable');
  const tiers=createTiers(group,experiment.lite,key);
  const tier=group==='B'?'frontier':'lite';
  // Provider secret exists only in this process's client configuration. It is
  // never an environment variable inherited by tool/browser child processes.
  globalThis[SLOT]={tiers,budget:createBudget(write)};
  key=undefined;
  registerHooks({load(url,context,next){
    const loaded=next(url,context);
    if(url===pathToFileURL(path.join(engine,'llm.mjs')).href) {
      const raw=String(loaded.source);write({event:'adapter_source',module:'llm',original_sha256:sha(raw)});
      return {...loaded,source:replaceTiers(raw)};
    }
    if(url===pathToFileURL(path.join(engine,'tools.mjs')).href) {
      const raw=String(loaded.source);write({event:'adapter_source',module:'tools',original_sha256:sha(raw)});
      return {...loaded,source:wrapTools(raw)};
    }
    return loaded;
  }});
  const actualFetch=globalThis.fetch;
  const modelOrigin=new URL(tiers[tier].base).origin;
  const pending=new Set();
  globalThis.fetch=async(input,options={})=>{
    const url=new URL(input instanceof URL?input.href:typeof input==='string'?input:input.url);
    const model=url.origin===modelOrigin && url.pathname.endsWith('/chat/completions');
    if(model)write({event:'model_request',model:tiers[tier].model,protocol:'chat-completions'});
    const response=await actualFetch(input,model?{...options,redirect:'error'}:options);
    if(model) {
      const task=(async()=>{
        let first=false,buffer='';
        const reader=response.clone().body?.getReader();if(!reader)return;
        const decoder=new TextDecoder();
        for(;;) {
          const {done,value}=await reader.read();if(done)break;
          buffer+=decoder.decode(value,{stream:true});
          if(buffer.length>2_000_000)throw Error('comparison_stream_line_too_large');
          let i;
          while((i=buffer.indexOf('\n'))>=0) {
            const line=buffer.slice(0,i).trim();buffer=buffer.slice(i+1);
            if(!line.startsWith('data:'))continue;
            let event;try{event=JSON.parse(line.slice(5));}catch{continue;}
            if(!first && event.choices?.[0]?.delta?.content){first=true;write({event:'first_model_text'});}
            if(event.usage){const usage=Object.fromEntries(Object.entries(event.usage).filter(([,v])=>Number.isFinite(v)));write({event:'usage',usage});}
          }
        }
        write({event:'model_end'});
      })().catch(()=>write({event:'usage_unavailable'}));
      pending.add(task);task.finally(()=>pending.delete(task));
    } else {
      // Read-only acquisition audit. The model receives the original response;
      // no source, answer or repaired data is injected into either engine.
      const type=response.headers.get('content-type')||'';
      const publicHost=url.protocol==='https:' && !['localhost','127.0.0.1','::1'].includes(url.hostname) && !url.hostname.endsWith('.local');
      const querySafe=![...url.searchParams.keys()].some(k=>/^(?:key|api_key|apikey|token|secret|authorization)$/i.test(k));
      if(publicHost && querySafe && /json|html|text\//i.test(type)) {
        const task=(async()=>{
          const reader=response.clone().body?.getReader();if(!reader)return;
          const chunks=[];let bytes=0;
          try {
            for(;;){const {done,value}=await reader.read();if(done)break;bytes+=value.length;if(bytes>2_000_000){await reader.cancel();write({event:'source_capture_unavailable',reason:'size_limit'});return;}chunks.push(value);}
            const raw=Buffer.concat(chunks),digest=sha(raw);
            const dir=path.join(root,'groups',group,'observed');fs.mkdirSync(dir,{recursive:true,mode:0o700});
            const filename=path.join(dir,digest+'.body');
            if(!fs.existsSync(filename))fs.writeFileSync(filename,raw,{mode:0o600,flag:'wx'});
            const final=new URL(response.url||url.href);
            if(final.username || final.password)throw Error('comparison_source_identity_invalid');
            write({event:'source_observed',url:url.href,final_url:final.href,status:response.status,content_type:type,sha256:digest,bytes,file:path.relative(root,filename)});
          }catch{write({event:'source_capture_unavailable',reason:'capture_failed'});}
        })();
        pending.add(task);task.finally(()=>pending.delete(task));
      }
    }
    return response;
  };
  await import(pathToFileURL(path.join(engine,'entry.mjs')).href);
  await Promise.allSettled([...pending]);
  delete globalThis[SLOT];
}

if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  try {await main();}catch{process.stderr.write('comparison_node_failed\n');process.exitCode=1;}
}
