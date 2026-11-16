import { safeLog } from './core.mjs';
import { escapeHTML as e } from './markdown.mjs';
import { createEventLab, renderEventLab } from './event-lab.mjs';

const rules = [
  ['volume_stall', '放量滞涨'],
  ['sma5_close', '跌破 5 日线'],
  ['sma10_close', '跌破 10 日线'],
  ['sma20_close', '跌破 20 日线'],
];
const labels = Object.fromEntries(rules);
const metrics = [
  ['volume_ratio', '放量倍数', 1.30, 1, 5, .01],
  ['near_high_pct', '距前高上限（%）', 2, .1, 20, .1],
  ['ma_previous_gap_pct', '对照前日距均线上限（%）', 3, .1, 20, .1],
  ['ma_close_gap_pct', '对照当日距均线上限（%）', 2.5, .1, 20, .1],
  ['sell_cost_bps', '每次卖出摩擦（基点）', 10, 0, 100, 1],
];
const pageSize = 50;
const horizons = [1, 5, 10];
const highWindows = [20, 60];
const account = () => String(globalThis.__RWB_USER_ID__ || 'single-user');
const timeFormat = new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Shanghai' });

function initialState() {
  return {
    datasets: [], runs: [], file: null, loading: false, busy: '', error: '', message: '',
    detail: null, detailLoading: false, events: null, eventsLoading: false, selectedRule: '',
    draft: {
      dataset_id: '', rules: rules.map(([id]) => id), horizon: 5, high_window: 20,
      ...Object.fromEntries(metrics.map(([id, , value]) => [id, value])),
    },
  };
}

const nameOfRule = id => Object.hasOwn(labels, id) ? labels[id] : id;
const timeOfRun = value => {
  if (value == null) return '—';
  const date = new Date(typeof value === 'number' && value < 1e12 ? value * 1000 : value);
  return Number.isNaN(date.getTime()) ? '—' : timeFormat.format(date);
};
const shown = value => value == null || value === '' ? '—' : e(value);
const percent = value => Number.isFinite(value) ? `${(value * 100).toFixed(2)}%` : '—';
const points = value => Number.isFinite(value) ? (value * 100).toFixed(3) : '—';
const formattedRate = value => Number.isFinite(value?.rate) && Number.isInteger(value.events) && Number.isInteger(value.n)
  ? `${percent(value.rate)}（${value.events.toLocaleString('zh-CN')} / ${value.n.toLocaleString('zh-CN')}）`
  : value?.n === 0 ? '—（0 笔可计算）' : '—';
const runDataset = (state, id) => state.datasets.find(item => item.id === id)?.name || id;
const selectOptions = (values, selected, label) => values.map(value => `<option value="${e(value)}"${String(value) === String(selected) ? ' selected' : ''}>${e(label(value))}</option>`).join('');
const interval = (values, format) => Array.isArray(values) && values.length === 2 && values.every(Number.isFinite)
  ? `<div class="muted small">95% 区间 ${e(format(values[0]))} 至 ${e(format(values[1]))}</div>` : '';

function renderRunConfiguration(configuration) {
  if (!configuration || typeof configuration !== 'object') return '';
  const configuredRules = Array.isArray(configuration.rules) ? configuration.rules.map(nameOfRule).join('、') : null;
  const fields = [
    ['策略', configuredRules], ['观察期限（交易日）', configuration.horizon], ['前高观察期（交易日）', configuration.high_window],
    ...metrics.map(([name, label]) => [label, configuration[name]]),
  ];
  return `<details data-strategy-run-configuration><summary>本次运行参数</summary>
    <dl class="runtime-details">${fields.map(([label, value]) => `<div><dt>${e(label)}</dt><dd>${shown(value)}</dd></div>`).join('')}</dl>
  </details>`;
}

