import { escapeHTML as e } from './markdown.mjs';
import { safeLog } from './core.mjs';

const MAX_BARS = 5000;
const INITIAL_BARS = 120;
const MIN_VISIBLE = 10;
const WIDTH = 1060;
const HEIGHT = 718;
const LEFT = 62;
const RIGHT = 972;
const PLOT_WIDTH = RIGHT - LEFT;
const PANELS = {
  price: { y: 26, h: 244, label: 'K 线' },
  volume: { y: 306, h: 64, label: '成交量' },
  macd: { y: 406, h: 72, label: 'MACD' },
  kdj: { y: 514, h: 68, label: 'KDJ' },
  rsi: { y: 618, h: 68, label: 'RSI' },
};
const prepared = new WeakSet();
const renderCache = new WeakMap();
const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
const validNumber = value => typeof value === 'number' && Number.isFinite(value);
const finite = value => {
  if (typeof value === 'string') {
    const text = value.trim();
    if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(text)) return null;
    value = Number(text);
  }
  return validNumber(value) ? value : null;
};
const field = (row, keys, positive = false) => {
  for (const key of keys) {
    const value = finite(row[key]);
    if (value !== null && (positive ? value > 0 : value >= 0)) return value;
  }
  return null;
};
const number = (value, digits = 2) => validNumber(value) ? value.toLocaleString('zh-CN', { maximumFractionDigits: digits }) : '—';
const fixed = value => Number(value.toFixed(2));
const clean = value => validNumber(value) ? value : null;

function normalizeDate(value) {
  if (typeof value !== 'string' && typeof value !== 'number') return null;
  const text = String(value).trim();
  const standardized = /^\d{8}$/.test(text) ? `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)}` : text;
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$/.exec(standardized);
  if (!match) return null;
  const year = Number(match[1]); const month = Number(match[2]); const day = Number(match[3]);
  if (year < 1900 || year > 2200) return null;
  const date = new Date(Date.UTC(year, month - 1, day));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
  if (text.length > 10 && text.includes(':') && !Number.isFinite(Date.parse(text))) return null;
  return { date: `${match[1]}-${match[2]}-${match[3]}`, ordinal: date.getTime() / 86400000 };
}

function mean(values) {
  if (!values.length || values.some(value => !validNumber(value))) return null;
  return clean(values.reduce((sum, value) => sum + value / values.length, 0));
}

function movingAverage(values, period, index) {
  return index + 1 < period ? null : mean(values.slice(index - period + 1, index + 1));
}

// A missing input resets the seed. EMA is not exposed before a full SMA seed.
function exponentialAverage(values, period) {
  let previous = null; let seed = [];
  const weight = 2 / (period + 1);
  return values.map(value => {
    if (!validNumber(value)) { previous = null; seed = []; return null; }
    if (previous === null) {
      seed.push(value);
      if (seed.length < period) return null;
      previous = mean(seed); seed = [];
    } else previous = clean(previous + weight * (value - previous));
    return previous;
  });
}

function relativeStrength(closes) {
  let previous = null; let gains = []; let losses = []; let averageGain = null; let averageLoss = null;
  return closes.map(close => {
    if (!validNumber(close)) {
      previous = null; gains = []; losses = []; averageGain = null; averageLoss = null;
      return null;
    }
    if (previous === null) { previous = close; return null; }
    const change = close - previous; previous = close;
    if (averageGain === null) {
      gains.push(Math.max(change, 0)); losses.push(Math.max(-change, 0));
      if (gains.length < 14) return null;
      averageGain = mean(gains); averageLoss = mean(losses);
    } else {
      averageGain = (averageGain * 13 + Math.max(change, 0)) / 14;
      averageLoss = (averageLoss * 13 + Math.max(-change, 0)) / 14;
    }
    if (averageGain === 0 && averageLoss === 0) return 50;
    return averageLoss === 0 ? 100 : clean(100 - 100 / (1 + averageGain / averageLoss));
  });
}

