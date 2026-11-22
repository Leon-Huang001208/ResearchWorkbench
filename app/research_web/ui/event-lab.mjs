import { escapeHTML as e } from './markdown.mjs';
import { safeLog } from './core.mjs';
import { inputControls, validationControls, scoreControls, collectionControls, manualEventControls, eventMergeControls, eventDetailControls } from './event-lab-controls.mjs';

const views = { timeline: ['事件时间线', '#/intel/timeline'], studies: ['事件与日历研究', '#/simulation/events'], scores: ['六维评分', '#/simulation/scores'] };
const markets = { CN: 'A股', US: '美股', HK: '港股' };
const familyLabels = { holiday: '节假日', weekday: '星期效应', month_end: '月末', month_start: '月初', quarter_end: '季末', quarter_start: '季初', year_end: '年末', year_start: '年初', macro: '宏观', policy: '政策', geopolitics: '地缘冲突', war: '战争', sports: '赛事', disaster: '灾害', unexpected: '突发事件', other: '其他重大事件' };
const labels = { candidate: '待确认', confirmed: '已确认', rejected: '已拒绝', announced: '已公布日程', scheduled: '已公布日程', occurred: '已发生', ongoing: '持续中', postponed: '已延期', cancelled: '已取消', scenario: '风险情景', DATA_INELIGIBLE: '数据不具备资格', INSUFFICIENT_SAMPLE: '样本不足', VALIDATION_FAILED: '验证未通过', VALIDATED: '冻结版本验证通过' };
const items = data => Array.isArray(data?.items) ? data.items : [];
const payload = record => record?.payload || record || {};
const title = record => payload(record).title || record?.id || '未命名';
const shown = value => value === null || value === undefined ? '待验证' : String(value);
const options = (values, selected) => Object.entries(values).map(([value, label]) => `<option value="${e(value)}" ${value === selected ? 'selected' : ''}>${e(label)}</option>`).join('');
const ruleLabel = rule => {
  if (rule === 'holiday_episode') return '完整休市段';
  if (rule === 'reopening_gap') return '复市跳空';
  if (rule === 'event_during') return '事件期间';
  const weekday = /^weekday_(\d)_(\d+)$/.exec(rule);
  if (weekday) return `星期${'一二三四五'[Number(weekday[1])]} · ${weekday[2]}交易日窗口`;
  const match = /^(holiday|event|month|quarter|year)_(pre|post|start|end)_(\d+)$/.exec(rule);
  return match ? `${({ holiday: '节假日', event: '事件', month: '月', quarter: '季', year: '年' })[match[1]]}${({ pre: '前', post: '后', start: '初', end: '末' })[match[2]]}${match[3]}交易日窗口` : rule;
};
const percent = value => typeof value === 'number' && Number.isFinite(value) ? `${(100 * value).toFixed(2)}%` : '待验证';
const formKinds = ['event-filters', 'event-study', 'event-import', 'event-calendar', 'event-native', 'event-links', 'event-source', 'event-schedule', 'event-seal', 'event-evaluate', 'event-score', 'event-create', 'event-merge', 'event-revise', 'event-split'];
const formKind = form => formKinds.find(name => form?.hasAttribute?.(`data-${name}`));
const formDraftKey = form => `${formKind(form) || ''}${form?.dataset?.draftKey ? `:${form.dataset.draftKey}` : ''}`;
const eventFields = event => Object.fromEntries(['title', 'category', 'occurrence_start', 'occurrence_end', 'date_precision', 'markets', 'lifecycle', 'description'].map(name => [name, event[name]]));