function renderResult(state) {
  const detail = state.detail;
  if (!detail) return '';
  const rows = detail.rules.map(row => `<tr>
    <th scope="row">${e(nameOfRule(row.id))}</th><td>${shown(row.signal_count)}</td>
    <td>${e(formattedRate(row.downside))}${interval(row.downside?.ci95, percent)}</td>
    <td>${e(formattedRate(row.sale))}${interval(row.sale?.ci95, percent)}</td><td>${e(points(row.sale?.mean))}${interval(row.sale?.ci_effect, points)}</td>
    <td>${shown(row.matched?.n)}</td><td>${e(percent(row.matched?.trigger_mean))}</td><td>${e(percent(row.matched?.control_mean))}</td>
    <td>${e(points(row.matched?.mean))}${interval(row.matched?.ci95, points)}</td></tr>`).join('');
  const coverage = detail.coverage;
  const summary = `<section class="desk-result" aria-labelledby="strategy-result-title" data-strategy-result>
    <div class="section-heading"><h2 id="strategy-result-title">验证结果</h2></div>
    <p class="muted">${e(runDataset(state, detail.dataset_id))} · 第 ${shown(detail.horizon)} 个交易日 · ${e(timeOfRun(detail.created_at))}</p>
    <p class="muted">下跌率以有完整后续行情的事件为分母。卖出胜率比较同一事件次日开盘卖出与持有至指定期限收盘卖出，平局计入分母。相似对照只使用信号当日及之前的数据配对。</p>
    <div class="table-scroll" tabindex="0" role="region" aria-label="策略汇总"><table class="market-table"><thead><tr>
      <th scope="col">策略</th><th scope="col">触发数</th><th scope="col">后续下跌率</th><th scope="col">次日卖出胜率</th><th scope="col">卖出减持有（百分点）</th>
      <th scope="col">配对数</th><th scope="col">配对触发均值</th><th scope="col">相似对照均值</th><th scope="col">触发减对照（百分点）</th>
    </tr></thead><tbody>${rows}</tbody></table></div>
    ${coverage ? `<p class="muted">行情覆盖 ${shown(coverage.first_market_session)} 至 ${shown(coverage.last_market_session)} · ${shown(coverage.ticker_count)} 只股票 · ${shown(coverage.analysis_days)} 个交易日 · ${shown(coverage.raw_rows)} 条日线</p>` : ''}
    ${renderRunConfiguration(detail.configuration)}
  </section>`;
  return summary + renderEvents(state);
}

function renderEvents(state) {
  const options = selectOptions(state.detail.rules.map(row => row.id), state.selectedRule, nameOfRule);
  const page = state.events;
  const rows = (page?.items || []).map(row => `<tr>
    <td>${shown(row.date)}</td><th scope="row">${shown(row.ticker)}</th>
    <td>${e(percent(row.hold_return))}</td><td>${e(points(row.sell_advantage))}</td>
    <td>${row.open_executable === true ? '可按假设成交' : row.open_executable === false ? '不可按假设成交' : '—'}</td>
    <td>${shown(row.control_ticker)}</td><td>${e(percent(row.control_return))}</td>
  </tr>`).join('');
  return `<section class="desk-result" aria-labelledby="strategy-events-title" data-strategy-events>
    <div class="section-heading"><h2 id="strategy-events-title">逐笔验证结果</h2></div>
    <label for="strategy-event-rule">筛选策略</label>
    <select id="strategy-event-rule" data-strategy-event-rule>${options}</select>
    ${state.eventsLoading ? '<p role="status">正在读取逐笔结果…</p>' : ''}
    ${!state.eventsLoading && page?.total === 0 ? '<p class="muted">所选策略没有触发事件。</p>' : ''}
    ${rows ? `<div class="table-scroll market-table-wrap" tabindex="0" role="region" aria-label="逐笔结果"><table class="market-table"><thead><tr>
      <th scope="col">信号日期</th><th scope="col">股票</th><th scope="col">继续持有收益</th><th scope="col">卖出减持有（百分点）</th>
      <th scope="col">次日开盘成交</th><th scope="col">相似对照股票</th><th scope="col">对照持有收益</th>
    </tr></thead><tbody>${rows}</tbody></table></div>` : ''}
    ${page?.total > 0 ? `<div class="button-row" aria-label="逐笔结果分页">
      <button type="button" class="button secondary" id="strategy-events-prev" data-strategy-offset="${Math.max(0, page.offset - pageSize)}"${state.eventsLoading || page.offset === 0 ? ' disabled' : ''}>上一页</button>
      <span class="muted" role="status">第 ${shown(page.offset + 1)}–${shown(page.offset + page.items.length)} 笔，共 ${shown(page.total)} 笔</span>
      <button type="button" class="button secondary" id="strategy-events-next" data-strategy-offset="${page.offset + pageSize}"${state.eventsLoading || page.offset + pageSize >= page.total ? ' disabled' : ''}>下一页</button>
    </div>` : ''}
  </section>`;
}

