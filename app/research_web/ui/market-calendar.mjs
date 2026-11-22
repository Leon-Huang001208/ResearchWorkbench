import { safeLog } from './core.mjs';
import { escapeHTML as e } from './markdown.mjs';

const CATEGORIES = { economic: '经济数据', ipo: '新股发行', notify: '交易提醒', report: '财报发行', inst: '机构交易' };
const COUNT_CATEGORIES = ['economic', 'ipo', 'notify', 'report'];
const SUBTYPES = {
  ipo: { ipo_listed: '今日上市', ipo_subscribe: '今日申购', ipo_lottery: '中签公布' },
  notify: { notify_attend: '股东大会', notify_divide: '分红派息', notify_suspend: '停复牌', notify_contract: '重大经营合同' },
};
const MARKETS = { all: '全部市场', ab: 'A股', hk: '港股', us: '美股' };
const HOLDINGS = { all: '全部', inc: '增持', dec: '减持', new: '新进', out: '清仓' };
const FILTER_SETS = { all: '全部', topAum: 'Top AUM', topChAumPr: 'Top AUM增长率' };
const WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日'];
const STATUS = {
  covered: '已覆盖',
  partial: '部分覆盖，仅展示已核实数据',
  stale: '数据已陈旧，保留上次已核实数据',
  unavailable: '来源暂不可用',
  not_connected: '尚未接入',
};
const TIME_NAME = ['event', '时间/名称'];
const IPO_OFFER = [TIME_NAME, ['issuePrice', '发行价'], ['peRatio', '市盈率'], ['subscriptionLimit', '申购上限'], ['prospectusDate', '招股日期']];
const COLUMNS = {
  economic: [TIME_NAME, ['actual', '公布'], ['forecast', '预期'], ['previous', '前值'], ['importance', '重要性'], ['impact', '利多/利空']],
  ipo_listed: [TIME_NAME, ['issuePrice', '发行价'], ['issuedShares', '发行股本'], ['raisedFunds', '募集资金']],
  ipo_subscribe: IPO_OFFER,
  ipo_lottery: IPO_OFFER,
  notify_attend: [TIME_NAME, ['meetingType', '股东大会类别']],
  notify_divide: [TIME_NAME, ['exDate', '除权日'], ['dividend', '分红'], ['bonusShares', '送股'], ['transferShares', '转增'], ['inKind', '实物']],
  notify_suspend: [TIME_NAME, ['suspendTime', '停牌时间'], ['reason', '停牌事项说明'], ['resumeTime', '复牌时间']],
  notify_contract: [TIME_NAME, ['subject', '合同标的'], ['amount', '涉及金额(元)'], ['termMonths', '合同期间(月)']],
  report: [TIME_NAME, ['session', '盘前/盘后'], ['fiscalPeriod', '财报期']],
  inst: [['institution', '机构'], ['direction', '方向'], ['transaction', '交易事项'], ['symbol', '交易股票']],
};
const ENDPOINT = '/market/financial-calendar';
const BEIJING_DATE = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' });
const BEIJING_TIME = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', dateStyle: 'short', timeStyle: 'short', hourCycle: 'h23' });
const DAY = 86400000;
const iso = date => date.toISOString().slice(0, 10);
const utc = date => new Date(`${date}T00:00:00Z`);
const isDate = date => typeof date === 'string' && /^[1-9]\d{3}-\d{2}-\d{2}$/.test(date) && Number.isFinite(+utc(date)) && iso(utc(date)) === date;
const addDays = (date, n) => iso(new Date(+utc(date) + n * DAY));
const weekday = date => (utc(date).getUTCDay() + 6) % 7;
const shortDate = date => `${Number(date.slice(5, 7))}月${Number(date.slice(8, 10))}日`;
const weekCardDate = date => `${date.slice(5, 7)}月${date.slice(8, 10)}日`;
const longDate = date => `${date.slice(0, 4)}年${shortDate(date)}`;
const dataDays = (result) => new Map((result?.days || []).map(day => [day.date, day]));
const calendarDays = ({ start, end }) => Array.from({ length: (+utc(end) - +utc(start)) / DAY + 1 }, (_, offset) => addDays(start, offset));
const stamp = value => typeof value === 'string' && Number.isFinite(Date.parse(value)) ? BEIJING_TIME.format(new Date(value)) : '';

