import { escapeHTML as e, safeURL } from './markdown.mjs';
import { safeLog } from './core.mjs';
import { assetNewsCode, cleanAsset } from './asset-navigation.mjs';

const text = value => typeof value === 'string' || typeof value === 'number' ? String(value) : '';
const sourceURL = value => { const url = safeURL(typeof value === 'string' && value.startsWith('/vibe-research/') ? `http://47.92.168.126${value}` : value); return url && /^https?:\/\//.test(url) ? url : null; };
export function createAssetNewsController({ fetcher = (...args) => fetch(...args), onChange = () => {}, account = () => globalThis.__RWB_USER_ID__ || 'local', timeoutMs = 20000 } = {}) {
  const state = { asset: '', assetType: 'stock', view: '', status: 'idle', items: [], error: '', limit: 20, selected: 0, retrievedAt: null };
  const cache = new Map(); let generation = 0; let abort; let owner = account();
  function cancel() { generation++; abort?.abort(); abort = null; if (state.status === 'loading') state.status = 'idle'; }
  async function activate(route, { refresh = false } = {}) {
    cancel();
    if (owner !== account()) { owner = account(); cache.clear(); }
    const asset = cleanAsset(route.asset); const view = route.assetView;
    const key = JSON.stringify([owner, route.assetType, asset, view]);
    Object.assign(state, { asset, assetType: route.assetType, view, status: 'idle', items: [], error: '', selected: 0, limit: 20, retrievedAt: null });
    if (!['news', 'announcements'].includes(view)) return;
    const code = assetNewsCode(asset, route.assetType);
    if (!code) { state.status = 'unsupported'; onChange(); return; }
    const previous = cache.get(key);
    if (previous) Object.assign(state, previous);
    if (previous && !refresh) { onChange(); return; }
    const ticket = generation; abort = new AbortController(); const requestAbort = abort; const signal = requestAbort.signal;
    state.status = 'loading'; onChange(); let timer;
    try {
      const expired = new Promise((_, reject) => { timer = setTimeout(() => { requestAbort.abort(); reject(new Error('资讯读取超时，请重试。')); }, timeoutMs); });
      const result = await Promise.race([(async () => {
        const response = await fetcher(`/api/research/intel/${view === 'announcements' ? 'announcements' : 'news'}?code=${code}`, { signal, credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail?.message || `资讯读取失败（${response.status}）`);
        if (!Array.isArray(data) || data.some(item => !item || typeof item !== 'object' || Array.isArray(item))) throw new Error('资讯响应格式异常，请重试。');
        return data;
      })(), expired]);
      if (ticket !== generation) return;
      Object.assign(state, { status: result.length ? 'complete' : 'empty', items: result, error: '', retrievedAt: new Date().toISOString() });
      cache.set(key, { ...state });
      if (cache.size > 32) cache.delete(cache.keys().next().value);
    } catch (error) {
      if (ticket !== generation) return;
      state.status = 'error'; state.error = error.message || '资讯读取失败，请重试。';
      safeLog('asset_news_read_failed', { status: view, method: 'GET' });
    } finally { clearTimeout(timer); if (ticket === generation) { abort = null; onChange(); } }
  }
  function select(index) { if (Number.isInteger(index) && index >= 0 && index < state.items.length) { state.selected = index; onChange(); } }
  function more() { state.limit += 20; onChange(); }
  return { state, activate, cancel, select, more };
}
export function renderAssetNews(state = {}) {
  const title = state.view === 'announcements' ? '公告' : '新闻';
  if (state.status === 'unsupported' || !state.asset) return `<section class="asset-topic-empty"><h2>${title}</h2><p>选择 A 股股票后查看${title}；其他资产当前没有对应的资讯覆盖。</p></section>`;
  const items = state.items || []; const item = items[state.selected || 0];
  const heading = row => text(row.title || row['新闻标题']) || '来源未提供标题';
  const when = row => text(row.published_at || row.date || row['发布时间'] || row.time) || '时间未提供';
  const source = row => text(row.source || row.type || row['文章来源']) || '公开来源';
  const body = row => text(row['新闻内容'] || row.content || row.summary);
  const url = item && sourceURL(item.url || item['新闻链接'] || item.document_url);
  return `<section class="asset-news-workspace" aria-label="${title}阅读"><header class="section-heading"><div><h2>${e(state.asset)} · ${title}</h2><p class="muted small">Golddata · 按代码查询 · 上游覆盖及逐条关联未经独立核验${state.retrievedAt ? ` · 读取于 ${e(state.retrievedAt)}` : ''}</p></div><button class="button small" data-asset-news-refresh ${state.status === 'loading' ? 'disabled' : ''}>${state.status === 'loading' ? '读取中…' : '刷新'}</button></header>${state.error ? `<p class="notice danger" role="alert">${e(state.error)}${items.length ? ' 以下保留上次读取内容。' : ''}</p>` : ''}${state.status === 'loading' ? '<p role="status">正在读取公开资讯…</p>' : ''}${state.status === 'empty' ? '<p class="muted">来源返回了空列表，当前没有记录。</p>' : ''}<div class="asset-news-grid"><div class="asset-news-list">${items.slice(0, state.limit || 20).map((row, index) => `<button class="asset-news-row ${index === (state.selected || 0) ? 'active' : ''}" data-asset-news-select="${index}" aria-pressed="${index === (state.selected || 0)}"><span class="muted small">${e(when(row))} · ${e(source(row))}</span><strong>${e(heading(row))}</strong></button>`).join('')}${items.length > (state.limit || 20) ? '<button class="button" data-asset-news-more>展开更多已取得记录</button>' : ''}</div>${item ? `<article class="asset-news-reader" tabindex="0"><p class="muted small">${e(when(item))} · ${e(source(item))}</p><h3>${e(heading(item))}</h3><p class="muted small">以下为来源返回的正文或摘要，未补充抓取全文。</p><div class="asset-reading-text">${e(body(item) || '来源未返回正文或摘要。')}</div>${url ? `<a href="${e(url)}" target="_blank" rel="noopener noreferrer">查看原文 ↗</a>` : ''}</article>` : ''}</div></section>`;
}
