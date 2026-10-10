import { escapeHTML as e, safeURL, renderMarkdown } from './markdown.mjs';
import { safeLog } from './core.mjs';
import { icon } from './icons.mjs';

export const intelTabs = [
  ['overview', '事件总览'], ['research-reports', '研究报告'],
  ['investment-news', 'Investment News'], ['wsc', '见闻快讯'],
  ['social', '社交媒体监控'], ['news', '公开新闻'], ['filings', 'A 股公告'], ['events', '事件概率'],
];
const list = value => Array.isArray(value) ? value : [];
const text = value => typeof value === 'string' || typeof value === 'number' ? String(value) : '';
export const validStockCode = value => /^[0-9]{6}$/.test(value);
export function intelURL(value) {
  if (typeof value !== 'string') return null;
  const url = value.startsWith('/vibe-research/') ? `http://47.92.168.126${value}` : value;
  const safe = safeURL(url);
  return safe && /^https?:\/\//.test(safe) ? safe : null;
}
const sourceLabel = (value, fallback = '公开来源') => /^[A-Za-z]:/.test(text(value)) ? '研报资料' : (text(value) || fallback);
const sourceLink = (url, label = '查看原文') => {
  const safe = intelURL(url);
  return safe ? `<a class="intel-source-link" href="${e(safe)}" target="_blank" rel="noopener noreferrer">${e(label)} ↗</a>` : '';
};
export function intelTime(value) {
  if (!value) return '时间待核实';
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const date = new Date(typeof value === 'number' ? value * 1000 : value);
  return Number.isNaN(date.valueOf()) ? text(value) : date.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false });
}
const tag = value => value ? `<span class="intel-tag">${e(text(value))}</span>` : '';
const empty = (message = '当前条件下暂无资讯。') => `<div class="intel-empty">${icon('search')}<p>${e(message)}</p></div>`;
const para = value => text(value) ? `<p>${e(text(value))}</p>` : '';
const groupsOf = item => list(item.groups).map(g => text(g) || text(g.id) || text(g.name));
export function filterIntelEvents(items, { query = '', group = 'all', category = 'all' } = {}) {
  const keyword = query.trim().toLocaleLowerCase();
  return list(items).filter(item => {
    if (group !== 'all' && !groupsOf(item).includes(group)) return false;
    if (category === 'counter' && !item._counter) return false;
    if (category === 'unnoticed' && !item.unnoticed) return false;
    if (category === 'changed' && !['重大变化', 'major_change'].includes(item.last_change) && Number(item.revision || 0) < 2) return false;
    return !keyword || [item.title, item.last_change, item.priority_reason, ...groupsOf(item)].map(text).join(' ').toLocaleLowerCase().includes(keyword);
  });
}
export function filterIntelPosts(posts, { query = '', platform = 'all', account = 'all' } = {}) {
  const keyword = query.trim().toLocaleLowerCase();
  return list(posts).filter(item => (platform === 'all' || item.platform === platform) && (account === 'all' || String(item.account_id) === account) && (!keyword || `${item.author || ''} ${item.text || ''}`.toLocaleLowerCase().includes(keyword)));
}