function ranges(date, mode) {
  if (mode !== 'month') {
    const start = addDays(date, -weekday(date));
    return { summary: { start, end: addDays(start, 6) }, events: { start, end: addDays(start, 6) } };
  }
  const start = `${date.slice(0, 7)}-01`;
  const last = utc(start);
  last.setUTCMonth(last.getUTCMonth() + 1, 0);
  return { summary: { start, end: iso(last) }, events: { start: date, end: date } };
}

function countRows(day, compact) {
  return COUNT_CATEGORIES.map(category => {
    const value = day?.counts?.[category];
    const known = Number.isSafeInteger(value) && value >= 0;
    const count = known ? `${value > 0 && day.status !== 'covered' ? '≥' : ''}${value}` : '—';
    const status = category === 'economic' && day?.status !== 'covered' && Object.hasOwn(STATUS, day?.status) ? ` · ${STATUS[day.status]}` : '';
    const title = `${CATEGORIES[category]}：${known ? count : '未覆盖'}${status}`;
    return `<span class="financial-calendar-count count-${category}" title="${title}">${compact ? `<span aria-hidden="true">${CATEGORIES[category].slice(0, 2)}</span>` : `<span aria-hidden="true">${CATEGORIES[category]}</span>`}<b aria-label="${title}">${count}</b></span>`;
  }).join('');
}

function dateGrid(state, summary) {
  const days = dataDays(state.summary);
  const dates = calendarDays(summary);
  if (state.mode === 'week') {
    return `<div class="financial-calendar-week" data-render-scroll-key="financial-calendar:week:${summary.start}" aria-label="周历">${dates.map(date => `<button type="button" id="financial-calendar-pick-${date}" class="financial-calendar-week-day${date === state.today ? ' is-today' : ''}" data-financial-calendar-action="day" data-date="${date}"${date === state.today ? ' aria-current="date"' : ''}><span class="financial-calendar-week-heading"><strong>${weekCardDate(date)}</strong> <span>周${WEEKDAYS[weekday(date)]}</span></span>${countRows(days.get(date), false)}</button>`).join('')}</div>`;
  }
  const leading = weekday(summary.start), trailing = 6 - weekday(summary.end);
  const padding = count => '<span class="financial-calendar-padding" aria-hidden="true"></span>'.repeat(count);
  return `<div class="financial-calendar-month-scroll" data-render-scroll-key="financial-calendar:month:${summary.start}" aria-label="月历"><div class="financial-calendar-month">${WEEKDAYS.map(day => `<span class="financial-calendar-weekday">${day}</span>`).join('')}${padding(leading)}${dates.map(date => `<button type="button" id="financial-calendar-pick-${date}" class="financial-calendar-month-day" data-financial-calendar-action="day" data-date="${date}" aria-pressed="${date === state.date}"${date === state.today ? ' aria-current="date"' : ''}><strong>${Number(date.slice(8))}</strong><span class="financial-calendar-month-counts">${countRows(days.get(date), true)}</span></button>`).join('')}${padding(trailing)}</div></div>`;
}

function choiceGroup(action, label, options, selected, className = '') {
  return `<div class="financial-calendar-choices ${className}" role="group" aria-label="${label}">${Object.entries(options).map(([value, text]) => `<button type="button" id="financial-calendar-${action}-${value}" data-financial-calendar-action="${action}" data-value="${value}" aria-pressed="${selected === value}">${text}</button>`).join('')}</div>`;
}

function categoryFilters(state) {
  const { category, market, subtype, holdingType, filterSet } = state;
  const marketControl = category === 'economic' ? '' : `<label class="financial-calendar-market">市场<select id="financial-calendar-market" data-financial-calendar-market aria-label="市场">${Object.entries(MARKETS).map(([value, label]) => `<option value="${value}"${market === value ? ' selected' : ''}>${label}</option>`).join('')}</select></label>`;
  const filters = SUBTYPES[category] ? choiceGroup('subtype', CATEGORIES[category] + '类型', SUBTYPES[category], subtype)
    : category === 'inst' ? `${choiceGroup('holding', '持仓变动', HOLDINGS, holdingType)}${choiceGroup('fund-set', '基金范围', FILTER_SETS, filterSet)}` : '';
  return `<div class="financial-calendar-filters"><div class="financial-calendar-category-row">${choiceGroup('category', '财经日历类别', CATEGORIES, category, 'financial-calendar-categories')}${marketControl}</div>${filters ? `<div class="financial-calendar-subfilters">${filters}</div>` : ''}</div>`;
}

