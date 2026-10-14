/** Public HTTP acquisition and durable parse inbox. No research or model bootstrap. */
import type postgres from 'postgres';
import type {PgBoss} from 'pg-boss';
import {readFile} from 'node:fs/promises';
import {randomUUID} from 'node:crypto';
import {parseFeed,feedNext,type FeedMaterial} from './feed.ts';
import {sha256,identityKeyForUrl,contentHash} from './material.ts';
import {ingestPage} from './database.ts';
import {withOwnerTransaction,type RuntimeOwner,type Claim} from './control.ts';
import {enqueueTransaction,type JobOutput} from './queue.ts';
import type {HotConfig} from './config.ts';
import {schemaName} from './config.ts';
import {logEvent} from './log.ts';
import {registerProcessing} from './processing.ts';

type Sql=ReturnType<typeof postgres>;
export interface PublicSource {id:string;operator:string;channelHint:string;official:boolean;url:string}
export async function publicSources():Promise<PublicSource[]>{
  const value=JSON.parse(await readFile(new URL('../../../app/research_web/datahub/hot_public_sources.json',import.meta.url),'utf8'));
  if(value.version!==1||!Array.isArray(value.sources)||value.sources.length>100)throw Error('hot_catalog_invalid');
  const ids=new Set<string>();
  for(const source of value.sources){
    const url=new URL(source.url);
    if(!/^[a-z][a-z0-9_-]{0,47}$/.test(source.id)||ids.has(source.id)||url.protocol!=='https:'||url.username||url.password||url.port||url.hash||!source.operator)throw Error('hot_catalog_invalid');
    ids.add(source.id);
  }
  return value.sources;
}
export async function seedPublicSources(db:Sql,schema:string):Promise<void>{
  schemaName(schema);
  for(const source of await publicSources())await db`insert into ${db(schema)}.sources(id,operator,config)
    values(${source.id},${source.operator},${db.json({adapter:'public_feed',catalogId:source.id})}) on conflict(id) do nothing`;
}
interface Acquisition {raw:Buffer|null;acquiredAt:Date;items:FeedMaterial[];code:string|null;retrySeconds:number;feedEntries?:number;timeConflicts?:number}
function combineFeedEntries(entries:FeedMaterial[]){
  const groups=new Map<string,FeedMaterial[]>();let timeConflicts=0;
  for(const item of entries){const identity=identityKeyForUrl(item.url)!;const group=groups.get(identity)??[];group.push(item);groups.set(identity,group);}
  const items=[...groups.values()].map(group=>{
    if(new Set(group.map(contentHash)).size!==1)throw Error('hot_source_identity_conflict');
    // A duplicate listing is one material, not independent corroboration. Keep all
    // raw timestamp declarations; never choose between contradictory instants.
    const sorted=[...group].sort((a,b)=>{
      const left=JSON.stringify(a),right=JSON.stringify(b);return left<right?-1:left>right?1:0;
    });
    const result={...sorted[0]};
    for(const [rawKey,timeKey]of [['publishedRaw','publishedAt'],['updatedRaw','sourceUpdatedAt']] as const){
      const raws=[...new Set(group.map(item=>item[rawKey]))].sort();
      const instants=[...new Set(group.map(item=>item[timeKey]?.toISOString()??null))];
      if(raws.length>1){
        result[rawKey]=JSON.stringify(raws);
        result[timeKey]=instants.length===1&&instants[0]!==null?new Date(instants[0]):null;
        if(instants.length!==1||instants[0]===null)timeConflicts++;
      }
    }
    if(new Set(group.map(item=>item.upstreamId)).size>1)result.upstreamId=null;
    return result;
  });
  return {items,timeConflicts};
}
export async function acquireFeed(source:PublicSource,signal:AbortSignal,fetcher:typeof fetch=fetch):Promise<Acquisition>{
  let raw:Buffer|null=null;let acquiredAt=new Date();
  try{
    const response=await fetcher(source.url,{signal:AbortSignal.any([signal,AbortSignal.timeout(25000)]),redirect:'error',
      headers:{accept:'application/rss+xml,application/atom+xml,application/xml,text/xml', 'user-agent':'ResearchWorkbench-Hot/1'}});
    if(!response.ok){
      const seconds=Number(response.headers.get('retry-after'));
      await response.body?.cancel();
      return {raw:null,acquiredAt:new Date(),items:[],code:response.status===429?'hot_source_rate_limited':'hot_source_http_failed',
        retrySeconds:Number.isFinite(seconds)&&seconds>0?Math.min(86400,Math.ceil(seconds)):60};
    }
    if(!response.body)throw Error('hot_source_empty');
    const reader=response.body.getReader(),chunks:Uint8Array[]=[];let size=0;
    try{while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;
      if(size>4194304){await reader.cancel();throw Error('hot_source_size_limit');}chunks.push(value);}}
    finally{reader.releaseLock();}
    raw=Buffer.concat(chunks);acquiredAt=new Date();
    const text=new TextDecoder('utf-8',{fatal:true}).decode(raw);
    const parsed=parseFeed(text,source.url,acquiredAt),combined=combineFeedEntries(parsed);
    return {raw,acquiredAt,...combined,feedEntries:parsed.length,code:null,retrySeconds:0};
  }catch(error){
    const cause=error instanceof Error&&error.cause&&typeof error.cause==='object'&&'code'in error.cause?String(error.cause.code):'';
    const network:Record<string,string>={ENOTFOUND:'hot_source_dns_failed',EAI_AGAIN:'hot_source_dns_failed',ECONNREFUSED:'hot_source_connection_refused',
      ECONNRESET:'hot_source_connection_reset',UND_ERR_SOCKET:'hot_source_connection_reset',UND_ERR_CONNECT_TIMEOUT:'hot_source_connect_timeout'};
    const code=signal.aborted?'hot_source_cancelled':error instanceof Error&&/^hot_source_[a-z_]+$/.test(error.message)?error.message:
      error instanceof Error&&error.name==='TimeoutError'?'hot_source_timeout':network[cause]??(raw!==null?'hot_source_parse_failed':'hot_source_network_failed');
    return {raw,acquiredAt,items:[],code,retrySeconds:60};
  }
}
export interface FeedPage {url:string;acquired:Acquisition}
export interface FeedPages {pages:FeedPage[];gap:string|null;stop:string}
/** A single owner-fenced job, at most 3 x 4 MiB, one shared 25-second deadline.
 * Partial HTTP failure keeps preceding raw pages and inbox entries for commit.
 * No date ordering or calendar completeness is inferred from a feed boundary.
 */
