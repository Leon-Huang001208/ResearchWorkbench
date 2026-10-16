// Report structure adapted from AIHOT ReportPaper/ReportNav (MIT); see third-party notice.
import { e, list, text, kinds, reportHash, external, itemLink, image, source, coverage, related, jump, weekday } from './aihot-common.mjs';

const keyOf = item => item.itemId || item.title;
const anchor = item => `aihot-r-${item.itemId || ''}`;
const mark = (kind, key) => kind === 'daily' ? key.slice(8) : kind === 'weekly' ? key.slice(6) : key.slice(5);
const period = kind => ({ daily: '今日', weekly: '本周', monthly: '本月' })[kind];
export function pagesOf(report) {
  const lead = list(report.sections).flatMap(s => list(s.items)).find(item => item.itemId === report.leadItemId && item.available !== false) || null;
  const seen = new Set(lead ? [keyOf(lead)] : []);
  const pages = list(report.sections).map((section, i) => ({ ...section, id: `aihot-s-${i + 1}`, items: list(section.items).filter(item => { if (seen.has(keyOf(item))) return false; seen.add(keyOf(item)); return true; }) })).filter(s => s.items.length);
  return { lead, pages };
}
export function archiveGroups(kind, entries) {
  const groups = new Map();
  for (const item of list(entries)) {
    if (typeof item.key !== 'string') continue;
    let key = kind === 'monthly' ? item.key.slice(0, 4) : item.key.slice(0, 7);
    if (kind === 'weekly') {
      const jan = new Date(Date.UTC(Number(item.key.slice(0, 4)), 0, 4));
      jan.setUTCDate(jan.getUTCDate() - (jan.getUTCDay() || 7) + 1 + (Number(item.key.slice(6)) - 1) * 7);
      key = jan.toISOString().slice(0, 7);
    }
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  }
  return [...groups].map(([id, items]) => ({ id, label: id.length === 4 ? `${id} 年` : `${id.slice(0, 4)} 年 ${Number(id.slice(5))} 月`, items }));
}
export function kindSwitch(kind) {
  return `<nav class="aihot-kind-switch" aria-label="切换日报、周报、月报">${Object.entries(kinds).map(([id, label]) => `<a href="${reportHash(id)}" ${id === kind ? 'aria-current="page"' : ''}>${label}</a>`).join('')}</nav>`;
}
function archiveEntry(item, kind, current) {
  return `<li><a href="${reportHash(kind, item.key)}" ${item.key === current ? 'aria-current="date"' : ''} title="${e(item.title || item.key)}"><span class="aihot-day-mark"><b>${e(mark(kind, item.key))}</b><small>${e(kind === 'daily' ? weekday(item.key, true) : kind === 'weekly' ? '周' : '月')}</small></span><span>${e(item.title || `${kinds[kind]} ${item.key}`)}</span></a></li>`;
}
export function renderArchive(state) {
  const groups = archiveGroups(state.kind, state.editions);
  return `<aside class="aihot-archive">${kindSwitch(state.kind)}<h2>往期</h2><nav class="aihot-archive-scroll" aria-label="${kinds[state.kind]}历史">${groups.map((g, i) => {
    const open = state.openMonths?.get(g.id) ?? (g.items.some(item => item.key === state.date) || !state.date && i === 0);
    const entries = state.months?.[g.id]?.items || g.items;
    return `<details data-aihot-month="${e(g.id)}" ${open ? 'open' : ''}><summary><span>${e(g.label)}</span><small>${g.items.length}</small></summary><ul>${entries.map(item => archiveEntry(item, state.kind, state.date)).join('')}</ul>${state.months?.[g.id]?.loading ? '<p role="status">读取中…</p>' : ''}${state.months?.[g.id]?.error ? `<p role="alert">${e(state.months[g.id].error)}<button data-aihot-month-retry="${e(g.id)}">重试</button></p>` : ''}</details>`;
  }).join('')}</nav>${state.kind === 'daily' ? '<a class="aihot-book" href="#/aihot/archive">日报合订本 <span>›</span></a>' : ''}</aside>`;
}
function weekStart(key) {
  const date = new Date(Date.UTC(Number(key.slice(0, 4)), 0, 4));
  date.setUTCDate(date.getUTCDate() - (date.getUTCDay() || 7) + 1 + (Number(key.slice(6)) - 1) * 7);
  return date;
}
function dateMark(kind, key) {
  if (kind === 'daily') return { figure:key.slice(8), top:`${key.slice(0,4)} 年 ${Number(key.slice(5,7))} 月`, bottom:weekday(key) };
  if (kind === 'monthly') return { figure:key.slice(5), top:`${key.slice(0,4)} 年`, bottom:`${Number(key.slice(5))} 月` };
  const start = weekStart(key), end = new Date(start); end.setUTCDate(end.getUTCDate() + 6);
  return { figure:key.slice(6), top:`${key.slice(0,4)} 年第 ${Number(key.slice(6))} 周`, bottom:`${start.toISOString().slice(5,10).replace('-', '.')} — ${end.toISOString().slice(5,10).replace('-', '.')}` };
}
function dots(report, index) {
  const { kind, key } = report;
  const year = Number(key.slice(0,4));
  const weeks = Math.floor((new Date(Date.UTC(year,11,28)) - weekStart(`${year}-W01`)) / 604800000) + 1;
  const count = kind === 'daily' ? new Date(Date.UTC(year, Number(key.slice(5,7)), 0)).getUTCDate() : kind === 'weekly' ? weeks : 12;
  const existing = new Map(list(index).map(item => [item.key,item]));
  existing.set(key,{ issueNumber:report.issueNumber });
  const pad = kind === 'daily' ? (new Date(Date.UTC(year, Number(key.slice(5,7))-1, 1)).getUTCDay()+6)%7 : 0;
  const columns = kind === 'daily' ? 7 : kind === 'weekly' ? 13 : 6;
  return `<div class="aihot-dot-calendar"><small>${kind === 'daily' ? `${Number(key.slice(5,7))}月` : `${year} 年`}</small><div class="aihot-issue-dots" style="grid-template-columns:repeat(${columns},1fr)" aria-label="期次日历">${kind === 'daily' ? ['一','二','三','四','五','六','日'].map(day=>`<small>${day}</small>`).join('') : ''}${'<span aria-hidden="true"></span>'.repeat(pad)}${Array.from({ length:count },(_,i)=> {
    const candidate = kind === 'daily' ? `${key.slice(0,7)}-${String(i+1).padStart(2,'0')}` : kind === 'weekly' ? `${year}-W${String(i+1).padStart(2,'0')}` : `${year}-${String(i+1).padStart(2,'0')}`;
    return existing.has(candidate) ? `<a href="${reportHash(kind,candidate)}" class="${candidate===key?'current':''}" title="${e(candidate)} · 第${e(existing.get(candidate).issueNumber)}期" aria-label="${e(candidate)}">●</a>` : `<span title="${e(candidate)} · 未出刊">·</span>`;
  }).join('')}</div></div>`;
}
function masthead(report, index, quiet) {
  const label = kinds[report.kind];
  const stamp = dateMark(report.kind, report.key);
  const date = report.kind === 'daily' ? `${report.key.slice(0, 4)} 年 ${Number(report.key.slice(5, 7))} 月 ${Number(report.key.slice(8))} 日 · ${weekday(report.key)}` : `${stamp.top} ${stamp.bottom}`;
  const metrics = [['totalEvents', '件大事'], ['sourcesCount', '个来源'], ['firstPartyEvents', '件一手发布'], ['modelsReleased', '个新模型'], ['selectedCount', '条精选'], ['reportsCovered', '期日报']];
  return `<header class="aihot-masthead"><div class="aihot-dateline"><span>${e(date)}</span><span>${report.kind === 'daily' ? '每天 08:00 出刊' : report.kind === 'weekly' ? '每周一出刊' : '每月 1 日出刊'}</span></div><div class="aihot-nameplate-row"><div><h1 id="aihot-report-start">AI ${label}</h1><p>RESEARCH WORKBENCH · 数据来源 AIHOT</p></div><div class="aihot-issue-box"><div><span>第 ${e(report.issueNumber ?? '—')} 期</span><strong>${e(stamp.figure)}</strong><small>${e(stamp.top)}</small><small>${e(stamp.bottom)}</small></div>${dots(report, index)}</div></div>${quiet ? '' : `<div class="aihot-metrics">${metrics.filter(([id]) => Number.isFinite(report.metrics?.[id]) && (id !== 'modelsReleased' || report.metrics[id] > 0)).map(([id, unit]) => `<span><b>${e(report.metrics[id])}</b>${unit}</span>`).join('')}<span class="aihot-reading-time">约 ${e(report.readingMinutes ?? '—')} 分钟读完</span></div>`}</header>`;
}
function story(item, dated) {
  return `<article class="aihot-story" ${item.itemId ? `id="${e(anchor(item))}"` : ''}><div class="aihot-story-meta">${source(item)}${item.available !== false ? coverage(item) : ''}${dated && item.publishedAt ? `<time>${e(item.publishedAt.slice(5, 10).replace('-', '.'))}</time>` : ''}</div><h3>${itemLink(item)}</h3>${item.available === false ? '<p class="muted">该内容已按来源方要求下架或调整展示方式。</p>' : `${item.summary ? `<p>${e(item.summary)}</p>` : ''}${related(item.related)}<div class="aihot-story-original">${external(item.sourceUrl, '原文 ↗')}</div>`}</article>`;
}
function sectionHeading(page, index) {
  return `<div class="aihot-section-title"><b>${String(index + 1).padStart(2, '0')}</b><h2>${e(page.label)}</h2>${jump('aihot-report-start', '↑ 回到头版')}</div>`;
}
export function renderPaper(report, index) {
  const { lead, pages } = pagesOf(report);
  const quiet = !pages.length && !lead && !list(report.flashes).length;
  const inPage = new Set(pages.flatMap(page => page.items).map(item => item.itemId).filter(Boolean));
  const highlights = list(report.highlights).filter(item => !lead || keyOf(item) !== keyOf(lead)).slice(0, 3);
  const outline = [...pages.map((s, i) => ({ ...s, count: `${s.items.length} 件`, no: i + 1 })), ...(list(report.flashes).length ? [{ id: 'aihot-s-flash', label: '快讯', count: `${report.flashes.length} 条`, no: pages.length + 1 }] : [])];
  const ratio = report.cover?.width > 0 && report.cover?.height > 0 ? report.cover.width / report.cover.height : 16/9;
  const picture = report.cover ? `<figure class="aihot-lead-figure">${image(report.cover,'','aihot-cover',true)}${report.cover.caption ? `<figcaption>图 · ${e(report.cover.caption)}</figcaption>` : ''}</figure>` : '';
  const front = `<section class="aihot-frontpage"><div class="aihot-lead ${ratio<1.25 ? 'aihot-square-cover' : ''}" ${lead ? `id="${e(anchor(lead))}"` : ''}><span class="aihot-kicker">${report.kind === 'daily' || lead ? '头条' : '本期导读'}</span>${ratio>=1.25 ? picture : ''}<h2>${lead ? itemLink(lead, report.lead?.title || lead.title) : e(report.lead?.title || report.title)}</h2>${ratio<1.25 ? picture : ''}<p>${e(report.lead?.leadParagraph || lead?.summary || report.overview || '')}</p>${lead ? `<div class="aihot-story-meta">${source(lead)}${coverage(lead)}${external(lead.sourceUrl, '原文 ↗')}</div>${related(lead.related)}` : ''}</div><aside class="aihot-front-aside">${highlights.length ? `<h2 class="aihot-kicker">${period(report.kind)}看点</h2><ol class="aihot-highlights">${highlights.map((item, i) => `<li><b>${i + 1}</b><div>${item.available !== false && item.itemId && inPage.has(item.itemId) ? jump(anchor(item), e(item.title)) : itemLink(item)}<small>${e(item.sourceName || '')}</small></div></li>`).join('')}</ol>` : ''}<nav aria-label="本期版面"><h2 class="aihot-kicker">本期版面</h2>${outline.map(s => jump(s.id, `<b>${String(s.no).padStart(2, '0')}</b><span>${e(s.label)}</span><small>${s.count}</small>`)).join('')}</nav></aside></section>`;
  const sections = pages.map((page, i) => `<section class="aihot-section" id="${page.id}">${sectionHeading(page, i)}${page.summary ? `<p class="aihot-section-guide"><b>本版导读</b> ${e(page.summary)}</p>` : ''}<div class="aihot-story-grid">${page.items.map(item => story(item, report.kind !== 'daily')).join('')}</div></section>`).join('');
  const flashes = list(report.flashes).length ? `<section class="aihot-section" id="aihot-s-flash">${sectionHeading({ label: '快讯' }, pages.length)}<ul class="aihot-flashes">${list(report.flashes).map(item => `<li>${itemLink(item)} <small>${e(item.sourceName || '')}</small>${item.followUp ? '<span class="aihot-badge">跟进</span>' : ''}</li>`).join('')}</ul></section>` : '';
  const neighbours = `<nav class="aihot-neighbours" aria-label="相邻期次">${['prev', 'next'].map((direction, i) => report[direction] ? `<a href="${reportHash(report.kind, report[direction])}"><span>${i ? '后一' : '前一'}${report.kind === 'daily' ? '日' : '期'} · ${e(report[direction])} ${i ? '→' : '←'}</span><b>${e(list(index).find(item => item.key === report[direction])?.title || `AI ${kinds[report.kind]} ${report[direction]}`)}</b></a>` : '<span></span>').join('')}</nav>`;
  const history = report.kind === 'daily' ? '' : `<section class="aihot-history" id="aihot-report-history"><h2>往期${kinds[report.kind]}</h2>${list(index).map(item => `<a href="${reportHash(report.kind, item.key)}"><time>${e(item.key)}</time>${e(item.title || '查看本期')}</a>`).join('')}</section>`;
  return `<article class="aihot-paper">${masthead(report, index, quiet)}${report.kind !== 'daily' && lead && report.overview ? `<p class="aihot-overview">${e(report.overview)}</p>` : ''}${quiet ? `<div class="aihot-quiet"><h2>${e(report.lead?.title || '本期暂无新内容')}</h2><p>${e(report.lead?.leadParagraph || '')}</p></div>` : front}${sections}${flashes}${neighbours}${history}<footer class="aihot-colophon"><b>（本期完）</b><p>AIHOT ${kinds[report.kind]}由编辑系统根据公开来源自动${report.kind === 'daily' ? '编辑' : '综合'}，每条均附原文 · <a href="${report.kind === 'daily' ? '#/aihot/archive' : reportHash(report.kind)}">${report.kind === 'daily' ? '日报合订本' : `往期${kinds[report.kind]}`}</a></p></footer></article>`;
}
export function renderArchiveBook(state) {
  return `<article class="aihot-paper aihot-archive-book"><div class="aihot-dateline"><span>AIHOT · AI 日报</span><span>共 ${e(state.editions[0]?.issueNumber ?? 0)} 期</span></div><h1>日报合订本</h1>${archiveGroups('daily', state.editions).map(g => `<section class="aihot-section"><h2>${e(g.label)}</h2><ul class="aihot-book-grid">${g.items.map(item => archiveEntry(item, 'daily', '')).join('')}</ul></section>`).join('')}</article>`;
}