function urlLink(value, label) {
  if (typeof value !== 'string') return e(label);
  try {
    const url = new URL(value);
    if (['https:', 'http:'].includes(url.protocol) && !url.username && !url.password) {
      return `<a href="${e(url.href)}" target="_blank" rel="noopener noreferrer">${e(label)}</a>`;
    }
  } catch { /* Invalid source metadata is displayed without a link. */ }
  return e(label);
}

function eventCell(row, sources) {
  const source = sources.get(row.source_id);
  const sourceText = source?.label || row.source_id;
  const time = typeof row.time === 'string' && row.time ? row.time : '时间未提供';
  const end = isDate(row.end_date) && row.end_date > row.date ? ` · 至${shortDate(row.end_date)}` : '';
  const observed = stamp(row.observed_at || source?.observed_at);
  return `<span class="financial-calendar-time">${e(time + end)}</span><strong>${e(row.title || '名称未提供')}</strong>${sourceText ? `<small>${urlLink(row.source_url || source?.url, sourceText)}${observed ? ` · ${e(observed)}` : ''}</small>` : ''}`;
}

function fieldCell(value) {
  return (typeof value === 'string' && value.trim() || typeof value === 'number' && Number.isFinite(value)) ? e(String(value)) : '—';
}

function eventTable({ columns, items, sources, state, date, empty }) {
  const scrollKey = ['financial-calendar', 'table', state.category, state.subtype || '', state.market || 'all', date].join(':');
  const rows = items.map(row => `<tr>${columns.map(([key]) => {
    if (key === 'event') return `<td>${eventCell(row, sources)}</td>`;
    if (state.category === 'inst' && key === 'institution') return `<td>${eventCell({ ...row, title: row.institution || row.title }, sources)}</td>`;
    return `<td>${fieldCell(row[key])}</td>`;
  }).join('')}</tr>`).join('');
  return `<div class="financial-calendar-table-scroll" id="financial-calendar-table-${date}" data-render-scroll-key="${e(scrollKey)}" tabindex="0" role="region" aria-labelledby="financial-calendar-heading-${date}"><table class="financial-calendar-table"><thead><tr>${columns.map(([, label]) => `<th scope="col">${label}</th>`).join('')}</tr></thead><tbody>${rows || `<tr><td class="financial-calendar-empty" colspan="${columns.length}">${e(empty)}</td></tr>`}</tbody></table></div>`;
}

function sourceFooter(sources) {
  if (!sources.length) return '';
  return `<div class="financial-calendar-sources"><strong>数据来源（北京时间）</strong><ul>${sources.map(source => {
    const observed = stamp(source.observed_at);
    return `<li>${urlLink(source.url, source.label || source.id)}${observed ? ` · ${e(observed)}` : ''}${Object.hasOwn(STATUS, source.status) ? ` · ${STATUS[source.status]}` : ''}</li>`;
  }).join('')}</ul></div>`;
}

