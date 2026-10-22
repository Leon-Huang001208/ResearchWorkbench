import { escapeHTML as e } from './markdown.mjs';
import { safeLog } from './core.mjs';

export const normalizeAssetSearch = value => String(value || '').normalize('NFKC').trim().toLowerCase().slice(0, 80);
const validItem = item => item && item.asset_type === 'stock' && /^\d{6}\.(SH|SZ|BJ)$/.test(item.asset) && typeof item.name === 'string' && item.name.trim();
const listId = 'asset-search-results';
const optionId = index => `asset-search-option-${index}`;

function resultHTML(state) {
  if (!state.open || !state.query) return '';
  const note = state.status === 'loading' ? '正在准备证券目录…' : state.status === 'stale' ? '正在更新目录，以下为已保存结果。' : state.status === 'empty' ? '没有匹配的 A 股。' : state.error || '';
  return `<div class="asset-search-popup"><div id="${listId}" role="listbox" aria-label="匹配的A股">${(state.items || []).map((item, index) => `<button type="button" role="option" id="${optionId(index)}" data-asset-search-result="${index}" aria-selected="${state.selected === index}"><strong>${e(item.name)}</strong><span>${e(item.asset)} · ${e(({ SH: '上海', SZ: '深圳', BJ: '北京' })[item.exchange] || item.exchange)}</span></button>`).join('')}</div>${note ? `<p role="status">${e(note)}</p>` : ''}${['error', 'unavailable'].includes(state.status) ? '<button type="button" class="button small" data-asset-search-retry>重试目录查询</button>' : ''}</div>`;
}

export function renderAssetSearch(state = {}) {
  return `<div class="asset-code-search"><label class="sr-only" for="asset-search-input">搜索A股：代码、名称或拼音首字母</label><input id="asset-search-input" type="search" maxlength="80" role="combobox" aria-autocomplete="list" aria-controls="${listId}" aria-expanded="${Boolean(state.open && state.query)}"${state.selected >= 0 ? ` aria-activedescendant="${optionId(state.selected)}"` : ''} autocomplete="off" spellcheck="false" placeholder="代码 / 名称 / 简拼" value="${e(state.query || '')}"><div data-asset-search-results>${resultHTML(state)}</div></div>`;
}