export function renderStrategyValidation(state) {
  const disabled = Boolean(state.busy || state.loading);
  const draft = state.draft;
  const datasets = state.datasets.map(item => `<option value="${e(item.id)}"${item.id === draft.dataset_id ? ' selected' : ''}>${e(item.name || item.id)}</option>`).join('');
  const dataset = state.datasets.find(item => item.id === draft.dataset_id);
  const runRows = state.runs.map(run => `<tr>
    <th scope="row">${e(runDataset(state, run.dataset_id))}</th><td>${shown(run.horizon)} 日</td>
    <td>${e(timeOfRun(run.created_at))}</td><td><button type="button" class="button secondary" data-strategy-run="${e(run.id)}"${disabled ? ' disabled' : ''}${state.detail?.id === run.id ? ' aria-current="true"' : ''}>查看结果</button></td>
  </tr>`).join('');
  return `<section class="strategy-validation" aria-busy="${disabled || state.detailLoading || state.eventsLoading}">
    <header class="page-header"><div><h1>策略验证</h1>
      <p class="muted">用冻结行情研究卖出规则及相似对照。研究结果仅用于历史分析。</p></div>
      <button type="button" class="button secondary" id="strategy-refresh" data-strategy-action="reload"${disabled ? ' disabled' : ''}>刷新历史</button>
    </header>
    ${state.error ? `<p class="notice error" role="alert">${e(state.error)}</p>` : ''}
    ${state.message ? `<p class="notice success" role="status">${e(state.message)}</p>` : ''}
    ${state.loading || state.busy ? `<p class="muted" role="status">${state.loading ? '正在读取历史…' : state.busy === 'import' ? '正在校验并导入行情…' : '正在计算策略与相似对照…'}</p>` : ''}
    <section class="desk-result" aria-labelledby="strategy-dataset-title">
      <div class="section-heading"><h2 id="strategy-dataset-title">冻结行情</h2></div>
      <form data-strategy-import>
        <div class="button-row"><label for="strategy-archive">行情 ZIP</label>
          <input id="strategy-archive" name="archive" type="file" accept=".zip,application/zip"${state.file ? '' : ' required'}${disabled ? ' disabled' : ''}>
          <button class="button secondary" type="submit"${disabled ? ' disabled' : ''}>导入冻结行情</button>
        </div>
        ${state.file ? `<p class="muted small">选定 ${e(state.file.name || '行情 ZIP')}</p>` : ''}
      </form>
    </section>
    <section class="workbench-query-form" aria-labelledby="strategy-config-title">
      <div class="section-heading"><h2 id="strategy-config-title">配置验证</h2></div>
      <form data-strategy-config>
        <fieldset${disabled ? ' disabled' : ''}>
          <legend>数据集和规则</legend>
          <div class="form-grid">
            <label for="strategy-dataset">数据集
              <select id="strategy-dataset" name="dataset_id" required><option value=""${draft.dataset_id ? '' : ' selected'}>请选择已导入行情</option>${datasets}</select>
            </label>
            <label for="strategy-horizon">观察期限
              <select id="strategy-horizon" name="horizon">${selectOptions(horizons, draft.horizon, value => `第 ${value} 个交易日`)}</select>
            </label>
          </div>
          ${dataset?.sha256 ? `<p class="muted small">冻结档案 SHA-256 <code>${e(dataset.sha256)}</code></p>` : ''}
          <div class="button-row">${rules.map(([id, label]) => `<label><input type="checkbox" id="strategy-rule-${id}" name="rules" value="${id}"${draft.rules.includes(id) ? ' checked' : ''}> ${e(label)}</label>`).join('')}</div>
        </fieldset>
        <fieldset${disabled ? ' disabled' : ''}>
          <legend>研究参数</legend>
          <div class="form-grid"><label for="strategy-high-window">前高观察期
            <select id="strategy-high-window" name="high_window">${selectOptions(highWindows, draft.high_window, value => `${value} 个交易日`)}</select>
          </label>${metrics.map(([id, label, , min, max, step]) => `<label for="strategy-${id}">${e(label)}
            <input id="strategy-${id}" name="${id}" type="number" min="${min}" max="${max}" step="${step}" value="${e(draft[id])}" required>
          </label>`).join('')}</div>
        </fieldset>
        <div class="button-row"><button class="button primary" type="submit"${disabled || !dataset ? ' disabled' : ''}>运行策略验证</button></div>
      </form>
    </section>
    <section class="desk-result" aria-labelledby="strategy-runs-title">
      <div class="section-heading"><h2 id="strategy-runs-title">验证历史</h2></div>
      ${runRows ? `<div class="table-scroll" tabindex="0" role="region" aria-label="历史结果"><table class="market-table"><thead><tr>
        <th scope="col">数据集</th><th scope="col">期限</th><th scope="col">运行时间</th><th scope="col">结果</th></tr></thead><tbody>${runRows}</tbody></table></div>` : '<p class="muted">还没有保存的验证结果。</p>'}
      ${state.detailLoading ? '<p role="status">正在读取验证结果…</p>' : ''}
    </section>
    ${renderResult(state)}
  </section>`;
}