/**
 * Normalize dated real records; the last duplicate row wins, without backfilling.
 * MA5/10/20 and BOLL20 (population sigma, ±2σ) require full close windows.
 * MACD(12,26,9) uses SMA-seeded EMAs: DIF first at record 26, DEA/hist at 34.
 * KDJ9 starts K=D=50 after nine complete candles; RSI14 uses Wilder smoothing
 * seeded by fourteen actual changes. Missing required values restart warmup.
 * Array.diagnostics describes dropped invalid dates, duplicates and missing data.
 */
export function enrichMarketBars(rows = []) {
  const diagnostics = { invalidDates: 0, invalidRows: 0, duplicates: 0, truncated: 0, missingOHLC: 0, missingVolume: 0 };
  const dated = new Map();
  for (const row of Array.isArray(rows) ? rows : []) {
    if (!row || typeof row !== 'object' || Array.isArray(row)) { diagnostics.invalidRows++; continue; }
    const rawDate = [row.date, row.trade_date, row.datetime, row.time, row['时间']].find(value => value !== null && value !== undefined && String(value).trim() !== '');
    const date = normalizeDate(rawDate);
    if (!date) { diagnostics.invalidDates++; continue; }
    const open = field(row, ['open', '开盘'], true); const high = field(row, ['high', '最高'], true);
    const low = field(row, ['low', '最低'], true); const close = field(row, ['close', '收盘', 'price', 'last'], true);
    const bar = {
      date: date.date, ordinal: date.ordinal, open, high, low, close,
      volume: field(row, ['volume', 'vol', '成交量']),
      amount: field(row, ['amount', 'turnover', '成交额']),
      turnover_rate_pct: field(row, ['turnover_rate_pct', 'turnover_rate', '换手率']),
      validOHLC: [open, high, low, close].every(validNumber) && high >= Math.max(open, close) && low <= Math.min(open, close) && low <= high,
    };
    if (dated.has(date.date)) diagnostics.duplicates++;
    dated.set(date.date, bar);
  }
  const sorted = [...dated.values()].sort((a, b) => a.ordinal - b.ordinal);
  diagnostics.truncated = Math.max(0, sorted.length - MAX_BARS);
  const normalized = sorted.slice(-MAX_BARS);
  const closes = normalized.map(bar => bar.close);
  const ema12 = exponentialAverage(closes, 12); const ema26 = exponentialAverage(closes, 26);
  const dif = closes.map((_, index) => ema12[index] === null || ema26[index] === null ? null : clean(ema12[index] - ema26[index]));
  const dea = exponentialAverage(dif, 9); const rsi = relativeStrength(closes);
  let k = 50; let d = 50;
  const bars = normalized.map((bar, index) => {
    if (!bar.validOHLC) diagnostics.missingOHLC++;
    if (bar.volume === null) diagnostics.missingVolume++;
    const ma20 = movingAverage(closes, 20, index);
    const variance = ma20 === null ? null : mean(closes.slice(index - 19, index + 1).map(value => (value - ma20) ** 2));
    const deviation = variance === null ? null : Math.sqrt(variance);
    const window = normalized.slice(index - 8, index + 1);
    let kValue = null; let dValue = null; let jValue = null;
    if (index >= 8 && window.every(item => item.validOHLC)) {
      const low = Math.min(...window.map(item => item.low)); const high = Math.max(...window.map(item => item.high));
      const rsv = high === low ? 50 : (bar.close - low) / (high - low) * 100;
      k = (2 * k + rsv) / 3; d = (2 * d + k) / 3;
      kValue = clean(k); dValue = clean(d); jValue = clean(3 * k - 2 * d);
    } else { k = 50; d = 50; }
    return {
      ...bar, gapDays: index ? bar.ordinal - normalized[index - 1].ordinal : 0,
      ma5: movingAverage(closes, 5, index), ma10: movingAverage(closes, 10, index), ma20,
      bollUpper: deviation === null ? null : clean(ma20 + 2 * deviation),
      bollLower: deviation === null ? null : clean(ma20 - 2 * deviation),
      dif: dif[index], dea: dea[index], macd: dif[index] === null || dea[index] === null ? null : clean(2 * (dif[index] - dea[index])),
      k: kValue, d: dValue, j: jValue, rsi: rsi[index],
    };
  });
  Object.defineProperty(bars, 'diagnostics', { value: diagnostics });
  prepared.add(bars);
  if (Array.isArray(rows)) renderCache.set(rows, bars);
  return bars;
}

