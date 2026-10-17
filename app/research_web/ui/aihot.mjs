import { safeLog, parseRoute } from './core.mjs';
import { e, list, kinds, reportHash, external } from './aihot-common.mjs';
import { renderArchive, renderArchiveBook, renderPaper, kindSwitch, pagesOf } from './aihot-report.mjs';
import { renderArticle, renderStory, renderTopic, articleMarkdown } from './aihot-reading.mjs';
import { renderHot } from './aihot-hot.mjs';
import { createNewsManagement, renderNewsManagement } from './ai-news-manage.mjs';

export function createAihotController({ fetcher = (...args) => fetch(...args), onChange = () => {}, canManage = () => !globalThis.__RWB_USER_ID__ || globalThis.__RWB_USER_ROLE__ === 'admin' } = {}) {
  const state = { tab: 'daily', kind: 'daily', date: '', editions: [], report: null, hot: null, loading: false, error: '', months: {}, openMonths: new Map(), detail: null, filter: 'all', order: 'desc', viewCache: new Map() };
  let generation = 0, abort, route = {};
  const readingHistory=[];
  const management = createNewsManagement({fetcher,onChange});
  state.management = management.state;
  state.canManage=Boolean(canManage());
  let linkIntent='';
  function routeHash(value) {
    const tab=value.aihotTab || 'daily';
    if (['item','story','topic'].includes(tab)) return `#/aihot/${tab}/${value.aihotId}${tab==='item' && value.aihotLanguage==='original' ? '?lang=original' : tab==='topic' ? `?page=${value.aihotPage || 1}` : ''}`;
    return `#/aihot/${tab}${value.aihotDate ? `?date=${value.aihotDate}` : ''}`;
  }
  function cancel() { generation++; abort?.abort(); management.cancel(); state.loading = false; for (const month of Object.values(state.months)) month.loading = false; }
  async function get(path, signal) {
    const response = await fetcher(`/api/research/aihot/${path}`, { signal, credentials: 'same-origin', headers: { Accept: 'application/json' } });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail?.message || `AIHOT 读取失败（${response.status}）`);
    return result;
  }
  async function activate(nextRoute) {
    route = { ...nextRoute }; cancel();
    state.canManage=Boolean(canManage());management.state.accessDenied=!state.canManage;
    if(route.aihotTab==='manage') {
      state.tab='manage';
      if(!state.canManage){Object.assign(management.state,{data:null,status:null,error:'',loading:false});onChange();return;}
      return management.activate(route.aiNewsSection);
    }
    const hash=routeHash(route);
    if (linkIntent !== hash && readingHistory.at(-2)===hash) readingHistory.pop();
    else if(readingHistory.at(-1)!==hash) {readingHistory.push(hash);if(readingHistory.length>50)readingHistory.shift();}
    linkIntent='';
    state.backHash=readingHistory.at(-2) || (route.aihotTab==='story' ? '#/aihot/hot' : '#/aihot/daily');
    const ticket = generation;
    const currentAbort = new AbortController(); abort = currentAbort;
    const timeout = setTimeout(() => currentAbort.abort(), 45000);
    const tab = ['hot', 'archive', 'daily', 'weekly', 'monthly', 'item', 'story', 'topic'].includes(route.aihotTab) ? route.aihotTab : 'daily';
    const kind = Object.hasOwn(kinds, tab) ? tab : 'daily';
    if (kind !== state.kind) { state.months = {}; state.openMonths = new Map(); }
    Object.assign(state, { tab, kind, date: route.aihotDate || '', report: null, hot: null, detail: null, editions: [], loading: true, error: '' });
    onChange();
    try {
      if (['item', 'story', 'topic'].includes(tab)) {
        let identity = route.aihotId;
        const prefix = ({item:'items', story:'stories', topic:'topics'})[tab];
        const suffix = tab === 'item' && route.aihotLanguage === 'original' ? '/original' : tab === 'topic' ? `?page=${route.aihotPage || 1}` : '';
        let detail;
        const seen = new Set();
        for (let hop = 0; hop < 4; hop++) {
          if (!/^[A-Za-z0-9_-]{1,80}$/.test(identity || '') || seen.has(identity)) throw new Error('专题合并链异常，请返回热点榜重试。');
          seen.add(identity);
          detail = await get(`${prefix}/${identity}${suffix}`, currentAbort.signal);
          if (ticket !== generation) return;
          if (tab !== 'story' || !detail.mergedInto) break;
          identity = detail.mergedInto;
          if (hop === 3) throw new Error('专题合并链过长，请返回热点榜重试。');
        }
        state.detail = detail;
        Object.assign(state, state.viewCache.get(identity) || {filter:'all',order:'desc'});
      } else if (tab === 'hot') {
        const hot = await get('pages/hot', currentAbort.signal);
        if (ticket !== generation) return;
        if (!Array.isArray(hot.entries)) throw new Error('AIHOT 热点数据格式已变化。');
        state.hot = hot;
      } else if (tab === 'archive') {
        const index = await get('reports/daily', currentAbort.signal);
        if (ticket !== generation) return;
        state.editions = list(index.items);
      } else if (state.date) {
        const date = state.date;
        const [report, index] = await Promise.all([get(`reports/${kind}/${encodeURIComponent(date)}`, currentAbort.signal), get(`reports/${kind}/navigation/${encodeURIComponent(date)}`, currentAbort.signal)]);
        if (ticket !== generation) return;
        state.report = report; state.editions = list(index.items);
      } else {
        const result = await get(`reports/${kind}/latest-page`, currentAbort.signal);
        if (ticket !== generation) return;
        state.report = result.report; state.editions = list(result.index); state.date = result.report?.key || '';
      }
      safeLog('aihot_loaded', { status: 'completed', method: 'GET' });
    } catch (error) {
      if (ticket !== generation) return;
      state.error = error.name === 'AbortError' ? 'AIHOT 读取超时，请重试。' : error.message || 'AIHOT 读取失败，请重试。';
      safeLog('aihot_load_failed', { status: 'failed', method: 'GET' });
    } finally {
      clearTimeout(timeout);
      if (ticket === generation) { state.loading = false; onChange(); }
    }
  }
  async function loadMonth(month) {
    if (state.kind !== 'daily' || !/^\d{4}-\d{2}$/.test(month) || state.months[month]?.loading) return;
    const ticket = generation, currentAbort = abort;
    state.months[month] = { loading: true, error: '' }; onChange();
    const deadline = new AbortController();
    const relay = () => deadline.abort();
    currentAbort?.signal.addEventListener('abort', relay, { once: true });
    const timeout = setTimeout(relay, 22000);
    try {
      const index = await get(`reports/daily/months/${month}`, deadline.signal);
      if (ticket === generation) state.months[month] = { items: list(index.items), error: '', loading: false };
    } catch (error) {
      if (ticket === generation) state.months[month] = { error: error.name === 'AbortError' ? '归档读取超时，请重试。' : error.message, loading: false };
      safeLog('aihot_archive_load_failed', { status: 'failed', method: 'GET' });
    } finally {
      clearTimeout(timeout); currentAbort?.signal.removeEventListener('abort', relay);
      if (ticket === generation) onChange();
    }
  }
  function toggleMonth(month, open) {
    state.openMonths.set(month, open);
    if (open && !state.loading && !state.months[month]?.items && !state.months[month]?.error && state.editions.some(item => item.key?.startsWith(month) && item.title === undefined)) void loadMonth(month);
  }
  function prepareLink(hash) { const target=typeof hash==='string' ? routeHash(parseRoute(hash)) : '';linkIntent=target !== routeHash(route) ? target : ''; }
  function back() {
    linkIntent='';
    if(readingHistory.length>1){readingHistory.pop();return readingHistory.at(-1);}
    const destination=state.backHash || '#/aihot/daily';readingHistory.length=0;return destination;
  }
  async function loadGroup() {
    const item = state.detail, ticket = generation;
    if (state.tab !== 'item' || !item?.group?.factId || item.groupLoading) return;
    if (!/^[A-Za-z0-9_-]{1,80}$/.test(item.group.factId)) return;
    item.groupLoading=true;item.groupError='';onChange();
    const deadline=new AbortController(), relay=()=>deadline.abort();
    const signal=abort?.signal;signal?.addEventListener('abort',relay,{once:true});
    const timer=setTimeout(relay,22000);
    try { const result=await get(`groups/${item.group.factId}/reports`,deadline.signal);if(ticket===generation)item.groupReports=list(result.reports); }
    catch { if(ticket===generation)item.groupError='来源列表读取失败，请重试。';safeLog('aihot_group_failed',{status:'failed'}); }
    finally { clearTimeout(timer);signal?.removeEventListener('abort',relay);if(ticket===generation){item.groupLoading=false;onChange();} }
  }
  function setStoryView(view) {
    if (state.tab !== 'story' || !state.detail) return;
    state.filter = ['all','official','selected'].includes(view.filter) ? view.filter : state.filter;
    state.order = ['asc','desc'].includes(view.order) ? view.order : state.order;
    state.viewCache.set(state.detail.publicId, {filter:state.filter,order:state.order});
    while (state.viewCache.size > 32) state.viewCache.delete(state.viewCache.keys().next().value);
    onChange();
  }
  async function copy(kind) {
    if (!state.detail || state.tab !== 'item') return;
    const item=state.detail,ticket=generation;
    try {
      const value = kind === 'markdown' ? articleMarkdown(item) : `${location.origin}${location.pathname}#/aihot/item/${encodeURIComponent(item.id)}`;
      await navigator.clipboard.writeText(value);
      if(ticket !== generation || state.detail !== item)return;
      item.actionNotice = '已复制';
    } catch {
      if(ticket !== generation || state.detail !== item)return;
      item.actionNotice = '复制失败，请允许剪贴板访问或使用导出。';
      safeLog('aihot_copy_failed',{status:'failed'});
    }
    onChange();
  }
  function download() {
    if (!state.detail || state.tab !== 'item') return;
    const url = URL.createObjectURL(new Blob([articleMarkdown(state.detail)],{type:'text/markdown;charset=utf-8'}));
    try { const anchor = document.createElement('a'); anchor.href=url;anchor.download=`aihot-${state.detail.id}.md`;anchor.click(); }
    catch { state.detail.actionNotice='导出失败，请重试。';safeLog('aihot_export_failed',{status:'failed'});onChange(); }
    finally { setTimeout(()=>URL.revokeObjectURL(url),1000); }
  }
  return { state, activate, cancel, management, loadMonth, toggleMonth, prepareLink, back, loadGroup, setStoryView, copy, download, refresh: () => activate(route) };
}