function dayCards(state, dateRange) {
  const eventDays = dataDays(state.events);
  const listedSources = state.events?.sources || [];
  const sources = new Map(listedSources.map(source => [source.id, source]));
  const columns = COLUMNS[state.subtype] || COLUMNS[state.category] || COLUMNS.economic;
  return calendarDays(dateRange).map(date => {
    const day = eventDays.get(date), items = Array.isArray(day?.items) ? day.items : [];
    const status = Object.hasOwn(STATUS, day?.status) ? STATUS[day.status] : '';
    const busy = state.pageLoading?.has(date);
    const error = state.pageErrors?.get(date);
    const hasMore = day?.has_more && state.events?.snapshot_id;
    const count = Number.isSafeInteger(day?.total) ? `${day.total > 0 && day.status !== 'covered' ? '≥' : ''}${day.total} 条` : '';
    const header = [count, items.length && day.status !== 'covered' ? status : ''].filter(Boolean).join(' · ');
    const empty = state.eventsLoading ? '正在读取…' : day?.status === 'covered' ? '当天没有事件' : status || '未取得该日数据';
    return `<section class="financial-calendar-day-card" id="financial-calendar-events-${date}" aria-labelledby="financial-calendar-heading-${date}"><header><h3 id="financial-calendar-heading-${date}">${shortDate(date)} <span>周${WEEKDAYS[weekday(date)]}</span></h3><span>${header}</span></header>${eventTable({ columns, items, sources, state, date, empty })}${error ? `<div class="financial-calendar-page-error" role="status">${e(error.message)}${error.reload ? ' <button type="button" data-financial-calendar-action="retry-events">重新读取</button>' : ''}</div>` : ''}${hasMore && !error?.reload ? `<button type="button" id="financial-calendar-more-${date}" class="financial-calendar-more" data-financial-calendar-action="more" data-date="${date}" aria-disabled="${Boolean(busy)}">${busy ? '正在读取…' : '加载更多'}</button>` : ''}</section>`;
  }).join('') + sourceFooter(listedSources);
}

function summaryStatus(summary) {
  if (!summary) return '';
  const statuses = new Set([...summary.days, ...summary.sources].map(item => item.status));
  const labels = [statuses.has('stale') && '部分来源已陈旧', statuses.has('unavailable') && '部分来源暂不可用'].filter(Boolean);
  return labels.length ? `<p class="financial-calendar-summary-status" role="status">经济数据：${labels.join('；')}</p>` : '';
}

export function renderFinancialCalendar(input = {}) {
  const today = isDate(input.today) ? input.today : BEIJING_DATE.format(new Date());
  const state = { ...input, today, date: isDate(input.date) ? input.date : today,
    mode: input.mode === 'month' ? 'month' : 'week', category: Object.hasOwn(CATEGORIES, input.category) ? input.category : 'economic',
  };
  const { summary, events } = ranges(state.date, state.mode);
  const period = `${longDate(summary.start)} - ${longDate(summary.end)}`;
  return `<section class="financial-calendar" aria-labelledby="financial-calendar-title">
    <h1 id="financial-calendar-title">财经日历</h1>
    <div class="financial-calendar-toolbar">
      <div class="financial-calendar-period">
        <button type="button" id="financial-calendar-today" data-financial-calendar-action="today">今日</button>
        <button type="button" id="financial-calendar-prev" data-financial-calendar-action="prev" aria-label="上一页"><span aria-hidden="true">‹</span></button>
        <strong aria-live="polite">${period}</strong>
        <button type="button" id="financial-calendar-next" data-financial-calendar-action="next" aria-label="下一页"><span aria-hidden="true">›</span></button>
      </div>
      ${choiceGroup('mode', '日历视图', { week: '周历', month: '月历' }, state.mode, 'financial-calendar-modes')}
    </div>
    <div aria-busy="${Boolean(state.summaryLoading)}">${dateGrid(state, summary)}<p class="financial-calendar-count-key">— 未覆盖 · ≥ 已观察条数，覆盖不完整</p>${summaryStatus(state.summary)}</div>
    ${state.summaryError ? `<p class="financial-calendar-read-error" role="status">${e(state.summaryError)} <button type="button" data-financial-calendar-action="retry-summary">重新读取</button></p>` : ''}
    ${categoryFilters(state)}
    <div class="financial-calendar-event-list" aria-busy="${Boolean(state.eventsLoading)}">
      ${state.eventsError ? `<p class="financial-calendar-read-error" role="status">${e(state.eventsError)} <button type="button" data-financial-calendar-action="retry-events">重新读取</button></p>` : dayCards(state, events)}
    </div>
  </section>`;
}