// Fetched row arrays are immutable snapshots; reconfigure with a new array on refresh.
function barsFor(rows) {
  if (!Array.isArray(rows)) return enrichMarketBars([]);
  if (prepared.has(rows)) return rows;
  return renderCache.get(rows) || enrichMarketBars(rows);
}

function rangeFor(length, start, end) {
  if (!length) return { start: 0, end: 0 };
  const last = validNumber(end) ? clamp(Math.floor(end), 1, length) : length;
  const first = validNumber(start) ? clamp(Math.floor(start), 0, last - 1) : Math.max(0, last - INITIAL_BARS);
  return { start: first, end: last };
}

function extent(values, { zero = false, padding = 0.06, fixedRange } = {}) {
  if (fixedRange) return fixedRange;
  const finiteValues = values.filter(validNumber);
  if (zero) finiteValues.push(0);
  if (!finiteValues.length) return [0, 1];
  const low = Math.min(...finiteValues); const high = Math.max(...finiteValues);
  const margin = (high - low || Math.abs(high) * 0.05 || 1) * padding;
  return [low - margin, high + margin];
}

function linePath(bars, key, xAt, yAt) {
  let connected = false;
  return bars.map((bar, index) => {
    if (!validNumber(bar[key])) { connected = false; return ''; }
    const command = connected ? 'L' : 'M'; connected = true;
    return `${command}${fixed(xAt(index))},${fixed(yAt(bar[key]))}`;
  }).filter(Boolean).join(' ');
}

function panelGrid(name, domain, scale) {
  const panel = PANELS[name]; const ticks = name === 'price' ? 5 : 3;
  return `<g class="asset-chart-grid" data-panel="${name}"><text class="asset-panel-label" x="${LEFT}" y="${panel.y - 9}">${panel.label}</text>${Array.from({ length: ticks }, (_, index) => {
    const value = domain[0] + (domain[1] - domain[0]) * index / (ticks - 1); const y = fixed(scale(value));
    return `<line x1="${LEFT}" y1="${y}" x2="${RIGHT}" y2="${y}"/><text class="asset-axis-value" x="${RIGHT + 8}" y="${y + 4}">${e(number(value))}</text>`;
  }).join('')}</g>`;
}

function valueReadout(bar, previous) {
  const change = validNumber(bar.close) && validNumber(previous?.close) && previous.close !== 0 ? (bar.close / previous.close - 1) * 100 : null;
  const values = [['开', bar.open], ['高', bar.high], ['低', bar.low], ['收', bar.close]];
  return `<div class="asset-terminal-quote asset-history-readout" data-active-date="${e(bar.date)}"><span class="asset-history-date">历史读数 <strong>${e(bar.date)}</strong></span>${values.map(([label, value]) => `<span>${label} <strong>${e(number(value))}</strong></span>`).join('')}<span>涨跌幅 <strong>${change === null ? '—' : `${change > 0 ? '+' : ''}${e(number(change))}%`}</strong></span><span>成交量（源单位） <strong>${e(number(bar.volume, 0))}</strong></span><span>成交额（源单位） <strong>${e(number(bar.amount, 0))}</strong></span><span>换手率 <strong>${bar.turnover_rate_pct === null ? '—' : `${e(number(bar.turnover_rate_pct))}%`}</strong></span>${bar.validOHLC ? '' : '<span class="asset-chart-warning">OHLC 缺失或不一致，未绘制该蜡烛</span>'}</div>`;
}

function indicatorReadout(bar, overlay) {
  const keys = overlay === 'ma' ? [['ma5', 'MA5'], ['ma10', 'MA10'], ['ma20', 'MA20']] : overlay === 'boll' ? [['ma20', 'BOLL中'], ['bollUpper', 'BOLL上'], ['bollLower', 'BOLL下']] : [];
  keys.push(['dif', 'DIF'], ['dea', 'DEA'], ['macd', 'MACD'], ['k', 'K'], ['d', 'D'], ['j', 'J'], ['rsi', 'RSI14']);
  return `<div class="asset-terminal-legend" aria-label="所选历史记录的指标">${keys.map(([key, label]) => `<span class="${key}" data-indicator="${key}">${label} <strong>${e(number(bar[key]))}</strong></span>`).join('')}<span class="up">上涨</span><span class="down">下跌</span></div>`;
}

