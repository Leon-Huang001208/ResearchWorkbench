/** Controller-only immutable brief versions; request UUID replay never resamples evidence. */
import type postgres from 'postgres';
import {freezeBrief,sealBrief,briefMarkdown,type FrozenBrief,type BriefPayload} from './briefs.ts';
import {withOwnerTransaction,type RuntimeOwner} from './control.ts';
import {schemaName} from './config.ts';
import {canonicalGroupingInput} from './processing.ts';
import {sha256,publicationTime} from './material.ts';
import {logEvent} from './log.ts';
type Sql=ReturnType<typeof postgres>;
type Params=Record<string,postgres.JSONValue>;
function uuid(value:unknown):string{if(typeof value!=='string'||!/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(value))throw Error('hot_brief_identity_invalid');return value.toLowerCase();}
function integer(value:unknown,fallback:number,min:number,max:number){const n=value??fallback;
  if(typeof n!=='number'||!Number.isSafeInteger(n)||n<min||n>max)throw Error('hot_brief_params_invalid');return n;}
function only(params:Params,keys:string[]){if(Object.keys(params).some(key=>!keys.includes(key)))throw Error('hot_brief_params_invalid');}
function metadata(row:Record<string,unknown>){return {briefId:row.brief_id,version:row.version,contentHash:row.content_hash,createdAt:row.created_at};}
function json(value:unknown){return JSON.parse(JSON.stringify(value)) as postgres.JSONValue;}
export async function briefGet(db:Sql,schema:string,params:Params){
  schemaName(schema);only(params,['briefId','version']);const id=uuid(params.briefId),version=integer(params.version,0,0,1000000);
  const [row]=await db`select v.* from ${db(schema)}.brief_versions v join ${db(schema)}.briefs b on b.id=v.brief_id
    where v.brief_id=${id} and v.version=case when ${version}=0 then b.current_version else ${version} end`;
  if(!row)throw Error('hot_brief_unknown');
  const brief:FrozenBrief={payload:row.payload as BriefPayload,contentHash:row.content_hash};
  if(sealBrief(brief.payload).contentHash!==brief.contentHash)throw Error('hot_brief_integrity_invalid');
  return json({...metadata(row),payload:brief.payload});
}
export async function briefExport(db:Sql,schema:string,params:Params){
  only(params,['briefId','version','offset']);const offset=integer(params.offset,0,0,4000000);
  if(offset>0&&params.version===undefined)throw Error('hot_brief_cutoff_required');
  if(offset>0)integer(params.version,0,1,1000000);
  const saved=await briefGet(db,schema,{briefId:params.briefId,...(params.version===undefined?{}:{version:params.version})}) as unknown as {briefId:string;version:number;contentHash:string;payload:BriefPayload};
  const bytes=Buffer.from(briefMarkdown({payload:saved.payload,contentHash:saved.contentHash}));
  if(bytes.length>4000000)throw Error('hot_brief_limit');
  if(offset>bytes.length||(offset<bytes.length&&(bytes[offset]&0xc0)===0x80))throw Error('hot_brief_params_invalid');
  let end=Math.min(offset+32768,bytes.length);
  while(end<bytes.length&&(bytes[end]&0xc0)===0x80)end--;
  return json({briefId:saved.briefId,version:saved.version,contentHash:saved.contentHash,format:'markdown',
    text:bytes.subarray(offset,end).toString('utf8'),offset,nextOffset:end<bytes.length?end:null,totalBytes:bytes.length,textHash:sha256(bytes)});
}
export async function briefList(db:Sql,schema:string,params:Params){
  schemaName(schema);only(params,['limit','offset','cutoff']);const limit=integer(params.limit,20,1,50),offset=integer(params.offset,0,0,10000);
  if(offset>0&&params.cutoff===undefined)throw Error('hot_brief_cutoff_required');
  const cutoff=params.cutoff===undefined?new Date():typeof params.cutoff==='string'?publicationTime(params.cutoff,new Date()):null;
  if(!cutoff||cutoff>new Date())throw Error('hot_brief_cutoff_invalid');
  const rows=await db`with latest as(select distinct on(brief_id) * from ${db(schema)}.brief_versions
    where created_at<=${cutoff} order by brief_id,version desc)
    select v.brief_id,v.version,v.content_hash,v.created_at,v.payload->>'cutoff' cutoff,
    v.payload->'channel'->>'channel_id' channel_id from latest v
    order by v.created_at desc,v.brief_id offset ${offset} limit ${limit+1}`;
  return json({cutoff:cutoff.toISOString(),items:rows.slice(0,limit).map(row=>({...metadata(row),cutoff:row.cutoff,channelId:row.channel_id})),limit,offset,hasMore:rows.length>limit});
}
export async function createBriefRequest(db:Sql,schema:string,owner:RuntimeOwner,requestId:string,params:Params,signal?:AbortSignal){
  schemaName(schema);requestId=uuid(requestId);only(params,['briefId','expectedVersion','eventIds','channelId','cutoff','from','to','timezone']);
  const briefId=uuid(params.briefId),expected=integer(params.expectedVersion,-1,0,999999);
  if(!Array.isArray(params.eventIds)||params.eventIds.some(id=>typeof id!=='string')||typeof params.channelId!=='string'||typeof params.cutoff!=='string'||
    ['from','to','timezone'].some(key=>params[key]!==undefined&&typeof params[key]!=='string'))throw Error('hot_brief_params_invalid');
  const input={eventIds:params.eventIds as string[],channelId:params.channelId,cutoff:params.cutoff,
    ...(params.from===undefined?{}:{from:params.from as string}),...(params.to===undefined?{}:{to:params.to as string}),
    ...(params.timezone===undefined?{}:{timezone:params.timezone as string})};
  const hash=sha256(canonicalGroupingInput(params));
  try{
    // Validate control privilege before any potentially expensive read snapshot.
    const [permission]=await db`select has_table_privilege(current_user,${schema+'.brief_requests'},'INSERT') allowed`;
    if(!permission.allowed)throw Error('hot_brief_control_denied');
    const lookup=async(connection:Sql)=>{
      const [cached]=await connection`select r.params_hash,v.brief_id,v.version,v.content_hash,v.created_at
        from ${connection(schema)}.brief_requests r join ${connection(schema)}.brief_versions v
        on v.brief_id=r.brief_id and v.version=r.version where r.request_id=${requestId}`;
      if(cached&&cached.params_hash!==hash)throw Error('hot_brief_request_conflict');return cached;
    };
    const prior=await lookup(db);signal?.throwIfAborted();
    if(prior)return await withOwnerTransaction(db,schema,owner,async()=>json({...metadata(prior),requestId}));
    const frozen=await freezeBrief(db,schema,input,signal);
    // Leave room for JSONB whitespace, signed response encoding and transport metadata.
    if(Buffer.byteLength(JSON.stringify(frozen.payload))>350000)throw Error('hot_brief_persist_limit');
    const result=await withOwnerTransaction(db,schema,owner,async tx=>{
      signal?.throwIfAborted();const cached=await lookup(tx as unknown as Sql);
      if(cached)return json({...metadata(cached),requestId});
      const [current]=await tx`select current_version from ${tx(schema)}.briefs where id=${briefId} for update`;
      if((current?.current_version??0)!==expected||(!current&&expected!==0))throw Error('hot_brief_version_conflict');
      if(!current)await tx`insert into ${tx(schema)}.briefs(id) values(${briefId})`;
      const [saved]=await tx`insert into ${tx(schema)}.brief_versions(brief_id,version,payload,content_hash)
        values(${briefId},${expected+1},${tx.json(JSON.parse(JSON.stringify(frozen.payload)))},${frozen.contentHash}) returning brief_id,version,content_hash,created_at`;
      await tx`insert into ${tx(schema)}.brief_requests(request_id,params_hash,brief_id,version,actor) values(${requestId},${hash},${briefId},${expected+1},'local_host')`;
      await tx`update ${tx(schema)}.briefs set current_version=${expected+1} where id=${briefId}`;
      signal?.throwIfAborted();return json({...metadata(saved),requestId});
    });
    logEvent('brief_saved');return result;
  }catch(error){logEvent('brief_failed');
    if(error instanceof Error&&/^hot_[a-z_]+$/.test(error.message))throw error;
    if(signal?.aborted)throw Error('hot_brief_cancelled');throw Error('hot_brief_save_failed');
  }
}