function renderDetail(record, kind = '', state = {}) {
  const value = payload(record);
  const summary = value.summary;
  const validation = value.validation;
  const windows = summary && typeof summary === 'object' ? `<div class="table-scroll"><table><thead><tr><th>窗口</th><th>样本</th><th>均值</th><th>中位数</th><th>下跌次数</th></tr></thead><tbody>${Object.entries(summary).map(([rule, stat]) => `<tr><td>${e(ruleLabel(rule))}</td><td>${e(stat.n)}</td><td>${e(percent(stat.mean))}</td><td>${e(percent(stat.median))}</td><td>${e(stat.down)}</td></tr>`).join('')}</tbody></table></div>` : '';
  const history = kind === 'study_history' && Array.isArray(record.items) ? `<ul>${record.items.map(run => `<li><button class="text-button" data-study-run="${e(run.id)}">${e(payload(run).created_at || payload(run).status || '已保存研究结果')}</button></li>`).join('')}</ul>` : '';
  const eventDetail = ['event_detail', 'event_historical'].includes(kind) ? eventDetailControls(record, state, kind === 'event_historical') : '';
  const versions = kind === 'event_versions' ? `<h3>事件版本历史</h3><p>历史版本只读；打开后显示该次保存的事实与来源状态。</p><button class="text-button" data-event-latest="${e(state.detailEventId)}">读取当前版本</button><ul>${items(record).map(row => `<li><button class="text-button" data-event-id="${e(state.detailEventId)}" data-event-version="${e(row.revision)}">版本${e(row.revision)} · ${e(title(row))}</button>${payload(row).revision_reason ? ` · ${e(payload(row).revision_reason)}` : ''}</li>`).join('')}</ul>` : '';
  const children = kind === 'event_split' ? `<p>拆分完成；子事件仍须确认与冻结。</p><ul>${(record.children || []).map(row => `<li><button class="text-button" data-event-detail="${e(row.id)}">${e(title(row))} · 版本${e(row.revision)}</button></li>`).join('')}</ul>` : '';
  const exports = value.study_id && /^[a-f0-9]{32}$/.test(record.id || '') ? `<p><a href="/api/research/event-studies/runs/${e(record.id)}/export?format=json">导出可复算JSON</a> · <a href="/api/research/event-studies/runs/${e(record.id)}/export?format=csv">导出窗口CSV</a></p>` : '';
  const next = value.state === 'completed' && value.checkpoint && (value.checkpoint.next_page !== null && value.checkpoint.next_page !== undefined || value.checkpoint.next_offset !== null && value.checkpoint.next_offset !== undefined) ? `<button class="button secondary" data-source-next="${e(record.id)}">继续本来源下一批</button>` : '';
  const calendar = ({ verified_sessions: '已核验的交易时段', observed_price_dates_only: '仅已有行情日期，完整交易日历待核验', provider_declared_days_standard_hours_unverified: '已登记来源日期，特殊时段与历史公告待核验' })[value.calendar_basis] || '按资料来源合同计算';
  return `<section class="market-panel"><button class="text-button" data-event-action="close">关闭详情</button><h2>${e(value.spec?.title || value.title || value.label || '研究证据与结果')}</h2>${validation ? `<p>${e(labels[validation.status] || validation.status || '待验证')}</p>` : ''}${value.calendar_basis ? `<p>日历口径：${e(calendar)}</p>` : ''}${eventDetail}${versions}${children}${windows}${history}${exports}${next}<details><summary>来源、版本、计算与缺口</summary><pre>${e(JSON.stringify(record, null, 2))}</pre></details></section>`;
}