export function createFinancialCalendarController({
  api, onChange = () => {}, now = () => new Date(), getAccount = () => globalThis.__RWB_USER_ID__ || 'local',
  documentRef = globalThis.document, logger = safeLog,
} = {}) {
  if (!api?.request) throw new TypeError('financial calendar API request is required');
  const state = { mode: 'week', category: 'economic', market: 'all', subtype: '', holdingType: 'all', filterSet: 'all',
    date: '', today: '', summary: null, events: null, summaryLoading: false, eventsLoading: false,
    summaryError: '', eventsError: '', pageLoading: new Set(), pageErrors: new Map() };
  const requests = new Map(), pages = new Map();
  let owner, active = false;
  const account = () => String(getAccount());
  const current = () => active && owner === account();
  const notify = () => { if (current()) onChange(); };
  const stop = key => { requests.get(key)?.abort(); requests.delete(key); };
  function clearPages() {
    for (const date of state.pageLoading) stop(date);
    state.pageLoading.clear(); state.pageErrors.clear(); pages.clear();
  }
  function cancel() {
    active = false;
    for (const key of requests.keys()) stop(key);
    clearPages();
    Object.assign(state, { summary: null, events: null, summaryLoading: false, eventsLoading: false, summaryError: '', eventsError: '' });
  }
  function start(key) {
    stop(key);
    const abort = new AbortController();
    requests.set(key, abort);
    return abort;
  }
  const stillCurrent = (key, abort) => current() && requests.get(key) === abort;
  function accessChanged(error) {
    if (error?.status !== 401 && error?.status !== 403) return false;
    cancel();
    if (owner === account()) {
      state.eventsError = '账号权限已变化，请重新加载页面。';
      onChange();
    }
    return true;
  }
  function params(view, range) {
    const query = new URLSearchParams({ view, ...range });
    if (view === 'summary') return query;
    query.set('category', state.category);
    if (state.category !== 'economic') query.set('market', state.market);
    if (state.subtype) query.set('subtype', state.subtype);
    if (state.category === 'inst') {
      query.set('holding_type', state.holdingType);
      query.set('filter_set', state.filterSet);
    }
    return query;
  }
  async function get(query, signal) {
    const result = await api.request(`${ENDPOINT}?${query}`, { signal });
    const validDays = Array.isArray(result?.days) && result.days.every(day => isDate(day?.date)
      && (query.get('view') === 'summary' || (Array.isArray(day.items) && day.items.every(row => typeof row?.id === 'string'))));
    if (!validDays || !Array.isArray(result?.sources) || !result.sources.every(source => typeof source?.id === 'string')) {
      throw new TypeError('calendar response is invalid');
    }
    return result;
  }
  async function read(view) {
    if (!current()) return;
    if (view === 'events') clearPages();
    const loading = `${view}Loading`, errorKey = `${view}Error`;
    const abort = start(view);
    state[view] = null; state[loading] = true; state[errorKey] = '';
    const query = params(view, ranges(state.date, state.mode)[view]);
    notify();
    try {
      const result = await get(query, abort.signal);
      if (stillCurrent(view, abort)) state[view] = result;
    } catch (error) {
      if (!stillCurrent(view, abort) || error?.name === 'AbortError') return;
      logger('financial_calendar_read_failed', { status: error?.status || 'failed', method: 'GET' });
      if (!accessChanged(error)) state[errorKey] = view === 'summary' ? '日历计数读取失败。' : '事件列表读取失败。';
    } finally {
      if (stillCurrent(view, abort)) { requests.delete(view); state[loading] = false; notify(); }
    }
  }
  async function activate() {
    cancel(); owner = account(); active = true;
    const today = BEIJING_DATE.format(now());
    Object.assign(state, { today, date: today, mode: 'week', category: 'economic', market: 'all', subtype: '', holdingType: 'all', filterSet: 'all' });
    await Promise.all([read('summary'), read('events')]);
  }
  async function updatePeriod(date) {
    if (!current() || !isDate(date) || date === state.date) return;
    const before = ranges(state.date, state.mode);
    state.date = date;
    const after = ranges(date, state.mode);
    if (before.summary.start !== after.summary.start) await Promise.all([read('summary'), read('events')]);
    else if (before.events.start !== after.events.start) await read('events');
    else notify();
  }
  async function shiftPeriod(direction) {
    if (!current() || ![-1, 1].includes(direction)) return;
    if (state.mode === 'week') return updatePeriod(addDays(state.date, direction * 7));
    const date = utc(`${state.date.slice(0, 7)}-01`);
    date.setUTCMonth(date.getUTCMonth() + direction);
    return updatePeriod(iso(date));
  }
  async function setMode(mode) {
    if (!current() || !['week', 'month'].includes(mode) || state.mode === mode) return;
    state.mode = mode;
    await Promise.all([read('summary'), read('events')]);
  }
  async function setDay(date) {
    if (!current() || !isDate(date)) return;
    const { start, end } = ranges(state.date, state.mode).summary;
    if (date < start || date > end) return;
    if (state.mode === 'month') return updatePeriod(date);
    documentRef?.getElementById?.(`financial-calendar-events-${date}`)?.scrollIntoView?.({ block: 'start' });
  }
  async function setCategory(category) {
    if (!current() || !Object.hasOwn(CATEGORIES, category) || state.category === category) return;
    state.category = category;
    state.subtype = Object.keys(SUBTYPES[category] || {})[0] || '';
    await read('events');
  }
  async function setFilter(key, value, options) {
    if (!current() || !options || !Object.hasOwn(options, value) || state[key] === value) return;
    state[key] = value;
    await read('events');
  }
  const setMarket = value => state.category !== 'economic' && setFilter('market', value, MARKETS);
  const setSubtype = value => setFilter('subtype', value, SUBTYPES[state.category]);
  const setHoldingType = value => state.category === 'inst' && setFilter('holdingType', value, HOLDINGS);
  const setFilterSet = value => state.category === 'inst' && setFilter('filterSet', value, FILTER_SETS);
  async function loadMore(date) {
    if (!current() || !isDate(date) || state.pageLoading.has(date)) return;
    const snapshot = state.events?.snapshot_id;
    const day = state.events?.days.find(item => item.date === date);
    if (!day?.has_more || !snapshot || state.pageErrors.get(date)?.reload) return;
    const page = (pages.get(date) || 0) + 1;
    const query = params('events', { start: date, end: date });
    query.set('page', page); query.set('snapshot_id', snapshot);
    const abort = start(date);
    state.pageErrors.delete(date); state.pageLoading.add(date); notify();
    try {
      const response = await get(query, abort.signal);
      if (!stillCurrent(date, abort)) return;
      if (response.snapshot_id !== snapshot || response.days.length !== 1 || response.days[0].date !== date || !Array.isArray(response.days[0].items)) {
        throw new TypeError('calendar snapshot response is invalid');
      }
      const next = response.days[0];
      const merged = new Map(day.items.map(row => [row.id, row]));
      for (const row of next.items) if (!merged.has(row.id)) merged.set(row.id, row);
      const items = [...merged.values()];
      state.events = { ...state.events, days: state.events.days.map(item => item.date === date ? { ...next, items } : item) };
      pages.set(date, page);
    } catch (error) {
      if (!stillCurrent(date, abort) || error?.name === 'AbortError') return;
      logger('financial_calendar_page_failed', { status: error?.status || 'failed', method: 'GET' });
      if (!accessChanged(error)) state.pageErrors.set(date, error?.status === 409
        ? { reload: true, message: '分页快照已失效，请重新读取。' }
        : { message: '下一页读取失败，已保留当前列表。' });
    } finally {
      if (stillCurrent(date, abort)) { requests.delete(date); state.pageLoading.delete(date); notify(); }
    }
  }
  function handleClick(event) {
    const target = event.target?.closest?.('[data-financial-calendar-action]');
    if (!target || !current()) return false;
    const { financialCalendarAction: action, value, date } = target.dataset;
    if (action === 'today') { state.today = BEIJING_DATE.format(now()); void updatePeriod(state.today); }
    else if (action === 'prev' || action === 'next') void shiftPeriod(action === 'prev' ? -1 : 1);
    else if (action === 'mode') void setMode(value);
    else if (action === 'day') void setDay(date);
    else if (action === 'category') void setCategory(value);
    else if (action === 'subtype') void setSubtype(value);
    else if (action === 'holding') void setHoldingType(value);
    else if (action === 'fund-set') void setFilterSet(value);
    else if (action === 'more') void loadMore(date);
    else if (action === 'retry-summary' || action === 'retry-events') void read(action.slice(6));
    else return false;
    return true;
  }
  function handleChange(event) {
    if (!current() || !event.target?.matches?.('[data-financial-calendar-market]')) return false;
    void setMarket(event.target.value); return true;
  }
  return { state, activate, cancel, setMode, shiftPeriod, setDay, setCategory, setMarket, setSubtype, setHoldingType, setFilterSet, loadMore, handleClick, handleChange };
}
