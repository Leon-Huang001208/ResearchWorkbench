/** Frozen brief input. No scheduling, source fetch, model call or research session. */
import type postgres from 'postgres';
import {channelsAt,eventDetail} from './projections.ts';
import {schemaName} from './config.ts';
import {sha256,publicationTime} from './material.ts';
import {logEvent} from './log.ts';
type Sql=ReturnType<typeof postgres>;
type Json=postgres.JSONValue;
export interface BriefPayload {
  schemaVersion:1;cutoff:string;timezone:string;window:{from:string|null;to:string|null};
  channel:Json;events:Json[];limitations:string[];
  selection?:PeriodicSelection;
}
export interface PeriodicSelection {kind:'periodic';planId:string;planVersion:number;runId:string;missedPeriods:number}
export interface FrozenBrief {payload:BriefPayload;contentHash:string}
function canonical(value:unknown):string {
  if(value instanceof Date)return JSON.stringify(value.toISOString());
  if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
  if(value!==null&&typeof value==='object')return '{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+canonical((value as Record<string,unknown>)[key])).join(',')+'}';
  const serialized=JSON.stringify(value);if(serialized===undefined)throw Error('hot_brief_input_invalid');return serialized;
}
function date(value:string):Date {
  if(!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?(?:Z|[+-]\d\d:\d\d)$/.test(value))throw Error('hot_brief_window_invalid');
  const parsed=publicationTime(value,new Date(8640000000000000));if(!parsed)throw Error('hot_brief_window_invalid');return parsed;
}
function validate(payload:BriefPayload){
  if(payload.schemaVersion!==1||!Array.isArray(payload.events)||payload.events.length>20)throw Error('hot_brief_limit');
  date(payload.cutoff);
  if(payload.selection){
    const s=payload.selection;
    if(s.kind!=='periodic'||Object.keys(s).some(key=>!['kind','planId','planVersion','runId','missedPeriods'].includes(key))||
      [s.planId,s.runId].some(id=>typeof id!=='string'||!/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(id))||
      !Number.isSafeInteger(s.planVersion)||s.planVersion<1||!Number.isSafeInteger(s.missedPeriods)||s.missedPeriods<0)throw Error('hot_brief_input_invalid');
  }
  try{new Intl.DateTimeFormat('zh-CN',{timeZone:payload.timezone});}catch{throw Error('hot_brief_timezone_invalid');}
  const {from,to}=payload.window;if(from)date(from);if(to)date(to);
  if(from&&to&&date(from)>date(to))throw Error('hot_brief_window_invalid');
  if(Buffer.byteLength(canonical(payload))>4*1024*1024)throw Error('hot_brief_limit');
}
export function sealBrief(payload:BriefPayload):FrozenBrief {
  validate(payload);return {payload:structuredClone(payload),contentHash:sha256(canonical(payload))};
}
function object(value:Json):Record<string,Json>{
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.getPrototypeOf(value)!==Object.prototype)throw Error('hot_brief_input_invalid');
  return value as Record<string,Json>;
}
function list(value:Json|undefined):Json[]{if(!Array.isArray(value))throw Error('hot_brief_input_invalid');return value;}
/** One repeatable-read view, bounded explicit selection. All material pages reuse the same cutoff. */
export async function freezeBrief(db:Sql,schema:string,input:{eventIds:string[];channelId:string;cutoff:string;
  from?:string;to?:string;timezone?:string;selection?:PeriodicSelection},signal?:AbortSignal):Promise<FrozenBrief>{
  schemaName(schema);
  if(!Array.isArray(input.eventIds)||!input.eventIds.length||input.eventIds.length>20||
    new Set(input.eventIds.map(id=>id.toLowerCase())).size!==input.eventIds.length||
    input.eventIds.some(id=>!/^([a-f0-9]{8})(-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(id))||
    !/^[a-z][a-z0-9_-]{0,47}$/.test(input.channelId))throw Error('hot_brief_selection_invalid');
  const cutoff=date(input.cutoff).toISOString();if(date(cutoff)>new Date())throw Error('hot_brief_window_invalid');
  const base:BriefPayload={schemaVersion:1,cutoff,timezone:input.timezone??'Asia/Shanghai',window:{from:input.from??null,to:input.to??null},
    channel:null,events:[],limitations:['显式选材，不代表频道或全天完整覆盖。',
      '来源摘录为发布者陈述，未经独立事实核验；事件标题为归组摘要。',
      '覆盖依据来自已保存的判断快照，缺失或较旧的覆盖不代表当前采集健康。']};
  if(input.selection){base.selection=input.selection;base.limitations[0]='Hot周期计划从截止时点已保存的频道事件中有界选材，不代表频道或全天完整覆盖。';
    if(input.selection.missedPeriods)base.limitations.push(`停机或延迟跳过 ${input.selection.missedPeriods} 个周期；只处理本次保存的截止窗口，不补造完整覆盖。`);}
  validate(base);
  try{
    const result=await db.begin('isolation level repeatable read read only',async tx=>{
      const reader=tx as unknown as Sql;signal?.throwIfAborted();
      const channels=object(await channelsAt(reader,schema,{cutoff}));
      const channel=list(channels.items).find(value=>object(value).channel_id===input.channelId);
      if(!channel)throw Error('hot_brief_channel_unknown');base.channel=channel;
      const selected=new Set<string>();
      for(const id of input.eventIds){
        signal?.throwIfAborted();const detail=object(await eventDetail(reader,schema,{eventId:id,cutoff,reportLimit:50},signal));
        const key=String(detail.canonicalId);if(selected.has(key))throw Error('hot_brief_selection_alias_duplicate');selected.add(key);
        const count=detail.materialCount;if(typeof count!=='number'||count<1||count>200)throw Error('hot_brief_evidence_missing');
        const reports=[...list(detail.reports)];
        for(let offset=50;offset<count;offset+=50){
          const page=object(await eventDetail(reader,schema,{eventId:id,cutoff,reportLimit:50,reportOffset:offset},signal));
          reports.push(...list(page.reports));
        }
        if(reports.length!==count)throw Error('hot_brief_evidence_missing');
        if(input.from||input.to){
          const inWindow=reports.some(value=>{const published=object(value).publishedAt;
            return typeof published==='string'&&(!input.from||date(published)>=date(input.from))&&(!input.to||date(published)<=date(input.to));});
          if(!inWindow)throw Error('hot_brief_selection_outside_window');
        }
        detail.reports=reports;detail.reportOffset=0;detail.reportLimit=count;
        detail.judgments=list(detail.judgments).filter(value=>object(value).channelId===input.channelId);
        if(!list(detail.judgments).length)base.limitations.push('此事件在截止时点没有频道判断：'+key);
        base.events.push(detail);
      }
      signal?.throwIfAborted();return sealBrief(base);
    });
    logEvent('brief_frozen',result.payload.events.length);return result;
  }catch(error){
    logEvent('brief_failed');
    if(error instanceof Error&&/^hot_[a-z_]+$/.test(error.message))throw error;
    if(signal?.aborted)throw Error('hot_brief_cancelled');throw Error('hot_brief_freeze_failed');
  }
}
function escape(value:Json|undefined):string {
  return String(value??'未知').replace(/\s+/g,' ').trim().replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/[\\`*_{}\[\]()#+.!|~\-]/g,'\\$&');
}
export function briefMarkdown(brief:FrozenBrief):string {
  validate(brief.payload);if(sha256(canonical(brief.payload))!==brief.contentHash)throw Error('hot_brief_integrity_invalid');
  const p=brief.payload;
  const time=(value:Json|undefined)=>typeof value==='string'?new Intl.DateTimeFormat('zh-CN',{timeZone:p.timezone,dateStyle:'medium',timeStyle:'medium'}).format(date(value)):'未知';
  const lines=['# 热点与事件简报','',`截止：${time(p.cutoff)} · 时区：${escape(p.timezone)}`,
    `选材发布时间窗口：${p.window.from?time(p.window.from):'未指定'} — ${p.window.to?time(p.window.to):'未指定'}`,
    `内容校验：${brief.contentHash}`,'','## 覆盖与限制',...p.limitations.map(value=>'- '+escape(value))];
  if(p.selection)lines.push('',`周期计划：${escape(p.selection.planId)} · 版本 ${p.selection.planVersion} · 运行 ${escape(p.selection.runId)} · 跳过周期 ${p.selection.missedPeriods}`);
  const channel=object(p.channel);lines.push('',`频道：${escape(channel.channel_id)} · 配置版本 ${escape(channel.version)}`);
  for(const value of p.events){const event=object(value);
    lines.push('','## 事件摘要（归组结果）',escape(event.title),`事件 ${escape(event.canonicalId)} · 版本 ${escape(event.revision)}`,
      `发生：${time(event.occurredAt)} · 生效：${time(event.effectiveAt)}`);
    for(const value of list(event.judgments)){const basis=object(value),judgment=object(basis.judgment);
      const label=basis.authority==='model'?'模型推断':basis.authority==='human'?'人工判断':'规则判断';
      lines.push('',`### ${label}`,`相关性 ${escape(judgment.relevance)} · 研究重要性 ${escape(judgment.importance)} · 热度 ${escape(judgment.heat)} · 信息增量 ${escape(judgment.informationIncrement)}`,
        escape(judgment.reason),`判断依据：原事件版本 ${escape(basis.event_revision)} · 原频道版本 ${escape(basis.channel_version)} · 判断 ${escape(basis.id)}`,
        `应用版本：事件 ${escape(basis.applied_event_revision)} · 频道 ${escape(basis.applied_channel_version)} · ${basis.inherited?'继承判断':'当前版本判断'}`);
      if(basis.ruleEvidence){const evidence=object(basis.ruleEvidence),details=object(evidence.details);
        lines.push(`报道 ${escape(details.reportCount)} · 来源 ${escape(details.sourceCount)} · 独立运营主体 ${escape(details.independentOperators)} · 趋势可比性 ${escape(details.comparability)}`,
          '覆盖（原判断快照）：');
        for(const value of list(details.coverage)){const source=object(value),snapshot=source.snapshot?object(source.snapshot):null;
          lines.push(`- ${escape(source.id)} · ${escape(source.operator)} · ${source.enabled?'启用':'暂停'} · ${snapshot?escape(snapshot.coverage):'无覆盖记录'} · ${snapshot?escape(snapshot.parsedCount):'未知'} 条 · 最近错误 ${escape(source.last_error_code)}`);
        }
      }else lines.push('覆盖依据：未知');
    }
    for(const value of list(event.reports)){const report=object(value);
      lines.push('','### 来源摘录',escape(report.title),`材料 ${escape(report.materialId)} · 版本 ${escape(report.revision)} · ${escape(report.contentHash)}`,
        `发表：${time(report.publishedAt)} · 取得：${time(report.acquiredAt)} · 来源更新时间：${time(report.sourceUpdatedAt)}`,
        `材料状态：${escape(report.state)} · 来源：${list(report.sources??[]).map(value=>{const source=object(value);return escape(source.id)+' / '+escape(source.operator);}).join('、')||'未知'}`,
        '> '+escape(report.excerpt),report.excerptIsPartial?'摘录截断；全文须按此材料版本读取。':'摘录不代表完整原文。');
      if(typeof report.url==='string'){try{const url=new URL(report.url);if(['http:','https:'].includes(url.protocol)&&!url.username&&!url.password)
        lines.push('[原始链接](<'+url.href.replace(/</g,'%3C').replace(/>/g,'%3E')+'>)');}catch{/* Untrusted URL omitted; frozen source identity remains. */}}
    }
  }
  return lines.join('\n')+'\n';
}