export function renderEventLab(state) {
  const view = state.view || 'timeline';
  const filters = state.filters || {};
  const rows = items(state.data);
  const draft = state.studyDraft || {};
  const family = draft.family || 'holiday';
  const familyRules = state.families?.[family] || [];
  const nav = `<nav class="intel-tabs" aria-label="事件研究视图">${Object.entries(views).map(([key, [label, href]]) => `<a href="${href}" ${key === view ? 'aria-current="page"' : ''}>${label}</a>`).join('')}</nav>`;
  const notice = `<p class="muted">候选可浏览，确认并冻结后才能正式研究。历史数据覆盖、可成交回测、评分有效性分别验证。采集计划默认关闭。</p>`;
  let content;
  if (view === 'timeline') {
    content = `<form data-event-filters class="intel-filters"><label>时间范围<select name="period">${options({ future: '未来12个月', history: '历史（1990年起）', scenarios: '风险情景' }, filters.period || 'future')}</select></label><label>市场<select name="market">${options({ '': '全部市场', ...markets }, filters.market || '')}</select></label><label>类别<select name="category">${options({ '': '全部类别', macro: '宏观', policy: '政策', geopolitics: '地缘冲突', war: '战争', sports: '赛事', unexpected: '突发事件', calendar: '日历效应' }, filters.category || '')}</select></label><label>开始日期<input name="start" type="date" min="1990-01-01" value="${e(filters.start || '')}"></label><label>结束日期<input name="end" type="date" value="${e(filters.end || '')}"></label><label>搜索<input name="q" maxlength="120" value="${e(filters.q || '')}"></label><button class="button" ${state.loading ? 'disabled' : ''}>筛选</button></form>
      <div class="intel-actions"><button class="button" data-event-action="confirm" ${state.busy || !state.selected?.length ? 'disabled' : ''}>确认所选</button><button class="button secondary" data-event-action="reject" ${state.busy || !state.selected?.length ? 'disabled' : ''}>拒绝所选</button><button class="button secondary" data-event-action="freeze" ${state.busy || !state.selected?.length ? 'disabled' : ''}>冻结所选版本</button><button class="button secondary" data-event-action="coverage">覆盖与缺口</button></div>
      <div class="table-scroll"><table><thead><tr><th>选择</th><th>事件</th><th>发生／计划时间</th><th>市场</th><th>状态</th><th>研究准入</th></tr></thead><tbody>${rows.map(record => { const value = payload(record); return `<tr><td><input type="checkbox" aria-label="选择 ${e(title(record))}" data-event-select="${e(record.id)}" ${state.selected?.includes(record.id) ? 'checked' : ''}></td><td><button class="text-button" data-event-detail="${e(record.id)}">${e(title(record))}</button></td><td>${e(value.occurs_at || value.start_at || value.start_date || value.occurrence_start || '时间待核实')}</td><td>${e((value.markets || []).map(m => markets[m] || m).join('、') || '相关性待核验')}</td><td>${e(labels[value.lifecycle] || value.lifecycle || labels[value.status] || value.status || '待核实')}</td><td>${e(labels[value.admission] || value.admission || '待确认')}</td></tr>`; }).join('')}</tbody></table></div>
      ${!rows.length && !state.loading ? '<p class="intel-empty">当前范围没有已收录事件；这不表示没有事件发生。可查看来源覆盖或手动更新公开来源。</p>' : ''}
      ${eventMergeControls(state)}${manualEventControls(state)}${collectionControls(state)}`;
  } else if (view === 'studies') {
    content = `<p>预先固定窗口：节假日前后1／5／10交易日；月、季、年边界前后1／5日。失败及弃用试验同样留档。</p>
      <form data-event-study><label>研究批次<input name="family_id" maxlength="128" required value="${e(draft.family_id || 'event-calendar-v1')}"></label><label>研究名称<input name="title" required maxlength="200" value="${e(draft.title || '')}"></label><label>代表指数<select name="index_id">${(state.indices || []).map(index => `<option value="${e(index.id)}" ${draft.index_id === index.id ? 'selected' : ''}>${e(index.name || index.id)}</option>`).join('')}</select></label><label>冻结数据<select name="bundle_id" required><option value="">请选择已登记资料</option>${(state.bundles || []).map(record => `<option value="${e(record.id)}" ${draft.bundle_id === record.id ? 'selected' : ''}>${e(title(record))}</option>`).join('')}</select></label><label>研究类别<select name="role">${options({ calendar_overlay: '日历效应', event_overlay: '重大事件', base_score: '六维基础评分' }, draft.role || 'calendar_overlay')}</select></label>
      <label>事件家族<select name="family">${options(familyLabels, family)}</select></label><label>预先固定窗口<select name="rule">${familyRules.map(rule => `<option value="${e(rule)}" ${draft.rule === rule ? 'selected' : ''}>${e(ruleLabel(rule))}</option>`).join('')}</select></label><label>研究假设<select name="direction">${options({ '1': '窗口内偏强', '-1': '窗口内偏弱' }, draft.direction || '1')}</select></label><label>已确认的事件版本<select name="freeze_id"><option value="">无（仅日历或基础研究）</option>${(state.freezes || []).map(record => `<option value="${e(record.id)}" ${draft.freeze_id === record.id ? 'selected' : ''}>${e(payload(record).label || record.id)}</option>`).join('')}</select></label>
      <button class="button" ${state.busy || !(state.bundles || []).length ? 'disabled' : ''}>创建研究</button></form>
      ${inputControls(state)}
      <p class="muted">没有冻结资料时，请先从已有研究会话的数据集中登记来源。缺失日历、交易代理或历史时点证据会明确阻止正式准入。</p>
      <ul>${rows.map(record => `<li><button class="text-button" data-study-detail="${e(record.id)}">${e(payload(record).spec?.title || title(record))}</button> <button class="text-button" data-study-analyze="${e(record.id)}" ${state.busy ? 'disabled' : ''}>计算描述统计</button> <button class="text-button" data-study-preflight="${e(record.id)}">检查资格</button><button class="text-button" data-study-history="${e(record.id)}">已保存结果</button></li>`).join('')}</ul>${!rows.length ? '<p>尚未创建事件研究。</p>' : ''}${validationControls(state)}`;
  } else {
    content = `${scoreControls(state)}<p>趋势、广度、情绪、资金、估值、风险六维等权；首版预测期为20交易日。事件修正合计限±5分。</p><p>任一维证据不足时总分保持“待验证”，不填中性分、不重配权重；分数不用于三地直接排名。</p><ul>${rows.map(record => { const value = payload(record).result || payload(record); return `<li>${e(value.index_id || title(record))} · ${e(labels[value.status] || value.status || '待验证')} · 历史研究分 ${e(shown(value.research_score))}<button class="text-button" data-score-detail="${e(record.id)}">查看证据</button></li>`; }).join('')}</ul>${!rows.length ? '<p>目前没有获准的综合评分。可用性以每个指数的冻结版本和验证结果为准。</p>' : ''}`;
  }
  return `<section class="event-lab intel-page" aria-busy="${Boolean(state.loading || state.busy)}"><header><h1>${views[view]?.[0] || views.timeline[0]}</h1>${nav}${notice}</header>${state.error ? `<p class="notice error" role="alert">${e(state.error)}</p>` : ''}${state.loading ? '<p role="status">正在读取…</p>' : ''}${content}${state.data?.next_cursor ? '<button class="button secondary" data-event-action="more">加载更多</button>' : ''}${state.detail ? renderDetail(state.detail, state.detailKind, state) : ''}</section>`;
}

