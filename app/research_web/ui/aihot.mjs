import { safeLog } from './core.mjs';
import { e, list, kinds, reportHash, external } from './aihot-common.mjs';
import { renderArchive, renderArchiveBook, renderPaper, kindSwitch, pagesOf } from './aihot-report.mjs';
import { renderHot } from './aihot-hot.mjs';

export function createAihotController({ fetcher = (...args) => fetch(...args), onChange = () => {} } = {}) {
  const state = { tab: 'daily', kind: 'daily', date: '', editions: [], report: null, hot: null, loading: false, error: '', months: {}, openMonths: new Map() };
  let generation = 0, abort, route = {};
  function cancel() { generation++; abort?.abort(); state.loading = false; for (const month of Object.values(state.months)) month.loading = false; }
  async function get(path, signal) {
    const response = await fetcher(`/api/research/aihot/${path}`, { signal, credentials: 'same-origin', headers: { Accept: 'application/json' } });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail?.message || `AIHOT 读取失败（${response.status}）`);
    return result;
  }
  async function activate(nextRoute) {
    route = { ...nextRoute }; cancel();
    const ticket = generation;
    const currentAbort = new AbortController(); abort = currentAbort;
    const timeout = setTimeout(() => currentAbort.abort(), 45000);
    const tab = ['hot', 'archive', 'daily', 'weekly', 'monthly'].includes(route.aihotTab) ? route.aihotTab : 'daily';
    const kind = Object.hasOwn(kinds, tab) ? tab : 'daily';
    if (kind !== state.kind) { state.months = {}; state.openMonths = new Map(); }
    Object.assign(state, { tab, kind, date: route.aihotDate || '', report: null, hot: null, editions: [], loading: true, error: '' });
    onChange();
    try {
      if (tab === 'hot') {
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
  return { state, activate, cancel, loadMonth, toggleMonth, refresh: () => activate(route) };
}

export function renderAihot(state) {
  const hot = state.tab === 'hot';
  const outline = state.report ? pagesOf(state.report).pages : [];
  const outlineLinks = outline.map((page, i) => `<button data-aihot-jump="${page.id}">${String(i + 1).padStart(2, '0')} ${e(page.label)}</button>`).join('') + (state.report?.flashes?.length ? '<button data-aihot-jump="aihot-s-flash">快讯</button>' : '');
  const body = state.loading ? '<p class="aihot-empty" role="status">正在读取 AIHOT…</p>' : state.error ? `<div class="notice danger" role="alert">${e(state.error)}<button class="text-button" data-aihot-refresh>重试</button></div>` : hot ? renderHot(state.hot || {}) : state.tab === 'archive' ? renderArchiveBook(state) : state.report ? renderPaper(state.report, state.editions) : `<p class="aihot-empty">当前暂无可用${kinds[state.kind] || '日报'}。</p>`;
  const recent = list(state.editions).slice(0, 3);
  return `<section class="aihot-page ${hot ? 'aihot-hot' : 'aihot-reports'}" aria-busy="${Boolean(state.loading)}"><div class="aihot-module-bar"><nav aria-label="AIHOT 栏目"><a href="#/aihot/daily" ${!hot ? 'aria-current="page"' : ''}>日报</a><a href="#/aihot/hot" ${hot ? 'aria-current="page"' : ''}>热点榜</a></nav><div>${external(hot ? 'https://aihot.news/hot' : `https://aihot.news/${state.kind}${state.date ? '/' + state.date : ''}`, '原站 ↗')}<button type="button" data-aihot-refresh ${state.loading ? 'disabled' : ''}>刷新</button></div></div><div class="aihot-layout">${!hot ? renderArchive(state) : ''}<div class="aihot-reading">${!hot ? `<div class="aihot-phone-bar">${kindSwitch(state.kind)}<button data-aihot-outline aria-label="本期目录">☷ 本期目录</button></div><nav class="aihot-recent" aria-label="最近期次">${recent.map((item, i) => `<a href="${reportHash(state.kind, item.key)}" ${item.key === state.date ? 'aria-current="date"' : ''}>${i === 0 ? '最新一期' : e(item.key)}</a>`).join('')}${state.kind === 'daily' ? '<a href="#/aihot/archive">更早</a>' : '<button data-aihot-jump="aihot-report-history">更早</button>'}</nav>` : ''}${body}</div></div><dialog class="aihot-outline-dialog" aria-labelledby="aihot-outline-title"><header><h2 id="aihot-outline-title">本期目录</h2><button data-aihot-outline-close aria-label="关闭目录">×</button></header><button data-aihot-jump="aihot-report-start">头版</button>${outlineLinks}</dialog><footer class="aihot-footer">${external('https://aihot.news', '数据来源：AIHOT ↗')}${!hot ? external(`https://aihot.news/feed/${state.kind}.xml`, 'RSS 订阅 ↗') : ''}<span>时间按北京时间显示 · 内容与热度均来自原站</span></footer></section>`;
}