function runInput(draft) {
  return {
    dataset_id: draft.dataset_id,
    rules: rules.map(([id]) => id).filter(id => draft.rules.includes(id)),
    horizon: Number(draft.horizon),
    volume_ratio: Number(draft.volume_ratio),
    high_window: Number(draft.high_window),
    near_high_pct: Number(draft.near_high_pct),
    ma_previous_gap_pct: Number(draft.ma_previous_gap_pct),
    ma_close_gap_pct: Number(draft.ma_close_gap_pct),
    sell_cost_bps: Number(draft.sell_cost_bps),
  };
}

export function createStrategyValidation({ api, onChange = () => {}, getIdentity = account, makeKey = () => globalThis.crypto.randomUUID() }) {
  const state = initialState();
  let owner = getIdentity(), active = false, generation = 0, detailTicket = 0, eventTicket = 0;
  let writePending = null;
  const pendingKeys = new Map();

  const current = (view, identity) => active && generation === view && identity === getIdentity();
  const paint = () => { if (active && owner === getIdentity()) onChange(); };
  const reportError = (error, logCode) => {
    state.error = error.message || '请求失败，请重试。';
    safeLog(logCode, { status: error.code || 'request_failed' });
  };
  function releaseVisibleRunKeys() {
    for (const [fingerprint, pending] of pendingKeys) {
      if (pending.runId && state.runs.some(run => run.id === pending.runId)) pendingKeys.delete(fingerprint);
    }
  }
  async function reload() {
    if (!active || state.loading || writePending) return;
    const view = generation, identity = owner;
    state.loading = true;
    state.error = '';
    paint();
    try {
      const result = await api.strategyValidation();
      if (!current(view, identity)) return;
      state.datasets = Array.isArray(result.datasets) ? result.datasets : [];
      state.runs = Array.isArray(result.runs) ? result.runs : [];
      releaseVisibleRunKeys();
      if (!state.datasets.some(item => item.id === state.draft.dataset_id)) state.draft.dataset_id = state.datasets[0]?.id || '';
    } catch (error) {
      if (current(view, identity)) reportError(error, 'strategy_validation_history_failed');
    } finally {
      if (current(view, identity)) {
        state.loading = false;
        paint();
      }
    }
  }

  async function activate() {
    if (owner !== getIdentity()) {
      owner = getIdentity();
      writePending = null;
      pendingKeys.clear();
      Object.assign(state, initialState());
    }
    active = true;
    generation += 1;
    state.loading = false;
    await reload();
  }

  function deactivate() {
    active = false;
    generation += 1;
    state.loading = false;
    state.detailLoading = false;
    state.eventsLoading = false;
    state.file = null;
  }

  async function loadEvents(rule, offset = 0) {
    const id = state.detail?.id;
    if (!active || owner !== getIdentity() || !id || !state.detail.rules.some(item => item.id === rule)) return;
    if (!Number.isSafeInteger(offset) || offset < 0 || offset % pageSize !== 0) return;
    const view = generation, ticket = ++eventTicket, identity = owner;
    const applicable = () => current(view, identity) && eventTicket === ticket && state.detail?.id === id;
    if (state.selectedRule !== rule) state.events = null;
    state.selectedRule = rule;
    state.eventsLoading = true;
    state.error = '';
    paint();
    try {
      const page = await api.strategyValidationEvents(id, rule, offset, pageSize);
      if (!Array.isArray(page.items) || page.items.length > pageSize || page.offset !== offset
          || page.limit !== pageSize || !Number.isSafeInteger(page.total) || page.total < 0) {
        throw new Error('逐笔结果分页格式异常。');
      }
      if (applicable()) state.events = page;
    } catch (error) {
      if (applicable()) reportError(error, 'strategy_validation_events_failed');
    } finally {
      if (applicable()) {
        state.eventsLoading = false;
        paint();
      }
    }
  }

  async function showRun(id) {
    if (!active || owner !== getIdentity() || !id || !state.runs.some(run => run.id === id)) return;
    const view = generation, ticket = ++detailTicket, identity = owner;
    const applicable = () => current(view, identity) && detailTicket === ticket;
    eventTicket += 1;
    state.detail = null;
    state.events = null;
    state.eventsLoading = false;
    state.detailLoading = true;
    state.error = '';
    paint();
    try {
      const detail = await api.strategyValidationDetail(id);
      if (detail.id !== id || !Array.isArray(detail.rules) || detail.rules.some(row => !Object.hasOwn(labels, row.id))) {
        throw new Error('验证结果格式异常。');
      }
      if (applicable()) {
        state.detail = detail;
        state.detailLoading = false;
        paint();
        if (detail.rules[0]) await loadEvents(detail.rules[0].id);
      }
    } catch (error) {
      if (applicable()) reportError(error, 'strategy_validation_result_failed');
    } finally {
      if (applicable()) {
        state.detailLoading = false;
        paint();
      }
    }
  }

  async function write(kind, request) {
    if (!active || owner !== getIdentity() || writePending || state.loading) return;
    const entry = {}, view = generation, identity = owner;
    writePending = entry;
    state.busy = kind;
    state.error = '';
    state.message = '';
    paint();
    let result, failure;
    try {
      result = await request();
    } catch (error) {
      failure = error;
    }
    if (writePending !== entry) return;
    writePending = null;
    state.busy = '';
    if (!active || owner !== identity || identity !== getIdentity()) return;
    const returned = view !== generation;
    if (returned) {
      // An acknowledgement from the previous visit is only a cue to read the current history.
      const returnedView = generation;
      await reload();
      if (!current(returnedView, identity)) return;
    }
    if (failure) {
      const historyError = state.error;
      reportError(failure, `strategy_validation_${kind}_failed`);
      if (kind === 'run') state.error += ' 可刷新历史核对结果，或者按原参数手动重试。';
      if (historyError) state.error = `${historyError}。${state.error}`;
      paint();
      return;
    }
    if (returned) {
      const visible = (kind === 'import' ? state.datasets : state.runs).some(item => item.id === result?.id);
      if (visible) state.message = kind === 'import' ? '冻结行情已导入。' : '验证已完成。';
      else if (!state.error) state.error = '已收到操作回执，历史暂未显示结果。请刷新历史后核对。';
      paint();
      return;
    }
    if (kind === 'import') {
      state.datasets = [result, ...state.datasets.filter(item => item.id !== result.id)];
      state.draft.dataset_id = result.id;
      state.file = null;
      state.message = '冻结行情已导入。';
      paint();
      return;
    }
    state.runs = [result, ...state.runs.filter(item => item.id !== result.id)];
    releaseVisibleRunKeys();
    state.message = '验证已完成。';
    await showRun(result.id);
  }

  async function importFile() {
    const file = state.file;
    if (!file?.size) {
      state.error = '请选择一个行情 ZIP。';
      paint();
      return;
    }
    await write('import', () => api.strategyValidationImport(file));
  }

  async function run() {
    const body = runInput(state.draft);
    if (!state.datasets.some(item => item.id === body.dataset_id) || !body.rules.length) {
      state.error = '请选择冻结行情并勾选至少一条策略。';
      paint();
      return;
    }
    const invalidMetric = metrics.some(([name, , , min, max, step]) => {
      const value = body[name], increments = (value - min) / step;
      return state.draft[name] === '' || !Number.isFinite(value) || value < min || value > max
        || Math.abs(increments - Math.round(increments)) > 1e-8;
    });
    if (!horizons.includes(body.horizon) || !highWindows.includes(body.high_window) || invalidMetric) {
      state.error = '请检查研究参数的取值。';
      paint();
      return;
    }
    const identity = owner, fingerprint = JSON.stringify(body);
    await write('run', async () => {
      const pending = pendingKeys.get(fingerprint) || { key: makeKey(), runId: '' };
      pendingKeys.set(fingerprint, pending);
      const result = await api.strategyValidationRun(body, pending.key);
      if (owner === identity && pendingKeys.get(fingerprint) === pending) pending.runId = result.id;
      return result;
    });
  }

  async function handle(event) {
    const element = event.target;
    if (!element.closest?.('.strategy-validation') || !active || owner !== getIdentity()) return false;
    if (event.type === 'input' || event.type === 'change') {
      if (element.name === 'archive' && event.type === 'change') {
        state.file = element.files?.[0] || null;
        paint();
        return true;
      }
      if (element.name === 'rules') {
        if (element.checked && !state.draft.rules.includes(element.value)) state.draft.rules.push(element.value);
        if (!element.checked) state.draft.rules = state.draft.rules.filter(rule => rule !== element.value);
      } else if (Object.hasOwn(state.draft, element.name)) {
        state.draft[element.name] = element.value;
        if (event.type === 'change' && element.name === 'dataset_id') paint();
      }
      if (event.type === 'change' && element.matches?.('[data-strategy-event-rule]')) await loadEvents(element.value);
      return true;
    }
    if (event.type === 'submit') {
      event.preventDefault();
      if (element.matches?.('[data-strategy-import]')) await importFile();
      if (element.matches?.('[data-strategy-config]')) await run();
      return true;
    }
    if (event.type === 'click') {
      const action = element.closest?.('[data-strategy-action], [data-strategy-run], [data-strategy-offset]');
      if (action?.dataset.strategyAction === 'reload') await reload();
      if (action?.dataset.strategyRun) await showRun(action.dataset.strategyRun);
      if (action?.dataset.strategyOffset !== undefined) await loadEvents(state.selectedRule, Number(action.dataset.strategyOffset));
      return Boolean(action);
    }
    return false;
  }

  function render() {
    const screen = owner === getIdentity() ? state : initialState();
    return renderStrategyValidation(active ? screen : { ...screen, loading: true });
  }
  return { state, activate, deactivate, handle, render };
}