export function createEventLab({ request, onChange = () => {}, makeKey = () => globalThis.crypto.randomUUID(), getIdentity = () => String(globalThis.__RWB_USER_ID__ || 'single-user') } = {}) {
  const state = { view: 'timeline', filters: { period: 'future', market: '', category: '', q: '' }, selected: [], data: null, sources: [{ id: 'fed_fomc', name: '美联储 FOMC' }, { id: 'bls_cpi', name: '美国 CPI' }, { id: 'bls_jobs', name: '美国就业报告' }], indices: [], bundles: [], profiles: [], loading: false, busy: false, error: '', detail: null };
  let generation = 0;
  let detailGeneration = 0;
  let owner = getIdentity();
  const pendingKeys = new Map();
  state.formDrafts = {};
  const sourceChoice = key => state.sourceChoices?.find(source => `${source.session_id}/${source.dataset_id}` === key);
  const reference = record => ({ id: record.id, revision: record.revision });
  const links = values => Object.fromEntries(Object.entries({ index_calendar_ref: 'calendars', calendar_ref: 'calendars', proxy_ref: 'proxies', proxy_calendar_ref: 'calendars', proxy_prices_ref: 'prices', factor_inputs_ref: 'inputs' }).flatMap(([name, kind]) => {
    const record = state.choices?.[kind]?.find(row => row.id === values[name]); return record ? [[name, reference(record)]] : [];
  }));
  const endpoint = () => state.view === 'timeline' ? '/events' : state.view === 'studies' ? '/event-studies' : '/market-scores/runs';
  async function load({ more = false } = {}) {
    const ticket = ++generation;
    const account = getIdentity();
    const path = endpoint();
    const query = new URLSearchParams();
    if (state.view === 'timeline') {
      const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai' }).format(new Date());
      const nextYear = new Date(`${today}T00:00:00Z`); nextYear.setUTCFullYear(nextYear.getUTCFullYear() + 1);
      query.set('start', state.filters.start || (state.filters.period === 'future' ? today : '1990-01-01'));
      query.set('end', state.filters.end || (state.filters.period === 'history' ? today : nextYear.toISOString().slice(0, 10)));
      if (state.filters.period === 'scenarios') query.set('lifecycle', 'scenario');
      for (const name of ['market', 'category', 'q']) if (state.filters[name]) query.set(name, state.filters[name]);
    }
    if (more && state.data?.next_cursor) query.set('cursor', state.data.next_cursor);
    state.loading = true; state.error = ''; onChange();
    try {
      const result = await request(`${path}${query.size ? `?${query}` : ''}`, { method: 'GET' });
      if (ticket !== generation || account !== getIdentity()) return;
      state.data = more ? { ...result, items: [...items(state.data), ...items(result)] } : result;
      if (result.sources) state.sources = result.sources;
      if (result.indices) state.indices = result.indices;
      if (result.bundles) state.bundles = result.bundles.filter(record => payload(record).price_role !== 'proxy');
      if (result.source_choices) state.sourceChoices = result.source_choices;
      if (result.families) state.families = result.families;
      if (result.freezes) state.freezes = result.freezes;
      if (result.validation_batches) state.validationBatches = result.validation_batches;
      if (state.view !== 'timeline') {
        void request('/event-studies/sources/choices', { method: 'GET' }).then(choices => {
          if (ticket === generation && account === getIdentity()) { state.choices = choices; onChange(); }
        }).catch(error => {
          if (ticket === generation && account === getIdentity()) { state.error = `输入目录暂不可用：${error.message}`; safeLog('event_lab_choices_failed'); onChange(); }
        });
      }
      state.selected = [];
    } catch (error) { if (ticket === generation && account === getIdentity()) { state.error = error.message; safeLog('event_lab_read_failed'); } }
    finally { if (ticket === generation && account === getIdentity()) { state.loading = false; onChange(); } }
  }
  async function write(path, body, method = 'POST') {
    if (state.busy) return;
    const ticket = generation, view = state.view, account = getIdentity();
    const current = () => ticket === generation && view === state.view && account === getIdentity();
    const identity = `${account}:${method}:${path}:${JSON.stringify(body)}`;
    const key = pendingKeys.get(identity) || makeKey(); pendingKeys.set(identity, key);
    state.busy = true; state.error = ''; onChange();
    try {
      if (account !== getIdentity()) throw new Error('账号已变化，操作未提交');
      if (!['POST', 'PATCH'].includes(method)) throw new Error('不支持的事件写入方法');
      const result = await request(path, { method, body: path.startsWith('/event-studies') ? body : { ...body, idempotency_key: key }, key, userAction: true });
      pendingKeys.delete(identity);
      if (current()) {
        detailGeneration += 1;
        state.detail = path === '/events/merge' ? result.event : result;
        state.detailKind = path === '/events/decisions' ? 'event_decisions' : /^\/events\/[^/]+\/split$/.test(path) ? 'event_split' : path === '/events' || path === '/events/merge' || method === 'PATCH' && /^\/events\/[^/]+$/.test(path) ? 'event_detail' : 'result';
        state.detailEventId = state.detailKind === 'event_detail' ? state.detail?.id : '';
        await load();
      }
      return result;
    } catch (error) { if (current()) state.error = `${error.message}。结果未确认时不会自动重发；再次明确操作会复用原请求标识。`; safeLog('event_lab_write_failed'); }
    finally { state.busy = false; onChange(); }
  }
  async function detail(path) {
    const ticket = generation, detailTicket = ++detailGeneration, account = getIdentity();
    const current = () => ticket === generation && detailTicket === detailGeneration && account === getIdentity();
    try {
      const result = await request(path, { method: 'GET' });
      if (current()) {
        const eventPath = /^\/events\/([a-f0-9]{32})(\/versions|\?revision=\d+)?$/.exec(path);
        state.detail = result;
        state.detailKind = eventPath ? eventPath[2] === '/versions' ? 'event_versions' : eventPath[2] ? 'event_historical' : 'event_detail' : /^\/event-studies\/[^/]+\/runs$/.test(path) ? 'study_history' : 'result';
        state.detailEventId = eventPath?.[1] || ''; state.error = '';
      }
    } catch (error) { if (current()) state.error = error.message; safeLog('event_lab_detail_failed'); }
    if (current()) onChange();
  }
  return {
    state, load, write,
    activate(view = 'timeline') {
      const next = Object.hasOwn(views, view) ? view : 'timeline';
      if (owner !== getIdentity()) {
        state.studyDraft = {}; state.formDrafts = {}; state.scheduleDrafts = {}; state.scheduleSource = ''; state.bundles = []; state.sourceChoices = []; state.freezes = []; state.sources = []; state.choices = {}; state.validationBatches = []; state.filters = { period: 'future', market: '', category: '', q: '' }; pendingKeys.clear();
      }
      owner = getIdentity(); state.view = next; state.detail = null; state.detailEventId = ''; state.data = null; state.selected = [];
      return load();
    },
    deactivate() { generation += 1; state.loading = false; },
    restore(container) {
      for (const form of container.querySelectorAll?.('.event-lab form') || []) {
        const entries = state.formDrafts[formDraftKey(form)]; if (!entries) continue;
        for (const field of form.elements) {
          if (!field.name) continue;
          const values = entries.filter(([name]) => name === field.name).map(([, value]) => value);
          if (['checkbox', 'radio'].includes(field.type)) field.checked = values.includes(field.value);
          else if (values.length) field.value = values[0];
        }
      }
    },
    async handle(event) {
      const target = event.target;
      if (!target?.closest?.('.event-lab')) return false;
      const form = target.closest('form');
      if (['input', 'change'].includes(event.type) && formKind(form)) state.formDrafts[formDraftKey(form)] = [...new FormData(form).entries()];
      if (['input', 'change'].includes(event.type) && form?.matches('[data-event-schedule]')) {
        const values = new FormData(form), id = values.get('source');
        if (target.name === 'source') {
          state.scheduleSource = id; delete state.formDrafts['event-schedule']; onChange();
        } else {
          state.scheduleDrafts ||= {};
          state.scheduleDrafts[id] = { expected_revision: state.scheduleDrafts[id]?.expected_revision || state.sources.find(source => source.id === id)?.schedule?.revision || 1, enabled: values.has('enabled'), interval_hours: Number(values.get('interval_hours')) };
        }
        return true;
      }
      if (['input', 'change'].includes(event.type) && form?.matches('[data-event-study]')) {
        state.studyDraft = Object.fromEntries(new FormData(form));
        if (target.name === 'family') { state.studyDraft.rule = ''; onChange(); }
        return true;
      }
      if (event.type === 'submit' && form?.matches('[data-event-filters]')) {
        event.preventDefault(); state.filters = Object.fromEntries(new FormData(form)); await load(); return true;
      }
      if (event.type === 'submit' && form?.matches('[data-event-create]')) {
        event.preventDefault(); const values = new FormData(form), markets = values.getAll('market');
        if (!markets.length) { state.error = '请选择至少一个相关市场。'; onChange(); return true; }
        await write('/events', { title: values.get('title'), category: values.get('category'), occurrence_start: values.get('occurrence_start'), occurrence_end: values.get('occurrence_end') || null, date_precision: 'day', markets, lifecycle: values.get('lifecycle'), description: values.get('description') || '' }); return true;
      }
      if (event.type === 'submit' && form?.matches('[data-event-merge]')) {
        event.preventDefault(); const values = new FormData(form);
        const selected = items(state.data).filter(row => state.selected.includes(row.id));
        if (state.view !== 'timeline' || selected.length < 2 || selected.length > 30 || selected.length !== state.selected.length || selected.some(row => payload(row).superseded_by)) {
          state.error = '请选择2至30项未被替代的当前事件版本。'; safeLog('event_lab_merge_selection_invalid'); onChange(); return true;
        }
        const result = await write('/events/merge', { events: selected.map(reference), title: values.get('title'), reason: values.get('reason') });
        if (result) { delete state.formDrafts[formDraftKey(form)]; onChange(); } return true;
      }
      if (event.type === 'submit' && (form?.matches('[data-event-revise]') || form?.matches('[data-event-split]'))) {
        event.preventDefault(); const record = state.detail, values = new FormData(form);
        if (state.view !== 'timeline' || state.detailKind !== 'event_detail' || record?.id !== form.dataset?.eventId || record?.revision !== Number(form.dataset?.eventRevision) || payload(record).superseded_by) {
          state.error = '此表单不是当前可编辑版本；请重新读取事件并核对草稿。'; safeLog('event_lab_edit_version_invalid'); onChange(); return true;
        }
        const base = { ...eventFields(payload(record)), occurrence_end: payload(record).occurrence_end ?? null, description: payload(record).description || '' };
        let body, path = `/events/${encodeURIComponent(record.id)}`, method = 'POST';
        if (form.matches('[data-event-revise]')) {
          const markets = values.getAll('market');
          if (!markets.length) { state.error = '请选择至少一个相关市场。'; onChange(); return true; }
          body = { title: values.get('title'), category: values.get('category'), occurrence_start: values.get('occurrence_start'), occurrence_end: values.get('occurrence_end') || null, date_precision: values.get('date_precision'), markets, lifecycle: values.get('lifecycle'), description: values.get('description') || '', expected_revision: record.revision, reason: values.get('reason') }; method = 'PATCH';
        } else {
          path += '/split';
          body = { expected_revision: record.revision, reason: values.get('reason'), children: [0, 1].map(index => ({ ...base, title: values.get(`child_${index}_title`), occurrence_start: values.get(`child_${index}_occurrence_start`), occurrence_end: values.get(`child_${index}_occurrence_end`) || null })) };
        }
        const result = await write(path, body, method);
        if (result) { delete state.formDrafts[formDraftKey(form)]; onChange(); } return true;
      }
      if (event.type === 'submit' && form?.matches('[data-event-study]')) {
        event.preventDefault(); const values = Object.fromEntries(new FormData(form));
        const bundle = state.bundles.find(record => record.id === values.bundle_id);
        const frozen = state.freezes?.find(record => record.id === values.freeze_id);
        if (bundle) await write('/event-studies', { title: values.title, family_id: values.family_id || 'event-calendar-v1', index_id: values.index_id, role: values.role, profile_version: 'market-six-axis-v1', bundle_ref: { id: bundle.id, revision: bundle.revision }, hypothesis: `fixed-${values.family}-${values.rule}-${values.direction}`, ...(values.role === 'base_score' ? {} : { family: values.family, rule: values.rule || null, direction: Number(values.direction) }), ...(frozen ? { frozen_event_ref: { id: frozen.id, revision: frozen.revision } } : {}) });
        return true;
      }
      if (event.type === 'submit' && form?.matches('[data-event-import]')) {
        event.preventDefault(); const choice = sourceChoice(String(new FormData(form).get('choice') || ''));
        if (choice?.kind === 'prices') await write('/event-studies/sources', { index_id: choice.index_id, session_id: choice.session_id, dataset_id: choice.dataset_id }); return true;
      }
      if (event.type === 'submit' && form?.matches('[data-event-calendar]')) {
        event.preventDefault(); const values = Object.fromEntries(new FormData(form));
        const choice = sourceChoice(values.calendar_choice), bundle = state.bundles.find(row => row.id === values.bundle_id), frozen = state.freezes?.find(row => row.id === values.freeze_id);
        if (choice?.kind === 'calendar' && bundle) await write('/event-studies/sources/calendar', { session_id: choice.session_id, dataset_id: choice.dataset_id, bundle_ref: reference(bundle), ...(frozen ? { holiday_freeze_ref: reference(frozen) } : {}) });
        return true;
      }
      if (event.type === 'submit' && form?.matches('[data-event-native]')) {
        event.preventDefault(); const values = Object.fromEntries(new FormData(form)); const choice = sourceChoice(values.native_choice);
        if (choice?.kind === 'native') await write('/event-studies/sources/native', { kind: choice.native_kind, session_id: choice.session_id, dataset_id: choice.dataset_id, index_id: values.index_id, links: links(values) });
        return true;
      }
      if (event.type === 'submit' && form?.matches('[data-event-links]')) {
        event.preventDefault(); const values = Object.fromEntries(new FormData(form)), bundle = state.bundles.find(row => row.id === values.bundle_id);
        if (bundle) await write('/event-studies/sources/link', { bundle_ref: reference(bundle), links: links(values) }); return true;
      }
      if (event.type === 'submit' && form?.matches('[data-event-seal]')) {
        event.preventDefault(); const ids = new FormData(form).getAll('study_id').filter(id => items(state.data).some(row => row.id === id));
        if (ids.length) await write('/event-studies/validation-batches', { study_ids: ids });
        else { state.error = '请选择本次一起封存的研究。'; onChange(); } return true;
      }
      if (event.type === 'submit' && form?.matches('[data-event-evaluate]')) {
        event.preventDefault(); const values = new FormData(form), batch = state.validationBatches?.find(row => row.id === values.get('batch_id'));
        if (values.has('acknowledge') && batch) await write(`/event-studies/validation-batches/${encodeURIComponent(batch.id)}/evaluate`, {}); return true;
      }
      if (event.type === 'submit' && form?.matches('[data-event-score]')) {
        event.preventDefault(); const values = new FormData(form), input = state.choices?.inputs?.find(row => row.id === values.get('inputs_id'));
        if (input?.latest_as_of) await write('/market-scores/runs', { index_id: input.index_id, as_of: input.latest_as_of, inputs_id: input.id, validation_id: values.get('validation_id') || null, overlay_ids: values.getAll('overlay_id').filter(id => state.choices.validations.some(row => row.id === id)) });
        else { state.error = '所选六维输入缺少有效观测时点。'; onChange(); } return true;
      }
      if (event.type === 'submit' && form?.matches('[data-event-source]')) {
        event.preventDefault(); const values = Object.fromEntries(new FormData(form)), body = { source: values.source };
        if (values.year) body.year = Number(values.year);
        if (body.source === 'gdelt' && !body.year) {
          const previous = new Date(Date.now() - 86400000); body.year = previous.getUTCFullYear(); body.page = Math.floor((previous - Date.UTC(body.year, 0, 1)) / 86400000);
        }
        if (state.sources.some(source => source.id === body.source)) await write('/events/sources/refresh', body); return true;
      }
      if (event.type === 'submit' && form?.matches('[data-event-schedule]')) {
        event.preventDefault(); const values = new FormData(form), source = state.sources.find(row => row.id === values.get('source'));
        const account = getIdentity();
        if (source) {
          const result = await write(`/events/sources/${encodeURIComponent(source.id)}/schedule`, { expected_revision: state.scheduleDrafts?.[source.id]?.expected_revision || source.schedule?.revision || 1, enabled: values.has('enabled'), interval_hours: Number(values.get('interval_hours')) });
          if (result?.revision && account === getIdentity() && state.scheduleDrafts?.[source.id]) state.scheduleDrafts[source.id].expected_revision = result.revision;
        } return true;
      }
      if (event.type === 'change' && target.matches('[data-event-select]')) {
        const id = target.dataset.eventSelect;
        state.selected = target.checked ? [...new Set([...state.selected, id])] : state.selected.filter(value => value !== id); onChange(); return true;
      }
      if (event.type !== 'click') return false;
      const button = target.closest('button'); if (!button || button.disabled) return false;
      const data = button.dataset;
      if (data.eventDetail) await detail(`/events/${encodeURIComponent(data.eventDetail)}`);
      else if (data.eventVersions) await detail(`/events/${encodeURIComponent(data.eventVersions)}/versions`);
      else if (data.eventLatest) await detail(`/events/${encodeURIComponent(data.eventLatest)}`);
      else if (data.eventVersion && data.eventId === state.detailEventId && Number.isSafeInteger(Number(data.eventVersion)) && Number(data.eventVersion) > 0) await detail(`/events/${encodeURIComponent(data.eventId)}?revision=${Number(data.eventVersion)}`);
      else if (data.sourceNext && data.sourceNext === state.detail?.id) {
        const job = payload(state.detail), point = job.checkpoint;
        if (job.state === 'completed' && point && (point.next_page !== null && point.next_page !== undefined || point.next_offset !== null && point.next_offset !== undefined)) {
          await write('/events/sources/backfill', { source: job.source, year: point.next_year ?? job.year, page: point.next_page ?? job.page, offset: point.next_offset ?? 0 });
        }
      }
      else if (data.studyDetail) await detail(`/event-studies/${encodeURIComponent(data.studyDetail)}`);
      else if (data.studyHistory) await detail(`/event-studies/${encodeURIComponent(data.studyHistory)}/runs`);
      else if (data.studyRun) await detail(`/event-studies/runs/${encodeURIComponent(data.studyRun)}`);
      else if (data.scoreDetail) await detail(`/market-scores/runs/${encodeURIComponent(data.scoreDetail)}`);
      else if (data.eventRefresh) await write('/events/sources/refresh', { source: data.eventRefresh });
      else if (data.studyAnalyze) await write(`/event-studies/${encodeURIComponent(data.studyAnalyze)}/analyze`, {});
      else if (data.studyPreflight) await detail(`/event-studies/${encodeURIComponent(data.studyPreflight)}/preflight`);
      else if (['confirm', 'reject'].includes(data.eventAction)) {
        const events = items(state.data).filter(record => state.selected.includes(record.id)).map(record => ({ id: record.id, revision: record.revision }));
        await write('/events/decisions', { events, decision: data.eventAction === 'confirm' ? 'confirmed' : 'rejected', reason: '用户在事件时间线明确处理所选事件' });
      } else if (data.eventAction === 'freeze') {
        const events = items(state.data).filter(record => state.selected.includes(record.id)).map(record => ({ id: record.id, revision: record.revision }));
        await write('/events/freeze', { events, label: '事件时间线选定版本' });
      } else if (data.eventAction === 'coverage') await detail('/events/coverage');
      else if (data.eventAction === 'more') await load({ more: true });
      else if (data.eventAction === 'close') { detailGeneration += 1; state.detail = null; state.detailEventId = ''; onChange(); }
      else return false;
      return true;
    },
  };
}
