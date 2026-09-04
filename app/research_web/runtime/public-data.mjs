/** Approval-gated native bridge. Provider parsing and immutable snapshots live in DataHub. */
import { constants } from 'node:fs';
import { open, lstat, realpath } from 'node:fs/promises';
import { basename, isAbsolute, join } from 'node:path';
import { trustedDirectory } from './research-tools.mjs';

export const name = 'research-data-tools';
export const inject = ['tools', 'sessions'];
const BUSINESS = {
  datahub_search_assets: ['search_assets','识别证券、基金和指数代码',{query:{type:'string'},market:{type:'string'},asset_type:{type:'string'}},['query']],
  datahub_get_trading_calendar: ['trading_calendar','读取交易日历',{market:{type:'string'},start_date:{type:'string'},end_date:{type:'string'}},['market','start_date','end_date']],
  datahub_get_market_bars: ['market_bars','读取历史行情与复权口径',{asset:{type:'string'},start_date:{type:'string'},end_date:{type:'string'},frequency:{type:'string'},adjustment:{type:'string'}},['asset','start_date','end_date']],
  datahub_get_market_snapshot: ['market_snapshot','读取当前或最近行情快照',{assets:{type:'array',items:{type:'string'}},fields:{type:'array',items:{type:'string'}}},['assets']],
  datahub_get_index_data: ['index_data','读取指数行情、成分或估值',{index:{type:'string'},dataset:{type:'string'},date:{type:'string'}},['index','dataset']],
  datahub_get_financials: ['financials','读取财务报表与标准化指标',{asset:{type:'string'},statements:{type:'array',items:{type:'string'}},periods:{type:'array',items:{type:'string'}}},['asset']],
  datahub_get_market_activity: ['market_activity','读取资金与交易事件',{asset:{type:'string'},dataset:{type:'string'},start_date:{type:'string'},end_date:{type:'string'}},['asset','dataset']],
  datahub_get_factor_macro: ['factor_macro','读取因子、技术指标和宏观序列',{series:{type:'array',items:{type:'string'}},assets:{type:'array',items:{type:'string'}},start_date:{type:'string'},end_date:{type:'string'}},['series']],
  datahub_get_fund_data: ['fund_data','读取基金净值、资料、分红或持仓',{dataset:{type:'string',enum:['nav','profile','distributions','holdings']},code:{type:'string'},start_date:{type:'string'},end_date:{type:'string'},year:{type:'integer'},limit:{type:'integer'}},['dataset','code']],
  datahub_search_news: ['search_news','搜索新闻与快讯',{query:{type:'string'},limit:{type:'integer'},start_date:{type:'string'},end_date:{type:'string'}},[]],
  datahub_search_announcements: ['search_announcements','搜索公司公告',{asset:{type:'string'},query:{type:'string'},start_date:{type:'string'},end_date:{type:'string'}},[]],
  datahub_search_research: ['search_research','搜索研报、公众号和会议纪要',{query:{type:'string'},document_type:{type:'string'},limit:{type:'integer'}},['query']],
  datahub_search_web: ['search_web','通过已配置供应商搜索公开网页',{query:{type:'string'},limit:{type:'integer'}},['query']],
};
const MAX_BYTES = 1048576;

function stableBusinessQuery(capability, args, properties) {
  if (!args || typeof args !== 'object' || Array.isArray(args)) throw Error('Business data arguments must be an object');
  const common=['source','allow_fallback','refresh'];
  const allowed=new Set([...common,...Object.keys(properties)]);
  if (Object.keys(args).some(key=>!allowed.has(key))) throw Error('Only registered business data arguments are accepted');
  if (args.source !== undefined && (typeof args.source !== 'string' || !/^[a-z0-9_]{1,64}$/.test(args.source))) throw Error('Data source is not a registered identifier');
  if (args.allow_fallback !== undefined && typeof args.allow_fallback !== 'boolean') throw Error('allow_fallback must be boolean');
  if (args.refresh !== undefined && typeof args.refresh !== 'boolean') throw Error('refresh must be boolean');
  const parameters=Object.fromEntries(Object.entries(args).filter(([key])=>!common.includes(key)));
  const raw=JSON.stringify(parameters);
  if (Buffer.byteLength(raw)>32768) throw Error('Business data arguments exceed size limit');
  return {capability,source:args.source || 'auto',allow_fallback:args.allow_fallback || false,parameters,refresh:args.refresh || false};
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
  if (!value || typeof value.dataset_id !== 'string' || typeof value.source !== 'string' || !/^[a-z0-9_]{1,64}$/.test(value.source) || !['complete','snapshot','empty','partial','failed'].includes(value.status) || !Array.isArray(value.files) || !Array.isArray(value.sample) || value.sample.length > 3 || !Number.isSafeInteger(value.row_count)) throw Error('DataHub response schema is invalid');
  const keys=['dataset_id','source','provider','capability','attempted_sources','source_url','schema_version','status','row_count','provider_total','pages_fetched','pagination_complete','requested_range','actual_range','retrieved_at','as_of','cache_hit','fields','missing','limitations','manifest_sha256'];
  return {dataset_id:value.dataset_id,source:value.source,status:value.status,
    manifest_json:JSON.stringify(Object.fromEntries(keys.filter(key=>key in value).map(key=>[key,value[key]]))),
    files_json:JSON.stringify(value.files.map(({name,path,sha256})=>({name,path,sha256}))),sample_json:JSON.stringify(value.sample)};
}