export function renderAihot(state) {
  if(state.tab==='manage')return renderNewsManagement(state.management);
  const hot = state.tab === 'hot';
  if (['item','story','topic'].includes(state.tab)) {
    const content = state.loading ? '<p class="aihot-empty" role="status">正在读取全文…</p>' : state.error ? `<div class="notice danger" role="alert">${e(state.error)}<button data-aihot-refresh>重试</button></div>` : state.detail ? state.tab === 'item' ? renderArticle(state.detail) : state.tab === 'story' ? renderStory(state.detail,state) : renderTopic(state.detail) : '<p>内容暂未提供。</p>';
    return `<section class="aihot-page aihot-full-reading" aria-busy="${Boolean(state.loading)}"><nav class="aihot-module-bar" aria-label="AI资讯阅读导航"><div><a data-aihot-back href="${e(state.backHash || '#/aihot/daily')}">← 返回</a><a href="#/aihot/daily">日报</a><a href="#/aihot/hot">热点榜</a></div><button data-aihot-refresh ${state.loading ? 'disabled' : ''}>刷新</button></nav>${content}<footer class="aihot-footer">本机自主资讯库 · 模型质量验收 NOT_RUN</footer></section>`;
  }
  const outline = state.report ? pagesOf(state.report).pages : [];
  const outlineLinks = outline.map((page, i) => `<button data-aihot-jump="${page.id}">${String(i + 1).padStart(2, '0')} ${e(page.label)}</button>`).join('') + (state.report?.flashes?.length ? '<button data-aihot-jump="aihot-s-flash">快讯</button>' : '');
  const body = state.loading ? '<p class="aihot-empty" role="status">正在读取 AIHOT…</p>' : state.error ? `<div class="notice danger" role="alert">${e(state.error)}<button class="text-button" data-aihot-refresh>重试</button></div>` : hot ? renderHot(state.hot || {}) : state.tab === 'archive' ? renderArchiveBook(state) : state.report ? renderPaper(state.report, state.editions) : `<p class="aihot-empty">当前暂无可用${kinds[state.kind] || '日报'}。</p>`;
  const recent = list(state.editions).slice(0, 3);
  return `<section class="aihot-page ${hot ? 'aihot-hot' : 'aihot-reports'}" aria-busy="${Boolean(state.loading)}"><div class="aihot-module-bar"><nav aria-label="AIHOT 栏目"><a href="#/aihot/daily" ${!hot ? 'aria-current="page"' : ''}>日报</a><a href="#/aihot/hot" ${hot ? 'aria-current="page"' : ''}>热点榜</a></nav><div>${state.canManage !== false ? '<a href="#/aihot/manage">采编管理</a>' : ''}<button type="button" data-aihot-refresh ${state.loading ? 'disabled' : ''}>刷新</button></div></div><div class="aihot-layout">${!hot ? renderArchive(state) : ''}<div class="aihot-reading">${!hot ? `<div class="aihot-phone-bar">${kindSwitch(state.kind)}<button data-aihot-outline aria-label="本期目录">☷ 本期目录</button></div><nav class="aihot-recent" aria-label="最近期次">${recent.map((item, i) => `<a href="${reportHash(state.kind, item.key)}" ${item.key === state.date ? 'aria-current="date"' : ''}>${i === 0 ? '最新一期' : e(item.key)}</a>`).join('')}${state.kind === 'daily' ? '<a href="#/aihot/archive">更早</a>' : '<button data-aihot-jump="aihot-report-history">更早</button>'}</nav>` : ''}${body}</div></div><dialog class="aihot-outline-dialog" aria-labelledby="aihot-outline-title"><header><h2 id="aihot-outline-title">本期目录</h2><button data-aihot-outline-close aria-label="关闭目录">×</button></header><button data-aihot-jump="aihot-report-start">头版</button>${outlineLinks}</dialog><footer class="aihot-footer"><span>本机自主资讯库</span>${!hot ? `<a href="/api/research/ai-news/feeds/${state.kind}.xml">RSS 订阅</a>` : ''}<span>时间按北京时间显示 · 从自主材料重新起刊</span></footer></section>`;
}