export function createIntelController({ fetcher = (...args) => fetch(...args), onChange = () => {} } = {}) {
  const state = {
    tab: null, entries: {}, query: '', group: 'all', category: 'all', impact: 'medium_high',
    industry: '', platform: 'all', account: 'all', limit: 20, code: '', stockError: '',
    detail: null, detailId: '', detailKind: '', detailLoading: false, detailError: '',
  };
  const requests = new Map();
  let generation = 0;
  let detailGeneration = 0;
  const entry = () => state.entries[state.tab] ||= { data: null, error: '', loading: false, offset: 0 };
  function cancel() {
    generation += 1;
    for (const abort of requests.values()) abort.abort();
    requests.clear();
    for (const item of Object.values(state.entries)) item.loading = false;
    state.detailLoading = false;
    detailGeneration += 1;
  }
  async function request(path, key) {
    requests.get(key)?.abort();
    const abort = new AbortController(); requests.set(key, abort);
    try {
      const response = await fetcher(`/api/research/intel/${path}`, { signal: abort.signal, headers: { Accept: 'application/json' } });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail?.message || `资讯读取失败（${response.status}）`);
      return result;
    } finally { if (requests.get(key) === abort) requests.delete(key); }
  }
  function pathFor(tab, current, more) {
    if (tab === 'overview') return `overview?impact=${encodeURIComponent(state.impact)}`;
    if (tab === 'research-reports') return `reports?limit=20&offset=${current.offset}`;
    if (tab === 'investment-news') return 'radar';
    if (tab === 'wsc') return more && current.data?.next_cursor ? `wsc?cursor=${encodeURIComponent(current.data.next_cursor)}` : 'wsc';
    if (tab === 'social') return 'social';
    return `${tab === 'filings' ? 'announcements' : 'news'}?code=${encodeURIComponent(state.code)}`;
  }
  async function load({ more = false } = {}) {
    if (!state.tab || state.tab === 'events') return;
    const tab = state.tab; const current = entry();
    if (current.loading) return;
    if (['news', 'filings'].includes(tab) && !validStockCode(state.code)) return;
    const ticket = generation;
    const requestedCode = state.code;
    current.loading = true; current.error = ''; onChange();
    try {
      const main = request(pathFor(tab, current, more), 'main');
      // Optional panels never turn a successful event list into a whole-page error.
      const optional = tab === 'overview' ? Promise.allSettled([request('story-focus', 'stories'), request('breakfast-focus', 'breakfast')]) : null;
      const result = await main;
      const extra = optional ? await optional : null;
      if (ticket !== generation || state.tab !== tab) return;
      if (more && tab === 'wsc') {
        const seen = new Set();
        const items = [...list(current.data?.items), ...list(result.items)].filter(item => {
          const id = String(item.id || `${item.url}-${item.time}`);
          if (seen.has(id)) return false; seen.add(id); return true;
        });
        current.data = { ...result, items };
      } else current.data = result;
      if (['news', 'filings'].includes(tab)) current.code = requestedCode;
      if (extra) {
        current.stories = extra[0].status === 'fulfilled' ? extra[0].value : null;
        current.breakfast = extra[1].status === 'fulfilled' ? extra[1].value : null;
        current.panelError = extra.some(item => item.status === 'rejected') ? '部分事件焦点暂未读取成功，可刷新重试。' : '';
      }
      if (tab === 'investment-news' && !list(result.industries).some(item => item.key === state.industry)) state.industry = list(result.industries)[0]?.key || '';
    } catch (error) {
      if (ticket !== generation || error.name === 'AbortError') return;
      current.error = error.message || '资讯读取失败，请重试。';
      safeLog('intel_read_failed', { status: tab, method: 'GET' });
    } finally {
      if (ticket === generation) { current.loading = false; onChange(); }
    }
  }
  async function activate(tab) {
    cancel();
    const nextTab = intelTabs.some(item => item[0] === tab) ? tab : 'overview';
    if (state.tab !== nextTab) { state.query = ''; state.group = 'all'; state.category = 'all'; state.platform = 'all'; state.account = 'all'; }
    state.tab = nextTab;
    state.detail = null; state.detailId = ''; state.detailError = ''; state.limit = 20;
    const current = entry(); onChange();
    if (!current.data || (['news', 'filings'].includes(state.tab) && current.code !== state.code)) await load();
  }
  async function openDetail(kind, id) {
    const ticket = generation;
    const detailTicket = ++detailGeneration;
    state.detailKind = kind; state.detailId = id; state.detail = null; state.detailError = ''; state.detailLoading = true; onChange();
    try {
      const result = await request(`${kind === 'report' ? 'reports' : 'events'}/${encodeURIComponent(id)}`, 'detail');
      if (ticket !== generation || detailTicket !== detailGeneration || state.detailId !== id) return;
      state.detail = result;
    } catch (error) {
      if (ticket !== generation || detailTicket !== detailGeneration || state.detailId !== id || error.name === 'AbortError') return;
      state.detailError = error.message || '详情读取失败，请重试。'; safeLog('intel_detail_failed', { status: kind, method: 'GET' });
    } finally { if (ticket === generation && detailTicket === detailGeneration && state.detailId === id) { state.detailLoading = false; onChange(); } }
  }
  function closeDetail() {
    detailGeneration += 1; requests.get('detail')?.abort(); state.detailId = ''; state.detail = null; state.detailLoading = false; onChange();
  }
  async function handle(event) {
    const target = event.target;
    if (!target?.closest?.('.intel-page')) return false;
    if (event.type === 'input' && target.matches('[data-intel-query]')) { state.query = target.value; state.limit = 20; onChange(); return true; }
    if (event.type === 'input' && target.matches('[data-intel-code]')) { state.code = target.value.trim(); return true; }
    if (event.type === 'change' && target.matches('[data-intel-filter]')) {
      state[target.dataset.intelFilter] = target.value; state.limit = 20;
      if (target.dataset.intelFilter === 'platform') state.account = 'all';
      if (target.dataset.intelFilter === 'impact') { cancel(); closeDetail(); entry().data = null; await load(); } else onChange();
      return true;
    }
    if (event.type === 'submit' && target.matches('[data-intel-stock]')) {
      event.preventDefault(); state.code = String(new FormData(target).get('code') || '').trim();
      state.stockError = validStockCode(state.code) ? '' : '请输入六位 A 股代码，例如 600519。';
      if (!state.stockError) { cancel(); state.limit = 20; entry().data = null; await load(); } else onChange();
      return true;
    }
    if (event.type !== 'click') return false;
    const action = target.closest('[data-intel-action]');
    if (!action) return false;
    event.preventDefault();
    const name = action.dataset.intelAction;
    if (name === 'refresh') { cancel(); await load(); }
    else if (name === 'more') { state.limit += 20; onChange(); }
    else if (name === 'wsc-more') await load({ more: true });
    else if (name === 'event' || name === 'report') await openDetail(name, action.dataset.id);
    else if (name === 'detail-retry') await openDetail(state.detailKind, state.detailId);
    else if (name === 'close') closeDetail();
    else if (name === 'industry') { state.industry = action.dataset.id; state.limit = 20; onChange(); }
    else if (name === 'report-next' || name === 'report-prev') {
      cancel(); closeDetail(); entry().offset = Math.max(0, entry().offset + (name === 'report-next' ? 20 : -20)); entry().data = null; await load();
    }
    return true;
  }
  return { state, activate, cancel, load, openDetail, closeDetail, handle };
}

