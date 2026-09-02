/** Approval-gated native bridge. Provider parsing and immutable snapshots live in DataHub. */
import { constants } from 'node:fs';
import { open, lstat, realpath } from 'node:fs/promises';
import { basename, isAbsolute, join } from 'node:path';
import { trustedDirectory } from './research-tools.mjs';

export const name = 'alphafoundry-public-data';
export const inject = ['tools', 'sessions'];
const SOURCES = ['fund_nav','cls_telegraph','fund_profile','fund_distributions','fund_holdings'];
const MAX_BYTES = 1048576;

function businessQuery(args) {
  if (!args || typeof args !== 'object' || Array.isArray(args) || Object.keys(args).some(key => !['source','code','limit','start_date','end_date','year','refresh'].includes(key)) || !SOURCES.includes(args.source)) throw Error('Only registered business query arguments are accepted');
  if (args.source === 'cls_telegraph' ? args.code !== undefined : typeof args.code !== 'string' || !/^[0-9]{6}$/.test(args.code)) throw Error('Invalid fund code');
  if (args.limit !== undefined && (!Number.isInteger(args.limit) || args.limit < 1 || args.limit > 100)) throw Error('limit must be 1–100');
  if (args.refresh !== undefined && typeof args.refresh !== 'boolean') throw Error('refresh must be boolean');
  if ((args.start_date !== undefined) !== (args.end_date !== undefined)) throw Error('Date bounds must be paired');
  if (args.start_date !== undefined) {
    if (args.source !== 'fund_nav') throw Error('Date range is only accepted for NAV');
    for (const value of [args.start_date,args.end_date]) {
      if (typeof value !== 'string' || !/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(value) || !Number.isFinite(Date.parse(value)) || new Date(value).toISOString().slice(0,10) !== value) throw Error('Invalid date');
    }
    const today = new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Shanghai'});
    const maximum = `${String(Number(args.start_date.slice(0,4))+10).padStart(4,'0')}${args.start_date.slice(4)}`;
    if (args.start_date > args.end_date || args.end_date > today || args.end_date > maximum) throw Error('Date range is future, reversed or exceeds ten years');
  }
  if (args.year !== undefined && (args.source !== 'fund_holdings' || !Number.isInteger(args.year) || args.year < 1990 || args.year > new Date().getFullYear())) throw Error('Invalid holdings year');
  return {...args};
}

