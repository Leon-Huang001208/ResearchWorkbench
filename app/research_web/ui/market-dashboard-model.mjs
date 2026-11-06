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
export function closedBars(row, cutoff = '') {
  return (Array.isArray(row?.daily_bars) ? row.daily_bars : []).filter(bar => /^\d{4}-\d{2}-\d{2}$/.test(bar.date || '') && (!cutoff || bar.date <= cutoff) && [bar.open, bar.high, bar.low, bar.close].every(value => numeric(value) !== null)).sort((a, b) => a.date.localeCompare(b.date));
}
export function indexQuote(row = {}, cutoff = '') {
  if (!cutoff) return row;
  const bars = closedBars(row, cutoff), last = bars.at(-1), previous = bars.at(-2);
  return { ...row, price: last?.close ?? null, change: last && previous ? last.close - previous.close : null, change_pct: last && previous && previous.close ? (last.close / previous.close - 1) * 100 : null, as_of: last?.timestamp || last?.date || '', quote_trade_date: last?.date || '', source: row.daily_source, stale: true };
}
export function scoreProjection(record, row = {}, mode = 'auto', replay = '') {
  const result = record?.current_eligibility;
  const isEngine = result?.version === 'market-six-axis-v1' && result.index_id === row.index_id;
  const date = String(result?.as_of || '').slice(0, 10);
  const historical = Boolean(date && date !== row.quote_trade_date);
  // A saved original result is historical evidence; only the server's recomputed
  // eligibility may populate axes. Replay must never borrow future qualification.
  const eligible = isEngine && !replay;
  const formal = eligible && Boolean(date && row.quote_trade_date) && !historical && result.formal_score_enabled === true && result.production_enabled === true && result.activation_status === 'ACTIVATED';
  mode = mode === 'auto' ? formal ? 'formal' : 'research' : mode;
  const axes = Object.fromEntries(Object.keys(AXIS_LABELS).map(key => [key, eligible && (mode !== 'formal' || formal) ? result.axes?.[key] || {} : {}]));
  return { axes, date, historical, formal, mode, value: mode === 'formal' ? formal ? numeric(result.effective_score) : null : eligible ? numeric(result.research_score) : null, reasons: result?.validation_reasons || result?.reasons || [], label: replay ? '回放不提供历史评分资格' : mode === 'formal' ? formal ? '正式分' : '正式评分未启用' : historical ? '历史研究分' : '研究候选分', result: eligible ? result : null };
}
export function timelineRange(range = 'month', now = new Date(), custom = {}) {
  const anchor = new Date(now), start = new Date(anchor), end = new Date(anchor);
  if (range === 'custom' && /^\d{4}-\d{2}-\d{2}$/.test(custom.start || '') && /^\d{4}-\d{2}-\d{2}$/.test(custom.end || '') && custom.start <= custom.end) return { start: custom.start, end: custom.end };
  const days = range === 'quarter' ? 90 : range === 'year' ? 365 : 30;
  start.setUTCDate(start.getUTCDate() - days); end.setUTCDate(end.getUTCDate() + days);
  return { start: start.toISOString().slice(0, 10), end: end.toISOString().slice(0, 10) };
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
  const start = Date.parse(range.start), end = Date.parse(range.end), days = Math.round((end - start) / 86400000);
  if (!Number.isFinite(days) || days < 0) return [];
  const step = Math.max(1, Math.ceil(days / 8));
  const offsets = [...new Set([...Array.from({ length: Math.floor(days / step) + 1 }, (_, i) => i * step), days])];
  return offsets.map(offset => { const date = new Date(start + offset * 86400000); return { date: date.toISOString().slice(0, 10), weekday: `周${'日一二三四五六'[date.getUTCDay()]}`, position: days ? offset / days * 100 : 50 }; });
}
export function eventSourceDetails(event, catalog = []) {
  const source = typeof event.source === 'string' ? event.source : event.source?.id || '';
  const entry = catalog.find(item => item.id === source);
  return { id: source, label: entry?.label || source || '来源尚未提供', directoryURL: /^https?:\/\//.test(entry?.url || '') ? entry.url : '', published: event.source_published_at || '', observed: event.first_observed || '', refs: Array.isArray(event.evidence_refs) ? event.evidence_refs : [] };
}
export function eventPointDate(record) {
  const event = payload(record), value = event.occurrence_start;
  if (event.date_precision && !['day', 'minute'].includes(event.date_precision)) return null;
  return /^\d{4}-\d{2}-\d{2}(?:T.*)?$/.test(value || '') && Number.isFinite(Date.parse(value)) ? value : null;
}