function controls(overlay, range, length) {
  const count = range.end - range.start;
  const button = (action, label, disabled = false) => `<button type="button" data-asset-chart-action="${action}" aria-label="${label}"${disabled ? ' disabled' : ''}>${label}</button>`;
  return `<div class="asset-chart-toolbar"><div class="asset-overlay-controls" role="group" aria-label="主图叠加指标">${[['ma', 'MA'], ['boll', 'BOLL'], ['none', '裸 K']].map(([mode, label]) => `<button type="button" data-asset-chart-action="overlay-${mode}" aria-pressed="${overlay === mode}">${label}</button>`).join('')}</div><div class="asset-range-controls" role="group" aria-label="行情视区">${button('pan-back', '向前查看', range.start === 0)}${button('pan-forward', '向后查看', range.end === length)}${button('zoom-in', '放大', count <= Math.min(MIN_VISIBLE, length))}${button('zoom-out', '缩小', count >= length)}${button('reset', '近120条')}</div><span class="asset-range-summary" data-visible-count="${count}">第 ${range.start + 1}–${range.end} 条 / 共 ${length} 条</span></div>`;
}

function renderTerminal(rows, options) {
  const allBars = barsFor(rows); const length = allBars.length;
  const overlay = ['ma', 'boll', 'none'].includes(options.overlay) ? options.overlay : 'ma';
  const header = '<header><div><span class="eyebrow">MARKET TERMINAL</span><h2>K 线与技术指标</h2></div><span class="asset-terminal-period">日 / 周 / 月由上方查询条件切换</span></header>';
  if (!length) {
    const diagnostics = allBars.diagnostics;
    return `<section class="asset-market-terminal" aria-label="K 线与技术指标">${header}<div class="chart-empty">没有可绘制的有效日期历史记录。${diagnostics.invalidDates ? `日期无效：${diagnostics.invalidDates} 条。` : ''}不会生成模拟行情。</div></section>`;
  }
  const range = rangeFor(length, options.start, options.end); const bars = allBars.slice(range.start, range.end);
  const activeIndex = validNumber(options.activeIndex) ? clamp(Math.round(options.activeIndex), range.start, range.end - 1) : range.end - 1;
  const active = allBars[activeIndex]; const count = bars.length;
  const xAt = index => LEFT + (index + 0.5) / count * PLOT_WIDTH;
  const candleWidth = Math.max(0.4, Math.min(12, PLOT_WIDTH / count * 0.65));
  const overlayKeys = overlay === 'ma' ? ['ma5', 'ma10', 'ma20'] : overlay === 'boll' ? ['ma20', 'bollUpper', 'bollLower'] : [];
  const priceValues = bars.flatMap(bar => [...(bar.validOHLC ? [bar.low, bar.high] : []), ...overlayKeys.map(key => bar[key])]);
  const macdValues = bars.flatMap(bar => [bar.macd, bar.dif, bar.dea]).filter(validNumber);
  const macdLimit = Math.max(...macdValues.map(Math.abs), 0.01);
  const domains = {
    price: extent(priceValues), volume: [0, Math.max(...bars.map(bar => bar.volume ?? 0), 1)],
    macd: [-macdLimit * 1.08, macdLimit * 1.08],
    kdj: extent(bars.flatMap(bar => [bar.k, bar.d, bar.j]).concat([0, 100]), { padding: 0.03 }), rsi: [0, 100],
  };
  const scales = Object.fromEntries(Object.entries(PANELS).map(([key, panel]) => [key, value => panel.y + (domains[key][1] - value) / (domains[key][1] - domains[key][0]) * panel.h]));
  const candles = bars.map((bar, index) => {
    if (!bar.validOHLC) return `<path class="asset-missing-candle" d="M${fixed(xAt(index) - 2)},${PANELS.price.y + PANELS.price.h - 4}h4"><title>${e(bar.date)} OHLC 缺失或不一致</title></path>`;
    const x = fixed(xAt(index)); const open = scales.price(bar.open); const close = scales.price(bar.close);
    return `<g class="asset-candle ${bar.close >= bar.open ? 'up' : 'down'}${activeIndex === range.start + index ? ' selected' : ''}"><line x1="${x}" y1="${fixed(scales.price(bar.high))}" x2="${x}" y2="${fixed(scales.price(bar.low))}"/><rect x="${fixed(x - candleWidth / 2)}" y="${fixed(Math.min(open, close))}" width="${fixed(candleWidth)}" height="${fixed(Math.max(0.8, Math.abs(open - close)))}"/></g>`;
  }).join('');
  const volumes = bars.map((bar, index) => {
    if (bar.volume === null) return '';
    const y = scales.volume(bar.volume); const direction = bar.validOHLC ? bar.close >= bar.open ? 'up' : 'down' : 'unknown';
    return `<rect class="asset-volume ${direction}" x="${fixed(xAt(index) - candleWidth / 2)}" y="${fixed(y)}" width="${fixed(candleWidth)}" height="${fixed(Math.max(0, PANELS.volume.y + PANELS.volume.h - y))}"/>`;
  }).join('');
  const histogram = bars.map((bar, index) => {
    if (bar.macd === null) return '';
    const y = scales.macd(bar.macd); const zero = scales.macd(0);
    return `<rect class="asset-macd ${bar.macd >= 0 ? 'up' : 'down'}" x="${fixed(xAt(index) - candleWidth / 2)}" y="${fixed(Math.min(y, zero))}" width="${fixed(candleWidth)}" height="${fixed(Math.abs(zero - y))}"/>`;
  }).join('');
  const path = (key, panel, className = key) => `<path class="asset-series ${className}" d="${linePath(bars, key, xAt, scales[panel])}"/>`;
  const overlayPaths = overlayKeys.map(key => path(key, 'price', overlay === 'boll' ? `boll ${key}` : key)).join('');
  const crosshairX = fixed(xAt(activeIndex - range.start));
  const pointerY = finite(options.crosshairY);
  const hovered = pointerY === null ? null : Object.entries(PANELS).find(([, panel]) => pointerY >= panel.y && pointerY <= panel.y + panel.h);
  let horizontal = '';
  if (hovered) {
    const [key, panel] = hovered; const value = domains[key][1] - (pointerY - panel.y) / panel.h * (domains[key][1] - domains[key][0]);
    horizontal = `<line class="asset-crosshair" x1="${LEFT}" y1="${fixed(pointerY)}" x2="${RIGHT}" y2="${fixed(pointerY)}"/><rect class="asset-crosshair-value-bg" x="${RIGHT}" y="${fixed(pointerY - 9)}" width="86" height="18"/><text class="asset-crosshair-value" x="${RIGHT + 5}" y="${fixed(pointerY + 4)}">${e(number(value))}</text>`;
  }
  const gaps = bars.map((bar, index) => bar.gapDays > 1 ? `<path class="asset-calendar-gap" d="M${fixed(xAt(index) - PLOT_WIDTH / count / 2)},${PANELS.price.y + PANELS.price.h - 8}v8"><title>与前条记录相隔 ${bar.gapDays} 个自然日；未补齐，不推断停牌</title></path>` : '').join('');
  const diagnostics = allBars.diagnostics; const warnings = [];
  if (diagnostics.invalidDates) warnings.push(`日期无效：${diagnostics.invalidDates} 条未绘制`);
  if (diagnostics.invalidRows) warnings.push(`无效记录：${diagnostics.invalidRows} 条未绘制`);
  if (diagnostics.duplicates) warnings.push(`重复日期：${diagnostics.duplicates} 条已按最后记录去重`);
  if (diagnostics.truncated) warnings.push(`超过上限：已保留最近 ${MAX_BARS} 条，省略 ${diagnostics.truncated} 条`);
  if (diagnostics.missingOHLC) warnings.push(`OHLC 缺失或不一致：${diagnostics.missingOHLC} 条保留时间槽`);
  if (diagnostics.missingVolume) warnings.push(`成交量缺失：${diagnostics.missingVolume} 条留空`);
  const dates = [0, Math.floor((count - 1) / 2), count - 1].filter((value, index, items) => items.indexOf(value) === index).map((index, order, items) => `<text class="asset-date-label" x="${fixed(xAt(index))}" y="${HEIGHT - 9}" text-anchor="${order === 0 ? 'start' : order === items.length - 1 ? 'end' : 'middle'}">${e(bars[index].date)}</text>`).join('');
  return `<section class="asset-market-terminal" aria-label="K 线与技术指标">${header}${controls(overlay, range, length)}${valueReadout(active, allBars[activeIndex - 1])}${indicatorReadout(active, overlay)}<div class="asset-chart-scroll"><svg class="asset-terminal-chart" data-asset-chart data-price-min="${domains.price[0]}" data-price-max="${domains.price[1]}" viewBox="0 0 ${WIDTH} ${HEIGHT}" role="img" tabindex="0" aria-label="包含 K 线、成交量、MACD、KDJ 和 RSI 的行情图；方向键选择历史记录，加减键缩放" aria-describedby="asset-chart-help" preserveAspectRatio="xMidYMid meet"><title>K 线、成交量、MACD、KDJ 与 RSI：${e(bars[0].date)} 至 ${e(bars.at(-1).date)}</title>${Object.keys(PANELS).map(key => panelGrid(key, domains[key], scales[key])).join('')}${candles}${overlayPaths}${volumes}${histogram}${path('dif', 'macd')}${path('dea', 'macd')}${path('k', 'kdj')}${path('d', 'kdj')}${path('j', 'kdj')}${[20, 80].map(value => `<line class="asset-threshold" x1="${LEFT}" x2="${RIGHT}" y1="${fixed(scales.rsi(value))}" y2="${fixed(scales.rsi(value))}"/>`).join('')}${path('rsi', 'rsi')}${gaps}<line class="asset-crosshair" x1="${crosshairX}" y1="${PANELS.price.y}" x2="${crosshairX}" y2="${PANELS.rsi.y + PANELS.rsi.h}"/>${horizontal}${dates}</svg></div><p class="asset-chart-help" id="asset-chart-help">指针或 ← → 查看历史读数；拖动或按钮平移；+ / − 缩放；Ctrl / ⌘ + 滚轮缩放，Shift + 滚轮平移。普通滚轮滚动页面。时间轴按真实记录排列，日期间隔不补齐、不推断停牌。</p><details class="asset-indicator-method"><summary>指标口径与预热</summary><p>MA5/10/20；BOLL20 使用总体标准差 ±2σ。MACD(12,26,9) 的 EMA 以完整均值播种，DIF 最早第26条、DEA 与柱最早第34条；柱 = 2×(DIF−DEA)。KDJ9 满9条完整蜡烛后从 K=D=50 递推；J 可超出0–100。RSI14 以14次真实价格变动播种，再用 Wilder 平滑。缺失所需值会重新预热，— 表示预热不足或缺失。成交量、成交额保持源单位，换手率为百分比。</p></details>${warnings.length ? `<p class="asset-chart-warning" role="status">${e(warnings.join('；'))}。</p>` : ''}</section>`;
}

