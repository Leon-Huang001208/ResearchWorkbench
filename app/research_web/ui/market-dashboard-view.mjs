import { escapeHTML as e } from './markdown.mjs';
import { AXIS_LABELS, GLOBAL_MARKETS, CATEGORIES, numeric, payload, closedBars, indexQuote, scoreProjection, eventLane, timelineRange, timelineTicks, eventSourceDetails, eventPointDate, DAY_WIDTH, DAY_MS, FIRST_DAY, LAST_DAY, eventDays, eventsOnDay, calendarStatus, exchangeClosure, CALENDAR_LABELS, closeSeries } from './market-dashboard-model.mjs';

const n = (value, digits = 2) => numeric(value) === null ? '—' : value.toLocaleString('zh-CN', { maximumFractionDigits: digits, minimumFractionDigits: digits });
const pct = value => numeric(value) === null ? '—' : `${value > 0 ? '+' : ''}${n(value)}%`;
const tone = value => numeric(value) === null || value === 0 ? 'flat' : value > 0 ? 'up' : 'down';
const sourceText = value => typeof value === 'string' ? value : value?.name || value?.provider || value?.url || '来源未提供';
const gaps = value => Array.isArray(value) ? value.map(item => typeof item === 'string' ? item : item?.reason || item?.code || JSON.stringify(item)).join('；') : typeof value === 'string' ? value : value ? JSON.stringify(value) : '';
const rowsFor = state => state.snapshot?.sections?.['indices:global-v1']?.rows || [];
const btn = (action, label, extra = '') => `<button type="button" class="button secondary small" data-md-action="${action}" ${extra}>${label}</button>`;
function scoreEvidence(state, index) {
  if (state.scores[index]) return state.scores[index];
  if (state.errors?.[`score:${index}`]) return { status: 'DETAIL_UNAVAILABLE', reason: '评分详情读取失败，无法核验已保存运行的资格。' };
  if (state.scoreCoverage?.complete !== true) return { status: 'UNKNOWN', reason: '评分历史尚未完整读取，无法确认该指数有无已保存运行。' };
  if (state.scoreCoverage.indices?.includes(index)) return { status: 'DETAIL_PENDING', reason: '已找到该指数的保存记录，评分详情尚未完整读取。' };
  return { status: 'EMPTY', reason: '完整历史读取后未发现该指数的已保存运行。' };
}
export function dashboardTabs(view = 'dashboard') {
  return `<nav class="market-tabs md-tabs" aria-label="全市场概览页面">${[['dashboard', '综合总览'], ['overview', '行情分析'], ['quotes', '沪深北行情'], ['sectors', '板块与资金'], ['workbench', '研究工作台']].map(([id, label]) => `<a href="#/market${id === 'dashboard' ? '' : `?view=${id}`}" ${view === id ? 'class="active" aria-current="page"' : ''}>${label}</a>`).join('')}</nav>`;
}
function header(view, actions = '') {
  return `<header class="market-page-heading md-heading"><div><p class="market-eyebrow">GLOBAL MARKET OBSERVATORY</p><h1>全市场概览</h1><p class="market-subtitle">市场状态、研究证据与事件脉络</p></div><div class="market-actions">${actions}</div></header>${dashboardTabs(view)}`;
}
function sparkline(bars, row, calendar) {
  const { values, breaks } = closeSeries(bars, row, calendar);
  if (!values.length) return '<p class="md-chart-empty">没有取得已收盘日线，暂无曲线。</p>';
  const last = values.at(-1), first = values[0];
  const low = Math.min(...values.map(bar => bar.close)), high = Math.max(...values.map(bar => bar.close));
  const margin = Math.max((high - low) * 0.12, high * 0.001), min = low - margin, max = high + margin;
  const x = index => 57 + index * 232 / Math.max(1, values.length - 1);
  const y = close => 82 - (close - min) / (max - min) * 70;
  const pointLabel = bar => `${bar.date} 收盘 ${n(bar.close)} 点`;
  const grid = [max, (max + min) / 2, min].map(value => `<line x1="57" x2="289" y1="${y(value)}" y2="${y(value)}" class="md-gridline"/><text x="54" y="${y(value) + 3}" text-anchor="end">${n(value)}</text>`).join('');
  const path = values.map((bar, index) => `${index === 0 || breaks.has(index) ? 'M' : 'L'}${x(index).toFixed(2)} ${y(bar.close).toFixed(2)}`).join(' ');
  const points = values.map((bar, index) => `<button type="button" class="md-chart-point" data-md-action="chart-point" data-md-focus="chart:${e(row.index_id)}:${e(bar.date)}" data-point-label="${e(pointLabel(bar))}" aria-label="${e(pointLabel(bar))}" aria-pressed="${bar === last}" tabindex="${bar === last ? '0' : '-1'}" style="left:${x(index) / 3}%;top:${y(bar.close)}%"></button>`).join('');
  const chart = values.length < 2 ? '<p class="md-chart-empty">仅取得 1 个收盘日，暂无区间曲线。</p>' : `<div class="md-chart-plot"><svg viewBox="0 0 300 100" aria-hidden="true">${grid}<path d="${path}" fill="none" stroke="currentColor" stroke-width="1.5"/>${values.map((bar, index) => `<circle cx="${x(index)}" cy="${y(bar.close)}" r="1.9" fill="currentColor"/>`).join('')}<text x="57" y="96">${e(first.date.slice(5))}</text><text x="289" y="96" text-anchor="end">${e(last.date.slice(5))}</text></svg><div class="md-chart-points" role="group" aria-label="逐日收盘点位，左右方向键切换">${points}</div></div>`;
  return `<div class="md-chart-caption"><span>收盘价（指数点）</span><span>${values.length} 个已收盘交易日${values.length > 1 ? ` · 首尾 ${pct((last.close / first.close - 1) * 100)}` : ''}</span></div>${chart}<output class="md-chart-value" data-md-chart-value aria-live="polite">${e(pointLabel(last))}</output><small>${e(first.date)} — ${e(last.date)} · ${e(sourceText(row.daily_source))}${breaks.size ? ' · 跨缺日／未核验交易日已断线' : ''}${values.length < 20 ? ' · 历史不足 20 日' : ''}</small>`;
}
const AXIS_STATUS = { NOT_IMPORTED: '尚未导入', SOURCE_UNAVAILABLE: '来源不可用', INSUFFICIENT_SAMPLE: '样本不足', RESEARCH_ONLY_SOURCE: '原值可核验，来源未准入评分', NOT_ADMITTED: '未准入', DATA_INELIGIBLE: '证据不合格', VALIDATION_FAILED: '验证失败', QUALIFIED: '证据已核验' };
const AXIS_REASON = { normalization_history_insufficient: '历史指标观测不足', source_not_admitted: '来源未准入', source_unavailable: '来源不可用', host_factor_evidence_not_admitted: '缺少有权的 DataHub 因子绑定', provider_not_in_frozen_profile: '来源不在冻结口径', qualified_factor_input_not_imported: '未登记合格维度输入', closed_price_history_insufficient: '有效收盘日线不足', original_missing_or_changed: '原件无法重新核验' };
function axisUnit(unit) {
  return { percent: '%', ratio: '（比例）', CNY: ' 元', multiple: ' 倍' }[unit] || '';
}
function scorePanel(state, market, row) {
  const score = scoreProjection(state.scores[row.index_id], row, state.modes[market.id] || 'auto', state.replay), mode = score.mode;
  const observed = !state.replay && mode === 'research' ? state.observations?.[row.index_id] : null;
  const axes = Object.entries(AXIS_LABELS).map(([key, label]) => {
    const axis = score.axes[key], value = numeric(axis.score), raw = observed?.axes?.[key];
    const status = value !== null ? (score.historical ? '历史' : mode === 'formal' ? '正式' : '研究') : state.replay ? '不回放' : mode === 'formal' ? '未启用' : AXIS_STATUS[axis.status] || AXIS_STATUS[raw?.status] || '缺失';
    const reasons = [axis.reasons || axis.reason, raw?.reasons].flat().filter(Boolean).map(reason => AXIS_REASON[reason] || reason);
    const actual = numeric(raw?.value);
    return `<div class="md-axis"><span>${label}</span><div class="md-axis-track">${value !== null ? `<i style="width:${Math.max(0, Math.min(100, value))}%"></i>` : ''}</div><span>${n(value, 0)}</span><small title="${e(gaps(reasons))}">${status}</small>${actual !== null || reasons.length ? `<p class="md-axis-evidence">${actual === null ? '' : `原值 ${n(actual)}${axisUnit(raw.unit)} · ${e(raw.as_of || observed?.as_of || '数据日未提供')} · ${e(sourceText(raw.source))}`}${reasons.length ? `${actual === null ? '' : ' · '}${e(gaps(reasons))}` : ''}</p>` : ''}</div>`;
  }).join('');
  return `<div class="md-score-summary"><div><span>${e(score.label)}</span><strong>${n(score.value, 0)}</strong></div><small>${score.date ? `${e(score.date)} · ` : ''}${score.value === null ? '证据或资格不足，保留缺口' : '仅研究参考，不用于跨市场排名'}</small></div><div class="md-score-tabs" role="group" aria-label="${e(market.name)}评分口径">${['research', 'formal'].map(value => `<button type="button" data-md-action="mode" data-market="${market.id}" data-mode="${value}" data-md-focus="mode:${market.id}:${value}" aria-pressed="${mode === value}">${value === 'research' ? '研究分' : '正式分'}</button>`).join('')}</div><div class="md-axes">${axes}</div><p class="md-qualification">${e(score.reasons.length ? gaps(score.reasons) : score.formal ? '服务端正式启用凭据已核验' : '正式评分未启用 · 缺失维度不补中性值、不重配权重')}<br>风险维度高分表示相对稳健。${state.scores[row.index_id] ? '已保存结果与当前资格分开核验。' : e(scoreEvidence(state, row.index_id).reason)} <a href="#/market?view=workbench">研究工作台 →</a></p>`;
}
function eventButton(record, scope, extra = '') {
  const event = payload(record);
  return `<button type="button" data-md-action="event" data-id="${e(record.id)}" data-md-focus="${scope}:${e(record.id)}" ${extra} title="${e(event.title || record.id)}">${e(event.title || record.id)}</button>`;
}
function indexCard(state, market) {
  const id = state.selected[market.id], row = rowsFor(state).find(item => item.index_id === id) || { index_id: id, market: market.id, name: market.indices.find(([key]) => key === id)?.[1] };
  const quote = indexQuote(row, state.replay), section = state.snapshot?.sections?.['indices:global-v1'] || {}, bars = closedBars(row, state.replay);
  const calendar = [...state.events, ...(state.dayEvents || []), ...(state.replayCalendar || [])];
  const notices = state.replay ? calendarStatus(calendar, market.id, state.replay) : [];
  const closure = state.replay && exchangeClosure(calendar, row, state.replay);
  const closureLabel = closure && eventSourceDetails(payload(closure), state.sources).label;
  const missing = state.replay && quote.price === null ? (closure ? `官方日历：所选日期休市（${closureLabel}）` : '未取得所选日期的已收盘行情') : '';
  const notice = notices.length ? notices.map(record => {
    const event = payload(record), source = eventSourceDetails(event, state.sources).label;
    return `${source}：${CALENDAR_LABELS[event.calendar_status]}`;
  }).join('；') + (closure && quote.price !== null ? ' · 与日线记录存在差异，保留实际来源点位' : '') : '';
  const quoteChange = state.replay && closeSeries(bars, row, calendar).breaks.has(Math.min(20, bars.length) - 1) ? null : quote.change_pct;
  const events = state.events.filter(record => payload(record).markets?.includes(market.id)).slice(0, 2);
  return `<article class="md-card"><header><span class="md-market-tag">${market.id}</span><h2>${market.name}</h2><select data-md-index="${market.id}" data-md-focus="index:${market.id}" aria-label="选择${market.name}指数">${market.indices.map(([key, label]) => `<option value="${key}" ${key === id ? 'selected' : ''}>${label}</option>`).join('')}</select></header><div class="md-quote"><span>${e(row.name || id)} <small>${market.currency}</small></span><strong class="market-${tone(missing ? null : quoteChange)}">${n(missing ? null : quote.price)}</strong>${missing ? `<p>${missing}${quote.reference_close ? ` · 参考前收 ${e(quote.reference_close.date)} ${n(quote.reference_close.close)} 点` : ''}</p>` : `<div class="market-${tone(quoteChange)}">${n(quoteChange === null ? null : quote.change)} <span>${pct(quoteChange)}</span></div>`}<p>${state.replay ? `回放日期 ${e(state.replay)} · ` : ''}实际行情日 ${e(missing ? '无该日行情' : quote.quote_trade_date || '未提供')}<br>${state.replay ? '收盘记录时间' : '报价时间'}：${e(missing ? '未提供' : quote.as_of || '未提供')}<br>${e(row.timezone || '时区未提供')} · 交易状态待确认<br>${state.replay ? '按已保存日线回放' : `缓存时效：${quote.stale || section.stale || !quote.as_of ? '陈旧／时效待核验' : '缓存报价，按来源时间展示'}`}${notice ? `<br>${e(notice)}` : ''}${row.partial_daily_bar && (!state.replay || row.partial_daily_bar.date <= state.replay) ? `<br>${e(row.partial_daily_bar.date)} 未确认收盘，未进入折线` : ''}</p></div><div class="md-spark">${sparkline(bars, row, calendar)}</div>${scorePanel(state, market, row)}<div class="md-card-events">${events.length ? events.map(event => eventButton(event, `card:${market.id}`)).join('') + '<p>待研究 · 未计分 · 未核验影响统计</p>' : '<p>本窗口暂无已收录的相关事件</p>'}</div><footer><small>报价 ${e(sourceText(quote.source))}<br>日线 ${e(sourceText(row.daily_source))}${row.gaps?.length ? `<br>缺口：${e(gaps(row.gaps))}` : ''}</small>${btn('detail', '查看指数 →', `data-index="${id}"`)}</footer></article>`;
}
function dayPanel(state) {
  const date = state.selectedDate || state.today, all = eventsOnDay(state.dayEvents || [], date);
  const rows = all.filter(record => (!state.market || payload(record).markets?.includes(state.market)) && (!state.category || payload(record).category === state.category));
  const coverage = (Array.isArray(state.coverage?.items) ? state.coverage.items : []).map(payload).filter(item => item.source && (!item.start || item.start <= date) && (!item.end || item.end >= date));
  const map = new Map(coverage.map(item => [item.source, item]));
  const officialIds = new Set(['fed_fomc', 'bls_cpi', 'bls_jobs', 'sse_trading_calendar', 'nyse_trading_calendar', 'hkex_securities_2026', 'hkex_securities_calendar']);
  const sourceRows = (state.sources || []).filter(source => officialIds.has(source.id) || map.has(source.id));
  const statuses = { source_failed: '来源读取失败', failed: '来源读取失败', partial_page: '已读取部分记录' };
  const stateMessage = state.errors?.day ? '该日记录读取失败，不能判定无事件。' : state.dayLoading ? '正在读取选中日期…' : state.dayCursor ? '当前只显示已加载记录，仍可继续读取本日。' : '未收录不表示没有事件。';
  return `<section class="md-day-panel" aria-label="所选日期详情"><header><div><h3>${e(date)} · 当日详情</h3><p>${e(stateMessage)}</p></div>${date > state.today ? '<span>未来日期仅看日程与情景，不显示行情</span>' : btn('view-day', '查看该日行情', 'data-md-focus="view-day"')}</header><div class="md-calendar-summary">${GLOBAL_MARKETS.map(market => {
    const found = calendarStatus(all, market.id, date);
    return `<div><strong>${market.name}</strong>${found.length ? found.map(record => eventButton(record, `calendar:${market.id}`, 'class="button secondary small"')).join('') + `<small>${[...new Set(found.map(record => CALENDAR_LABELS[payload(record).calendar_status]))].join('／')}</small>` : '<span>无已核实的休市／半日市／复市记录</span>'}</div>`;
  }).join('')}</div><div class="md-day-events">${rows.length ? rows.map(record => eventButton(record, 'day-event', 'class="button secondary small"')).join('') : `<p>${state.dayStatus === 'ready' && !state.errors?.day ? '当前筛选下暂无已收录记录。' : e(stateMessage)}</p>`}</div>${state.dayCursor ? btn('more-day', '继续读取本日', state.dayLoading ? 'disabled' : 'data-md-focus="more-day"') : ''}<details class="md-source-coverage" data-md-retain><summary>来源覆盖 · 读取不代表完整</summary>${state.errors?.coverage ? '<p>覆盖读取失败</p>' : sourceRows.length ? `<ul>${sourceRows.map(source => {
    const entry = map.get(source.id), href = eventSourceDetails({ source: source.id }, state.sources).directoryURL;
    return `<li>${href ? `<a href="${e(href)}" target="_blank" rel="noopener noreferrer">${e(source.label || source.id)}</a>` : e(source.label || source.id)} · ${entry ? e(statuses[entry.state || entry.status] || '已登记范围，完整性待核验') : '所选日未登记覆盖'}${entry?.observed_at ? ` · 取得 ${e(entry.observed_at)}` : ''}</li>`;
  }).join('')}</ul>` : '<p>尚无已登记来源覆盖</p>'}<a href="#/market?view=workbench">研究工作台 →</a></details></section>`;
}
function timelineLane(events, key, label, range) {
  const rows = events.map(record => ({ record, span: eventDays(record) })).filter(({ record, span }) => span && eventLane(record) === key).sort((a, b) => a.span.start.localeCompare(b.span.start));
  const slots = [];
  const cards = rows.map(({ record, span }) => {
    const start = span.start < range.start ? range.start : span.start, end = span.end > range.end ? range.end : span.end;
    const from = (Date.parse(start) - Date.parse(range.start)) / DAY_MS, to = (Date.parse(end) - Date.parse(range.start)) / DAY_MS;
    if (from > to) return '';
    let slot = slots.findIndex(last => last < from);
    if (slot < 0) slot = slots.length;
    slots[slot] = to;
    return eventButton(record, 'event', `class="md-time-event md-lane-${key}" style="left:${from * DAY_WIDTH + 3}px;top:${slot * 32 + 28}px;width:${(to - from + 1) * DAY_WIDTH - 6}px"`);
  }).join('');
  return `<div class="md-time-lane" style="min-height:${Math.max(51, slots.length * 32 + 30)}px"><strong>${label}</strong>${cards || '<p>本范围暂无已收录记录</p>'}</div>`;
}
function timeline(state) {
  const range = state.window || timelineRange(state.range, state.anchor || state.today, state.custom);
  const ticks = timelineTicks(range), selected = state.selectedDate || state.today, events = state.events || [], imprecise = events.filter(record => !eventDays(record));
  const lanes = [['macro','宏观'],['policy','政策'],['conflict','地缘与冲突'],['sports','赛事'],['unexpected','灾害与突发'],['continuous','持续事件'],['calendar','交易日历'],['forecast','预测情景'],['other','其他']];
  const dateInput = (name, label, value) => `<label>${label}<input type="date" name="${name}" required min="${FIRST_DAY}" max="${LAST_DAY}" data-md-date-draft="${name}" data-md-focus="input:${name}" value="${e(value)}"></label>`;
  const selects = `<select data-md-filter="range" data-md-focus="filter:range" aria-label="时间范围">${[['month', '前后30天'], ['quarter', '前后90天'], ['year', '前后一年'], ['custom', '自定义范围']].map(([key, label]) => `<option value="${key}" ${key === state.range ? 'selected' : ''}>${label}</option>`).join('')}</select><select data-md-filter="market" data-md-focus="filter:market" aria-label="事件市场"><option value="">全部市场</option>${GLOBAL_MARKETS.map(m => `<option value="${m.id}" ${state.market === m.id ? 'selected' : ''}>${m.name}</option>`).join('')}</select><select data-md-filter="category" data-md-focus="filter:category" aria-label="事件类别"><option value="">全部类别</option>${Object.entries(CATEGORIES).map(([key, label]) => `<option value="${key}" ${state.category === key ? 'selected' : ''}>${label}</option>`).join('')}</select>`;
  return `<section id="md-timeline-date" class="md-timeline"><header><div><p class="market-eyebrow">EVENTS & CALENDAR</p><h2>市场事件与交易日历</h2><p>逐日浏览，点击日期查看详情。今日按北京时间标记。</p></div><div class="md-timeline-controls">${selects}</div></header><div class="md-date-controls"><div>${btn('previous-month','← 上一月','data-md-focus="previous-month"')}${btn('today','今天','data-md-focus="today"')}${btn('next-month','下一月 →','data-md-focus="next-month"')}</div><form data-md-select-date>${dateInput('date','选择日期',state.dateDraft ?? selected)}<button class="button secondary small" data-md-focus="select-date">定位日期</button></form><form data-md-dates>${dateInput('start','开始',state.customDraft?.start ?? range.start)}${dateInput('end','结束',state.customDraft?.end ?? range.end)}<button class="button secondary small" data-md-focus="apply-range">应用范围</button></form></div>${state.dateError ? `<p class="md-date-error" role="alert">${e(state.dateError)}</p>` : ''}${dayPanel(state)}<div class="md-time-ruler"><span>${e(range.start)} 至 ${e(range.end)}</span><span>横向滚动查看日期 · 方向键逐日移动</span></div><div class="md-time-scroll" tabindex="0" role="region" aria-label="日期与事件横向滚动区"><div class="md-time-canvas" style="--md-day-width:${DAY_WIDTH}px;width:${ticks.length * DAY_WIDTH}px"><div class="md-date-ticks" aria-label="日期与星期刻度">${ticks.map(tick => `<button type="button" data-md-action="day" data-date="${e(tick.date)}" data-md-focus="day:${e(tick.date)}" aria-label="${e(tick.date)} ${tick.weekday}${tick.date === state.today ? ' 今天' : ''}" aria-pressed="${tick.date === selected}" tabindex="${tick.date === selected ? '0' : '-1'}"${tick.date === state.today ? ' aria-current="date"' : ''}>${e(tick.date.slice(5))}<small>${tick.weekday}</small></button>`).join('')}</div>${lanes.map(([key,label]) => timelineLane(events,key,label,range)).join('')}</div></div>${imprecise.length ? `<section class="md-imprecise-events" aria-label="时间待精确的事件"><h3>月份区间／时间待精确</h3><p>保留原时间精度，不补造具体日期。</p>${imprecise.map(record => eventButton(record, 'imprecise', 'class="button secondary small"')).join('')}</section>` : ''}<footer><span>${events.length} 条已加载记录 · ${state.errors?.events ? '范围读取失败' : state.eventsLoading ? '正在读取范围' : state.nextCursor ? '范围未加载完' : '未收录不表示没有事件'}</span>${state.nextCursor ? btn('more', '加载更多事件', state.eventsLoading ? 'disabled' : 'data-md-focus="more"') : ''}<a href="#/intel/timeline">完整事件时间线 →</a></footer></section>`;
}
function candleChart(state, row) {
  const bars = closedBars(row, state.replay).slice(-60);
  if (!bars.length) return '<p class="md-chart-empty">没有取得可绘制的真实 OHLC 日线</p>';
  const low = Math.min(...bars.map(bar => bar.low)), high = Math.max(...bars.map(bar => bar.high)), span = high - low || 1;
  const y = value => 220 - (value - low) / span * 190, x = i => 46 + i * 700 / Math.max(1, bars.length - 1), volumeMax = Math.max(1, ...bars.map(bar => numeric(bar.volume) ?? 0));
  const marks = state.events.filter(record => payload(record).markets?.includes(row.market)).flatMap(record => { const point = eventPointDate(record); if (!point) return []; const date = point.slice(0, 10), index = bars.findIndex(bar => bar.date === date); return index < 0 ? [] : [`<circle cx="${x(index)}" cy="17" r="5" fill="var(--blue)"><title>${e(payload(record).title)} · ${e(date)}</title></circle>`]; }).join('');
  return `<svg class="md-candles" viewBox="0 0 800 330" role="img" aria-label="真实开高低收与成交量；上方圆点为同日事件"><text x="4" y="35">${n(high)}</text><text x="4" y="220">${n(low)}</text>${marks}${bars.map((bar, i) => `<g class="market-${tone(bar.close - bar.open)}"><line x1="${x(i)}" x2="${x(i)}" y1="${y(bar.high)}" y2="${y(bar.low)}" stroke="currentColor"/><rect x="${x(i) - 3}" y="${Math.min(y(bar.open), y(bar.close))}" width="6" height="${Math.max(1, Math.abs(y(bar.open) - y(bar.close)))}" fill="currentColor"/>${numeric(bar.volume) !== null ? `<rect x="${x(i) - 3}" y="${300 - bar.volume / volumeMax * 55}" height="${bar.volume / volumeMax * 55}" width="6" fill="currentColor"/>` : ''}<title>${e(bar.date)} 开${n(bar.open)} 高${n(bar.high)} 低${n(bar.low)} 收${n(bar.close)} 量${n(bar.volume, 0)}</title></g>`).join('')}<text x="45" y="325">${e(bars[0].date)}</text><text x="665" y="325">${e(bars.at(-1).date)}</text></svg><p class="md-qualification">上：真实 OHLC；下：来源成交量，缺量不补值。事件圆点仅同日事实标注，不代表当时已知。已收盘日线 ${bars.length} 根；当日未收盘柱单独保留，不混入本图。</p><details><summary>查看日线原始数值与来源</summary><div class="table-scroll"><table><thead><tr><th>日期</th><th>开</th><th>高</th><th>低</th><th>收</th><th>量</th></tr></thead><tbody>${bars.map(bar => `<tr><td>${e(bar.date)}</td>${[bar.open, bar.high, bar.low, bar.close, bar.volume].map(value => `<td>${n(value)}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details>`;
}
function detail(state) {
  const row = rowsFor(state).find(item => item.index_id === state.detail) || { index_id: state.detail }, market = GLOBAL_MARKETS.find(m => m.indices.some(([id]) => id === state.detail));
  return `<section class="md-detail">${btn('back', '← 返回综合总览')}<h2>${e(row.name || state.detail)}</h2><div class="md-detail-grid"><article class="md-card md-detail-chart">${candleChart(state, row)}<p>日线来源 ${e(sourceText(row.daily_source))} · ${e(row.daily_history_status || '状态未提供')}</p>${row.partial_daily_bar ? `<p>单独的未收盘日线：${e(row.partial_daily_bar.date || '')}；不参与已收盘曲线和历史回放。</p>` : ''}</article><article class="md-card md-detail-score">${market ? scorePanel(state, market, row) : ''}<details><summary>评分运行、资格和来源证据</summary><pre>${e(JSON.stringify(scoreEvidence(state, state.detail), null, 2))}</pre></details><a href="#/simulation/scores">进入六维评分研究 →</a></article></div></section>`;
}
function drawer(state) {
  if (!state.drawer) return '';
  const record = state.drawer, event = payload(record), source = eventSourceDetails(event, state.sources || []);
  return `<div class="md-drawer-backdrop"><section class="md-drawer" role="dialog" aria-modal="true" aria-labelledby="md-event-title" tabindex="-1"><header><span>事件事实与研究资格</span>${btn('close', '关闭 ×', 'aria-label="关闭事件详情" data-md-focus="drawer:close"')}</header><h2 id="md-event-title">${e(event.title || record.id)}</h2><p>${e(event.description || '尚无事实说明')}</p><dl>${[['发生时间', `${event.occurrence_start || '待确认'} — ${event.occurrence_end || '未提供结束时间'}`], ['类别／状态', `${CATEGORIES[event.category] || event.category || '待确认'} · ${event.lifecycle || '待确认'}`], ['相关市场', (event.markets || []).join('、') || '待确认'], ...(event.calendar_close_local ? [['公告提前收盘', [event.calendar_close_local, event.calendar_timezone].filter(Boolean).join(' ')]] : []), ['事实确认', event.admission || '待确认'], ['记录版本', `${record.id || ''} · v${record.revision || '未知'}`]].map(([key, value]) => `<div><dt>${key}</dt><dd>${e(value)}</dd></div>`).join('')}</dl><h3>来源与公开时间</h3><p>${e(source.label)}${source.originalURL ? ` <a href="${e(source.originalURL)}" target="_blank" rel="noopener noreferrer" data-md-focus="drawer:source">该记录的公开来源 ↗</a>` : source.directoryURL ? ` <a href="${e(source.directoryURL)}" target="_blank" rel="noopener noreferrer" data-md-focus="drawer:source">来源目录页面 ↗</a>` : ' · 来源目录链接未解析'}</p><dl><div><dt>来源公开时间</dt><dd>${e(source.published || '来源未提供公布时间')}</dd></div><div><dt>首次取得时间</dt><dd>${e(source.observed || '首次取得时间未提供')}</dd></div></dl>${source.originalURL ? '<p>公开来源与已归档原件分开保留；证据引用可用于核对版本。</p>' : '<p>来源目录页面不代表本事件版本的原件。该版本原件链接未提供／未解析；证据引用仅按记录展示，不构造下载地址。</p>'}${source.refs.length ? `<details open data-md-details="refs"><summary data-md-focus="drawer:refs">该版本证据引用</summary><pre>${e(JSON.stringify(source.refs, null, 2))}</pre></details>` : '<p>该版本暂无原件证据引用。</p>'}${record.evidence_gaps?.length ? `<p>证据缺口：${e(gaps(record.evidence_gaps))}</p>` : ''}<h3>窗口与历史研究</h3><p>固定研究窗口须由已冻结的研究运行提供。本事件没有在此页核验关联运行，样本、均值、胜率与评分修正均为待验证。</p><p>事实确认不等于历史 PIT，不等于正式评分准入。预测情景不会显示成已发生事实。</p><details data-md-details="facts"><summary data-md-focus="drawer:facts">完整事实、来源与资格字段</summary><pre>${e(JSON.stringify(record, null, 2))}</pre></details><div class="md-drawer-actions"><a class="button secondary" href="#/simulation/events" data-md-focus="drawer:research">事件与日历研究</a><a href="#/intel/timeline" data-md-focus="drawer:timeline">完整事件时间线</a></div></section></div>`;
}
export function workbenchPage(bootstrap = '') {
  return `<div class="market-page md-page">${header('workbench')}<section class="md-workbench"><p class="market-eyebrow">RESEARCH WORKSPACE</p><h2>从真实资料与冻结证据开始研究</h2><p>资料登记、事件审核、固定窗口研究及六维评分沿用已有研究流程。</p><div class="md-workbench-links"><a href="#/intel/timeline">事件事实、来源与审核 →</a><a href="#/simulation/events">事件与日历窗口研究 →</a><a href="#/simulation/scores">六维评分与验证证据 →</a><a href="#/assets">资产行情与研究资料 →</a></div><p>进入页面只读取已存资料；创建研究、采集和计算仍须在对应界面明确执行。</p>${bootstrap}</section></div>`;
}
export function dashboardPage(state) {
  const errors = [state.error, ...Object.entries(state.errors || {}).map(([key, message]) => `${key}：${message}`)].filter(Boolean);
  return `<div class="market-page md-page" aria-busy="${Boolean(state.loading)}">${header('dashboard', `${btn('refresh', state.refreshing ? '更新中…' : '刷新全球行情', state.loading || state.refreshing || state.replay ? 'disabled' : '')}<span class="md-readonly">缓存只读 · 不自动采集</span>`)}${state.replay ? `<div class="md-replay-banner" role="status"><strong>历史价格回放 · 截至 ${e(state.replay)}</strong><span>只截断已有已收盘日线；事件资料为当前记录，不声称历史 PIT；评分不回放。</span>${btn('exit-replay', '退出回放')}</div>` : ''}${errors.length ? `<div class="notice warning" role="alert">${errors.map(error => `<p>${e(error)}</p>`).join('')}</div>` : ''}${state.loading ? '<p role="status">正在读取已保存行情、评分资格与事件…</p>' : ''}<div class="md-overview-toolbar"><span>三地市场独立口径 · 不做跨市场分数排名</span><button type="button" data-md-action="jump-date" class="button secondary small">选择时间线日期 ↓</button></div>${state.detail ? detail(state) : `<div class="md-market-grid">${GLOBAL_MARKETS.map(market => indexCard(state, market)).join('')}</div>`}${timeline(state)}<footer class="md-page-footer"><span>仅展示实际缓存与已保存研究 · 缺口保留 · 正式评分须独立启用</span><span>market-six-axis-v1 · 观察日期 ${e(state.today)}</span></footer>${drawer(state)}</div>`;
}