function researchView(route) {
  if (route.page === 'intel' && route.intelTab === 'timeline') return 'timeline';
  if (route.page !== 'simulation') return null;
  if (route.simulationView === 'events') return 'studies';
  if (route.simulationView === 'scores' || route.simulationView === 'strategies') return route.simulationView;
  return null;
}

export function createEventResearchWorkspace({ api, getRoute, onChange }) {
  const currentView = () => researchView(getRoute());
  const isEventLab = view => view && view !== 'strategies';
  const eventLab = createEventLab({ request: (...args) => api.request(...args), onChange: () => { if (isEventLab(currentView())) onChange(); } });
  const strategy = createStrategyValidation({ api, onChange: () => { if (currentView() === 'strategies') onChange(); } });
  const eventController = target => {
    if (target.closest?.('.strategy-validation')) return strategy;
    if (target.closest?.('.event-lab')) return eventLab;
    return null;
  };
  return {
    isActiveRoute: () => Boolean(currentView()),
    owns: event => Boolean(eventController(event.target)),
    showsEtfErrors: () => getRoute().page === 'simulation' && currentView() !== 'strategies',
    render() {
      const view = currentView();
      if (view === 'strategies') return strategy.render();
      return isEventLab(view) ? renderEventLab(eventLab.state) : '';
    },
    activate() {
      const view = currentView();
      if (view === 'strategies') return strategy.activate();
      if (isEventLab(view)) return eventLab.activate(view);
    },
    deactivate() {
      eventLab.deactivate();
      strategy.deactivate();
    },
    restore(root) {
      if (isEventLab(currentView())) eventLab.restore(root);
    },
    handleInput(event) {
      const controller = eventController(event.target);
      if (!controller) return false;
      void controller.handle(event);
      return true;
    },
    handle: event => eventController(event.target)?.handle(event) || false,
  };
}
