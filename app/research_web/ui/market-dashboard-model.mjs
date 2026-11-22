/** Display projections only. Never derives a score or treats observed data as PIT. */
export const GLOBAL_MARKETS = [
  { id: 'CN', name: '中国 A 股', currency: 'CNY', indices: [['SSE', '上证综指'], ['CSI300', '沪深300'], ['CHINEXT', '创业板指']] },
  { id: 'US', name: '美国市场', currency: 'USD', indices: [['SP500', '标普500'], ['NASDAQ', '纳斯达克综合'], ['DJI', '道琼斯工业']] },
  { id: 'HK', name: '中国香港', currency: 'HKD', indices: [['HSI', '恒生指数'], ['HSCEI', '恒生国企'], ['HSTECH', '恒生科技']] },
];
export const AXIS_LABELS = { trend: '趋势', breadth: '广度', sentiment: '情绪', funds: '资金', valuation: '估值', risk: '风险' };
export const CATEGORIES = { macro: '宏观', policy: '政策', geopolitics: '地缘', war: '战争', sports: '赛事', disaster: '灾害', unexpected: '突发', calendar: '日历效应', other: '其他' };
export const numeric = value => typeof value === 'number' && Number.isFinite(value) ? value : null;
export const payload = row => row?.payload || row || {};
export const DAY_MS = 86400000;
export const DAY_WIDTH = 64;
export const MAX_WINDOW_DAYS = 731;
export const FIRST_DAY = '1990-01-01';
export const LAST_DAY = '2199-12-31';
const dayStamp = value => Date.parse(value + 'T00:00:00Z');
export function validDate(value) {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    value >= FIRST_DAY && value <= LAST_DAY && Number.isFinite(dayStamp(value)) &&
    new Date(dayStamp(value)).toISOString().slice(0, 10) === value;
}
export function validTimelineRange(range = {}) {
  return validDate(range.start) && validDate(range.end) && range.start <= range.end &&
    (dayStamp(range.end) - dayStamp(range.start)) / DAY_MS < MAX_WINDOW_DAYS;
}
export function calendarToday(now) {
  const fields = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(now);
  const get = key => fields.find(field => field.type === key).value;
  return [get('year'), get('month'), get('day')].join('-');
}
export function offsetDay(date, days) {
  return new Date(dayStamp(date) + days * DAY_MS).toISOString().slice(0, 10);
}
export function offsetMonth(date, months) {
  const [year, month, day] = date.split('-').map(Number);
  const endOfMonth = new Date(Date.UTC(year, month + months, 0)).getUTCDate();
  return new Date(Date.UTC(year, month + months - 1, Math.min(day, endOfMonth))).toISOString().slice(0, 10);
}
export function closedBars(row, cutoff = '') {
  const valid = (Array.isArray(row?.daily_bars) ? row.daily_bars : []).filter(bar => validDate(bar?.date) && bar.date !== row?.partial_daily_bar?.date && (!cutoff || bar.date <= cutoff) && [bar.open, bar.high, bar.low, bar.close].every(value => numeric(value) > 0));
  const counts = new Map();
  for (const bar of valid) counts.set(bar.date, (counts.get(bar.date) || 0) + 1);
  return valid.filter(bar => counts.get(bar.date) === 1).sort((a, b) => a.date.localeCompare(b.date));
}
export function indexQuote(row = {}, cutoff = '') {
  if (!cutoff) return row;
  const bars = closedBars(row, cutoff), last = bars.at(-1), previous = bars.at(-2);
  const chosen = last?.date === cutoff ? last : null;
  return { ...row, price: chosen?.close ?? null, change: chosen && previous ? chosen.close - previous.close : null, change_pct: chosen && previous ? (chosen.close / previous.close - 1) * 100 : null, as_of: chosen?.timestamp || chosen?.date || '', quote_trade_date: chosen?.date || '', source: row.daily_source, stale: true, reference_close: chosen ? null : last || null };
}
export function scoreProjection(record, row = {}, mode = 'auto', replay = '') {
  const result = record?.current_eligibility;
  const isEngine = result?.version === 'market-six-axis-v1' && result.index_id === row.index_id;
  const date = String(result?.as_of || '').slice(0, 10);
  const historical = Boolean(date && date !== row.quote_trade_date);
  // A saved original result is historical evidence; only the server's recomputed
  // eligibility may populate axes. Replay must never borrow future qualification.
  const eligible = isEngine && !replay;
  const complete = eligible && Object.keys(AXIS_LABELS).every(key => numeric(result.axes?.[key]?.score) !== null);
  const formal = complete && Boolean(date && row.quote_trade_date) && !historical && result.formal_score_enabled === true && result.production_enabled === true && result.activation_status === 'ACTIVATED';
  mode = mode === 'auto' ? formal ? 'formal' : 'research' : mode;
  const axes = Object.fromEntries(Object.keys(AXIS_LABELS).map(key => [key, eligible && (mode !== 'formal' || formal) ? result.axes?.[key] || {} : {}]));
  return { axes, date, historical, formal, mode, value: mode === 'formal' ? formal ? numeric(result.effective_score) : null : complete ? numeric(result.research_score) : null, reasons: result?.validation_reasons || result?.reasons || [], label: replay ? '回放不提供历史评分资格' : mode === 'formal' ? formal ? '正式分' : '正式评分未启用' : historical ? '历史研究分' : '研究候选分', result: eligible ? result : null };
}
export function timelineRange(range = 'month', now = new Date(), custom = {}) {
  const anchor = validDate(now) ? now : calendarToday(new Date(now));
  if (range === 'custom' && validTimelineRange(custom)) return { start: custom.start, end: custom.end };
  const days = range === 'quarter' ? 90 : range === 'year' ? 365 : 30;
  return { start: [FIRST_DAY, offsetDay(anchor, -days)].sort().at(-1), end: [LAST_DAY, offsetDay(anchor, days)].sort()[0] };
}
export function eventLane(record) {
  const event = payload(record);
  if (['scenario', 'forecast'].includes(event.lifecycle)) return 'forecast';
  if (['calendar', 'holiday', 'weekday', 'month_end', 'month_start', 'quarter_end', 'quarter_start', 'year_end', 'year_start'].includes(event.category)) return 'calendar';
  if (event.lifecycle === 'ongoing' || event.occurrence_end && event.occurrence_end > event.occurrence_start) return 'continuous';
  if (['geopolitics', 'war'].includes(event.category)) return 'conflict';
  if (['unexpected', 'disaster'].includes(event.category)) return 'unexpected';
  return ['macro', 'policy', 'sports'].includes(event.category) ? event.category : 'other';
}
export function timelineTicks(range) {
  if (!validTimelineRange(range)) return [];
  const start = dayStamp(range.start), days = (dayStamp(range.end) - start) / DAY_MS;
  return Array.from({ length: days + 1 }, (_, index) => {
    const date = new Date(start + index * DAY_MS);
    return { date: date.toISOString().slice(0, 10), weekday: `周${'日一二三四五六'[date.getUTCDay()]}`, index, position: days ? index / days * 100 : 50 };
  });
}
export function eventSourceDetails(event, catalog = []) {
  const source = typeof event.source === 'string' ? event.source : event.source?.id || '';
  const entry = catalog.find(item => item.id === source);
  return { id: source, label: entry?.label || source || '来源尚未提供', directoryURL: /^https?:\/\//.test(entry?.url || '') ? entry.url : '', originalURL: /^https?:\/\//.test(event.source_url || '') ? event.source_url : '', published: event.source_published_at || '', observed: event.first_observed || '', refs: Array.isArray(event.evidence_refs) ? event.evidence_refs : [] };
}
export function eventPointDate(record) {
  const event = payload(record), value = event.occurrence_start;
  if (event.date_precision && !['day', 'minute'].includes(event.date_precision)) return null;
  return /^\d{4}-\d{2}-\d{2}(?:T.*)?$/.test(value || '') && Number.isFinite(Date.parse(value)) ? value : null;
}
export function eventDays(record) {
  const event = payload(record);
  if (event.date_precision === 'interval') {
    const start = event.occurrence_start, end = event.occurrence_end;
    return validDate(start) && validDate(end) && start <= end ? { start, end } : null;
  }
  const point = eventPointDate(record);
  if (!point || !validDate(point.slice(0, 10))) return null;
  const start = point.slice(0, 10), end = String(event.occurrence_end || '').slice(0, 10);
  return { start, end: validDate(end) && end >= start ? end : start };
}
export function eventsOnDay(records, date) {
  return (records || []).filter(record => {
    const days = eventDays(record);
    return days && date >= days.start && date <= days.end;
  });
}
export const CALENDAR_LABELS = { closed: '休市', half_day: '半日市', reopen: '复市', reopened: '复市' };
export function calendarStatus(records, market, day) {
  return eventsOnDay(records, day).filter(record => {
    const event = payload(record);
    return eventLane(record) === 'calendar' && event.admission !== 'rejected' && !event.superseded_by && event.markets?.includes(market) && Object.hasOwn(CALENDAR_LABELS, event.calendar_status);
  });
}
// An exchange announcement is not proof that every index in a market
// stopped trading. Composite indices (and indices with a different venue)
// do not inherit a closure from a market-level notice.
export function exchangeClosure(records, row, day) {
  const exchange = row.index_id === 'SSE' ? 'SSE' : ['HSI', 'HSCEI', 'HSTECH'].includes(row.index_id) ? 'HKEX' : null;
  if (!exchange) return null;
  const sources = exchange === 'SSE' ? ['sse_trading_calendar'] : ['hkex_securities_2026', 'hkex_securities_calendar'];
  return calendarStatus(records, exchange === 'SSE' ? 'CN' : 'HK', day).find(record => {
    const event = payload(record);
    return event.calendar_status === 'closed' && sources.includes(event.source);
  }) || null;
}
export function closeSeries(bars, row, calendar = []) {
  const values = bars.slice(-20), breaks = new Set();
  const reported = new Set((Array.isArray(row?.gaps) ? row.gaps : []).map(gap => gap?.date).filter(validDate));
  values.forEach((bar, index) => {
    if (!index) return;
    let day = offsetDay(values[index - 1].date, 1);
    // Gaps are not interpolated. An intervening weekday is connected only if
    // explicit exchange evidence says it was closed.
    for (; day < bar.date; day = offsetDay(day, 1)) {
      const weekday = new Date(dayStamp(day)).getUTCDay();
      if (reported.has(day) || (weekday !== 0 && weekday !== 6 && !exchangeClosure(calendar, row || {}, day))) { breaks.add(index); break; }
    }
  });
  return { values, breaks };
}