export function renderMarketTerminal(rows = [], options = {}) {
  try { return renderTerminal(rows, options || {}); }
  catch {
    safeLog('asset_chart_render_failed', { status: 'error', method: 'render' });
    return '<section class="asset-market-terminal"><div class="chart-empty" role="status">行情图表暂时无法绘制，请刷新历史数据。</div></section>';
  }
}

/** Browser-independent controller. start/end are a half-open range in normalized
 * full history; activeIndex is absolute. configure never emits onChange.
 * Attach delegated click/pointermove/down/up/cancel/leave, keydown and a nonpassive
 * wheel listener. onChange should redraw only the chart slot, preserving focus.
 */
export function createAssetChartController({ onChange = () => {}, logger = safeLog } = {}) {
  let bars = []; let sourceRows; let identity; let drag = null;
  let state = { overlay: 'ma', start: 0, end: 0, activeIndex: -1, crosshairY: null };
  const getState = () => ({ ...state });
  function update(next, reason) {
    const changed = Object.keys(next).some(key => next[key] !== state[key]);
    if (!changed) return false;
    state = { ...state, ...next };
    try { onChange(getState(), { reason }); }
    catch { logger('asset_chart_change_failed', { status: 'error', method: reason }); }
    return true;
  }
  function configure(rows = [], nextIdentity = '') {
    if (sourceRows === rows && identity === nextIdentity) return getState();
    const previousBars = bars; const previous = state; sourceRows = rows;
    bars = enrichMarketBars(rows);
    if (identity !== nextIdentity || !previousBars.length) {
      identity = nextIdentity; drag = null;
      state = { overlay: 'ma', ...rangeFor(bars.length), activeIndex: bars.length - 1, crosshairY: null };
    } else {
      const count = Math.min(previous.end - previous.start, bars.length);
      const pinnedToLatest = previous.end === previousBars.length;
      const firstDate = previousBars[previous.start]?.date;
      const selectedDate = previousBars[previous.activeIndex]?.date;
      let start = pinnedToLatest ? bars.length - count : bars.findIndex(bar => bar.date === firstDate);
      if (start < 0) start = Math.max(0, Math.min(previous.start, bars.length - count));
      const end = Math.min(bars.length, start + count);
      let activeIndex = previous.activeIndex === previousBars.length - 1 && pinnedToLatest ? bars.length - 1 : bars.findIndex(bar => bar.date === selectedDate);
      activeIndex = bars.length ? clamp(activeIndex < 0 ? start : activeIndex, start, end - 1) : -1;
      state = { ...previous, start, end, activeIndex, crosshairY: null }; drag = null;
    }
    return getState();
  }
  function select(index, extra = {}) {
    if (!bars.length || !validNumber(index)) return false;
    const activeIndex = clamp(Math.round(index), 0, bars.length - 1); const count = state.end - state.start;
    let start = state.start;
    if (activeIndex < start) start = activeIndex;
    if (activeIndex >= state.end) start = activeIndex - count + 1;
    return update({ start, end: start + count, activeIndex, ...extra }, 'select');
  }
  function pan(delta) {
    if (!bars.length || !validNumber(delta)) return false;
    const count = state.end - state.start; const start = clamp(state.start + Math.round(delta), 0, bars.length - count); const end = start + count;
    return update({ start, end, activeIndex: clamp(state.activeIndex, start, end - 1), crosshairY: null }, 'pan');
  }
  function zoom(factor, anchorIndex = state.activeIndex) {
    if (!bars.length || !validNumber(factor) || factor <= 0) return false;
    const count = state.end - state.start;
    const nextCount = clamp(Math.round(count * factor), Math.min(MIN_VISIBLE, bars.length), bars.length);
    const anchor = clamp(validNumber(anchorIndex) ? anchorIndex : state.activeIndex, state.start, state.end - 1);
    const ratio = count === 1 ? 0.5 : (anchor - state.start) / (count - 1);
    const start = clamp(Math.round(anchor - ratio * (nextCount - 1)), 0, bars.length - nextCount); const end = start + nextCount;
    return update({ start, end, activeIndex: clamp(state.activeIndex, start, end - 1), crosshairY: null }, 'zoom');
  }
  function reset() {
    drag = null;
    return update({ ...rangeFor(bars.length), activeIndex: bars.length - 1, crosshairY: null }, 'reset');
  }
  function cancel() { drag = null; return update({ crosshairY: null }, 'cancel'); }
  function position(event, element) {
    const rect = element.getBoundingClientRect();
    if (!rect.width || !rect.height || !validNumber(event.clientX)) return null;
    const x = (event.clientX - rect.left) / rect.width * WIDTH;
    const y = validNumber(event.clientY) ? (event.clientY - rect.top) / rect.height * HEIGHT : null;
    return { rect, x, y, index: clamp(state.start + Math.floor((x - LEFT) / PLOT_WIDTH * (state.end - state.start)), state.start, state.end - 1) };
  }
  function handleEvent(event) {
    const target = event?.target;
    if (!target || typeof target.closest !== 'function') return false;
    if (event.type === 'click') {
      const control = target.closest('[data-asset-chart-action]'); if (!control || control.disabled) return false;
      const action = control.dataset.assetChartAction;
      if (['overlay-ma', 'overlay-boll', 'overlay-none'].includes(action)) { update({ overlay: action.slice(8) }, 'overlay'); return true; }
      const step = Math.max(1, Math.round((state.end - state.start) / 4));
      if (action === 'pan-back') pan(-step);
      else if (action === 'pan-forward') pan(step);
      else if (action === 'zoom-in') zoom(0.75);
      else if (action === 'zoom-out') zoom(1.4);
      else if (action === 'reset') reset();
      else return false;
      return true;
    }
    if (event.type === 'pointerup' || event.type === 'pointercancel') {
      if (!drag || (event.pointerId !== undefined && drag.pointerId !== event.pointerId)) return false;
      drag = null; return true;
    }
    const element = target.closest('[data-asset-chart]');
    if (event.type === 'pointermove' && drag) {
      if (event.buttons === 0) { drag = null; return false; }
      if (event.pointerId !== undefined && event.pointerId !== drag.pointerId) return false;
      const dx = event.clientX - drag.x; const dy = (event.clientY ?? drag.y) - drag.y;
      if (Math.abs(dx) > 5 && Math.abs(dx) > Math.abs(dy)) {
        const count = state.end - state.start;
        const delta = Math.round(-dx / drag.width * WIDTH / PLOT_WIDTH * count);
        const start = clamp(drag.start + delta, 0, bars.length - count);
        update({ start, end: start + count, activeIndex: clamp(state.activeIndex, start, start + count - 1), crosshairY: null }, 'drag');
        event.preventDefault?.(); return true;
      }
    }
    if (!element || !bars.length) return false;
    if (event.type === 'pointerdown') {
      if (event.button !== undefined && event.button !== 0) return false;
      const point = position(event, element); if (!point) return false;
      drag = { x: event.clientX, y: event.clientY, width: point.rect.width, start: state.start, pointerId: event.pointerId };
      select(point.index, { crosshairY: point.y === null ? null : Math.round(point.y) }); return true;
    }
    if (event.type === 'pointermove') {
      const point = position(event, element); if (!point) return false;
      select(point.index, { crosshairY: point.y === null ? null : Math.round(point.y) }); return true;
    }
    if (event.type === 'pointerleave') {
      // Capturing listeners also see leaves from candle descendants. A drag is
      // document-scoped and ends only on pointerup/cancel, even outside the SVG.
      if (target !== element) return false;
      update({ crosshairY: null }, 'leave'); return true;
    }
    if (event.type === 'wheel') {
      if (!event.ctrlKey && !event.metaKey && !event.shiftKey) return false;
      const delta = finite(event.deltaY) || finite(event.deltaX); if (!delta) return false;
      if (event.ctrlKey || event.metaKey) { const point = position(event, element); zoom(delta < 0 ? 0.85 : 1.18, point?.index); }
      else pan(Math.sign(delta) * Math.max(1, Math.round((state.end - state.start) / 12)));
      event.preventDefault?.(); return true;
    }
    if (event.type === 'keydown') {
      if (event.altKey || event.ctrlKey || event.metaKey) return false;
      if (event.key === 'ArrowLeft') select(state.activeIndex - 1, { crosshairY: null });
      else if (event.key === 'ArrowRight') select(state.activeIndex + 1, { crosshairY: null });
      else if (event.key === 'Home') select(0, { crosshairY: null });
      else if (event.key === 'End') select(bars.length - 1, { crosshairY: null });
      else if (['+', '='].includes(event.key)) zoom(0.75);
      else if (['-', '−', '_'].includes(event.key)) zoom(1.4);
      else if (event.key === 'Escape') cancel();
      else return false;
      event.preventDefault?.(); return true;
    }
    return false;
  }
  function handle(event) {
    try { return handleEvent(event); }
    catch { logger('asset_chart_interaction_failed', { status: 'error', method: 'handle' }); return false; }
  }
  return { configure, getState, handle, select, pan, zoom, reset, cancel };
}