export function apply(ctx, config) {
  if (typeof config?.researchRoot !== 'string' || !isAbsolute(config.researchRoot)) throw Error('Public data requires an absolute research root');
  const outputKeys=['dataset_id','source','status','manifest_json','files_json','sample_json'];
  for (const [toolName,[capability,description,properties,required]] of Object.entries(BUSINESS)) {
    const common={source:{type:'string',description:'目录来源 ID；默认 auto'},allow_fallback:{type:'boolean'},refresh:{type:'boolean'}};
    ctx.tools.register({
      name:toolName,
      description:`${description}。由 DataHub 按静态目录选源、校验并保存会话隔离快照；目录登记不代表来源已适配或在线。`,
      parameters:{type:'object',properties:{...properties,...common},required,additionalProperties:false},
      output:{schema:{type:'object',properties:Object.fromEntries(outputKeys.map(key=>[key,{type:'string'}])),required:outputKeys,additionalProperties:false},render(_args,value){return [{type:'text',text:JSON.stringify(value)}];}},
      async execute(args,exec) {
        const query=stableBusinessQuery(capability,args,properties);exec.signal.throwIfAborted();
        const cwd=await trustedDirectory(ctx,exec,config);exec.signal.throwIfAborted();
        if (!/^[a-zA-Z0-9_.-]{1,120}$/.test(exec.agent.session.header.id) || !/^[a-zA-Z0-9_.:-]{1,120}$/.test(exec.callId)) throw Error('Native call identity is invalid');
        const identity={session_id:basename(cwd),call_id:`${exec.agent.session.header.id}:${exec.callId}`};
        const approval=ctx.get('approval');
        if (!approval) throw Error('Native approval unavailable; HTTP not sent');
        const source=query.source==='auto'?'DataHub 自动选源':query.source;
        const outcome=await approval.request({agent:exec.agent,toolName,callId:exec.callId,reason:`${description}；来源：${source}。只发送业务参数，不发送附件、聊天、模型凭据或宿主路径。`,signal:exec.signal});
        if (outcome!=='allowed-once') {ctx.logger.info('business_data_not_authorized tool=%s outcome=%s',toolName,outcome);throw Error(`Business data approval ${outcome}; HTTP not sent`);}
        exec.signal.throwIfAborted();
        const control=await privateControl(config.researchRoot);exec.signal.throwIfAborted();
        const headers={'Content-Type':'application/json','X-Research-Data-Key':control.token};
        const signal=AbortSignal.any([exec.signal,AbortSignal.timeout(22000)]);
        let cancellation;
        const cancel=()=>cancellation ??= (async()=>{try {const response=await globalThis.fetch(control.url+'/api/research/internal/data/cancel',{method:'POST',headers,body:JSON.stringify(identity),redirect:'error',credentials:'omit',signal:AbortSignal.timeout(2500)});await response.body?.cancel();if(!response.ok)throw Error('cancel rejected');} catch {ctx.logger.warn('datahub_cancel_not_confirmed');}})();
        signal.addEventListener('abort',cancel,{once:true});
        ctx.logger.info('business_data_request_started tool=%s',toolName);
        try {
          const response=await globalThis.fetch(control.url+'/api/research/internal/data/business-query',{method:'POST',headers,body:JSON.stringify({...identity,query}),redirect:'error',credentials:'omit',signal});
          const result=smallResult(await boundedJson(response,signal));
          ctx.logger.info('business_data_request_completed tool=%s',toolName);return result;
        } catch(error) {await cancel();ctx.logger.warn('business_data_request_failed tool=%s type=%s',toolName,error.name);throw error;}
        finally {signal.removeEventListener('abort',cancel);if(cancellation)await cancellation;}
      },
    });
  }
}
