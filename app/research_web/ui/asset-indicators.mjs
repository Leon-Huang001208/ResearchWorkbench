import { estimateChips } from './asset-chips.mjs';
// Deterministic AlphaFoundry calculations. No browser globals or supplier calls.
export const MA_PERIODS = [5, 10, 20, 60, 120, 250];
export const finite = value => {
  if (typeof value === 'string' && /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(value.trim())) value = Number(value);
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
};
const mean = values => values.length && values.every(v => finite(v) !== null) ? values.reduce((s, v) => s + v / values.length, 0) : null;
const read = (row, keys, positive = false) => {
  for (const key of keys) { const value = finite(row[key]); if (value !== null && (positive ? value > 0 : value >= 0)) return value; }
  return null;
};
const validOHLC = b => [b.open, b.high, b.low, b.close].every(v => finite(v) !== null) && b.low <= Math.min(b.open, b.close) && b.high >= Math.max(b.open, b.close) && b.low <= b.high;

function parseDate(raw, timestamp = false) {
  if (!['string', 'number'].includes(typeof raw)) return null;
  let text = String(raw).trim(); if (/^\d{8}$/.test(text)) text = `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6)}`;
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$/.exec(text);
  if (!match) return null;
  const [year, month, day] = match.slice(1).map(Number); const stamp = Date.UTC(year, month - 1, day); const date = new Date(stamp);
  if (year < 1900 || year > 2200 || date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day || (text.length > 10 && !Number.isFinite(Date.parse(text)))) return null;
  if (timestamp) {
    // Closed minute snapshots carry an explicit exchange offset, never local time.
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00\+08:00$/.test(text)) return null;
    return { date: text, ordinal: Date.parse(text) / 86400000 };
  }
  return { date: text.slice(0, 10), ordinal: stamp / 86400000 };
}

/** Nulls, invalid OHLC and explicit gap records reset warmup, never becoming zero.
 * Trading-calendar weekends/holidays are factual gapDays, not synthetic bars.
 * BOLL sample sigma; EMA first-close/adjust=False; KDJ first valid RSV; RSI SMA.
 */
export function calculateIndicators(normalized) {
  let segment = []; let gains = []; let losses = []; let ema12 = null; let ema26 = null; let signal = null; let k = null; let d = null;
  const bars = normalized.map((input, index) => {
    const bar = { ...input, gapDays: index ? input.ordinal - normalized[index - 1].ordinal : 0 };
    const complete = bar.validOHLC && !bar.gap;
    if (!complete) { segment = []; gains = []; losses = []; ema12 = ema26 = signal = k = d = null; }
    const previous = segment.at(-1);
    if (complete) {
      segment.push(bar);
      if (previous) { const delta = bar.close - previous.close; gains.push(Math.max(delta, 0)); losses.push(Math.max(-delta, 0)); if (gains.length > 14) { gains.shift(); losses.shift(); } }
      ema12 = ema12 === null ? bar.close : ema12 + 2 / 13 * (bar.close - ema12);
      ema26 = ema26 === null ? bar.close : ema26 + 2 / 27 * (bar.close - ema26);
      const rawDif = ema12 - ema26;
      signal = signal === null ? rawDif : signal + .2 * (rawDif - signal);
    }
    for (const n of MA_PERIODS) bar[`ma${n}`] = segment.length >= n ? mean(segment.slice(-n).map(b => b.close)) : null;
    const ma20 = bar.ma20; const sigma = ma20 === null ? null : Math.sqrt(segment.slice(-20).reduce((sum, b) => sum + (b.close - ma20) ** 2, 0) / 19);
    bar.bollUpper = sigma === null ? null : ma20 + 2 * sigma; bar.bollLower = sigma === null ? null : ma20 - 2 * sigma;
    bar.dif = segment.length >= 26 ? ema12 - ema26 : null; bar.dea = segment.length >= 34 ? signal : null; bar.macd = bar.dea === null ? null : 2 * (bar.dif - bar.dea);
    // AF rolling(9,min_periods=1) feeds the internal EWM from the first
    // valid candle. Nine bars is only the public display warmup mask.
    if (complete) {
      const recent = segment.slice(-9); const low = Math.min(...recent.map(b => b.low)); const high = Math.max(...recent.map(b => b.high)); const rsv = high === low ? 50 : (bar.close - low) / (high - low) * 100;
      k = k === null ? rsv : k + (rsv - k) / 3; d = d === null ? k : d + (k - d) / 3;
    }
    bar.k = segment.length >= 9 ? k : null; bar.d = segment.length >= 9 ? d : null; bar.j = segment.length >= 9 ? 3 * k - 2 * d : null;
    const gain = gains.length === 14 ? mean(gains) : null; const loss = losses.length === 14 ? mean(losses) : null;
    bar.rsi = gain === null ? null : gain === 0 && loss === 0 ? 50 : loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
    for (const n of [5, 10]) bar[`volumeMA${n}`] = index + 1 >= n ? mean(normalized.slice(index - n + 1, index + 1).map(b => b.gap ? null : b.volume)) : null;
    // AF names retained alongside the existing RWB public bar keys.
    Object.assign(bar, { boll_middle: ma20, boll_upper: bar.bollUpper, boll_lower: bar.bollLower, macd_dif: bar.dif, macd_dea: bar.dea, macd_hist: bar.macd, kdj_k: bar.k, kdj_d: bar.d, kdj_j: bar.j });
    return bar;
  });
  return bars;
}

