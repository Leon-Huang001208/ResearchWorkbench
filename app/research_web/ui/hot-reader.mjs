// Reading patterns adapted from AIHOT 652bd6b (MIT); own RWB identity and data contracts.
import {escapeHTML as e} from './markdown.mjs';
import {safeLog} from './core.mjs';

const number = value => typeof value === 'number' && Number.isFinite(value) ? String(value) : '—';
function observation(value, timezone) {
  const date = value ? new Date(value) : null;
  if (!date || Number.isNaN(date.valueOf())) return {key:'unknown',label:'观察时间未知',clock:'—'};
  try {
    const parts = Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(date).map(p=>[p.type,p.value]));
    return {key:`${parts.year}-${parts.month}-${parts.day}`,
      label:new Intl.DateTimeFormat('zh-CN',{timeZone:timezone,month:'long',day:'numeric',weekday:'long'}).format(date),
      clock:new Intl.DateTimeFormat('zh-CN',{timeZone:timezone,hour:'2-digit',minute:'2-digit',hour12:false}).format(date)};
  } catch {safeLog('hot_reader_time_invalid');return {key:'unknown',label:'观察时间未知',clock:'—'};}
}
export function hotReaderDays(events, timezone='Asia/Shanghai') {
  const groups=new Map();
  for (const event of events) {
    const stamp=observation(event.observedAt,timezone);
    if (!groups.has(stamp.key)) groups.set(stamp.key,{...stamp,events:[]});
    groups.get(stamp.key).events.push(event);
  }
  return [...groups.values()];
}
function feedRow(event, timezone, loading, includeDate) {
  const stamp=observation(event.observedAt,timezone),judgment=event.judgment;
  const metrics=[['传播热度','heat'],['研究重要性','importance'],['信息增量','informationIncrement'],['相关性','relevance']];
  return `<article class="hot-reader-row"><div class="hot-reader-time"><time>${e(stamp.clock)}</time><span>观察时点</span>${includeDate?`<span>${e(stamp.label)}</span>`:''}</div><div class="hot-reader-story hot-card">
    <header class="hot-reader-meta"><span>本地事件</span><span>·</span><span>${e(event.ruleEvidence?.reportCount??event.materialCount??'未知')} 份报道</span><span class="hot-reader-evidence">${e(event.ruleEvidence?.independentOperators??'未知')} 个独立主体</span></header>
    <h2><button class="hot-event-title" data-hot-action="detail" data-event="${e(event.id)}" ${loading?'disabled':''}>${e(event.title||'未命名事件')}</button></h2>
    <p class="hot-reader-reason"><span>研究理由</span>${e(judgment?.reason||'频道判断待处理。')}</p>
    <dl class="hot-reader-scores">${metrics.map(([label,key])=>`<div><dt>${label}</dt><dd>${e(number(judgment?.[key]))}</dd></div>`).join('')}</dl>
    <footer><span>信源 ${e(event.ruleEvidence?.sourceCount??'未知')}</span><span>观察日期不等于发生、发布或生效日期</span><button data-hot-action="detail" data-event="${e(event.id)}" ${loading?'disabled':''}>查看来源与进展 <span aria-hidden="true">→</span></button></footer>
  </div></article>`;
}
export function renderHotReaderFeed(events,timezone='Asia/Shanghai',{loading=false,blocked=false,sort='recent'}={}) {
  if (!events.length) return `<section class="hot-reader-empty hot-card" role="status"><span class="hot-reader-empty-mark" aria-hidden="true">○</span><h2>${loading?'正在读取资料…':'此范围暂无事件'}</h2><p>${blocked?'资料可以继续采集，模型条件满足后再处理。':'配置 Hot 后，真实事件会显示在这里。也可以调整频道与筛选条件。'}</p><a href="#/settings/hot">查看运行配置 →</a></section>`;
  if (sort!=='recent') return `<div class="hot-reader-feed"><p class="hot-reader-sort-note">按${e({importance:'研究重要性',heat:'传播热度',increment:'信息增量',relevance:'相关性'}[sort]||'当前条件')}排序 · ${events.length} 条观察记录</p>${events.map(event=>feedRow(event,timezone,loading,true)).join('')}</div>`;
  return `<div class="hot-reader-feed">${hotReaderDays(events,timezone).map(day=>`<section class="hot-reader-day"><header class="hot-reader-daybar"><h2>${e(day.label)}</h2><span>观察记录 · ${day.events.length} 条</span></header>${day.events.map(event=>feedRow(event,timezone,loading,false)).join('')}</section>`).join('')}</div>`;
}
export function renderHotReaderRank(events,{loading=false}={}) {
  const ranked=events.filter(event=>typeof event.judgment?.heat==='number'&&Number.isFinite(event.judgment.heat)&&event.judgment.heat>0).slice().sort((a,b)=>b.judgment.heat-a.judgment.heat).slice(0,5);
  return `<section class="hot-reader-rank" aria-label="本页传播热度"><header><h2><span aria-hidden="true" class="hot-reader-live"></span>传播热度</h2><span>本页已读取事件 · 非完整榜单</span></header>${ranked.length?`<ol>${ranked.map((event,index)=>`<li><button data-hot-action="detail" data-event="${e(event.id)}" ${loading?'disabled':''}><span class="hot-reader-rank-number">${index+1}</span><span class="hot-reader-rank-title">${e(event.title)}</span><span class="hot-reader-rank-value">${e(number(event.judgment.heat))}<small>热度</small></span><span aria-hidden="true">↗</span></button></li>`).join('')}</ol>`:'<p class="hot-reader-rank-empty">当前页暂无正热度事件。低热度的重要事件仍保留在下方。</p>'}</section>`;
}