function eventRows(items, limit = 20) {
  return list(items).slice(0, limit).map(item => `<button type="button" class="intel-event-row" data-intel-action="event" data-id="${e(item.id)}"><span class="intel-item-meta">${tag(item.impact ? `影响力：${item.impact}` : '')}${tag(item.credibility ? `可信度：${item.credibility}` : '')}<time>${e(intelTime(item.updated_at || item.first_public_at))}</time></span><strong>${e(item.title || '未命名事件')}</strong>${para(item.priority_reason || item.last_change)}<span class="intel-item-meta">${e(groupsOf(item).join(' · '))}${Number(item.report_count) ? ` · ${e(item.report_count)} 篇报道` : ''}</span></button>`).join('');
}
const section = (title, content, caption = '') => `<section class="intel-section"><div class="section-heading"><h2>${e(title)}</h2>${caption ? `<span class="muted small">${e(caption)}</span>` : ''}</div>${content}</section>`;
const option = (value, label, selected) => `<option value="${e(value)}" ${value === selected ? 'selected' : ''}>${e(label)}</option>`;
const select = (key, label, options, value) => `<label>${e(label)}<select id="intel-${key}" data-intel-filter="${key}">${options.map(([id, name]) => option(id, name, value)).join('')}</select></label>`;
const search = s => `<label class="intel-search">关键词<input id="intel-query" data-intel-query type="search" value="${e(s.query)}" placeholder="搜索标题、来源或内容"></label>`;
const moreButton = (length, limit) => length > limit ? `<button class="button intel-more" data-intel-action="more">加载更多 · 还有 ${length - limit} 条</button>` : '';