async function privateControl(root) {
  const canonical = await realpath(root);
  const dir = join(canonical,'.control');
  const parent = await lstat(dir);
  if (!parent.isDirectory() || parent.isSymbolicLink() || parent.mode & 0o077 || parent.uid !== process.getuid()) throw Error('Private DataHub directory is unsafe');
  const handle = await open(join(dir,'datahub.json'),constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
  try {
    const info = await handle.stat();
    if (!info.isFile() || info.nlink !== 1 || info.mode & 0o077 || info.uid !== process.getuid() || info.size > 4096) throw Error('Private DataHub file is unsafe');
    const after = await lstat(dir);
    if (after.ino !== parent.ino || after.dev !== parent.dev || after.isSymbolicLink()) throw Error('Private DataHub directory changed');
    const buffer = Buffer.alloc(4097); const {bytesRead} = await handle.read(buffer,0,buffer.length,0);
    if (bytesRead > 4096) throw Error('Private DataHub configuration exceeds its cap');
    const value = JSON.parse(buffer.subarray(0,bytesRead).toString('utf8'));
    const url = new URL(value.url);
    if (url.protocol !== 'http:' || !['127.0.0.1','[::1]'].includes(url.hostname) || !url.port || /[@?#]/.test(value.url) || url.username || url.password || !['','/'].includes(url.pathname) || typeof value.token !== 'string' || !/^[A-Za-z0-9_-]{43,128}$/.test(value.token)) throw Error('Private DataHub origin or token is invalid');
    return {url:url.origin,token:value.token};
  } finally {await handle.close();}
}

async function boundedJson(response, signal) {
  if (!response.ok || response.redirected) {await response.body?.cancel();throw Error(`DataHub request failed (HTTP ${response.status})`);}
  if (!response.headers.get('content-type')?.includes('application/json') || !response.body || Number(response.headers.get('content-length')) > MAX_BYTES) {await response.body?.cancel();throw Error('DataHub response type or size is invalid');}
  const reader=response.body.getReader();const chunks=[];let size=0;
  try {
    while(true) {signal.throwIfAborted();const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>MAX_BYTES)throw Error('DataHub response size exceeds limit');chunks.push(value);}
  } finally {await reader.cancel();}
  signal.throwIfAborted();
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}

function smallResult(value) {
  if (!value || typeof value.dataset_id !== 'string' || !SOURCES.includes(value.source) || !['complete','snapshot','empty','partial','failed'].includes(value.status) || !Array.isArray(value.files) || !Array.isArray(value.sample) || value.sample.length > 3 || !Number.isSafeInteger(value.row_count)) throw Error('DataHub response schema is invalid');
  const keys=['dataset_id','source','source_url','schema_version','status','row_count','provider_total','pages_fetched','pagination_complete','requested_range','actual_range','retrieved_at','as_of','cache_hit','fields','missing','limitations','manifest_sha256'];
  return {dataset_id:value.dataset_id,source:value.source,status:value.status,
    manifest_json:JSON.stringify(Object.fromEntries(keys.filter(key=>key in value).map(key=>[key,value[key]]))),
    files_json:JSON.stringify(value.files.map(({name,path,sha256})=>({name,path,sha256}))),sample_json:JSON.stringify(value.sample)};
}

export function apply(ctx, config) {
  if (typeof config?.researchRoot !== 'string' || !isAbsolute(config.researchRoot)) throw Error('Public data requires an absolute research root');
  const outputKeys=['dataset_id','source','status','manifest_json','files_json','sample_json'];
  ctx.tools.register({
    name:'af_public_data',
    description:'After native approval, prepare an immutable input dataset using registered fund_nav, fund_profile, fund_distributions, fund_holdings or cls_telegraph. NAV accepts paired start_date/end_date (up to ten years); no dates means only the legacy recent snapshot, limit 1–100. Holdings accepts optional year. Parent prepares data once and passes manifest/files to children; no child refetch. Read CSV/JSON paths with af_run_script; output is a short manifest and at most three sample rows, not full history.',
    parameters:{type:'object',properties:{source:{type:'string',enum:SOURCES},code:{type:'string'},limit:{type:'integer'},start_date:{type:'string'},end_date:{type:'string'},year:{type:'integer'},refresh:{type:'boolean'}},required:['source'],additionalProperties:false},
    output:{schema:{type:'object',properties:Object.fromEntries(outputKeys.map(key=>[key,{type:'string'}])),required:outputKeys,additionalProperties:false},render(_args,value){return [{type:'text',text:JSON.stringify(value)}];}},
    async execute(args,exec) {
      const query=businessQuery(args);exec.signal.throwIfAborted();
      const cwd=await trustedDirectory(ctx,exec,config);exec.signal.throwIfAborted();
      if (!/^[a-zA-Z0-9_.-]{1,120}$/.test(exec.agent.session.header.id) || !/^[a-zA-Z0-9_.:-]{1,120}$/.test(exec.callId)) throw Error('Native call identity is invalid');
      const identity={session_id:basename(cwd),call_id:`${exec.agent.session.header.id}:${exec.callId}`};
      const approval=ctx.get('approval');
      if (!approval) throw Error('Native approval unavailable; HTTP not sent');
      const outcome=await approval.request({agent:exec.agent,toolName:'af_public_data',callId:exec.callId,
        reason:`准备 ${args.source}${args.code ? ' '+args.code : ''} 资料，${args.start_date ? args.start_date+' 至 '+args.end_date : args.year ? args.year+' 年披露快照' : '公开快照'}。固定${args.source==='cls_telegraph'?'财联社':'东方财富'}来源；仅发送查询参数，不发送附件、聊天或模型凭据。`,signal:exec.signal});
      if (outcome!=='allowed-once') {ctx.logger.info('public_data_not_authorized outcome=%s',outcome);throw Error(`Public data approval ${outcome}; HTTP not sent`);}
      exec.signal.throwIfAborted();
      const control=await privateControl(config.researchRoot);exec.signal.throwIfAborted();
      const headers={'Content-Type':'application/json','X-Research-Data-Key':control.token};
      const signal=AbortSignal.any([exec.signal,AbortSignal.timeout(22000)]);
      let cancellation;
      const cancel=()=>cancellation ??= (async()=>{
        try {const response=await globalThis.fetch(control.url+'/api/research/internal/data/cancel',{method:'POST',headers,body:JSON.stringify(identity),redirect:'error',credentials:'omit',signal:AbortSignal.timeout(2500)});await response.body?.cancel();if(!response.ok)throw Error('cancel rejected');}
        catch {ctx.logger.warn('datahub_cancel_not_confirmed');}
      })();
      signal.addEventListener('abort',cancel,{once:true});
      ctx.logger.info('public_data_request_started source=%s',query.source);
      try {
        signal.throwIfAborted();
        const response=await globalThis.fetch(control.url+'/api/research/internal/data/query',{method:'POST',headers,body:JSON.stringify({...identity,query}),redirect:'error',credentials:'omit',signal});
        const result=smallResult(await boundedJson(response,signal));
        ctx.logger.info('public_data_request_completed source=%s',query.source);return result;
      } catch(error) {await cancel();ctx.logger.warn('public_data_request_failed source=%s type=%s',query.source,error.name);throw error;}
      finally {signal.removeEventListener('abort',cancel);if(cancellation)await cancellation;}
    },
  });
}
