/** Explicit domain rules and immutable score evidence; never a trading recommendation. */
import type postgres from 'postgres';
import type {ChannelConfig,ChannelJudgment,EventSnapshot} from './events.ts';
import {saveChannelJudgmentTransaction,judgmentAt} from './events.ts';
import {withOwnerTransaction,type RuntimeOwner,type Tx} from './control.ts';
import {canonicalGroupingInput} from './processing.ts';
import {sha256} from './material.ts';
import {publicSources,type PublicSource} from './collection.ts';
import {schemaName} from './config.ts';
import {logEvent} from './log.ts';
type Sql=ReturnType<typeof postgres>;
export const RULE_VERSION='hot-domain-rules-v1';
export interface RuleReport {id:string;revision:number;contentHash:string;title:string;excerpt:string;url:string;publishedAt:Date|null;acquiredAt:Date;
  state:string;official:boolean;sources:{id:string;operator:string}[]}
function hit(text:string,keyword:string){
  const term=keyword.normalize('NFKC').toLowerCase().trim(),normalized=text.normalize('NFKC').toLowerCase();
  if(!term)return false;
  if(/^[a-z0-9 ]+$/.test(term))return new RegExp('(?:^|[^\\p{L}\\p{N}])'+term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'(?:$|[^\\p{L}\\p{N}])','u').test(normalized);
  return normalized.includes(term);
}
export function scoreChannel(config:ChannelConfig,reports:RuleReport[],previousHashes:string[],cutoff:Date){
  if(!Number.isFinite(cutoff.getTime()))throw Error('hot_channel_cutoff_invalid');
  const visible=reports.filter(r=>r.acquiredAt<=cutoff),active=visible.filter(r=>r.state!=='retracted');
  const terms=active.map(r=>({id:r.id,text:r.title+'\n'+r.excerpt,official:r.official}));
  const topics=config.topics.filter(topic=>terms.some(r=>hit(r.text,topic)));
  let relevance=topics.length?70:0,importance=topics.length?40:0;
  const matchedRules:{id:string;keywords:string[];materialIds:string[]}[]=[];
  for(const rule of config.rules??[]){
    const rows=terms.filter(r=>(!rule.requireOfficial||r.official)&&rule.keywords.some(term=>hit(r.text,term)));
    if(!rows.length)continue;
    matchedRules.push({id:rule.id,keywords:rule.keywords.filter(term=>rows.some(r=>hit(r.text,term))),materialIds:rows.map(r=>r.id)});
    relevance=Math.max(relevance,rule.relevance);importance=Math.max(importance,rule.importance);
  }
  const sourceIds=[...new Set(visible.flatMap(r=>r.sources.map(s=>s.id)))].sort();
  const operators=[...new Set(visible.flatMap(r=>r.sources.map(s=>s.operator)))].sort();
  // Hourly observation window: known publication only. Acquisition never supplies freshness.
  const start=new Date(Math.floor(cutoff.getTime()/3600000)*3600000-23*3600000);
  const fresh=active.filter(r=>r.publishedAt&&r.publishedAt>=start&&r.publishedAt<=cutoff);
  const freshOperators=new Set(fresh.flatMap(r=>r.sources.map(s=>s.operator)));
  const heat=fresh.length?Math.min(100,fresh.length*5+freshOperators.size*5):0;
  const novel=[...new Set(active.map(r=>r.contentHash))].filter(hash=>!previousHashes.includes(hash));
  const official=active.filter(r=>r.official);
  const metrics={reportCount:new Set(visible.map(r=>r.id)).size,sourceCount:sourceIds.length,independentOperators:operators.length,
    sourceIds,operators,freshReports:new Set(fresh.map(r=>r.id)).size,publicationWindowStart:start.toISOString(),novelContentVersions:novel.length,
    matchedTopics:topics,matchedRules,officialMaterialIds:official.map(r=>r.id)};
  const limitations=['规则分数是排序依据，未经概率校准；信源数量不等于独立事实核验。','信息增量统计内容版本差异，不等于已确认的新事实。','覆盖取决于已取得材料，不代表全行业或全天完整覆盖。'];
  if(visible.some(r=>!r.publishedAt))limitations.push('部分发布时间未知，未计入传播热度。');
  if(visible.some(r=>r.state==='retracted'))limitations.push('引用包含撤回材料，排除规则命中与新鲜度，仍需人工复核。');
  const judgment:ChannelJudgment={relevance,importance,informationIncrement:Math.min(100,novel.length*25),heat,
    evidence:official.length&&visible.every(r=>r.state!=='retracted')?'single_official':'unverified',
    reason:matchedRules.length?'命中规则 '+matchedRules.map(r=>r.id).join('、')+'；相关性与研究重要性独立于报道热度。':topics.length?'命中频道主题 '+topics.join('、')+'。':'未命中频道主题或规则；来源在配置中不自动代表内容相关。',limitations};
  return {judgment,metrics};
}
function official(report:{url:string;sources:{id:string;operator:string}[]},catalog:PublicSource[]){
  let host:string;try{host=new URL(report.url).hostname.replace(/^www\./,'');}catch{return false;}
  return report.sources.some(source=>catalog.some(entry=>{const expected=new URL(entry.url).hostname.replace(/^www\./,'');
    return entry.official&&entry.id===source.id&&entry.operator===source.operator&&(host===expected||host.endsWith('.'+expected));}));
}
async function reportsFor(tx:Tx,schema:string,id:string,revision:number,cutoff:Date,catalog:PublicSource[]):Promise<RuleReport[]>{
  const rows=await tx`select distinct on (v.material_id) v.*,m.original_url,
    (select coalesce(jsonb_agg(distinct jsonb_build_object('id',d.source_id,'operator',s.operator)),'[]'::jsonb)
      from ${tx(schema)}.discoveries d join ${tx(schema)}.raw_pages p on p.id=d.page_id join ${tx(schema)}.sources s on s.id=d.source_id
      where d.material_id=v.material_id and d.revision=v.revision and p.acquired_at<=${cutoff}) sources
    from ${tx(schema)}.event_materials r join ${tx(schema)}.material_versions v on v.material_id=r.material_id and v.revision=r.material_revision
    join ${tx(schema)}.materials m on m.id=v.material_id where r.event_id=${id} and r.event_revision=${revision} and v.acquired_at<=${cutoff}
    order by v.material_id,v.revision desc`;
  return rows.map(row=>{const report={id:row.material_id,revision:row.revision,contentHash:row.content_hash,title:row.title,
    excerpt:row.excerpt.slice(0,2000),url:row.original_url,publishedAt:row.published_at,acquiredAt:row.acquired_at,state:row.state,
    sources:(row.sources as {id:string;operator:string}[]).sort((a,b)=>a.id.localeCompare(b.id))};return {...report,official:official(report,catalog)};});
}
/** Bounded round-robin on the existing worker heartbeat; no second scheduler/queue. */
export async function evaluateChannelRules(db:Sql,schema:string,owner:RuntimeOwner,limit=20){
  schemaName(schema);if(!Number.isInteger(limit)||limit<1||limit>50)throw Error('hot_channel_batch_invalid');
  const catalog=await publicSources();
  return withOwnerTransaction(db,schema,owner,async tx=>{
    const [{cutoff}]=await tx`select clock_timestamp() cutoff`;
    const [cursor]=await tx`select after_key from ${tx(schema)}.channel_rule_cursor where singleton for update`;
    const load=(after:string)=>tx`select e.id,e.current_revision,v.snapshot,c.id channel_id,c.current_version,cv.config,
      e.id::text||':'||c.id scan_key from ${tx(schema)}.events e join ${tx(schema)}.event_versions v on v.event_id=e.id and v.revision=e.current_revision
      cross join ${tx(schema)}.channels c join ${tx(schema)}.channel_versions cv on cv.channel_id=c.id and cv.version=c.current_version
      where v.snapshot->>'state'='active' and e.id::text||':'||c.id>${after}
        and (v.snapshot->'manual'->'channels'='null'::jsonb or (v.snapshot->'manual'->'channels') ? c.id)
        and not exists(select 1 from ${tx(schema)}.channel_judgments j where j.event_id=e.id and j.channel_id=c.id and j.authority='human')
      order by scan_key limit ${limit}`;
    let pairs=await load(cursor.after_key);if(!pairs.length)pairs=await load('');
    let saved=0;
    for(const pair of pairs){
      const reports=await reportsFor(tx,schema,pair.id,pair.current_revision,cutoff,catalog);
      const config=pair.config as ChannelConfig;
      const sourceIds=[...new Set([...config.sourceIds,...reports.flatMap(r=>r.sources.map(s=>s.id))])].sort();
      const context=await tx`select s.id,s.operator,s.enabled,s.config_revision::text,s.last_error_code,
        (select jsonb_build_object('coverage',p.coverage,'gap',p.gap,'oldestPublishedAt',p.oldest_published_at,'newestPublishedAt',p.newest_published_at,
          'parsedCount',p.parsed_count,'frozenSubset',p.metadata->'subset','timeConflicts',p.metadata->'timeConflicts') from ${tx(schema)}.raw_pages p
          where p.source_id=s.id and p.acquired_at<=${cutoff} order by p.acquired_at desc,p.id desc limit 1) snapshot
        from ${tx(schema)}.sources s where id=any(${tx.array(sourceIds)}::text[]) order by id`;
      const contextHash=sha256(canonicalGroupingInput([...context]));
      const [previous]=await tx`select details,source_context_hash from ${tx(schema)}.channel_rule_evidence x join ${tx(schema)}.channel_judgments j on j.id=x.judgment_id
        where j.event_id=${pair.id} and j.channel_id=${pair.channel_id} and x.observed_at<=${cutoff} order by x.observed_at desc limit 1`;
      const oldHashes=await tx`select distinct mv.content_hash from ${tx(schema)}.event_materials r join ${tx(schema)}.material_versions mv
        on mv.material_id=r.material_id and mv.revision=r.material_revision where r.event_id=${pair.id} and r.event_revision=${pair.current_revision-1}`;
      const previousHashes=previous?.details?.materials?.map((r:{contentHash:string})=>r.contentHash)??oldHashes.map(r=>r.content_hash);
      const scored=scoreChannel(config,reports,previousHashes,cutoff);
      const comparability=previous?(previous.source_context_hash===contextHash?'comparable':'changed'):'no_baseline';
      scored.judgment.limitations.push(comparability==='changed'?'来源配置、断采或覆盖状态变化，传播热度趋势不可直接比较。':comparability==='no_baseline'?'尚无来源覆盖历史基线，未宣称热度趋势可比。':'本次与上一条判断来源覆盖状态相同，仍受已知覆盖缺口限制。');
      if(reports.some(r=>r.excerpt.length>=2000))scored.judgment.limitations.push('规则只读取每篇前2000字符，可能遗漏后文主题。');
      const fingerprint=sha256(canonicalGroupingInput(JSON.parse(JSON.stringify({algorithm:RULE_VERSION,catalog,config,eventRevision:pair.current_revision,
        channelVersion:pair.current_version,contextHash,material:reports.map(r=>({...r,excerpt:undefined})),hour:Math.floor(cutoff.getTime()/3600000)}))));
      const prior=await tx`select id from ${tx(schema)}.channel_judgments where event_id=${pair.id} and event_revision=${pair.current_revision}
        and channel_id=${pair.channel_id} and channel_version=${pair.current_version} and input_hash=${fingerprint}`;
      if(prior.length)continue;
      const id=await saveChannelJudgmentTransaction(tx,schema,{eventId:pair.id,eventRevision:pair.current_revision,channelId:pair.channel_id,
        channelVersion:pair.current_version,inputHash:fingerprint,authority:'rule',judgment:scored.judgment});
      const details={...scored.metrics,comparability,coverage:[...context],materials:reports.map(r=>({id:r.id,revision:r.revision,contentHash:r.contentHash,url:r.url,
        publishedAt:r.publishedAt,acquiredAt:r.acquiredAt,official:r.official,state:r.state})),channelVersion:pair.current_version,ruleVersion:RULE_VERSION};
      await tx`insert into ${tx(schema)}.channel_rule_evidence(judgment_id,algorithm_version,input_hash,observed_at,source_context_hash,details)
        values(${id},${RULE_VERSION},${fingerprint},${cutoff},${contextHash},${tx.json(JSON.parse(JSON.stringify(details)))})`;
      saved++;
    }
    await tx`update ${tx(schema)}.channel_rule_cursor set after_key=${pairs.at(-1)?.scan_key??''} where singleton`;
    if(saved)logEvent('channels_evaluated',saved);return saved;
  });
}
export async function ruleEvidenceAt(db:Sql,schema:string,eventId:string,channelId:string,cutoff:Date){
  const judgment=await judgmentAt(db,schema,eventId,channelId,cutoff);if(!judgment)return null;
  const [row]=await db`select x.details,x.observed_at,x.algorithm_version from ${db(schema)}.channel_rule_evidence x where judgment_id=${judgment.id}`;
  return {judgment,evidence:row??null};
}