export function createAssetSearchController({ api, onChange = () => {}, onSelect = () => {}, account = () => globalThis.__RWB_USER_ID__ || 'local', debounceMs = 200, pollMs = 500, maxPollMs = 60000 } = {}) {
  const state = { query: '', items: [], status: 'idle', open: false, selected: -1, error: '', totalCount: 0 };
  let owner = account(); let generation = 0; let abort; let timer; let disposed = false;
  const current = ticket => !disposed && ticket === generation && owner === account();
  const notify = () => { if (!disposed) onChange(state); };
  function cancel() { generation++; abort?.abort(); abort = null; clearTimeout(timer); }
  function ensureOwner() {
    if (owner === account()) return true;
    cancel(); owner = account(); Object.assign(state, { query: '', items: [], open: false, selected: -1, status: 'idle', error: '', totalCount: 0 }); notify(); return false;
  }
  async function read(ticket, query, started) {
    if (!current(ticket)) { ensureOwner(); return; }
    abort = new AbortController(); const request = abort;
    try {
      const data = await api.searchAssets(query, { signal: request.signal, limit: 20 });
      if (!current(ticket)) { ensureOwner(); return; }
      if (!data || !Array.isArray(data.items) || !['loading', 'ready', 'stale', 'error', 'unavailable'].includes(data.status)) throw new Error('证券目录响应格式异常，请重试。');
      state.items = data.items.filter(validItem).slice(0, 20).map(item => ({ ...item, name: item.name.slice(0, 120), exchange: item.asset.split('.')[1] }));
      state.totalCount = Number.isSafeInteger(data.total_count) ? data.total_count : 0;
      state.status = data.status === 'ready' && !state.items.length ? 'empty' : data.status;
      state.selected = state.items.length ? Math.min(Math.max(0, state.selected), state.items.length - 1) : -1;
      state.error = ['error', 'unavailable'].includes(data.status) ? '证券目录暂不可用，请重试。' : '';
      if (['loading', 'stale'].includes(data.status)) {
        if (Date.now() - started < maxPollMs) timer = setTimeout(() => { void read(ticket, query, started); }, pollMs);
        else { state.status = 'error'; state.error = '证券目录仍未加载完成，请稍后重试。'; }
      }
      notify();
    } catch (error) {
      if (!current(ticket)) { ensureOwner(); return; }
      state.status = 'error'; state.error = error.name === 'AbortError' ? '证券目录读取已取消，请重试。' : error.message || '证券目录读取失败，请重试。';
      safeLog('asset_search_failed', { status: error.code || 'request_failed' }); notify();
    } finally { if (abort === request) abort = null; }
  }
  function search(value) {
    if (disposed) return Promise.resolve();
    ensureOwner(); cancel(); const query = normalizeAssetSearch(value);
    Object.assign(state, { query, items: [], selected: -1, status: query ? 'loading' : 'idle', open: Boolean(query), error: '' }); notify();
    return query ? read(generation, query, Date.now()) : Promise.resolve();
  }
  function schedule(value) {
    if (disposed) return;
    ensureOwner(); cancel(); const query = normalizeAssetSearch(value);
    Object.assign(state, { query, items: [], selected: -1, status: query ? 'loading' : 'idle', open: Boolean(query), error: '' }); notify();
    if (query) { const ticket = generation; timer = setTimeout(() => { if (current(ticket)) void read(ticket, query, Date.now()); }, debounceMs); }
  }
  function select(index) {
    if (!ensureOwner() || disposed || !state.open || !Number.isInteger(index) || !validItem(state.items[index])) return;
    const item = state.items[index]; state.open = false; notify();
    try { Promise.resolve(onSelect({ ...item })).catch(() => { safeLog('asset_search_select_failed', { status: 'navigation_failed' }); }); }
    catch { safeLog('asset_search_select_failed', { status: 'navigation_failed' }); }
  }
  function key(value) {
    if (!ensureOwner() || disposed) return false;
    if (value === 'Escape') { state.open = false; notify(); return true; }
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End', 'Enter'].includes(value) || !state.items.length) return false;
    if (value === 'Enter') { select(Math.max(0, state.selected)); return true; }
    state.open = true;
    state.selected = value === 'Home' ? 0 : value === 'End' ? state.items.length - 1 : (state.selected + (value === 'ArrowDown' ? 1 : -1) + state.items.length) % state.items.length;
    notify(); return true;
  }
  return { state, search, schedule, key, select, close() { state.open = false; notify(); }, dispose() { cancel(); disposed = true; state.items = []; state.open = false; } };
}

export function mountAssetSearch(slot, { asset = '', onSelect, api, account } = {}) {
  let currentAsset = asset;
  slot.innerHTML = renderAssetSearch();
  const input = slot.querySelector('input'); const results = slot.querySelector('[data-asset-search-results]');
  const controller = createAssetSearchController({ api, onSelect, account, onChange(state) {
    results.innerHTML = resultHTML(state);
    input.setAttribute('aria-expanded', String(Boolean(state.open && state.query)));
    if (state.selected >= 0 && state.open) input.setAttribute('aria-activedescendant', optionId(state.selected));
    else input.removeAttribute('aria-activedescendant');
  } });
  const onInput = () => controller.schedule(input.value);
  const onKey = event => { if (!event.isComposing && controller.key(event.key)) event.preventDefault(); };
  const onClick = event => { const result = event.target.closest('[data-asset-search-result]'); if (result) controller.select(Number(result.dataset.assetSearchResult)); else if (event.target.closest('[data-asset-search-retry]')) void controller.search(input.value); };
  const onOutside = event => { if (!slot.contains(event.target)) controller.close(); };
  const onFocus = () => { if (normalizeAssetSearch(input.value)) { controller.state.open = true; results.innerHTML = resultHTML(controller.state); input.setAttribute('aria-expanded', 'true'); } };
  input.addEventListener('input', onInput); input.addEventListener('keydown', onKey); input.addEventListener('focus', onFocus); slot.addEventListener('click', onClick); slot.ownerDocument.addEventListener('pointerdown', onOutside);
  return { update({ asset: next = '' } = {}) { if (next !== currentAsset) { currentAsset = next; input.value = ''; void controller.search(''); } }, dispose() { controller.dispose(); input.removeEventListener('input', onInput); input.removeEventListener('keydown', onKey); input.removeEventListener('focus', onFocus); slot.removeEventListener('click', onClick); slot.ownerDocument.removeEventListener('pointerdown', onOutside); } };
}