export async function acquireFeedPages(source:PublicSource,signal:AbortSignal,backfillDays:number,fetcher:typeof fetch=fetch):Promise<FeedPages>{
  if(!Number.isInteger(backfillDays)||backfillDays<0||backfillDays>3650)throw Error('hot_collection_payload_invalid');
  const combined=AbortSignal.any([signal,AbortSignal.timeout(25000)]),pages:FeedPage[]=[],seen=new Set<string>();
  const cutoff=Date.now()-backfillDays*86400000;let url=source.url;
  for(let index=0;index<3;index++){
    seen.add(url);const acquired=await acquireFeed({...source,url},combined,fetcher);pages.push({url,acquired});
    if(acquired.code)return {pages,gap:acquired.code,stop:'page_failed'};
    let next:string|null;
    try{next=feedNext(acquired.raw!.toString('utf8'),url,new URL(source.url).origin);}
    catch(error){return {pages,gap:error instanceof Error?error.message:'hot_source_pagination_unsafe',stop:'link_rejected'};}
    if(!next)return {pages,gap:null,stop:'no_next_link'};
    if(seen.has(next))return {pages,gap:'hot_source_pagination_cycle',stop:'link_rejected'};
    if(backfillDays===0)return {pages,gap:'hot_source_backfill_disabled',stop:'range_disabled'};
    if(acquired.items.length&&acquired.items.every(item=>item.publishedAt!==null&&item.publishedAt.getTime()<cutoff))return {pages,gap:'hot_source_backfill_boundary',stop:'range_boundary'};
    if(index===2)return {pages,gap:'hot_source_page_limit',stop:'page_limit'};
    url=next;
  }
  throw Error('hot_source_page_limit');
}
function payload(value:postgres.JSONValue,key:string,allowed=[key]):string{
  if(!value||typeof value!=='object'||Array.isArray(value))throw Error('hot_collection_payload_invalid');
  const row=value as Record<string,unknown>;
  if(typeof row[key]!=='string'||Object.keys(row).some(name=>!allowed.includes(name)))throw Error('hot_collection_payload_invalid');
  return row[key];
}
export function collectionHandlers(db:Sql,boss:PgBoss,schema:string,owner:RuntimeOwner,config:HotConfig,
  fetcher:typeof fetch=fetch,sourceControllers:Map<string,AbortController>=new Map()){
  schemaName(schema);
  return {
    'hot.collect':async(value:postgres.JSONValue,signal:AbortSignal,granted:Claim):Promise<JobOutput>=>{
      const sourceId=payload(value,'sourceId',['sourceId','sequence']);
      const sequence=payload(value,'sequence',['sourceId','sequence']);
      if(!/^\d{1,18}$/.test(sequence))throw Error('hot_collection_payload_invalid');
      const inputKey='hot.collect:'+sourceId+':'+sequence;
      const source=(await publicSources()).find(item=>item.id===sourceId);
      signal.throwIfAborted();
      if(!source)throw Error('hot_source_unknown');
      if(granted.inputKey!==inputKey||granted.owner.generation!==owner.generation)throw Error('hot_claim_stale');
      const runId=randomUUID();
      const sourceController=new AbortController();
      if(sourceControllers.has(sourceId))throw Error('hot_source_busy');
      sourceControllers.set(sourceId,sourceController);
      const combined=AbortSignal.any([signal,sourceController.signal]);
      let batch:FeedPages;
      try{
      await withOwnerTransaction(db,schema,owner,async tx=>{
        combined.throwIfAborted();
        const [row]=await tx`select enabled,config from ${tx(schema)}.sources where id=${sourceId}`;
        if(!row?.enabled||row.config.adapter!=='public_feed'||row.config.catalogId!==sourceId)throw Error('hot_source_paused');
        const [claim]=await tx`select attempt,lease_token from ${tx(schema)}.job_claims where input_key=${inputKey} and state='running'
          and generation=${owner.generation} and lease_until>clock_timestamp() and lease_token=${granted.leaseToken}
          and worker_id=${granted.workerId} and job_id=${granted.jobId}`;
        if(!claim)throw Error('hot_claim_stale');
        await tx`insert into ${tx(schema)}.collection_runs(id,source_id,generation,input_key,attempt,lease_token,state)
          values(${runId},${sourceId},${owner.generation},${inputKey},${claim.attempt},${claim.lease_token},'running')`;
        combined.throwIfAborted();
      });
      combined.throwIfAborted();
      batch=await acquireFeedPages(source,combined,config.collection.backfillDays,fetcher);
      if(combined.aborted)throw Error('hot_source_cancelled');
      }
      finally{if(sourceControllers.get(sourceId)===sourceController)sourceControllers.delete(sourceId);}
      const pages=batch.pages.map(page=>({...page,pageId:randomUUID()}));
      const failed=pages.find(page=>page.acquired.code!==null);
      const errorCode=failed?.acquired.code??(batch.stop==='link_rejected'?batch.gap:null);
      const itemCount=pages.reduce((count,page)=>count+page.acquired.items.length,0);
      const latest=pages.at(-1)!.acquired.acquiredAt;
      return {result:{sourceId,runId,state:errorCode?'failed':'acquired',itemCount,pageCount:pages.length,stop:batch.stop,gap:batch.gap},commit:async tx=>{
        const [sourceState]=await tx`select last_success_at,enabled from ${tx(schema)}.sources where id=${sourceId} for update`;
        if(!sourceState?.enabled)throw Error('hot_source_paused');
        if(sourceState.last_success_at&&sourceState.last_success_at>pages[0].acquired.acquiredAt)throw Error('hot_page_obsolete');
        for(const [index,{url,pageId,acquired}]of pages.entries()){
          if(acquired.raw===null)continue;
          const times=acquired.items.flatMap(item=>item.publishedAt?[item.publishedAt]:[]).sort((a,b)=>a.getTime()-b.getTime());
          await tx`insert into ${tx(schema)}.raw_pages(id,source_id,body,body_hash,acquired_at,metadata,coverage,oldest_published_at,newest_published_at,parsed_count,gap)
            values(${pageId},${sourceId},${acquired.raw},${sha256(acquired.raw)},${acquired.acquiredAt},
            ${tx.json({runId,pageIndex:index,url,pageCount:pages.length,stop:batch.stop,backfillDays:config.collection.backfillDays,feedEntries:acquired.feedEntries??0,timeConflicts:acquired.timeConflicts??0})},
            ${acquired.code?'unknown':pages.length>1||batch.gap?'partial':'latest_snapshot'},${times[0]??null},${times.at(-1)??null},${acquired.items.length},
            ${batch.gap?tx.json({code:batch.gap}):acquired.timeConflicts?tx.json({code:'hot_source_time_conflict',fields:acquired.timeConflicts}):null})`;
          for(let ordinal=0;ordinal<acquired.items.length;ordinal++)await tx`insert into ${tx(schema)}.material_inbox(page_id,ordinal,payload)
            values(${pageId},${ordinal},${tx.json(JSON.parse(JSON.stringify(acquired.items[ordinal])))})`;
        }
        const firstPending=pages.find(page=>page.acquired.items.length);
        if(firstPending)await enqueueTransaction(boss,tx,'hot.parse',firstPending.pageId+':0',{pageId:firstPending.pageId});
        await tx`update ${tx(schema)}.collection_runs set finished_at=clock_timestamp(),state=${errorCode?'failed':'acquired'},error_code=${errorCode},
          raw_page_id=${pages.find(page=>page.acquired.raw!==null)?.pageId??null},item_count=${itemCount} where id=${runId}`;
        if(errorCode){
          // Earlier pages remain recoverable but an incomplete request never advances success.
          await tx`update ${tx(schema)}.sources set last_error_code=${errorCode},consecutive_failures=least(consecutive_failures+1,10),
            next_due_at=clock_timestamp()+greatest(${failed?.acquired.retrySeconds??60},least(86400,60*power(2,least(consecutive_failures,10))))*interval '1 second' where id=${sourceId}`;
          logEvent('collection_failed');return;
        }
        // Every page and inbox is durable in this owner/claim-fenced transaction before watermark.
        await tx`update ${tx(schema)}.sources set last_success_at=${latest},last_error_code=null,consecutive_failures=0,
          cursor=${tx.json({pageId:pages.at(-1)!.pageId,pageIds:pages.map(page=>page.pageId),stage:itemCount?'queued':'parsed',count:itemCount,stop:batch.stop,gap:batch.gap})} where id=${sourceId}`;
        logEvent('collection_acquired',itemCount);
      }};
    },
    'hot.parse':async(value:postgres.JSONValue,signal:AbortSignal):Promise<JobOutput>=>{
      const pageId=payload(value,'pageId');
      const [page]=await db`select p.*,s.enabled from ${db(schema)}.raw_pages p join ${db(schema)}.sources s on s.id=p.source_id where p.id=${pageId}`;
      if(!page||!page.enabled)throw Error('hot_source_paused');
      const entries=await db`select ordinal,payload from ${db(schema)}.material_inbox where page_id=${pageId} and not processed order by ordinal limit ${config.collection.maxItems}`;
      const items=entries.map(row=>({...row.payload,publishedAt:row.payload.publishedAt?new Date(row.payload.publishedAt):null,
        sourceUpdatedAt:row.payload.sourceUpdatedAt?new Date(row.payload.sourceUpdatedAt):null})) as FeedMaterial[];
      if(signal.aborted)throw Error('hot_source_cancelled');
      return {result:{pageId,processed:items.length},commit:async tx=>{
        const [enabled]=await tx`select enabled from ${tx(schema)}.sources where id=${page.source_id} for update`;
        if(!enabled?.enabled)throw Error('hot_source_paused');
        const stored=await ingestPage(tx,{source:page.source_id,raw:page.body.toString('utf8'),acquiredAt:page.acquired_at,
          materials:items,cursor:{pageId,stage:'parsing'},existingPageId:pageId},schema);
        await registerProcessing(tx,schema,stored.materialIds);
        for(const row of entries)await tx`update ${tx(schema)}.material_inbox set processed=true where page_id=${pageId} and ordinal=${row.ordinal}`;
        const remaining=await tx`select ordinal from ${tx(schema)}.material_inbox where page_id=${pageId} and not processed order by ordinal limit 1`;
        if(remaining.length)await enqueueTransaction(boss,tx,'hot.parse',pageId+':'+remaining[0].ordinal,{pageId});
        else {
          const next=await tx`select i.page_id,min(i.ordinal)::int ordinal from ${tx(schema)}.material_inbox i join ${tx(schema)}.raw_pages p on p.id=i.page_id
            where p.source_id=${page.source_id} and not i.processed group by i.page_id,p.acquired_at,p.metadata->>'pageIndex' order by p.acquired_at,p.metadata->>'pageIndex',i.page_id limit 1`;
          if(next.length)await enqueueTransaction(boss,tx,'hot.parse',next[0].page_id+':'+next[0].ordinal,{pageId:next[0].page_id});
          else await tx`update ${tx(schema)}.sources set cursor=cursor||'{"stage":"parsed"}'::jsonb where id=${page.source_id} and last_error_code is null`;
        }
      }};
    }
  };
}
export async function scheduleCollection(db:Sql,boss:PgBoss,schema:string,owner:RuntimeOwner,config:HotConfig):Promise<number>{
  return withOwnerTransaction(db,schema,owner,async tx=>{
    await tx`update ${tx(schema)}.collection_runs r set state='failed',finished_at=clock_timestamp(),error_code='hot_collection_interrupted'
      where r.state='running' and (r.generation<>${owner.generation} or not exists(select 1 from ${tx(schema)}.job_claims c
        where c.input_key=r.input_key and c.lease_token=r.lease_token and c.state='running' and c.lease_until>clock_timestamp()))`;
    // Resume unfinished parsing first. Collection of the same source waits for this inbox.
    const pending=await tx`select distinct on(p.source_id) i.page_id,min(i.ordinal)::int ordinal from ${tx(schema)}.material_inbox i
      join ${tx(schema)}.raw_pages p on p.id=i.page_id join ${tx(schema)}.sources s on s.id=p.source_id
      where not i.processed and s.enabled group by p.source_id,i.page_id,p.acquired_at,p.metadata->>'pageIndex'
      order by p.source_id,p.acquired_at,p.metadata->>'pageIndex',i.page_id limit 100`;
    for(const row of pending)await enqueueTransaction(boss,tx,'hot.parse',row.page_id+':'+row.ordinal,{pageId:row.page_id});
    const sources=await tx`select s.id,s.schedule_sequence from ${tx(schema)}.sources s where enabled and config->>'adapter'='public_feed'
      and (next_due_at is null or next_due_at<=clock_timestamp())
      and not exists(select 1 from ${tx(schema)}.job j where j.name='hot.collect' and j.state in ('created','retry','active') and j.data->'payload'->>'sourceId'=s.id)
      and not exists(select 1 from ${tx(schema)}.collection_runs r where r.source_id=s.id and r.state='running')
      and not exists(select 1 from ${tx(schema)}.raw_pages p join ${tx(schema)}.material_inbox i on i.page_id=p.id where p.source_id=s.id and not i.processed)
      order by s.id for update of s skip locked limit 100`;
    for(const row of sources){
      await enqueueTransaction(boss,tx,'hot.collect',row.id+':'+row.schedule_sequence,{sourceId:row.id,sequence:String(row.schedule_sequence)});
      await tx`update ${tx(schema)}.sources set schedule_sequence=schedule_sequence+1,
        next_due_at=clock_timestamp()+coalesce(frequency_seconds,${config.collection.frequencySeconds})*interval '1 second' where id=${row.id}`;
    }
    return sources.length;
  });
}