function renderOverview(s, current) {
  const d = current.data;
  if (!d) return '';
  const logicNames = new Map(list(d.logics).map(item => [item.id, item.name]));
  const all = list(d.reading).map(item => ({ ...item, _counter: list(d.challenges).some(c => c.id === item.id) }));
  const filtered = filterIntelEvents(all, s);
  const filters = `<div class="intel-filters" role="search">${search(s)}${select('impact', '影响力', [['medium_high', '中高影响'], ['high', '高影响'], ['all', '全部影响']], s.impact)}${select('group', '行业', [['all', '全部行业'], ...logicNames], s.group)}${select('category', '线索', [['all', '全部线索'], ['counter', '反证'], ['unnoticed', '新焦点'], ['changed', '新增进展']], s.category)}</div>`;
  const stories = list(current.stories?.stories || d.story_focus?.stories);
  const storyCards = stories.map(item => `<article class="intel-story"><div class="intel-item-meta">${tag(item.focus_level || '持续线索')}${tag(item.current_stage)}</div><h3>${e(item.title)}</h3>${para(item.why_now)}${item.market_chain ? `<p class="muted small">传导：${e(item.market_chain)}</p>` : ''}${item.next_watch ? `<p class="intel-next">下一观察：${e(item.next_watch)}</p>` : ''}<details><summary>查看事件演变</summary>${list(item.timeline).map(step => `<div class="intel-timeline-step"><time>${e(intelTime(step.at || step.date))}</time>${step.event_id ? `<button class="text-button" data-intel-action="event" data-id="${e(step.event_id)}">${e(step.title || '事件详情')}</button>` : para(step.title)}${para(step.new_information)}</div>`).join('') || '<p class="muted">暂无时间线。</p>'}</details></article>`).join('');
  const confidence = item => ({ '低': 25, '中': 50, '高': 75 })[item.support_level];
  const markets = list(d.trading).slice(0, 6).map(item => `<article class="intel-market"><div class="intel-item-meta">${tag(confidence(item) === undefined ? '置信分数：暂无分数' : `置信分数：${confidence(item)}/100`)}<span>${e(item.market?.as_of || '')}</span></div><h3>${e(item.name)}</h3>${para(item.activity?.summary || item.market?.summary || item.summary || item.recent_change)}<details><summary>查看观察依据</summary><p class="muted small">置信分数由证据支持等级换算：低 25、中 50、高 75；不代表统计概率。</p>${para(item.next_check || item.market_assessment)}${para(item.market?.summary)}${list(item.counter_ids).slice(0, 3).map(id => `<button class="text-button" data-intel-action="event" data-id="${e(id)}">查看反证事件</button>`).join('')}</details></article>`).join('');
  return `<div class="intel-overview-meta"><span class="intel-live-dot"></span>判断时点 ${e(intelTime(d.as_of))}<span>${all.length.toLocaleString()} 条事件</span>${d.cache_stale ? tag('上次结果 · 等待上游更新') : ''}</div>${current.panelError ? `<p class="notice warning">${e(current.panelError)}</p>` : ''}${section('持续演进的事件焦点', storyCards ? `<div class="intel-story-grid">${storyCards}</div>` : empty('暂无持续演进的事件焦点。'))}${section('最近交易日行情焦点', markets ? `<div class="intel-market-grid">${markets}</div>` : empty('暂无行情焦点。'), '已有行情与资讯判断，不代表实时行情') }<div class="intel-two-zones">${section('潜在变化', eventRows(d.potential, 3) || empty('暂无已识别的潜在变化。'))}${section('反证与风险', eventRows(d.challenges, 3) || empty('暂无已识别反证，仍需持续核实。'))}</div>${section('哪些资讯值得看', `${filters}<div class="intel-result-meta">${filtered.length.toLocaleString()} 条匹配事件</div><div class="intel-event-list">${eventRows(filtered, s.limit) || empty()}</div>${moreButton(filtered.length, s.limit)}`)}${list(current.breakfast?.stories).length ? section('近七天早餐 · 持续要闻', `<div class="intel-story-grid">${list(current.breakfast.stories).map(item => `<article class="intel-story"><h3>${e(item.title)}</h3>${para(item.why_now)}${para(item.market_chain)}</article>`).join('')}</div>`) : ''}`;
}
function articleCard(item, { title, content, time, url, source } = {}) {
  const heading = title || item.title;
  const body = content || item.summary || item.content;
  return `<article class="intel-article"><div class="intel-item-meta"><span>${e(source || item.source || '公开来源')}</span><time>${e(intelTime(time || item.time))}</time></div>${title || item.title ? `<h3>${e(title || item.title)}</h3>` : ''}${text(body).trim() === text(heading).trim() ? '' : para(body)}${sourceLink(url || item.url)}</article>`;
}
function renderReports(s, current) {
  const d = current.data; if (!d) return '';
  const items = list(d.items);
  return `<div class="intel-result-meta">共 ${Number(d.total || 0).toLocaleString()} 篇研报 · 第 ${Math.floor(current.offset / 20) + 1} 页</div><div class="intel-event-list">${items.map(item => `<button class="intel-event-row" data-intel-action="report" data-id="${e(item.id)}"><span class="intel-item-meta"><span>${e(sourceLabel(item.source, '研究报告'))}</span><time>${e(intelTime(item.published_at || item.received_at))}</time>${tag(processingLabel(item.processing?.status))}</span><strong>${e(item.title)}</strong>${para(item.summary)}</button>`).join('') || empty('暂无研究报告。')}</div><div class="intel-pagination"><button class="button" data-intel-action="report-prev" ${!current.offset || current.loading ? 'disabled' : ''}>上一页</button><button class="button" data-intel-action="report-next" ${current.offset + items.length >= Number(d.total || 0) || current.loading ? 'disabled' : ''}>下一页</button></div>`;
}
function renderRadar(s, current) {
  const d = current.data; if (!d) return '';
  const industries = list(d.industries); const industry = industries.find(item => item.key === s.industry);
  const keyword = s.query.trim().toLocaleLowerCase();
  const items = list(industry?.items).filter(item => !keyword || `${item.title} ${item.summary || ''} ${item.source}`.toLocaleLowerCase().includes(keyword));
  return `<div class="intel-result-meta">公开 RSS 资讯 · ${industries.length} 个赛道 · 更新于 ${e(intelTime(d.generated_at))}</div><div class="intel-industry-tabs" aria-label="资讯赛道">${industries.map(item => `<button class="button ${item.key === s.industry ? 'active' : ''}" data-intel-action="industry" data-id="${e(item.key)}" aria-pressed="${item.key === s.industry}">${e(item.name)}<span>${Number(item.total || list(item.items).length)}</span></button>`).join('')}</div><div class="intel-filters">${search(s)}</div><div class="intel-article-grid">${items.slice(0, s.limit).map(item => articleCard(item)).join('') || empty()}</div>${moreButton(items.length, s.limit)}`;
}
function renderWsc(s, current) {
  const d = current.data; if (!d) return '';
  const items = list(d.items);
  return `<div class="intel-result-meta">华尔街见闻 · 重要快讯 · ${items.length} 条</div><div class="intel-feed">${items.map(item => articleCard(item, { source: '华尔街见闻', url: item.url || item.related_article_url })).join('') || empty('暂无见闻快讯。')}</div>${d.has_more ? `<button class="button intel-more" data-intel-action="wsc-more" ${current.loading ? 'disabled' : ''}>${current.loading ? '读取中…' : '加载更多快讯'}</button>` : ''}`;
}
const platformNames = { x: 'X', twitter: 'X', xiaohongshu: '小红书', douyin: '抖音', wechat: '微信公众号' };
function renderSocial(s, current) {
  const d = current.data; if (!d) return '';
  const accounts = list(d.accounts).filter(item => s.platform === 'all' || item.platform === s.platform);
  const platforms = [...new Set([...list(d.accounts), ...list(d.posts)].map(item => item.platform).filter(Boolean))];
  const items = filterIntelPosts(d.posts, s);
  return `<div class="intel-result-meta">${list(d.accounts).length} 个已有账号 · ${list(d.posts).length} 条公开内容</div><div class="intel-filters">${search(s)}${select('platform', '平台', [['all', '全部平台'], ...platforms.map(id => [id, platformNames[id] || id])], s.platform)}${select('account', '账号', [['all', '全部账号'], ...accounts.map(item => [String(item.id), item.name])], s.account)}</div><div class="intel-feed">${items.slice(0, s.limit).map(item => articleCard(item, { source: `${platformNames[item.platform] || item.platform} · ${item.author || '公开账号'}`, content: item.text })).join('') || empty()}</div>${moreButton(items.length, s.limit)}`;
}
function renderStock(s, current) {
  const items = list(current.data);
  const form = `<form class="intel-stock-form" data-intel-stock><label for="intel-code">A 股代码<input id="intel-code" data-intel-code name="code" type="text" inputmode="numeric" maxlength="6" placeholder="例如 600519" value="${e(s.code)}" autocomplete="off"></label><button class="button primary" type="submit" ${current.loading ? 'disabled' : ''}>查询${s.tab === 'filings' ? '公告' : '新闻'}</button></form>${s.stockError ? `<p class="notice danger" role="alert">${e(s.stockError)}</p>` : ''}`;
  if (!current.data) return form + (current.loading ? '' : empty('输入六位 A 股代码，读取该股票的公开资讯。'));
  return form + `<div class="intel-result-meta">${e(current.code || '')} · ${items.length} 条结果</div><div class="intel-feed">${items.slice(0, s.limit).map(item => articleCard(item, { title: item.title || item['新闻标题'], time: item.date || item['发布时间'], content: item['新闻内容'] || item.content, source: item.type || item['文章来源'], url: item.url || item['新闻链接'] })).join('') || empty('该股票暂无可用资讯。')}</div>${moreButton(items.length, s.limit)}`;
}
function processingLabel(status) {
  return ({ complete: '处理完成', completed: '处理完成', pending: '待处理', running: '处理中', processing: '处理中', partial: '部分完成', failed: '处理未完成', deferred: '等待处理', preface: '合集前言' })[status] || (status ? '处理状态待确认' : '原文已收录');
}
function renderFact(value) {
  if (text(value)) return para(value);
  if (!value || typeof value !== 'object') return '';
  return para(value.fact || value.text || value.summary || value.content || value.claim || value.title || value.quote);
}
function renderIntelMarkdown(value) {
  const sanitized = value.replace(/(\[[^\]\n]*\])\(([^)\s]+)\)/g, (whole, label, url) => {
    const safe = intelURL(url); return safe ? `${label}(${safe})` : label;
  });
  return renderMarkdown(sanitized);
}
function reportSection(item) {
  const analysis = item.analysis;
  const structured = analysis && typeof analysis === 'object';
  const narrative = structured ? `${para(analysis.summary)}<div class="intel-item-meta">${list(analysis.topics).map(tag).join('')}</div>${list(analysis.points).map(point => `<div class="intel-evidence">${renderFact(point)}${point.quote ? `<blockquote>${e(point.quote)}</blockquote>` : ''}</div>`).join('')}${list(analysis.risks).length ? `<h3>风险与不确定性</h3>${list(analysis.risks).map(renderFact).join('')}` : ''}` : renderIntelMarkdown(text(analysis || item.content || item.summary));
  return `<details class="intel-detail-section"><summary><strong>${e(item.title || item.name || '分析章节')}</strong> ${tag(processingLabel(item.status))}</summary><div class="intel-document">${narrative || '<p class="muted">本章节尚无分析结果。</p>'}</div>${item.original ? `<details><summary>本章节原文</summary>${para(item.original)}</details>` : ''}</details>`;
}
function renderDetail(s) {
  if (!s.detailId) return '';
  const d = s.detail;
  let content = s.detailLoading ? '<p class="intel-loading" role="status">正在读取详情与原文依据…</p>' : '';
  if (s.detailError) content += `<p class="notice danger" role="alert">${e(s.detailError)}</p><button class="button" data-intel-action="detail-retry">重试详情</button>`;
  if (d && s.detailKind === 'report') {
    const sections = Array.isArray(d.processing?.sections) ? d.processing.sections : [];
    content += `<div class="intel-item-meta">${tag(processingLabel(d.processing?.status))}<time>${e(intelTime(d.published_at))}</time></div><h2>${e(d.title)}</h2>${para(d.summary)}${sourceLink(d.source_url, sourceLabel(d.source, '报告原文'))}${sections.map(reportSection).join('')}<details class="intel-detail-section" ${sections.length ? '' : 'open'}><summary>完整报告原文</summary><div class="intel-document">${renderIntelMarkdown(text(d.content))}</div></details>`;
  } else if (d) {
    const event = d.event || {}; const extraction = event.extraction || {};
    content += `<div class="intel-item-meta">${tag(event.impact ? `影响力：${event.impact}` : '')}${tag(event.credibility ? `可信度：${event.credibility}` : '')}<time>${e(intelTime(event.first_public_at))}</time></div><h2>${e(event.title)}</h2>${para(event.last_change)}${para(event.priority_reason)}${para(event.credibility_reason)}${d.explanation?.text ? `<section class="intel-detail-section"><h3>已有解读</h3>${para(d.explanation.text)}</section>` : ''}${Object.entries({ '新增事实': extraction.new_facts || extraction.facts, '投资传导': extraction.market_chain || extraction.transmission, '反证与不确定性': extraction.counter_evidence || extraction.uncertainties }).map(([label, value]) => value ? `<section class="intel-detail-section"><h3>${label}</h3>${Array.isArray(value) ? value.map(renderFact).join('') : renderFact(value)}</section>` : '').join('')}<section class="intel-detail-section"><h3>原始报道 · ${list(d.articles).length} 篇</h3>${list(d.articles).map(item => `<article class="intel-evidence"><div class="intel-item-meta"><span>${e(item.source || '原始来源')}</span><time>${e(intelTime(item.received_at))}</time></div>${sourceLink(item.url)}${para(item.content)}${item.original_content && item.original_content !== item.content ? `<details><summary>展开完整原文</summary>${para(item.original_content)}</details>` : ''}</article>`).join('') || '<p class="muted">暂无原始报道。</p>'}</section>${list(d.revisions).length ? `<details class="intel-detail-section"><summary>版本记录 · ${list(d.revisions).length}</summary>${list(d.revisions).map(item => `<div class="intel-evidence">${tag(`版本 ${item.revision || item.version || '待核实'}`)}${para(item.change_reason || item.summary || item.title)}<span class="muted small">${e(intelTime(item.updated_at || item.created_at))}</span></div>`).join('')}</details>` : ''}`;
  }
  return `<aside class="intel-detail" aria-label="${s.detailKind === 'report' ? '研报' : '事件'}详情"><header class="intel-detail-header"><strong id="intel-detail-title" tabindex="-1">${s.detailKind === 'report' ? '研报阅读' : '事件与证据'}</strong><button class="button" data-intel-action="close" aria-label="关闭详情">关闭 ${icon('close')}</button></header><div class="intel-detail-body">${content}</div></aside>`;
}
export function renderIntel(s) {
  const current = s.entries[s.tab] || { data: null, loading: false, error: '' };
  const title = intelTabs.find(item => item[0] === s.tab)?.[1] || '事件总览';
  const views = { overview: renderOverview, 'research-reports': renderReports, 'investment-news': renderRadar, wsc: renderWsc, social: renderSocial, news: renderStock, filings: renderStock };
  const content = s.tab === 'events' ? section('事件概率', empty('该数据源规划中，可先浏览事件总览或公开资讯。'), '全球宏观预期概率 · 后续接入') : (views[s.tab]?.(s, current) || '');
  return `<div class="intel-page"><header class="intel-page-header"><div><span class="eyebrow">INTELLIGENCE RADAR</span><h1>资讯雷达</h1><p class="muted">跨来源阅读资讯，追踪事件变化与原文证据。</p></div>${s.tab !== 'events' ? `<button class="button" data-intel-action="refresh" ${current.loading || (['news', 'filings'].includes(s.tab) && !validStockCode(s.code)) ? 'disabled' : ''}>${icon('restore')}${current.loading ? '读取中…' : '刷新资讯'}</button>` : ''}</header><nav class="intel-tabs" aria-label="资讯栏目">${intelTabs.map(([id, label]) => `<a href="#/intel/${id}" class="${s.tab === id ? 'active' : ''}" ${s.tab === id ? 'aria-current="page"' : ''}>${e(label)}</a>`).join('')}</nav><div class="intel-reading-layout ${s.detailId ? 'has-detail' : ''}"><div class="intel-main" aria-label="${e(title)}"><div class="intel-status" aria-live="polite">${current.error ? `<div class="notice danger" role="alert">${e(current.error)} <button class="text-button" data-intel-action="refresh">重试</button></div>` : ''}${current.loading ? '<p class="intel-loading" role="status">正在读取资讯…</p>' : ''}</div>${content}</div>${renderDetail(s)}</div><footer class="intel-footer">数据来自 Golddata / Vibe-Research · 时间按北京时间显示 · 仅展示现有资讯与分析</footer></div>`;
}
