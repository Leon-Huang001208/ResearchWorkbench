import { escapeHTML as e } from './markdown.mjs';
import { safeLog } from './core.mjs';
import { renderIntelligenceNavigation } from './intel.mjs';
import { dossierActions, renderDossierMethodGuide } from './dossier-methods.mjs';
export { dossierActions } from './dossier-methods.mjs';

const list = value => Array.isArray(value) ? value : [];
const text = value => value == null ? '' : typeof value === 'object' ? JSON.stringify(value) : String(value);
const kindNames = { opinion: '观点', catalyst: '催化剂', risk: '风险', note: '研究笔记', signal: '信号' };
const stateNames = { open: '待验证', supported: '已获支持', refuted: '已被反证', resolved: '已解除', dismissed: '已排除' };
function coverageLabel(value) {
  if (value === 'evidence_only') return '仅本档案冻结证据';
  if (value?.status === 'frozen_evidence' && value.scope === 'personal') return '当前账户已归档材料';
  if (value === 'not_scanned' || value?.status === 'not_scanned') return '尚未扫描';
  if (Number.isSafeInteger(value?.accepted) && Number.isSafeInteger(value?.evidence_total) && value.accepted >= 0 && value.evidence_total >= value.accepted) {
    const cutoff = typeof value.as_of === 'string' ? `截止时点：${value.as_of}` : '截止时点未确认';
    const eligible = value.eligible === true ? '扫描资格已满足' : value.eligible === false ? '扫描资格不足' : '扫描资格未确认';
    return `已核验 ${value.accepted}/${value.evidence_total} · ${cutoff} · ${eligible}`;
  }
  return typeof value === 'string' && /[\u3400-\u9fff]/.test(value) && !/^[\s]*[\[{]/.test(value) ? value : '覆盖未确认';
}
function sourceLabel(value) {
  return list(Array.isArray(value) ? value : [value]).map(item => {
    if (typeof item === 'string' || typeof item === 'number') return String(item);
    const label = item?.label || item?.name;
    const id = item?.id || item?.source_id;
    return typeof label === 'string' ? `${label}${typeof id === 'string' && id !== label ? `（${id}）` : ''}` : typeof id === 'string' ? id : '';
  }).filter(Boolean).join('、') || '来源待核验';
}
const gapLabels = {
  manual_scan_required: '需先手动扫描', no_frozen_evidence: '尚无已归档证据', capability_not_covered: '本次未覆盖该类数据',
  evidence_unavailable: '证据当前不可用', coverage_incomplete: '数据覆盖不足', source_not_admitted: '来源尚未通过准入',
  rule_not_covered: '暂无适用扫描规则', subject_not_covered: '当前对象暂不适用', structured_data_unavailable: '结构化资料不可用',
  data_time_unknown: '数据时点未确认', publication_time_unknown: '首次公开时间未确认', report_period_unknown: '报告期未确认',
  future_evidence: '资料晚于扫描截止时点', stale_evidence: '资料已过期', security_identity_mismatch: '证券身份不匹配',
  event_provenance_missing: '事件缺少原始出处', announcement_title_missing: '公告标题缺失', watch_evidence_unavailable: '观察项证据不可用',
  watch_window_unknown: '观察窗口未确认', watch_window_invalid: '观察窗口无效', dossier_source_revoked: '来源授权已撤销',
  dossier_evidence_changed: '原件已变化', dossier_evidence_missing: '原件缺失', evidence_projection_incomplete: '证据正文不完整',
  structured_data_invalid: '结构化资料格式异常',
};
function gapLabel(value) {
  const code = typeof value === 'string' && /^[a-z][a-z0-9_]+$/.test(value) ? value : typeof value?.code === 'string' ? value.code : '';
  if (!code) return typeof value === 'string' && !/^[\s]*[\[{]/.test(value) ? value : '资料缺口待核验';
  const capability = typeof value?.capability === 'string' ? value.capability : '';
  const capabilityName = ({ earnings_revision: '盈利预测调整', profit_notice_surprise: '业绩预告预期差', risk_alerts: '风险事件', financials: '财务披露', announcements: '公告' })[capability] || capability;
  return `${gapLabels[code] || '资料缺口待核验'}${capabilityName ? `：${capabilityName}` : ''}（代码：${code}）`;
}
export const dossierDateInput = value => /^\d{4}-\d{2}-\d{2}(?:T.*)?$/.test(value || '') ? value.slice(0, 10) : '';
export function dossierWatchDate(value, original, counterpart) {
  if (!value) return null;
  if (value.includes('T')) return value;
  if (original && dossierDateInput(original) === value) return original;
  const suffix = original?.slice(10) || `T00:00:00${/(Z|[+-]\d{2}:\d{2})$/.exec(counterpart || '')?.[1] || (counterpart ? '' : '+08:00')}`;
  return `${value}${suffix}`;
}
export const dossierQuality = item => typeof item?.quality === 'string' ? item.quality : item?.quality?.status || item?.quality_status || '未核验';
export const dossierHref = id => `#/assets?view=dossiers${id ? `&dossier=${encodeURIComponent(id)}` : ''}`;
export function dossierSessionHref(item) {
  const mode = item.source_mode || item.mode, session = item.source_session_id || item.session_id;
  return ['fingpt', 'claw'].includes(mode) && /^[A-Za-z0-9_-]{1,255}$/.test(session || '') ? `#/${mode}?session=${encodeURIComponent(session)}` : '#/history';
}
export const isDossierRoute = route => route?.page === 'assets' && route.assetView === 'dossiers' || route?.page === 'intel' && route.intelTab === 'signals';
const detailOf = result => result?.dossier || result;
const timelineItem = item => {
  const value = { ...item, ...(item.payload && typeof item.payload === 'object' ? item.payload : {}), revision: item.revision, created_at: item.created_at };
  value.title ||= ({ create: '创建研究档案', patch: '更新档案设置', evidence: '归入原始证据', link: '关联研究成果', scan: '完成证据扫描', handoff: '准备冻结研究草稿', tracking: '更新持续跟踪设置' })[item.kind] || kindNames[value.kind] || '档案更新';
  return value;
};
const trackingReason = value => ({ manual_scan_required: '需先完成手动扫描与资料核验，再开启持续跟踪。', evidence_not_qualified: '当前资料尚未满足持续跟踪要求，请核对证据和扫描缺口。', dossier_archived: '档案已归档，请先恢复后再设置持续跟踪。' })[value] || (typeof value === 'string' && /^[a-z][a-z0-9_]+$/.test(value) ? '持续跟踪尚未就绪，请核对资料与扫描状态。' : value);

// All pending responses are scoped to the current route AND current authenticated account.
export function createDossierController({ api, onChange = () => {}, onNavigate = () => {}, onDraft = async () => {}, getAccount = () => globalThis.__RWB_USER_ID__ || 'local', makeID = () => globalThis.crypto.randomUUID(), logger = safeLog } = {}) {
  const state = { mode: 'dossiers', active: false, id: '', items: [], detail: null, timeline: [], timelineCursor: null, signals: [], coverage: null, missing: [], scanCoverage: null, scanMissing: [], loading: false, detailLoading: false, busy: '', error: '', timelineError: '', message: '', forbidden: false, preview: null, previewError: '', includeArchived: false, nextCursor: null, query: '', signalKind: 'all', forms: {}, form: '' };
  let generation = 0, account = text(getAccount());
  const pending = new Map(), attempts = new Map(), drafts = new Map(), recordWindows = new Map();
  let previewGeneration = 0;
  const changed = () => onChange(state);
  function updateProjection(detail) {
    state.detail = detail;
    state.items = state.items.map(item => item.id === detail.id ? { ...item, title: detail.title, subject: detail.subject, revision: detail.revision, archived: detail.archived, updated_at: detail.updated_at } : item);
  }
  const scope = () => ({ generation, account, id: state.id });
  const current = ticket => state.active && ticket.generation === generation && ticket.account === text(getAccount()) && ticket.account === account && ticket.id === state.id;
  function cancel() { generation++; previewGeneration++; for (const abort of pending.values()) abort.abort(); pending.clear(); state.preview = null; state.previewError = ''; state.active = false; state.loading = false; state.detailLoading = false; state.busy = ''; }
  async function request(name, run) {
    pending.get(name)?.abort(); const abort = new AbortController(); pending.set(name, abort);
    try { return await run({ signal: abort.signal }); }
    finally { if (pending.get(name) === abort) pending.delete(name); }
  }
  function fail(error, ticket) {
    if (!current(ticket) || error?.name === 'AbortError') return;
    if ([401, 403].includes(error.status)) {
      state.forbidden = true; previewGeneration++; pending.get('preview')?.abort();
      state.preview = null; state.previewError = ''; state.detail = null; state.timeline = []; state.items = []; state.signals = []; state.coverage = null; state.missing = []; recordWindows.clear();
    }
    state.error = error.status === 409 ? '档案已有新版本，本次未覆盖。输入已保留，请刷新核对后重新提交。' : error.message || '档案操作失败，输入已保留，请重试。';
    logger('dossier_request_failed', { status: error.status || 0, code: error.code || 'request_failed' });
  }
  function saveForms() { drafts.set(state.id || 'new', structuredClone(state.forms)); }
  async function loadDetail(ticket = scope()) {
    if (!state.id) return;
    state.detailLoading = true; state.timelineError = ''; changed();
    const id = state.id;
    const results = await Promise.allSettled([
      request('detail', options => api.dossier(id, options)),
      request('timeline', options => api.dossierTimeline(id, options)),
    ]);
    if (!current(ticket)) return;
    if (results[0].status === 'fulfilled') {
      const detail = detailOf(results[0].value);
      if (detail?.id !== id) fail(new Error('档案身份与请求不符，已拒绝展示。'), ticket);
      else if (!state.forbidden) updateProjection(detail);
    } else fail(results[0].reason, ticket);
    if (results[1].status === 'fulfilled' && !state.forbidden) { state.timeline = list(results[1].value.items).map(timelineItem); state.timelineCursor = results[1].value.next_cursor || null; }
    else if (results[1].reason?.name !== 'AbortError') { state.timelineError = '观点时间线暂未读取成功，当前判断仍保留。'; logger('dossier_timeline_failed'); }
    state.detailLoading = false; changed();
  }
  async function load({ more = false } = {}) {
    const ticket = scope(); state.loading = true; state.error = ''; state.forbidden = false; changed();
    try {
      if (state.mode === 'signals') {
        const result = await request('signals', options => api.dossierSignals(options));
        if (!current(ticket) || state.forbidden) return;
        state.signals = list(result.items); state.coverage = result.coverage || null; state.missing = list(result.missing);
      } else {
        const result = await request('list', options => api.dossiers({ ...options, includeArchived: state.includeArchived, cursor: more ? state.nextCursor : null }));
        if (!current(ticket) || state.forbidden) return;
        const items = more ? [...state.items, ...list(result.items)] : list(result.items);
        state.items = [...new Map(items.map(item => [item.id, item])).values()]; state.nextCursor = result.next_cursor || null;
      }
    } catch (error) { fail(error, ticket); }
    finally { if (current(ticket)) { state.loading = false; changed(); } }
  }
  async function activate(route) {
    saveForms(); cancel();
    const nextAccount = text(getAccount());
    if (account !== nextAccount) {
      account = nextAccount; drafts.clear(); attempts.clear(); recordWindows.clear(); state.items = []; state.signals = []; state.coverage = null; state.missing = []; state.includeArchived = false;
    }
    state.active = true; state.mode = route.page === 'intel' ? 'signals' : 'dossiers'; state.id = route.dossierId || '';
    Object.assign(state, { detail: null, timeline: [], timelineCursor: null, scanCoverage: null, scanMissing: [], error: '', message: '', preview: null, previewError: '', review: null, forbidden: false, form: '', forms: structuredClone(drafts.get(state.id || 'new') || {}) });
    const ticket = scope(); changed();
    await Promise.all([load(), state.mode === 'dossiers' ? loadDetail(ticket) : Promise.resolve()]);
  }
  // Reuse the exact key and expected revision after a timeout; never replay automatically.
  async function mutate(name, values, run, { close = true, expectedRevision = state.detail?.revision } = {}) {
    if (state.busy || !state.active) return null;
    const ticket = scope(), signature = `${state.id}:${name}:${JSON.stringify(values)}`;
    let attempt = attempts.get(signature);
    if (!attempt) {
      attempt = { ...values, ...(name === 'create' ? {} : { expected_revision: expectedRevision }), idempotency_key: makeID() };
      attempts.set(signature, attempt);
    }
    state.busy = name; state.error = ''; state.message = ''; changed();
    try {
      const result = await request('mutation', options => run(attempt, options));
      if (!current(ticket)) return null;
      attempts.delete(signature);
      if (close) { delete state.forms[name]; state.form = ''; state.review = null; saveForms(); }
      const detail = detailOf(result);
      if (name === 'create' && detail?.id) { state.message = '档案已创建。'; onNavigate(dossierHref(detail.id)); }
      else if (detail?.id === state.id && Number.isInteger(detail.revision)) { updateProjection({ ...detail, ...(result.tracking ? { tracking: result.tracking } : {}) }); }
      state.message ||= '已保存为档案新版本。'; logger('dossier_mutation_completed', { method: name });
      return result;
    } catch (error) {
      if (current(ticket) && error.status === 409) attempts.delete(signature);
      fail(error, ticket); return null;
    } finally { if (current(ticket)) { state.busy = ''; changed(); } }
  }
  async function submit(name, values, { expectedRevision = state.detail?.revision } = {}) {
    state.forms[name] = { ...values }; saveForms();
    const id = state.id;
    let result;
    if (name === 'create') result = await mutate(name, { title: values.title.trim(), subject: { kind: values.kind, key: values.key.trim(), label: values.label.trim() } }, (body, options) => api.createDossier(body, options));
    else if (name === 'record') {
      const body = { kind: values.kind, title: values.title.trim(), body: values.body.trim(), state: values.state || 'open', reason: values.reason.trim(), evidence_ids: (values.evidence_ids || '').split(',').map(value => value.trim()).filter(Boolean) };
      if (values.record_id) body.record_id = values.record_id;
      const original = recordWindows.get(`${id}:${values.record_id}`) || {};
      body.watch_from = dossierWatchDate(values.watch_from, original.watch_from, original.watch_until);
      body.watch_until = dossierWatchDate(values.watch_until, original.watch_until, original.watch_from);
      result = await mutate(name, body, (body, options) => api.addDossierRecord(id, body, options));
    } else if (name === 'evidence') result = await mutate(name, { source_session_id: values.source_session_id.trim(), reference: { type: values.type, id: values.reference_id.trim() }, ...(values.locator ? { locator: values.locator.trim() } : {}) }, (body, options) => api.addDossierEvidence(id, body, options), { expectedRevision });
    else if (name === 'link') result = await mutate(name, { source_session_id: values.source_session_id.trim(), type: values.type, ...(values.reference_id?.trim() ? { reference_id: values.reference_id.trim() } : {}) }, (body, options) => api.addDossierLink(id, body, options), { expectedRevision });
    if (result && name !== 'create' && state.active && state.id === id) await loadDetail();
    return result;
  }
  async function evidence(id, kind = 'evidence') {
    const ticket = scope(), previewTicket = ++previewGeneration; state.preview = null; state.previewError = ''; state.busy = 'preview'; changed();
    try {
      const result = await request('preview', options => kind === 'link' ? api.dossierLink(state.id, id, options) : api.dossierEvidence(state.id, id, options));
      if (current(ticket) && !state.forbidden && previewTicket === previewGeneration) state.preview = kind === 'link' ? { ...result, state: 'available', ...(result.content === null ? { projection: 'binary_source' } : {}) } : result;
    }
    catch (error) { if (current(ticket) && error.name !== 'AbortError') { if ([401, 403].includes(error.status)) fail(error, ticket); else state.previewError = error.message || '证据当前不可读取，可能已撤权、缺失或内容变化。'; logger('dossier_evidence_failed', { status: error.status || 0 }); } }
    finally { if (current(ticket)) { state.busy = ''; changed(); } }
  }
  async function prepare(values) {
    const ticket = scope(), expectedRevision = state.detail?.revision;
    const result = await mutate('handoff', values, (body, options) => api.dossierHandoff(state.id, body, options), { close: false });
    if (!result || !current(ticket)) return;
    if (result.auto_send !== false || result.mode !== values.mode || typeof result.prompt !== 'string' || !/^[a-f0-9]{64}$/i.test(result.context?.sha256 || '') || !/^[a-f0-9]{32}$/.test(result.context?.handoff_id || '') || result.context.dossier_id !== state.id || result.context.revision !== expectedRevision) {
      state.error = '冻结研究上下文不完整，未准备草稿。'; changed(); return;
    }
    if (Number.isInteger(result.dossier_revision) && result.dossier_revision > state.detail.revision) updateProjection({ ...state.detail, revision: result.dossier_revision });
    try { await onDraft(result); }
    catch (error) { fail(error, ticket); changed(); }
  }
  async function handle(event) {
    if (!event.target?.closest?.('[data-dossier-workspace]')) return false;
    const form = event.target.closest('[data-dossier-form]');
    if (event.type === 'input' || event.type === 'change') {
      if (form) { state.forms[form.dataset.dossierForm] = Object.fromEntries(new FormData(form)); state.review = null; saveForms(); if (form.dataset.dossierForm === 'handoff' && event.type === 'change') changed(); return true; }
      if (event.target.matches('[data-dossier-filter]')) { state[event.target.dataset.dossierFilter] = event.target.type === 'checkbox' ? event.target.checked : event.target.value; if (event.target.dataset.dossierFilter === 'includeArchived') await load(); else changed(); return true; }
      return false;
    }
    if (event.type === 'submit' && form) {
      event.preventDefault(); const name = form.dataset.dossierForm, values = Object.fromEntries(new FormData(form));
      if (['evidence', 'link'].includes(name)) { state.forms[name] = values; saveForms(); state.review = { name, values, revision: state.detail?.revision }; changed(); }
      else await submit(name, values);
      return true;
    }
    if (event.type !== 'click') return false;
    const action = event.target.closest('[data-dossier-action]'); if (!action) return false;
    event.preventDefault(); const name = action.dataset.dossierAction;
    if (name === 'section') {
      const workspace = action.closest('[data-dossier-workspace]');
      const section = workspace.querySelector(`#dossier-${action.dataset.section}`);
      const scroller = workspace.closest('#main');
      if (section && scroller) scroller.scrollTop += section.getBoundingClientRect().top - scroller.getBoundingClientRect().top;
      section?.querySelector('h2')?.focus({ preventScroll: true });
    }
    else if (name === 'refresh') { await Promise.all([load(), state.mode === 'dossiers' ? loadDetail() : Promise.resolve()]); }
    else if (name === 'more') await load({ more: true });
    else if (name === 'timeline-more') {
      if (!state.timelineCursor || state.busy) return true;
      const ticket = scope(); state.busy = 'timeline'; changed();
      try { const result = await request('timeline', options => api.dossierTimeline(state.id, { ...options, cursor: state.timelineCursor })); if (current(ticket) && !state.forbidden) { state.timeline.push(...list(result.items).map(timelineItem)); state.timelineCursor = result.next_cursor || null; } }
      catch (error) { fail(error, ticket); }
      finally { if (current(ticket)) { state.busy = ''; changed(); } }
    }
    else if (name === 'form') { state.form = state.form === action.dataset.form ? '' : action.dataset.form; state.review = null; changed(); }
    else if (name === 'edit-import') { state.review = null; changed(); }
    else if (name === 'confirm-import' && state.review) await submit(state.review.name, state.review.values, { expectedRevision: state.review.revision });
    else if (name === 'revise') { const record = list(state.detail?.records).find(item => (item.record_id || item.id) === action.dataset.id); if (record) { recordWindows.set(`${state.id}:${record.record_id || record.id}`, { watch_from: record.watch_from, watch_until: record.watch_until }); state.forms.record = { ...record, record_id: record.record_id || record.id, evidence_ids: list(record.evidence_ids).join(','), reason: '' }; state.form = 'record'; saveForms(); changed(); } }
    else if (name === 'evidence') await evidence(action.dataset.id);
    else if (name === 'link-preview') await evidence(action.dataset.id, 'link');
    else if (name === 'close-preview') { state.preview = null; state.previewError = ''; changed(); }
    else if (name === 'handoff') await prepare({ mode: action.dataset.mode, action: state.forms.handoff?.action || 'update_view' });
    else if (name === 'archive') await mutate('archive', { archived: !state.detail.archived }, (body, options) => api.updateDossier(state.id, body, options));
    else if (name === 'scan') { const result = await mutate('scan', {}, (body, options) => api.scanDossier(state.id, body, options), { close: false }); if (result && state.active) { state.scanCoverage = result.coverage || null; state.scanMissing = list(result.missing); state.message = '手动扫描已完成，请核对信号的证据和数据覆盖。'; await loadDetail(); } }
    else if (name === 'tracking') await mutate('tracking', { enabled: state.detail?.tracking?.enabled !== true }, (body, options) => api.setDossierTracking(state.id, body, options), { close: false });
    return true;
  }
  return { state, activate, cancel, load, loadDetail, submit, mutate, evidence, prepare, handle };
}

const badge = (value, label = value) => `<span class="badge">${e(label || '待核验')}</span>`;
const empty = message => `<p class="dossier-empty">${e(message)}</p>`;
const paragraph = value => `<p class="dossier-body">${e(text(value))}</p>`;
const button = (label, action, attrs = '', disabled = false) => `<button type="button" class="button small" data-dossier-action="${action}"${attrs ? ` ${attrs}` : ''}${disabled ? ' disabled' : ''}>${label}</button>`;
const options = (items, value) => items.map(([key, label]) => `<option value="${e(key)}" ${key === value ? 'selected' : ''}>${e(label)}</option>`).join('');
const field = (name, label, values, { required = false, type = 'text', placeholder = '', max = 500 } = {}) => `<label>${label}<input id="dossier-field-${name}" name="${name}" type="${type}" value="${e(type === 'date' ? dossierDateInput(values[name]) : values[name] || '')}" ${required ? 'required' : ''} maxlength="${max}" placeholder="${e(placeholder)}"></label>`;
const select = (name, label, items, value) => `<label>${label}<select id="dossier-field-${name}" name="${name}">${options(items, value)}</select></label>`;
const textarea = (name, label, values, required = true) => `<label class="dossier-wide">${label}<textarea id="dossier-field-${name}" name="${name}" rows="4" maxlength="${name === 'reason' ? 2000 : 20000}" ${required ? 'required' : ''}>${e(values[name] || '')}</textarea></label>`;
function editForm(s) {
  const name = s.form; if (!name) return '';
  if (s.review?.name === name) {
    const review = s.review;
    return `<section class="dossier-editor" aria-label="归档预览"><h3>归档预览</h3><p>归入档案：${e(s.detail?.title)} · 当前预览版本 ${e(review.revision)}</p><p>来源会话：${e(review.values.source_session_id)}</p><p>类型／引用：${e(review.values.type)} · ${e(review.values.reference_id || '由 Host 解析当前原始报告或会话')}</p>${paragraph(review.values.locator || '')}<p class="muted small">确认后，Host 会重新核验来源、权限、原始版本与质量状态；此预览尚未写入档案。</p><div class="button-row">${button('确认写入新版本', 'confirm-import', '', Boolean(s.busy))}${button('返回编辑', 'edit-import', '', Boolean(s.busy))}</div></section>`;
  }
  const v = s.forms[name] || {}; let fields = '', heading = '';
  if (name === 'create') {
    heading = '新建长期研究档案'; fields = field('title', '档案名称', v, { required: true, max: 200 }) + select('kind', '研究对象', [['company', '公司'], ['industry', '行业'], ['theme', '主题']], v.kind || 'company') + field('key', '规范身份／分类代码', v, { required: true, max: 120, placeholder: '公司：600519.SH；主题使用独立标识' }) + field('label', '对象名称', v, { required: true, max: 160 });
  } else if (name === 'record') {
    heading = v.record_id ? '追加记录修订' : '新增观点、催化剂或风险'; fields = `<input type="hidden" name="record_id" value="${e(v.record_id || '')}">` + (v.record_id ? `<input type="hidden" name="kind" value="${e(v.kind)}"><p class="small">记录类型：${e(kindNames[v.kind] || v.kind)}（修订保留原类型）</p>` : select('kind', '记录类型', Object.entries(kindNames).filter(([key]) => key !== 'signal'), v.kind || 'opinion')) + select('state', '验证状态', Object.entries(stateNames), v.state || 'open') + field('title', '标题', v, { required: true, max: 200 }) + field('evidence_ids', '证据 ID（逗号分隔）', v, { max: 3400 }) + textarea('body', '判断与待验证假设', v) + textarea('reason', '本次记录／修订原因', v) + field('watch_from', '观察开始', v, { type: 'date' }) + field('watch_until', '观察结束', v, { type: 'date' });
  } else if (name === 'evidence' || name === 'link') {
    heading = name === 'evidence' ? '从原会话归入证据' : '关联已有研究成果'; fields = field('source_session_id', '来源会话 ID', v, { required: true }) + select('type', '材料类型', name === 'evidence' ? [['dataset', '数据快照'], ['file', '文件'], ['source', '网页来源']] : [['report', '报告'], ['file', '计算底稿／附件'], ['session', '研究会话']], v.type || (name === 'evidence' ? 'dataset' : 'report')) + field('reference_id', '来源 ID／会话内文件路径', v, { required: name === 'evidence' || v.type === 'file', max: 500, placeholder: name === 'link' ? '报告和会话可留空；文件填写 inputs/ 或 outputs/ 内路径' : '' }) + (name === 'evidence' ? field('locator', '引用位置（可选）', v, { max: 2000 }) : '');
  } else return '';
  return `<form class="dossier-editor" data-dossier-form="${name}"><h3>${heading}</h3><fieldset ${s.busy ? 'disabled' : ''}><div class="dossier-form-grid">${fields}</div><div class="button-row"><button class="button primary" type="submit">${s.busy ? '保存中…' : ['evidence', 'link'].includes(name) ? '预览归档' : '保存新版本'}</button>${button('收起（保留输入）', 'form', `data-form="${name}"`)}</div></fieldset><p class="muted small">来源身份、正文 hash 和质量状态由服务端核验。修订保留原版本。</p></form>`;
}
function recordRows(records, busy) {
  return list(records).map(record => `<article class="dossier-record"><header><h3>${e(record.title || kindNames[record.kind] || '研究记录')}</h3>${badge(record.state, stateNames[record.state])}</header>${paragraph(record.body)}<p class="muted small">${e(record.updated_at || record.created_at || '')} · 修订 ${e(record.revision || record.version || 1)}${record.watch_until ? ` · 观察至 ${e(record.watch_until)}` : ''}</p>${record.reason ? paragraph(`修订依据：${record.reason}`) : ''}<p class="small">证据：${list(record.evidence_ids).map(id => button(e(id), 'evidence', `data-id="${e(id)}"`, busy)).join(' ') || '尚未关联证据'}</p>${button(record.kind === 'signal' ? '核验／处置信号' : '修订记录', 'revise', `data-id="${e(record.record_id || record.id)}"`, busy)}</article>`).join('');
}
function renderDetail(s) {
  const d = s.detail;
  if (!d) return empty(s.detailLoading ? '正在读取档案与历史版本…' : s.id ? '档案暂不可读取，请核对权限或刷新。' : '选择一份档案，查看跨会话积累的判断与证据。');
  const busy = Boolean(s.busy) || d.archived, records = list(d.records);
  const section = (id, title, content) => `<section class="dossier-section" id="dossier-${id}" aria-labelledby="dossier-${id}-title"><h2 id="dossier-${id}-title" tabindex="-1">${title}</h2>${content}</section>`;
  return `<header class="dossier-detail-heading"><div><span class="eyebrow">${e(d.subject?.label || '')} · ${e(d.subject?.key || '')}</span><h1>${e(d.title)}</h1><p class="muted small">档案版本 ${e(d.revision)} · ${e(d.updated_at || '更新时间未知')} ${d.archived ? '· 已归档' : ''}</p></div>${button(d.archived ? '恢复档案' : '归档', 'archive', '', Boolean(s.busy))}</header>
  <div class="button-row">${button('新增研究记录', 'form', 'data-form="record"', busy)}${button('归入证据', 'form', 'data-form="evidence"', busy)}${button('关联成果', 'form', 'data-form="link"', busy)}${button('手动扫描', 'scan', '', busy)}${button(d.tracking?.enabled === true ? '关闭持续跟踪' : '开启持续跟踪', 'tracking', '', busy || d.tracking?.eligible !== true && d.tracking?.enabled !== true)}</div>
  <p class="muted small">${e(trackingReason(d.tracking?.reason) || '持续跟踪默认关闭，单次闭环通过后才可开启。浏览和准备草稿不会启动模型。')}</p>
  ${s.scanCoverage ? paragraph(`本次扫描覆盖：${coverageLabel(s.scanCoverage)}`) : ''}${s.scanMissing.length ? `<p class="notice warning">本次扫描缺失：${e(s.scanMissing.map(gapLabel).join('、'))}</p>` : ''}
  ${editForm(s)}<nav class="dossier-anchor-nav" aria-label="档案内容">${[['current', '当前判断'], ['timeline', '观点时间线'], ['evidence', '证据'], ['risks', '催化剂与风险'], ['results', '研究成果']].map(([id, title]) => button(title, 'section', `data-section="${id}"`)).join('')}</nav>
  ${section('current', '当前判断', recordRows(records.filter(item => ['opinion', 'note'].includes(item.kind)), busy) || empty('尚未记录观点。新增判断时请关联证据和下一项验证。'))}
  ${section('timeline', '观点时间线', (s.timelineError ? `<p class="notice warning">${e(s.timelineError)}</p>` : list(s.timeline).map(item => `<article class="dossier-timeline-item"><p class="muted small">${e(item.created_at || item.updated_at || '')} · 版本 ${e(item.revision || item.version || '')}</p><strong>${e(item.title || item.kind || '档案更新')}</strong>${paragraph(item.body || item.reason || item.action || '')}</article>`).join('') || empty('尚无历史修订。')) + (s.timelineCursor ? button('加载更早版本', 'timeline-more', '', Boolean(s.busy)) : ''))}
  ${section('evidence', '证据', list(d.evidence).map(item => `<article class="dossier-evidence"><strong>${e(item.title || item.reference?.id || item.id)}</strong><p class="small">来源：${e(text(item.source || item.provider || item.source_session_id || '待核验'))} · 公开时间：${e(item.published_at || item.first_public_at || '未知，不具历史可知资格')} · 取得时间：${e(item.retrieved_at || item.acquired_at || '未知')}</p><p class="small mono">${e(item.sha256 || item.content_hash || 'hash 待核验')}</p>${paragraph(item.locator || '')}${item.state && item.state !== 'available' ? `<p class="notice warning">${e(({revoked:'来源已撤权',changed:'原始材料已变化',missing:'原始材料缺失',unavailable:'原始材料不可用'})[item.state] || item.state)}${item.error_code ? ` · ${e(item.error_code)}` : ''}：需要核验原材料状态。</p>` : ''}${button('重新鉴权并读取', 'evidence', `data-id="${e(item.id)}"`, Boolean(s.busy))}</article>`).join('') || empty('没有证据引用。可从已存在的会话数据快照、来源或文件归入。'))}
  ${section('risks', '催化剂与风险', recordRows(records.filter(item => ['catalyst', 'risk', 'signal'].includes(item.kind)), busy) || empty('尚无已记录催化剂或风险；不代表没有风险。'))}
  ${section('results', '研究成果', list(d.links).map(item => `<article class="dossier-result"><strong>${e(item.title || item.reference?.id || item.id || '研究成果')}</strong><p class="small">${e(item.type || item.kind || item.reference?.type || '')} · 质量状态：${e(dossierQuality(item))}</p>${paragraph(item.source_session_id || item.session_id || '')}${item.state !== 'available' ? `<p class="notice warning">原成果${e(({changed:'已变化',missing:'缺失',revoked:'来源已撤权',unavailable:'不可用'})[item.state] || '待核验')} · ${e(item.error_code || '请刷新核验')}；未开放旧原件。</p>` : ''}${button('受控原件预览', 'link-preview', `data-id="${e(item.id)}"`, item.state !== 'available' || Boolean(s.busy))}${item.state === 'available' ? `<a class="button small" href="${e(dossierSessionHref(item))}">${dossierSessionHref(item) === '#/history' ? '到历史记录核对来源' : '查看来源会话（当前记录）'}</a>` : ''}</article>`).join('') || empty('没有关联成果。报告质量沿用原始 passed／incomplete／invalid 状态。'))}
  <section class="dossier-section"><h2>继续研究</h2><form data-dossier-form="handoff">${select('action', '研究方法', dossierActions, s.forms.handoff?.action || 'update_view')}</form>${renderDossierMethodGuide({action:s.forms.handoff?.action || 'update_view'})}<div class="button-row">${button('准备 FinGPT 草稿', 'handoff', 'data-mode="fingpt"', busy)}${button('准备 Claw 草稿', 'handoff', 'data-mode="claw"', busy)}</div><p class="muted small">冻结当前档案版本和可读取证据，进入原研究输入框；核对后由你发送。</p></section>`;
}
export function filterDossierSignals(items, query = '', kind = 'all') {
  const q = query.trim().toLocaleLowerCase();
  return list(items).filter(item => (kind === 'all' || (item.signal_type || item.kind) === kind) && (!q || `${item.title || ''} ${item.body || ''} ${item.subject?.label || ''} ${item.source || ''}`.toLocaleLowerCase().includes(q)));
}
function renderSignals(s) {
  const items = filterDossierSignals(s.signals, s.query, s.signalKind);
  return `${renderIntelligenceNavigation('signals')}<header class="page-header"><div><span class="eyebrow">RESEARCH INTELLIGENCE</span><h1>机会与风险</h1><p class="muted">关注对象的证据变化与待验证信号；扫描不会自动改写观点。</p></div></header><div class="dossier-signal-filters"><label>关键词<input id="dossier-signal-query" type="search" data-dossier-filter="query" value="${e(s.query)}"></label><label>信号类型<select id="dossier-signal-kind" data-dossier-filter="signalKind">${options([['all', '全部'], ['review', '待研究'], ['signal', '研究线索'], ['opportunity', '机会'], ['risk', '风险'], ['catalyst', '催化剂']], s.signalKind)}</select></label><a class="button" href="${dossierHref()}">管理研究档案与手动扫描</a></div>${s.coverage ? paragraph(`数据覆盖：${coverageLabel(s.coverage)}`) : '<p class="notice warning">当前未提供完整数据覆盖，不能把没有信号解释为没有机会或风险。</p>'}${s.missing.length ? `<p class="notice warning">缺失：${e(s.missing.map(gapLabel).join('、'))}</p>` : ''}${items.map(item => `<article class="dossier-record"><header><h2>${e(item.title || '待核验信号')}</h2>${badge(item.kind, ({ review: '待研究', signal: '研究线索', opportunity: '机会', risk: '风险', catalyst: '催化剂' })[item.signal_type || item.kind])}${badge(item.state, stateNames[item.state])}</header>${paragraph(item.body || item.reason)}<p class="small muted">时点：${e(item.as_of || item.created_at || '未知')} · 来源：${e(sourceLabel(item.source))} · 覆盖：${e(coverageLabel(item.coverage))}</p>${item.stale ? '<p class="notice warning">数据已过期，请更新并核对后使用。</p>' : ''}${list(item.missing).length ? paragraph(`待核验：${item.missing.map(gapLabel).join('、')}`) : ''}<p class="small">证据引用：${e(list(item.evidence_ids).join('、') || '暂无可核验证据')}</p><a class="button" href="${dossierHref(item.dossier_id)}">查看证据与原观点</a></article>`).join('') || empty(s.loading ? '正在读取信号…' : '当前筛选下没有已记录信号。请先核对扫描是否完成以及数据覆盖。')}`;
}
function renderDossierPreview(s) {
  if (s.forbidden || !s.active || (!s.preview && !s.previewError)) return '';
  let content;
  if (s.previewError) content = `<p class="notice danger" role="alert">${e(s.previewError)}</p>`;
  else if (s.preview.state !== 'available') content = '<p class="notice warning">当前原始证据状态未获确认，未展示正文。</p>';
  else if (s.preview.link?.type === 'session') content = '<p class="muted">这是原会话关联，未提供固定正文；可到来源会话核对当前记录。</p>';
  else if (s.preview.projection === 'binary_source') content = '<p class="notice warning">原始材料为二进制文件，此处没有文本正文；请到原会话核对文件。</p>';
  else {
    const previewText = typeof s.preview.content === 'string' ? s.preview.content : '';
    content = `<pre>${e(previewText.slice(0, 30000))}</pre>${s.preview.truncated === true || previewText.length > 30000 ? '<p class="notice warning">此处仅为部分正文预览；服务端或页面已截断，不代表完整材料。</p>' : ''}`;
  }
  return `<aside class="dossier-preview" aria-label="证据读取结果"><div class="section-heading"><h2>${s.preview?.link ? '冻结研究成果' : '原始证据'}</h2>${button('关闭证据', 'close-preview')}</div>${s.preview?.link ? `<p class="small">原 Host 质量状态：${e(dossierQuality(s.preview.link))}</p>` : ''}${content}</aside>`;
}
export function renderDossiers(s) {
  if (!s.active) return '<div class="dossier-workspace" role="status">正在打开研究档案…</div>';
  return `<div class="dossier-workspace" data-dossier-workspace aria-busy="${Boolean(s.loading || s.detailLoading || s.busy)}"><div class="dossier-status" aria-live="polite">${s.error ? `<p class="notice danger" role="alert">${e(s.error)}</p>` : ''}${s.message ? `<p class="notice success" role="status">${e(s.message)}</p>` : ''}${s.loading || s.detailLoading ? '<p role="status">正在读取；已有内容和输入仍保留。</p>' : ''}${s.busy ? '<p role="status">正在处理，请等待结果；不会自动重发。</p>' : ''}</div><div class="button-row">${button('刷新档案与状态', 'refresh', '', Boolean(s.busy || s.loading))}</div>${s.forbidden ? empty('当前账户没有权限读取这部分档案，请重新登录或核对来源授权。') : s.mode === 'signals' ? renderSignals(s) : `<nav class="workbench-tabs" aria-label="资产观察视图"><a href="#/assets">行情与基本面</a><a href="#/assets/funds">基金数据</a><a href="${dossierHref()}" class="active" aria-current="page">研究档案</a></nav><div class="dossier-layout"><aside class="dossier-list" aria-label="长期研究档案"><h2>研究档案</h2>${button('新建档案', 'form', 'data-form="create"', Boolean(s.busy))}<label class="dossier-archived"><input type="checkbox" data-dossier-filter="includeArchived" ${s.includeArchived ? 'checked' : ''}>包含已归档</label>${s.items.map(item => `<a class="dossier-list-item ${item.id === s.id ? 'active' : ''}" href="${dossierHref(item.id)}" ${item.id === s.id ? 'aria-current="page"' : ''}><strong>${e(item.title)}</strong><span>${e(item.subject?.label || '')} · v${e(item.revision || 1)}${item.archived ? ' · 已归档' : ''}</span></a>`).join('') || empty(s.loading ? '读取中…' : '尚无研究档案，先创建研究对象。')}${s.nextCursor ? button('加载更多档案', 'more', '', s.loading) : ''}</aside><div class="dossier-detail" role="region" aria-label="档案详情">${s.form === 'create' ? editForm(s) : renderDetail(s)}</div></div>`}${renderDossierPreview(s)}</div>`;
}
