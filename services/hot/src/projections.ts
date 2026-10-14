/** Read-only bounded as-of projections. Never schedules, fetches or calls a model. */
import type postgres from 'postgres';
import {eventAt,judgmentAt} from './events.ts';
import {publicationTime} from './material.ts';
import {schemaName} from './config.ts';
type Sql=ReturnType<typeof postgres>;
function paramsOnly(params:Record<string,postgres.JSONValue>,keys:string[]){if(Object.keys(params).some(k=>!keys.includes(k)))throw Error('hot_projection_params_invalid');}
function integer(value:unknown,fallback:number,max:number){const n=value??fallback;if(typeof n!=='number'||!Number.isSafeInteger(n)||n<0||n>max)throw Error('hot_projection_params_invalid');return n;}
function string(value:unknown,max=200){if(value===undefined)return '';if(typeof value!=='string'||value.length>max)throw Error('hot_projection_params_invalid');return value;}
function instant(value:unknown,optional=false,allowFuture=false):Date|null{
  if(value===undefined&&optional)return null;
  if(typeof value!=='string'||!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?(?:Z|[+-]\d\d:\d\d)$/.test(value))throw Error('hot_projection_cutoff_invalid');
  const date=publicationTime(value,allowFuture?new Date(8640000000000000):new Date());if(!date||(!allowFuture&&date.getTime()>Date.now()))throw Error('hot_projection_cutoff_invalid');return date;
}
function channel(value:unknown){const id=string(value,48);if(id&&!/^[a-z][a-z0-9_-]{0,47}$/.test(id))throw Error('hot_projection_channel_invalid');return id;}
function pattern(value:string){return '%'+value.replace(/[\\%_]/g,'\\$&')+'%';}
function json(value:unknown){return JSON.parse(JSON.stringify(value)) as postgres.JSONValue;}
export async function channelsAt(db:Sql,schema:string,params:Record<string,postgres.JSONValue>){
  schemaName(schema);paramsOnly(params,['cutoff']);const cutoff=instant(params.cutoff,true)??new Date();
  const rows=await db`select distinct on (channel_id) channel_id,version,config,created_at from ${db(schema)}.channel_versions
    where created_at<=${cutoff} order by channel_id,version desc limit 100`;
  return json({cutoff:cutoff.toISOString(),items:[...rows]});
}
export async function eventsList(db:Sql,schema:string,params:Record<string,postgres.JSONValue>){
  schemaName(schema);paramsOnly(params,['cutoff','channelId','q','topic','institution','asset','from','to','sort','limit','offset','minRelevance']);
  const cutoff=instant(params.cutoff,true)??new Date(),id=channel(params.channelId),limit=integer(params.limit,20,50),offset=integer(params.offset,0,10000);
  if(limit<1)throw Error('hot_projection_params_invalid');
  if(offset>0&&params.cutoff===undefined)throw Error('hot_projection_cutoff_required');
  const minRelevance=integer(params.minRelevance,id?1:0,100);
  const terms=['q','topic','institution','asset'].map(key=>string(params[key])).filter(Boolean).map(pattern);
  const from=instant(params.from,true,true),to=instant(params.to,true,true);if(from&&to&&from>to)throw Error('hot_projection_params_invalid');
  const sort=string(params.sort)||'recent';if(!['recent','heat','importance','increment','relevance'].includes(sort)||(!id&&sort!=='recent'))throw Error('hot_projection_sort_invalid');
  if(id){const rows=await db`select channel_id from ${db(schema)}.channel_versions where channel_id=${id} and created_at<=${cutoff} limit 1`;if(!rows.length)throw Error('hot_projection_channel_unknown');}
  const rows=await db`with latest as (
    select distinct on (event_id) event_id,revision,snapshot,created_at from ${db(schema)}.event_versions where created_at<=${cutoff} order by event_id,revision desc
  ),config as (select version from ${db(schema)}.channel_versions where channel_id=${id} and created_at<=${cutoff} order by version desc limit 1)
  select l.event_id id,l.revision,l.snapshot->>'title' title,l.created_at as "observedAt",
    l.snapshot->'occurredAt' as "occurredAt",l.snapshot->'effectiveAt' as "effectiveAt",jsonb_array_length(l.snapshot->'materials') as "materialCount",
    j.id as "judgmentId",j.judgment,j.authority,j.event_revision as "judgmentEventRevision",j.channel_version as "judgmentChannelVersion",x.details as "ruleEvidence"
  from latest l left join lateral (
    select * from ${db(schema)}.channel_judgments j where j.event_id=l.event_id and j.channel_id=${id} and j.created_at<=${cutoff}
      and (j.authority='human' or (j.event_revision=l.revision and j.channel_version=(select version from config)))
    order by case when j.authority='human' then 0 else 1 end,j.created_at desc,j.id desc limit 1
  ) j on true left join ${db(schema)}.channel_rule_evidence x on x.judgment_id=j.id
  where l.snapshot->>'state'='active' and (${!id} or l.snapshot->'manual'->'channels'='null'::jsonb or (l.snapshot->'manual'->'channels') ? ${id})
    and (${!id} or coalesce((j.judgment->>'relevance')::numeric,0)>=${minRelevance}
      or (${params.minRelevance===undefined} and (l.snapshot->'manual'->'channels') ? ${id}))
    and not exists(select 1 from unnest(${db.array(terms)}::text[]) term where
      not ((l.snapshot->>'title') ilike term or exists(select 1 from ${db(schema)}.event_materials r join ${db(schema)}.material_versions v
        on v.material_id=r.material_id and v.revision=r.material_revision where r.event_id=l.event_id and r.event_revision=l.revision and v.acquired_at<=${cutoff}
        and (v.title ilike term or v.excerpt ilike term))))
    and ((${from}::timestamptz is null and ${to}::timestamptz is null) or exists(
      select 1 from ${db(schema)}.event_materials r join ${db(schema)}.material_versions v on v.material_id=r.material_id and v.revision=r.material_revision
      where r.event_id=l.event_id and r.event_revision=l.revision and v.acquired_at<=${cutoff} and v.published_at is not null
        and (${from}::timestamptz is null or v.published_at>=${from}) and (${to}::timestamptz is null or v.published_at<=${to})))
  order by case when ${sort}='heat' then coalesce((j.judgment->>'heat')::numeric,0)
    when ${sort}='importance' then coalesce((j.judgment->>'importance')::numeric,0)
    when ${sort}='increment' then coalesce((j.judgment->>'informationIncrement')::numeric,0)
    when ${sort}='relevance' then coalesce((j.judgment->>'relevance')::numeric,0) else 0 end desc,l.created_at desc,l.event_id
  offset ${offset} limit ${limit+1}`;
  return json({cutoff:cutoff.toISOString(),channelId:id||null,sort,offset,limit,minRelevance,hasMore:rows.length>limit,nextOffset:rows.length>limit?offset+limit:null,
    filterMode:'literal_material_text',timeField:'publication',items:[...rows].slice(0,limit)});
}
export async function eventDetail(db:Sql,schema:string,params:Record<string,postgres.JSONValue>,signal?:AbortSignal){
  schemaName(schema);paramsOnly(params,['eventId','cutoff','reportOffset','reportLimit']);
  const id=string(params.eventId,36);if(!/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(id))throw Error('hot_projection_event_invalid');
  const cutoff=instant(params.cutoff,true)??new Date(),offset=integer(params.reportOffset,0,200),limit=integer(params.reportLimit,20,50);
  if(offset>0&&params.cutoff===undefined)throw Error('hot_projection_cutoff_required');
  if(!limit)throw Error('hot_projection_params_invalid');signal?.throwIfAborted();
  const event=await eventAt(db,schema,id,cutoff);if(!event)throw Error('hot_projection_event_unknown');
  const rows=await db`select v.*,m.original_url,r.relation,
    (select coalesce(jsonb_agg(source),'[]'::jsonb) from (select distinct s.id,s.operator from ${db(schema)}.discoveries d
      join ${db(schema)}.sources s on s.id=d.source_id join ${db(schema)}.raw_pages p on p.id=d.page_id
      where d.material_id=v.material_id and d.revision=v.revision and p.acquired_at<=${cutoff} order by s.id limit 10) source) sources
    from ${db(schema)}.event_materials r join ${db(schema)}.material_versions v on v.material_id=r.material_id and v.revision=r.material_revision
    join ${db(schema)}.materials m on m.id=v.material_id where r.event_id=${event.id} and r.event_revision=${event.revision} and v.acquired_at<=${cutoff}
    order by v.material_id,v.revision offset ${offset} limit ${limit}`;
  const reports=rows.map(row=>({materialId:row.material_id,revision:row.revision,contentHash:row.content_hash,title:row.title.slice(0,500),excerpt:row.excerpt.slice(0,1000),
    excerptIsPartial:row.excerpt.length>1000,titleIsPartial:row.title.length>500,url:row.original_url,relation:row.relation,state:row.state,
    publishedAt:row.published_at,acquiredAt:row.acquired_at,sourceUpdatedAt:row.source_updated_at,sources:row.sources}));
  const history=await db`select revision,created_at,snapshot->>'title' title,snapshot->>'state' state,snapshot->>'canonicalId' as "canonicalId"
    from ${db(schema)}.event_versions where event_id=${event.id} and created_at<=${cutoff} order by revision desc limit 20`;
  const channels=await db`select distinct channel_id from ${db(schema)}.channel_versions where created_at<=${cutoff} order by channel_id limit 100`;
  const judgments=[];
  for(const row of channels){signal?.throwIfAborted();const judgment=await judgmentAt(db,schema,event.id,row.channel_id,cutoff);if(judgment){
    const [evidence]=await db`select details,algorithm_version from ${db(schema)}.channel_rule_evidence where judgment_id=${judgment.id}`;
    judgments.push({channelId:row.channel_id,...judgment,ruleEvidence:evidence??null});}}
  signal?.throwIfAborted();return json({requestedId:id,canonicalId:event.id,revision:event.revision,cutoff:cutoff.toISOString(),title:event.snapshot.title,
    occurredAt:event.snapshot.occurredAt,effectiveAt:event.snapshot.effectiveAt,dateEvidence:event.snapshot.dateEvidence??null,links:event.snapshot.links,manual:event.snapshot.manual,
    reportOffset:offset,reportLimit:limit,materialCount:event.snapshot.materials.length,reports,history:[...history],historyLimitedTo:20,judgments});
}