export function enrichMarketBars(rows = [], {timestamp = false} = {}) {
  const diagnostics = { invalidDates: 0, invalidRows: 0, duplicates: 0, truncated: 0, missingOHLC: 0, missingVolume: 0 };
  const dated = new Map();
  for (const row of Array.isArray(rows) ? rows : []) {
    if (!row || typeof row !== 'object' || Array.isArray(row)) { diagnostics.invalidRows++; continue; }
    const date = parseDate([row.date, row.trade_date, row.datetime, row.time, row['时间']].find(v => v !== null && v !== undefined && String(v).trim()), timestamp);
    if (!date) { diagnostics.invalidDates++; continue; }
    const bar = { ...date, asset: row.asset, open: read(row, ['open', '开盘'], true), high: read(row, ['high', '最高'], true), low: read(row, ['low', '最低'], true), close: read(row, ['close', '收盘', 'price', 'last'], true), volume: read(row, ['volume', 'vol', '成交量']), amount: read(row, ['amount', 'turnover', '成交额']), turnover_rate_pct: read(row, ['turnover_rate_pct', 'turnover_rate', '换手率']), vwap: read(row, ['vwap', 'avg_price', 'average_price'], true), gap: row.gap === true || row.missing === true };
    bar.validOHLC = validOHLC(bar);
    if (dated.has(bar.date)) diagnostics.duplicates++;
    dated.set(bar.date, bar);
  }
  const normalized = [...dated.values()].sort((a, b) => a.ordinal - b.ordinal);
  diagnostics.missingOHLC = normalized.filter(b => !b.validOHLC).length; diagnostics.missingVolume = normalized.filter(b => b.volume === null).length;
  const bars = calculateIndicators(normalized); Object.defineProperty(bars, 'diagnostics', { value: diagnostics }); return bars;
}

export function sourceFrequency(value) {
  const text = String(value || 'daily').toLowerCase();
  if (text === 'minute') return 'minute';
  if (['daily', 'day', 'd', '1d', '日', '日线'].includes(text)) return 'day';
  if (['weekly', 'week', 'w', '1w', '周', '周线'].includes(text)) return 'week';
  if (['monthly', 'month', 'm', '1m', '月', '月线'].includes(text)) return 'month';
  return 'unknown';
}

export function aggregateMarketBars(bars, period = 'day') {
  if (period === 'day') return bars;
  const groups = new Map();
  for (const bar of bars) {
    const date = new Date(bar.ordinal * 86400000); const key = period === 'month' ? bar.date.slice(0, 7) : bar.ordinal - ((date.getUTCDay() + 6) % 7);
    if (!groups.has(key)) groups.set(key, []); groups.get(key).push(bar);
  }
  const aggregated = [...groups.values()].map(group => {
    const first = group[0]; const last = group.at(-1); const complete = group.every(b => b.validOHLC && !b.gap);
    const sum = key => group.every(b => finite(b[key]) !== null) ? group.reduce((s, b) => s + b[key], 0) : null;
    // Daily turnover rates need a verified period share-base contract. The
    // final-day rate cannot describe the aggregate and therefore stays unknown.
    const result = { date: last.date, ordinal: last.ordinal, source_start_date: first.date, source_end_date: last.date, open: first.open, close: last.close, high: complete ? Math.max(...group.map(b => b.high)) : null, low: complete ? Math.min(...group.map(b => b.low)) : null, volume: sum('volume'), amount: sum('amount'), turnover_rate_pct: null, vwap: null, gap: !complete, validOHLC: complete };
    return result;
  });
  const result = calculateIndicators(aggregated); Object.defineProperty(result, 'diagnostics', { value: bars.diagnostics || {} }); return result;
}

/** Compatibility surface; new turnover model never fabricates missing holdings inputs. */
export function estimateChipDistribution(source, start = 0, end = source.length - 1, _renderDomain = null, buckets = 180, settings = {}) {
  return estimateChips(source.slice(Math.max(0, start), Math.min(source.length, end + 1)), settings, buckets);
}
