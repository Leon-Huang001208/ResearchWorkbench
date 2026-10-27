/** Actual pinned ToolRuntime -> private Host -> DataHub; no provider/model network. */
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createInterface} from 'node:readline';
import {apply as applyData} from '../../../app/research_web/runtime/public-data.mjs';
import {apply as applyGuard} from '../../../app/research_web/runtime/guard.mjs';

const config=JSON.parse(await readFile(process.argv[2],'utf8'));
const source=process.env.RWB_DSH_TEST_SOURCE;
const require=createRequire(join(source,'packages/core/tools/package.json'));
const {Context}=await import(pathToFileURL(require.resolve('@deepseek-ai/cordis')));
const {default:SystemPrompt}=await import(pathToFileURL(require.resolve('@deepseek-ai/dsh-system-prompt')));
const {default:ToolRuntime}=await import(pathToFileURL(join(source,'packages/core/tools/lib/index.js')));
const lines=createInterface({input:process.stdin});
const pending=new Map(); let ordinal=0;
lines.on('line',line=>{const value=JSON.parse(line);const resolve=pending.get(value.id);pending.delete(value.id);resolve(value);});
globalThis.fetch=async (url,options)=>{
  const id=++ordinal;const reply=new Promise(resolve=>pending.set(id,resolve));
  process.stdout.write(JSON.stringify({kind:'bridge',id,path:new URL(url).pathname,body:JSON.parse(options.body),authorizationPresent:typeof options.headers['X-Research-Data-Key']==='string'})+'\n');
  const value=await reply;
  return new Response(JSON.stringify(value.body),{status:value.status,headers:{'content-type':'application/json'}});
};
const ctx=new Context();
try {
  await ctx.plugin(SystemPrompt);
  await ctx.plugin(ToolRuntime);
  const logger={info(){},warn(){},error(){},debug(){}};
  const session={header:{id:config.sid,cwd:join(config.researchRoot,'sessions',config.sid)},snapshotEvents(){return [];}};
  const adapter={tools:ctx.tools,on:ctx.on.bind(ctx),logger,sessions:{get(id){return id===config.sid?session:undefined;}}};
  applyData(adapter,{researchRoot:config.researchRoot,enabledTools:['datahub_search_news']});
  applyGuard(adapter,{researchRoot:config.researchRoot,enabled:true});
  const agent={ctx,session}; const results=[];
  for(let index=0;index<config.cases.length;index++) results.push(await ctx.tools.execute({name:'rwb_query_latest_cls_news',callId:'owned-news-'+index,arguments:config.cases[index],agent,signal:new AbortController().signal}));
  process.stdout.write(JSON.stringify({kind:'result',results,original:ctx.tools.get('datahub_search_news').parameters})+'\n');
} finally {await ctx.fiber.dispose();lines.close();}
