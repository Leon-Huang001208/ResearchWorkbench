/** Keyless real DSH ToolRuntime + filesystem Skill + managed research tool.
 * Only HTTP transport is carried over test pipes; decisions are the real Host.
 * No control secret is emitted to the pipe or given to the Python sandbox.
 */
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createInterface} from 'node:readline';
import {apply as applyResearch} from '../../../app/research_web/runtime/research-tools.mjs';
import {apply as applyGuard} from '../../../app/research_web/runtime/guard.mjs';

const config = JSON.parse(await readFile(process.argv[2],'utf8'));
const source = process.env.RWB_DSH_TEST_SOURCE;
const require = createRequire(join(source,'packages/core/tools/package.json'));
const {Context} = await import(pathToFileURL(require.resolve('@deepseek-ai/cordis')));
const {default:SystemPrompt} = await import(pathToFileURL(require.resolve('@deepseek-ai/dsh-system-prompt')));
const {default:ToolRuntime} = await import(pathToFileURL(join(source,'packages/core/tools/lib/index.js')));
const {FileSystemSkillProvider} = await import(pathToFileURL(join(source,'packages/skill/skill-filesystem/lib/index.js')));
const {apply:applySkill} = await import(pathToFileURL(join(source,'packages/skill/tool-skill/lib/index.js')));
const lines = createInterface({input:process.stdin});
const pending = new Map();
let ordinal = 0;
let cancelController;
lines.on('line',line=>{const value=JSON.parse(line);const resolve=pending.get(value.id);pending.delete(value.id);resolve(value);});
globalThis.fetch = async (url, options) => {
  const id = ++ordinal;
  const reply = new Promise(resolve=>pending.set(id,resolve));
  const authorizationPresent = typeof options.headers['X-Research-Data-Key']==='string';
  process.stdout.write(JSON.stringify({kind:'bridge',id,path:new URL(url).pathname,body:JSON.parse(options.body),authorizationPresent})+'\n');
  const value = await reply;
  if (config.cancel && JSON.parse(options.body).pack_start === true) setTimeout(()=>cancelController.abort(),0);
  return new Response(JSON.stringify(value.body),{status:value.status,headers:{'content-type':'application/json'}});
};
const ctx = new Context();
let provider;
try {
  await ctx.plugin(SystemPrompt);
  await ctx.plugin(ToolRuntime);
  const logger={info(){},warn(){},error(){},debug(){}};
  const controller=new AbortController();
  cancelController=controller;
  provider = new FileSystemSkillProvider({get(){return undefined;},logger},{signal:controller.signal,invalidate(){}},{includeDefaultRoots:false,customSkillDirs:[config.nativeRoot],watch:false,watchFollowSymlinks:false});
  const session = {header:{id:config.sid,cwd:join(config.researchRoot,'sessions',config.sid)},snapshotEvents(){return [];}};
  const adapter={tools:ctx.tools,on:ctx.on.bind(ctx),logger,sessions:{get(id){return id===config.sid?session:undefined;}},skills:{list:lookup=>provider.list(lookup),async get(name,lookup){const candidate=(await provider.list(lookup)).find(item=>item.name===name);return candidate?provider.get(candidate,lookup):undefined;}}};
  applySkill(adapter);
  applyResearch(adapter,config);
  applyGuard(adapter,{...config,enabled:true});
  const agent={ctx,session};
  const loaded=await ctx.tools.execute({name:'skill',callId:'actual-native-load',arguments:{name:'research-pack-event-review'},agent,signal:controller.signal});
  if(loaded.isError)throw Error('native_skill_load_failed:'+JSON.stringify(loaded));
  const actual=await ctx.tools.execute({name:'research_run_script',callId:'actual-native-pack',arguments:{pack_execution:config.descriptor},agent,signal:controller.signal});
  process.stdout.write(JSON.stringify({kind:'result',loaded,actual})+'\n');
} finally {
  await provider?.dispose();
  await ctx.fiber.dispose();
  lines.close();
}
