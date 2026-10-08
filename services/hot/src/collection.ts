/** Public HTTP acquisition and durable parse inbox. No research or model bootstrap. */
import type postgres from 'postgres';
import type {PgBoss} from 'pg-boss';
import {readFile} from 'node:fs/promises';
import {randomUUID} from 'node:crypto';
import {parseFeed,type FeedMaterial} from './feed.ts';
import {sha256,identityKeyForUrl,contentHash} from './material.ts';
import {ingestPage} from './database.ts';
import {withOwnerTransaction,type RuntimeOwner,type Claim} from './control.ts';
import {enqueueTransaction,type JobOutput} from './queue.ts';
import type {HotConfig} from './config.ts';
import {schemaName} from './config.ts';
import {logEvent} from './log.ts';

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
      let acquired:Acquisition;
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
      acquired=await acquireFeed(source,combined,fetcher);
      if(combined.aborted)throw Error('hot_source_cancelled');
      }
      finally{if(sourceControllers.get(sourceId)===sourceController)sourceControllers.delete(sourceId);}
      const pageId=randomUUID();
      return {result:{sourceId,runId,state:acquired.code?'failed':'acquired',itemCount:acquired.items.length},commit:async tx=>{
        const [sourceState]=await tx`select last_success_at from ${tx(schema)}.sources where id=${sourceId} for update`;
        const [enabled]=await tx`select enabled from ${tx(schema)}.sources where id=${sourceId}`;
        if(!enabled.enabled)throw Error('hot_source_paused');
        if(sourceState.last_success_at&&sourceState.last_success_at>acquired.acquiredAt)throw Error('hot_page_obsolete');
        if(acquired.raw!==null){
          const times=acquired.items.flatMap(item=>item.publishedAt?[item.publishedAt]:[]).sort((a,b)=>a.getTime()-b.getTime());
          await tx`insert into ${tx(schema)}.raw_pages(id,source_id,body,body_hash,acquired_at,metadata,coverage,oldest_published_at,newest_published_at,parsed_count,gap)
              values(${pageId},${sourceId},${acquired.raw},${sha256(acquired.raw)},${acquired.acquiredAt},
              ${tx.json({runId,feedEntries:acquired.feedEntries??0,timeConflicts:acquired.timeConflicts??0})},${acquired.code?'unknown':'latest_snapshot'},${times[0]??null},${times.at(-1)??null},${acquired.items.length},
              ${acquired.code?tx.json({code:acquired.code}):acquired.timeConflicts?tx.json({code:'hot_source_time_conflict',fields:acquired.timeConflicts}):null})`;
        }
        await tx`update ${tx(schema)}.collection_runs set finished_at=clock_timestamp(),state=${acquired.code?'failed':'acquired'},error_code=${acquired.code},
          raw_page_id=${acquired.raw!==null?pageId:null},item_count=${acquired.items.length} where id=${runId}`;
        if(acquired.code){
          await tx`update ${tx(schema)}.sources set last_error_code=${acquired.code},consecutive_failures=least(consecutive_failures+1,10),
            next_due_at=clock_timestamp()+greatest(${acquired.retrySeconds},least(86400,60*power(2,least(consecutive_failures,10))))*interval '1 second' where id=${sourceId}`;
          logEvent('collection_failed');return;
        }
        for(let ordinal=0;ordinal<acquired.items.length;ordinal++)await tx`insert into ${tx(schema)}.material_inbox(page_id,ordinal,payload)
          values(${pageId},${ordinal},${tx.json(JSON.parse(JSON.stringify(acquired.items[ordinal])))})`;
        // All material records OR durable pending records exist before publishing the acquisition watermark.
        await tx`update ${tx(schema)}.sources set last_success_at=${acquired.acquiredAt},last_error_code=null,consecutive_failures=0,
          cursor=${tx.json({pageId,stage:acquired.items.length?'queued':'parsed',count:acquired.items.length})} where id=${sourceId}`;
        if(acquired.items.length)await enqueueTransaction(boss,tx,'hot.parse',pageId+':0',{pageId});
        logEvent('collection_acquired',acquired.items.length);
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
        await ingestPage(tx,{source:page.source_id,raw:page.body.toString('utf8'),acquiredAt:page.acquired_at,
          materials:items,cursor:{pageId,stage:'parsing'},existingPageId:pageId},schema);
        for(const row of entries)await tx`update ${tx(schema)}.material_inbox set processed=true where page_id=${pageId} and ordinal=${row.ordinal}`;
        const remaining=await tx`select ordinal from ${tx(schema)}.material_inbox where page_id=${pageId} and not processed order by ordinal limit 1`;
        if(remaining.length)await enqueueTransaction(boss,tx,'hot.parse',pageId+':'+remaining[0].ordinal,{pageId});
        else await tx`update ${tx(schema)}.sources set cursor=${tx.json({pageId,stage:'parsed',count:page.parsed_count})} where id=${page.source_id}`;
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
    const pending=await tx`select i.page_id,min(i.ordinal)::int ordinal from ${tx(schema)}.material_inbox i
      join ${tx(schema)}.raw_pages p on p.id=i.page_id join ${tx(schema)}.sources s on s.id=p.source_id
      where not i.processed and s.enabled group by i.page_id limit 100`;
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
