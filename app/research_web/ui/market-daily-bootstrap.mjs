import { safeLog } from './core.mjs';

const groups = Object.freeze({
  events: { title: '事件与交易日历', path: '/events/initial-batch', detail: '读取已公告的三地交易安排与官方宏观日程。' },
  scores: { title: '六维研究证据', path: '/market-scores/initial-evidence', detail: '先补上证综指、标普500、恒生指数的真实证据，只有合格维度才给研究分。' },
});
const stateLabels = { preview: '预检', completed: '完成', complete: '完成', ready: '可取得', partial: '部分完成', failed: '来源失败', source_unavailable: '来源不可用', qualified: '合格', raw_only: '仅原值', not_imported: '尚无输入', insufficient_sample: '样本不足', not_admitted: '未准入', run_saved: '研究运行已保存' };
const reasonLabels = { host_factor_evidence_not_admitted: '原值尚未取得六维输入资格', provider_not_in_frozen_profile: '来源不在该维度的冻结名单', normalization_history_insufficient: '历史归一化样本不足', qualified_factor_input_not_imported: '尚无合格的因子原件', current_factor_inputs_not_imported: '尚无当日合格输入', no_qualified_current_axis: '没有通过核验的当日维度', original_missing_or_changed: '原件缺失或已变化', price_sources_unavailable: '本次未取得可核验的日线', closed_price_history_insufficient: '已收盘日线不足', initial_evidence_not_imported: '尚未导入证据' };
const axes = { trend: '趋势', risk: '风险', breadth: '广度', sentiment: '情绪', funds: '资金', valuation: '估值' };
const indices = { SSE: '上证综指', SP500: '标普500', HSI: '恒生指数' };
const escape = value => String(value ?? '').replace(/[&<>"']/g, ch => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' })[ch]);
const human = value => stateLabels[String(value || '').toLowerCase()] || (value ? String(value) : '状态未提供');
const reason = value => reasonLabels[value] || value;
function sourceLink(url) {
  if (typeof url !== 'string') return '';
  try { const u = new URL(url); if (u.protocol === 'https:' && !u.username && !u.password) return ` <a href="${escape(u.href)}" target="_blank" rel="noopener noreferrer">查看来源</a>`; }
  catch { safeLog('market_daily_source_link_invalid', { status: 'rejected' }); }
  return '';
}

function rows(data) {
  if (!Array.isArray(data?.items) || !data.items.length) return '';
  const attempts = Array.isArray(data.research_attempts) ? data.research_attempts : [];
  return `<ul>${data.items.filter(row => row && typeof row === 'object').map(row => {
    const label = indices[row.index_id] || row.label || row.source || row.index_id || '来源未提供';
    const detail = row.axes ? Object.entries(axes).map(([key,name]) => {
      const a = row.axes[key] || {};
      return `${name}：${Number.isFinite(a.value) ? `${a.value.toFixed(2)} ${a.unit === 'percent' ? '%' : a.unit || ''} · ` : ''}${human(a.status)}${Array.isArray(a.reasons) && a.reasons.length ? `（${a.reasons.map(reason).join('、')}）` : ''}`;
    }).join('；') : [human(row.status), Number.isInteger(row.records) ? `${row.records} 条` : '', row.error].filter(Boolean).join(' · ');
    const url = row.url || row.axes?.trend?.source?.url || row.axes?.risk?.source?.url;
    const attempt = attempts.find(item => item?.index_id === row.index_id);
    return `<li><strong>${escape(label)}</strong>${row.as_of ? ` · ${escape(row.as_of)}` : ''} ${escape(detail)}${sourceLink(url)}${attempt ? `<small> · ${escape(human(attempt.status))}${attempt.reason ? `：${escape(reason(attempt.reason))}` : ''}</small>` : ''}</li>`;
  }).join('')}</ul>`;
}

export function createMarketDailyBootstrap({ api, storage, getIdentity = () => String(globalThis.__RWB_USER_ID__ || 'single-user'), onChange = () => {}, makeKey = () => globalThis.crypto.randomUUID() } = {}) {
  if (storage === undefined) {
    try { storage = globalThis.sessionStorage; }
    catch { safeLog('market_daily_session_storage_unavailable', { status: 'failed' }); }
  }
  const blank = () => ({ stage: 'idle', pending: null, preview: null, result: null, key: '' });
  const validKey = key => typeof key === 'string' && /^[A-Za-z0-9_.:-]{8,128}$/.test(key);
  const storageKey = (account, group) => `rwb:${encodeURIComponent(String(account))}:market-daily-pending:${group}`;
  const initial = account => Object.fromEntries(Object.keys(groups).map(group => {
    const state = blank();
    try {
      const key = storage?.getItem(storageKey(account, group));
      if (validKey(key)) Object.assign(state, { key, stage: 'unknown' });
    } catch { safeLog('market_daily_pending_key_read_failed', { status: 'failed' }); }
    return [group, state];
  }));
  let owner = getIdentity();
  let states = initial(owner);
  function syncOwner() {
    const identity = getIdentity();
    if (identity === owner) return;
    for (const state of Object.values(states)) state.pending?.abort();
    states = initial(identity);
    owner = identity;
  }
  const busy = () => Object.values(states).some(state => state.pending);
  function render() {
    syncOwner();
    return `<section class="md-workbench md-initial-data" aria-label="首批真实资料"><h2>首批真实资料</h2><p>预检先核对来源与缺口；确认后才导入。这里不会启用采集日程或正式评分。</p>${Object.entries(groups).map(([id, group]) => {
      const state = states[id], unknown = state.stage === 'unknown', ready = state.stage === 'ready';
      const message = { idle: '尚未预检。', checking: '正在核对实际来源…', ready: '已完成预检；执行时重新核对并登记原件。', importing: '正在执行一次性操作…', unknown: '结果未知，请用同一操作核对，避免重复提交。', interrupted: '操作已中断；保留已完成的结果。可重新预检后明确执行。', done: '本次操作已返回；已导入记录与缺口如下。', failed: '预检失败，未执行导入。', blocked: '无法保存本次操作编号，未发送导入请求。请允许浏览器会话存储后重试。' }[state.stage];
      const data = state.result || state.preview;
      return `<section class="md-initial-group" aria-label="${group.title}"><h3>${group.title}</h3><p>${group.detail}</p><div class="md-inline-form"><button type="button" class="button secondary small" data-market-daily-action="preview" data-market-daily-group="${id}" ${busy() || unknown ? 'disabled' : ''}>预检${group.title}</button><button type="button" class="button small" data-market-daily-action="execute" data-market-daily-group="${id}" ${busy() || !(ready || unknown) ? 'disabled' : ''}>${unknown ? '核对上次操作' : '执行一次性导入'}</button></div><p role="status">${message}</p>${data?.start && data?.end ? `<p>核对范围：${escape(data.start)} 至 ${escape(data.end)}</p>` : ''}${rows(data)}</section>`;
    }).join('')}</section>`;
  }
  async function handleClick(event) {
    const target = event.target?.closest?.('[data-market-daily-action]');
    if (!target) return false;
    const { marketDailyGroup: group, marketDailyAction: action } = target.dataset || {};
    if (!Object.hasOwn(groups, group) || !['preview', 'execute'].includes(action)) return false;
    event.preventDefault(); syncOwner();
    const state = states[group], write = action === 'execute';
    if (busy() || (write ? !['ready','unknown'].includes(state.stage) : state.stage === 'unknown')) return true;
    const token = new AbortController(), account = owner;
    const keySlot = storageKey(account, group);
    if (write) {
      try {
        const key = state.key || makeKey();
        if (!storage || !validKey(key)) throw new Error('pending_key_unavailable');
        storage.setItem(keySlot, key);
        if (storage.getItem(keySlot) !== key) throw new Error('pending_key_unavailable');
        state.key = key;
      } catch {
        if (state.stage !== 'unknown') state.stage = 'blocked';
        safeLog('market_daily_pending_key_write_failed', { status: 'blocked' });
        onChange(); return true;
      }
    }
    state.pending = token;
    state.stage = write ? 'importing' : 'checking';
    if (!write) { state.preview = null; state.result = null; state.key = ''; }
    onChange();
    try {
      const data = await api.request(groups[group].path + (write ? '' : '/preview'), {
        method: 'POST', body: write ? { idempotency_key: state.key } : {}, userAction: true, signal: token.signal,
      });
      if (states[group] !== state || state.pending !== token || getIdentity() !== account) return true;
      if (!Array.isArray(data?.items)) throw new Error('invalid_batch_result');
      if (write) {
        state.result = data;
        state.stage = data.status === 'interrupted' ? 'interrupted' : ['running', 'unknown'].includes(data.status) ? 'unknown' : 'done';
        if (state.stage !== 'unknown') {
          try { if (storage.getItem(keySlot) === state.key) storage.removeItem(keySlot); }
          catch { safeLog('market_daily_pending_key_clear_failed', { status: 'failed' }); }
        }
      }
      else { state.preview = data; state.stage = 'ready'; }
    } catch (error) {
      if (states[group] === state && state.pending === token && getIdentity() === account) {
        state.stage = write ? 'unknown' : 'failed';
        safeLog('market_daily_batch_failed', { group, action, status: error.name === 'AbortError' ? 'interrupted' : 'failed' });
      }
    } finally {
      if (states[group] === state && state.pending === token && getIdentity() === account) { state.pending = null; onChange(); }
    }
    return true;
  }
  function dispose() {
    syncOwner();
    for (const state of Object.values(states)) if (state.pending) {
      state.pending.abort(); state.pending = null;
      state.stage = state.stage === 'importing' ? 'unknown' : 'idle';
    }
  }
  return { render, handleClick, dispose };
}
