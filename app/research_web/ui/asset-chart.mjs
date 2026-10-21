import { escapeHTML as e } from './markdown.mjs';
import { safeLog } from './core.mjs';
import { MA_PERIODS, finite, enrichMarketBars, aggregateMarketBars, estimateChipDistribution, sourceFrequency } from './asset-indicators.mjs';
export { enrichMarketBars } from './asset-indicators.mjs';

const UP = '#ff4d4f'; const DOWN = '#00c896';
const CHART_THEMES = {
  dark: { text: '#d1d5db', muted: '#9ca3af', grid: 'rgba(148,163,184,.18)', surface: '#11151c', selected: 'rgba(148,163,184,.18)' },
  light: { text: '#242424', muted: '#686860', grid: '#e8e8e5', surface: '#fafaf9', selected: '#e8e8e5' },
};
// Pure option builders remain usable without a DOM; browser controllers supply
// the resolved page tokens so the canvas never owns a separate color scheme.
const chartTheme = theme => ({ ...(theme === 'light' || theme?.mode === 'light' ? CHART_THEMES.light : CHART_THEMES.dark), ...(theme && typeof theme === 'object' ? theme : {}) });
const COLORS = ['#ed8936', '#3182ce', '#805ad5', '#10b981', '#22d3ee', '#a3a3a3'];
const BOLL = [['bollUpper', 'BOLL上轨', '#ffff00'], ['ma20', 'BOLL中轨', '#d9d9d9'], ['bollLower', 'BOLL下轨', '#ff00ff']];
const clamp = (v, low, high) => Math.min(high, Math.max(low, v));
const fmt = (v, digits = 2) => finite(v) === null ? '—' : v.toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
const priceFmt = value => finite(value) === null ? '—' : Number(value).toFixed(2);
const initialRange = length => ({ start: Math.max(0, length - 120), end: length, activeIndex: length - 1 });
const periodLabel = period => ({ day: '日', week: '周', month: '月', unknown: '原始（频率未知）' })[period] || '原始';
const maEnabled = state => Array.isArray(state.enabledMA) ? state.enabledMA : MA_PERIODS;
const overlayKeys = state => state.overlay === 'boll' ? BOLL.map(v => v[0]) : state.overlay === 'none' ? [] : maEnabled(state).map(n => `ma${n}`);
function rangeFor(length, state = {}) {
  if (!length) return { start: 0, end: 0, activeIndex: -1 };
  const end = finite(state.end) === null || !state.end ? length : clamp(Math.floor(state.end), 1, length);
  const start = finite(state.start) === null ? Math.max(0, end - 120) : clamp(Math.floor(state.start), 0, end - 1);
  const activeIndex = finite(state.activeIndex) === null ? end - 1 : clamp(Math.round(state.activeIndex), start, end - 1);
  return { start, end, activeIndex };
}
function displayBars(rows, state, metadata) {
  const bars = enrichMarketBars(rows); const source = sourceFrequency(metadata.frequency);
  return source === 'day' && ['week', 'month'].includes(state.period) ? aggregateMarketBars(bars, state.period) : bars;
}
function priceDomain(bars, state) {
  const { start, end } = rangeFor(bars.length, state); const keys = overlayKeys(state); const values = [];
  for (const bar of bars.slice(start, end)) {
    if (bar.validOHLC && !bar.gap) values.push(bar.low, bar.high);
    for (const key of keys) if (finite(bar[key]) !== null) values.push(bar[key]);
  }
  if (!values.length) return [0, 1];
  const low = Math.min(...values); const high = Math.max(...values); const padding = Math.max((high - low) * .08, .01);
  return [low - padding, high + padding];
}
function kdjDomain(bars, state) {
  const range = rangeFor(bars.length, state);
  const values = bars.slice(range.start, range.end).flatMap(b => [b.k, b.d, b.j]).filter(v => finite(v) !== null);
  return [Math.min(0, ...values), Math.max(100, ...values)];
}
function fieldUnit(metadata, key) {
  const fields = metadata.fields; const field = Array.isArray(fields) ? fields.find(f => f?.name === key || f?.key === key) : fields?.[key];
  if (typeof field !== 'object' || !field) return '';
  const unit = String(field.unit || field.units || '').trim(); const normalized = unit.toLowerCase();
  const currency = String(field.currency || (normalized === 'currency' ? metadata.currency : '') || '').toUpperCase();
  const currencies = { CNY: '元', RMB: '元', USD: '美元', HKD: '港元', EUR: '欧元', GBP: '英镑', JPY: '日元' };
  if (normalized === 'share' || normalized === 'shares') return '股';
  if (currencies[unit.toUpperCase()]) return currencies[unit.toUpperCase()];
  if ((!unit || normalized === 'currency') && currencies[currency]) return currencies[currency];
  return /^(?:万|亿)?(?:股|手|元|美元|港元|份|张|吨|克)$/.test(unit) ? unit : '';
}
function metadataLabel(metadata) {
  const currency = metadata.currency || metadata.fields?.close?.currency || '';
  const dataset = typeof metadata.dataset === 'string' ? metadata.dataset : metadata.dataset?.dataset_id || metadata.dataset?.id || '';
  return `源数据频率：${periodLabel(sourceFrequency(metadata.frequency))} ${currency} ${metadata.adjustment || ''} ${dataset}`;
}
function readout(bar, previous, metadata = {}) {
  if (!bar) return '<span>没有可绘制的有效日期历史记录。不会生成模拟行情。</span>';
  const base = finite(previous?.close); const change = base && finite(bar.close) !== null ? (bar.close / base - 1) * 100 : null;
  const changeAmount = base !== null && finite(bar.close) !== null ? bar.close - base : null;
  const amplitude = base && bar.validOHLC ? (bar.high - bar.low) / base * 100 : null;
  const volumeUnit = fieldUnit(metadata, 'volume') || '源单位'; const amountUnit = fieldUnit(metadata, 'amount') || fieldUnit(metadata, 'turnover') || '源单位';
  const values = [['开', fmt(bar.open)], ['高', fmt(bar.high)], ['低', fmt(bar.low)], ['收', fmt(bar.close)], ['涨跌额', changeAmount === null ? '—' : `${changeAmount > 0 ? '+' : ''}${fmt(changeAmount)}`], ['涨跌幅', change === null ? '—' : `${change > 0 ? '+' : ''}${fmt(change)}%`], ['均价（源字段）', fmt(bar.vwap)], ['振幅', amplitude === null ? '—' : `${fmt(amplitude)}%`], [`成交量（${volumeUnit}）`, fmt(bar.volume, 0)], [`成交额（${amountUnit}）`, fmt(bar.amount, 0)], ['换手率', bar.turnover_rate_pct === null ? '—' : `${fmt(bar.turnover_rate_pct)}%`]];
  return `<span class="asset-history-date">历史读数 <strong>${e(bar.date)}</strong></span>${values.map(([label, value]) => `<span>${e(label)} <strong>${e(value)}</strong></span>`).join('')}${bar.validOHLC && !bar.gap ? '' : '<span class="asset-chart-warning">OHLC 缺失、间断或不一致，未绘制该蜡烛</span>'}`;
}
function overlayReadout(bar, state) {
  if (!bar) return '';
  const keys = state.overlay === 'boll' ? BOLL : state.overlay === 'none' ? [] : maEnabled(state).map(n => [`ma${n}`, `MA${n}`, COLORS[MA_PERIODS.indexOf(n)]]);
  return keys.map(([key, label, color]) => `<span style="--asset-series-color:${color}">${label}: ${e(fmt(bar[key]))}</span>`).join('');
}
function panelLabels(bar = {}, theme = CHART_THEMES.dark) {
  return [['vol', '53.5%', `VOL:${fmt(bar.volume, 0)} MA5:${fmt(bar.volumeMA5, 0)} MA10:${fmt(bar.volumeMA10, 0)}`], ['macd', '64.5%', `MACD(12,26,9) DIF:${fmt(bar.dif, 4)} DEA:${fmt(bar.dea, 4)} MACD:${fmt(bar.macd, 4)}`], ['kdj', '77.5%', `KDJ(9,3,3) K:${fmt(bar.k)} D:${fmt(bar.d)} J:${fmt(bar.j)}`], ['rsi', '89.5%', `RSI(14):${fmt(bar.rsi)}`]].map(([id, top, text]) => ({ id: `kline-panel-label-${id}`, type: 'text', left: 50, top, silent: true, style: { fill: theme.text, font: '12px JetBrains Mono, SF Mono, Consolas, monospace', textAlign: 'left', textVerticalAlign: 'top', text } }));
}
function controls(state, length, metadata) {
  const source = sourceFrequency(metadata.frequency); const button = (action, label, active = false, disabled = false) => `<button type="button" class="kline-btn${active ? ' active' : ''}" data-asset-chart-action="${action}" aria-pressed="${active}"${disabled ? ' disabled' : ''}>${label}</button>`;
  const periods = [['day', '日K'], ['week', '周K'], ['month', '月K']].map(([p, label]) => button(`period-${p}`, label, state.period === p && !state.showAll, source !== 'day' && source !== p)).join('');
  return `<div class="asset-chart-toolbar"><div class="kline-period-group" role="group" aria-label="K线周期">${button('intraday', '分时', false, true)}${button('multiday', '多日', false, true)}${periods}${button('all', '全部', state.showAll)}</div><div class="asset-overlay-controls" role="group" aria-label="主图叠加指标">${button('overlay-ma', 'MA', state.overlay === 'ma')}${button('overlay-boll', 'BOLL', state.overlay === 'boll')}${button('overlay-none', '裸 K', state.overlay === 'none')}${MA_PERIODS.map(n => button(`ma-${n}`, `MA${n}`, maEnabled(state).includes(n))).join('')}</div><div class="asset-range-controls" role="group" aria-label="行情视区">${button('pan-back', '向前查看', false, !state.start)}${button('pan-forward', '向后查看', false, state.end === length)}${button('zoom-in', '放大')}${button('zoom-out', '缩小')}${button('reset', '近120条')}</div><span class="asset-range-summary" data-asset-range-summary>第 ${length ? state.start + 1 : 0}–${state.end} 条 / 共 ${length} 条</span></div>`;
}
function chipStats(chip) {
  const percent = v => v === null ? '—' : `${fmt(v * 100, 1)}%`;
  return [['筹码峰', fmt(chip.peak)], ['上边界', fmt(chip.upper)], ['下边界', fmt(chip.lower)], ['平均成本', fmt(chip.averageCost)], ['估算获利', percent(chip.profitFraction)], ['估算套牢', percent(chip.lockedFraction)]].map(([label, value]) => `<div><span>${label}</span><strong>${e(value)}</strong></div>`).join('');
}
export function renderMarketTerminal(rows = [], state = {}, metadata = {}) {
  const source = sourceFrequency(metadata.frequency); const normalized = { overlay: 'ma', enabledMA: [...MA_PERIODS], period: source, showAll: false, ...state };
  const bars = displayBars(rows, normalized, metadata); Object.assign(normalized, rangeFor(bars.length, normalized));
  const active = bars[normalized.activeIndex]; const chip = estimateChipDistribution(bars, normalized.start, normalized.activeIndex, priceDomain(bars, normalized));
  return `<section class="asset-market-terminal" aria-label="K 线与技术指标"><header><div><span class="eyebrow">MARKET TERMINAL</span><h2>K 线与技术指标</h2></div><span class="asset-terminal-period" data-asset-chart-metadata>${e(metadataLabel(metadata))}</span></header>${controls(normalized, bars.length, metadata)}<div class="asset-terminal-quote asset-history-readout" data-asset-history aria-live="off">${readout(active, bars[normalized.activeIndex - 1], metadata)}</div><div class="kline-terminal-layout"><div class="kline-indicator-rail" aria-hidden="true"><span class="active">主图</span><span>成交量</span><span>MACD</span><span>KDJ</span><span>RSI</span></div><div class="asset-kline-stage"><div class="asset-main-overlay" data-asset-overlay-label>${overlayReadout(active, normalized)}</div><div class="asset-terminal-chart" data-asset-chart data-asset-echarts role="img" tabindex="0" aria-label="包含 K 线、成交量、MACD、KDJ 和 RSI 的联动行情图"></div></div><aside class="asset-chip-panel"><div class="asset-chip-heading">筹码分布 <small>OHLCV估算</small></div><div class="chip-window-label" data-asset-chip-window>${chip.startDate ? e(`${chip.startDate}–${chip.endDate}`) : '暂无有效窗口'}</div><div class="asset-chip-chart" data-asset-chip-chart role="img" aria-label="OHLCV估算筹码分布"></div><div class="asset-chip-stats" data-asset-chip-stats>${chipStats(chip)}</div><p class="asset-chip-note">OHLCV估算：按区间成交量均匀分配价格，不是实际持仓；未建模换手衰减。</p></aside></div><p class="asset-chart-help">滚轮缩放、拖动平移与底部滑块联动五个面板。方向键选历史记录；离开图表后返回可见区最右记录。“全部”仅展示已加载数据，不请求供应商。</p><details class="asset-indicator-method"><summary>指标计算与数据缺口</summary><p>MA5/10/20/60/120/250 使用完整窗口；BOLL20 为样本标准差 ±2σ。EMA12/26 首收盘价起算，DIF 第26条、DEA9 与 MACD×2 第34条显示。KDJ9 从首个有效 RSV 起算、α=1/3；RSI14 为14个实际涨跌的简单滚动均值。缺失或无效 OHLC 和明确间断重置预热，周/月先聚合 OHLCV 再重算全部指标。成交量均线仅显示数值，单位按源字段。缺失数据保留缺口。</p></details></section>`;
}

/** Original AF ECharts 5.5 five-grid terminal configuration. */
export function buildMarketChartOption(bars, state = {}, metadata = {}, theme) {
  const palette = chartTheme(theme);
  const range = rangeFor(bars.length, state); const domain = priceDomain(bars, state); const dates = bars.map(b => b.date);
  const line = (name, key, axis, color) => ({ name, type: 'line', xAxisIndex: axis, yAxisIndex: axis, data: bars.map((b, i) => [i, b[key]]), smooth: false, connectNulls: false, lineStyle: { width: 1, color }, itemStyle: { color }, symbol: 'none', showSymbol: false });
  const series = [{ name: 'K线', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0, data: bars.map(b => b.validOHLC && !b.gap ? [b.open, b.close, b.low, b.high] : [null, null, null, null]), itemStyle: { color: UP, color0: DOWN, borderColor: UP, borderColor0: DOWN } }, { name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: bars.map((b, i) => [i, b.volume, b.validOHLC ? (b.close >= b.open ? 1 : -1) : 0]), barWidth: '60%', itemStyle: { color: p => p.data[2] > 0 ? UP : p.data[2] < 0 ? DOWN : palette.muted } }, ...MA_PERIODS.map((n, i) => line(`MA${n}`, `ma${n}`, 0, COLORS[i])), ...BOLL.map(([key, name, color]) => line(name, key, 0, color)), { name: 'MACD柱', type: 'bar', xAxisIndex: 2, yAxisIndex: 2, data: bars.map((b, i) => [i, b.macd, b.macd >= 0 ? 1 : -1]), barWidth: '60%', itemStyle: { color: p => p.data[2] > 0 ? UP : DOWN } }, line('DIF', 'dif', 2, COLORS[0]), line('DEA', 'dea', 2, COLORS[1]), line('K', 'k', 3, COLORS[0]), line('D', 'd', 3, COLORS[1]), line('J', 'j', 3, COLORS[2]), { ...line('RSI', 'rsi', 4, COLORS[2]), markLine: { silent: true, symbol: 'none', label: { color: palette.muted }, lineStyle: { type: 'dashed', width: 1, color: palette.grid }, data: [{ yAxis: 70 }, { yAxis: 30 }] } }];
  const selected = Object.fromEntries([...MA_PERIODS.map(n => [`MA${n}`, (state.overlay || 'ma') === 'ma' && maEnabled(state).includes(n)]), ...BOLL.map(([, name]) => [name, state.overlay === 'boll'])]);
  const [kdjMin, kdjMax] = kdjDomain(bars, state);
  const axisStyle = { axisLine: { onZero: false, lineStyle: { color: palette.grid } }, axisTick: { show: false }, splitLine: { show: false }, min: 'dataMin', max: 'dataMax' };
  return { backgroundColor: 'transparent', animation: false, legend: { show: false, selected }, tooltip: { trigger: 'axis', axisPointer: { type: 'cross', crossStyle: { color: palette.muted } }, backgroundColor: palette.surface, borderColor: palette.grid, textStyle: { color: palette.text, fontSize: 12 }, formatter: params => { const i = params?.[0]?.dataIndex; return i === undefined ? '' : readout(bars[i], bars[i - 1], metadata); } }, axisPointer: { link: [{ xAxisIndex: 'all' }], lineStyle: { color: palette.muted }, label: { backgroundColor: palette.surface, color: palette.text } }, graphic: panelLabels(bars[range.activeIndex], palette), grid: [{ left: 46, right: 8, top: 28, height: '44%' }, { left: 46, right: 8, top: '53%', height: '8%' }, { left: 46, right: 8, top: '64%', height: '10%' }, { left: 46, right: 8, top: '77%', height: '9%' }, { left: 46, right: 8, top: '89%', height: '6%' }], xAxis: Array.from({ length: 5 }, (_, i) => ({ ...axisStyle, type: 'category', gridIndex: i, data: dates, boundaryGap: true, axisLabel: { show: [0, 2, 4].includes(i), color: palette.muted, fontSize: 10 } })), yAxis: Array.from({ length: 5 }, (_, i) => ({ scale: i < 3, gridIndex: i, ...(i === 0 ? { min: domain[0], max: domain[1] } : i === 3 ? { min: kdjMin, max: kdjMax } : i === 4 ? { min: 0, max: 100 } : {}), splitNumber: i === 1 || i === 4 ? 2 : 3, axisLabel: { color: palette.muted, fontSize: i === 0 ? 10 : 9, formatter: i === 0 ? priceFmt : undefined }, ...(i === 0 ? { axisPointer: { label: { formatter: params => priceFmt(params.value) } } } : {}), axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: i !== 1, lineStyle: { color: palette.grid } }, splitArea: { show: false } })), dataZoom: [{ type: 'inside', xAxisIndex: [0, 1, 2, 3, 4], startValue: range.start, endValue: Math.max(0, range.end - 1), filterMode: 'none', zoomOnMouseWheel: true, moveOnMouseMove: true, moveOnMouseWheel: false }, { type: 'slider', xAxisIndex: [0, 1, 2, 3, 4], startValue: range.start, endValue: Math.max(0, range.end - 1), filterMode: 'none', height: 18, bottom: 2, borderColor: palette.grid, backgroundColor: 'transparent', fillerColor: palette.selected, dataBackground: { lineStyle: { color: palette.muted }, areaStyle: { color: palette.grid } }, selectedDataBackground: { lineStyle: { color: palette.muted }, areaStyle: { color: palette.selected } }, handleStyle: { color: palette.muted, borderColor: palette.surface }, moveHandleStyle: { color: palette.muted }, emphasis: { handleStyle: { color: palette.text }, moveHandleStyle: { color: palette.text } }, textStyle: { color: palette.muted, fontSize: 10 } }], series };
}

export function buildChipChartOption(chip, domain, echarts = null, theme) {
  const palette = chartTheme(theme);
  const markers = [['筹码峰', chip.peak, '#eab308'], ['上边界', chip.upper, '#f59e0b'], ['下边界', chip.lower, '#f59e0b'], ['参考收盘', chip.referenceClose, COLORS[0]], ['均本', chip.averageCost, COLORS[1]]].filter(([, value]) => finite(value) !== null).map(([name, value, color]) => ({ yAxis: value, name, lineStyle: { color, width: name === '筹码峰' ? 2 : 1.5, type: name === '筹码峰' ? 'solid' : 'dashed' }, label: { formatter: name, color: palette.text, fontSize: 10 } }));
  return { backgroundColor: 'transparent', animation: false, tooltip: { trigger: 'axis', axisPointer: { type: 'shadow', shadowStyle: { color: palette.selected } }, backgroundColor: palette.surface, borderColor: palette.grid, textStyle: { color: palette.text, fontSize: 11 }, formatter: p => p?.[0] ? `OHLCV估算<br>价格：${e(fmt(p[0].data[1]))}<br>占比：${e(fmt(p[0].data[0]))}%` : '' }, grid: { left: 4, right: 36, top: 8, bottom: 12, containLabel: false }, xAxis: { type: 'value', axisLabel: { color: palette.muted, fontSize: 9 }, axisLine: { show: false }, axisTick: { show: false }, splitLine: { lineStyle: { color: palette.grid } }, max: v => v.max ? v.max * 1.25 : 1 }, yAxis: { type: 'value', min: domain[0], max: domain[1], axisLabel: { color: palette.muted, fontSize: 9, formatter: v => fmt(v) }, axisLine: { lineStyle: { color: palette.grid } }, axisTick: { show: false }, splitLine: { show: false } }, graphic: chip.points.length ? [] : [{ type: 'text', left: 'center', top: 'middle', style: { text: '需至少5条有效OHLCV\n暂无筹码估算', fill: palette.muted, font: '11px sans-serif', textAlign: 'center' } }], series: [{ name: 'OHLCV估算筹码分布', type: 'custom', data: chip.points.map(p => [p.concentration_pct, p.price]), renderItem: (params, api) => { const concentration = api.value(0); const price = api.value(1); const start = api.coord([0, price]); const end = api.coord([concentration, price]); const height = Math.max(1, Math.min(3, Math.abs(api.size([0, (chip.bucketWidth || .01) * .72])[1]))); const rect = { x: start[0], y: start[1] - height / 2, width: Math.max(1, end[0] - start[0]), height }; const shape = echarts?.graphic?.clipRectByRect ? echarts.graphic.clipRectByRect(rect, params.coordSys) : rect; return shape ? { type: 'rect', shape, style: api.style({ fill: price > chip.referenceClose ? '#22c55e' : UP }) } : null; }, markLine: { silent: true, symbol: 'none', label: { position: 'end', fontSize: 9, color: palette.muted }, data: markers } }] };
}

export function createAssetChartController({ onChange = () => {}, logger = safeLog } = {}) {
  let rawRows = []; let bars = []; let identity; let metadata = {}; let source = 'day';
  let state = { overlay: 'ma', enabledMA: [...MA_PERIODS], period: 'day', showAll: false, ...initialRange(0), crosshairY: null };
  let slot = null; let main = null; let chips = null; let observer = null; let frame = null; let needsFull = false; let needsResize = false; let view = null; let library = null;
  let theme = chartTheme();
  const listeners = []; const chartListeners = []; const zrListeners = [];
  const log = method => { try { logger(`asset_chart_${method}_failed`, { status: 'error', method }); } catch { /* Diagnostic failures cannot stop resource disposal. */ } };
  const guarded = (method, fn) => { try { return fn(); } catch { log(method); return false; } };
  const getState = () => ({ ...state, enabledMA: [...state.enabledMA] });
  const find = selector => slot?.querySelector(selector);
  const notify = reason => guarded('change', () => onChange(getState(), { reason }));
  function pageTheme() {
    const root = slot?.ownerDocument?.documentElement;
    const fallback = chartTheme(root && root.dataset?.theme !== 'dark' ? 'light' : 'dark');
    try {
      const styles = view?.getComputedStyle?.(find('.asset-market-terminal') || slot);
      if (!styles) return fallback;
      return Object.fromEntries([['text', '--text'], ['muted', '--muted'], ['grid', '--line'], ['surface', '--surface'], ['selected', '--selected']].map(([key, token]) => [key, styles.getPropertyValue(token).trim() || fallback[key]]));
    } catch { log('theme'); return fallback; }
  }
  function syncLabels() {
    const meta = find('[data-asset-chart-metadata]'); if (meta) meta.textContent = metadataLabel(metadata);
    const bar = bars[state.activeIndex]; const history = find('[data-asset-history]'); if (history) history.innerHTML = readout(bar, bars[state.activeIndex - 1], metadata);
    const overlay = find('[data-asset-overlay-label]'); if (overlay) overlay.innerHTML = overlayReadout(bar, state);
    const summary = find('[data-asset-range-summary]'); if (summary) summary.textContent = `第 ${bars.length ? state.start + 1 : 0}–${state.end} 条 / 共 ${bars.length} 条`;
    for (const button of slot?.querySelectorAll('[data-asset-chart-action]') || []) {
      const action = button.dataset.assetChartAction; let pressed = false;
      if (action.startsWith('overlay-')) pressed = state.overlay === action.slice(8);
      else if (action.startsWith('ma-')) pressed = state.enabledMA.includes(Number(action.slice(3)));
      else if (action.startsWith('period-')) { const p = action.slice(7); pressed = state.period === p && !state.showAll; button.disabled = source !== 'day' && source !== p; }
      else if (action === 'all') pressed = state.showAll;
      else if (action === 'pan-back') button.disabled = state.start === 0;
      else if (action === 'pan-forward') button.disabled = state.end === bars.length;
      button.setAttribute('aria-pressed', String(pressed)); button.classList.toggle('active', pressed);
    }
    const layout = find('.kline-terminal-layout'); const chart = find('[data-asset-echarts]'); layout?.style.setProperty('--chip-chart-height', `${Math.max(220, Math.round((chart?.clientHeight || 690) * .44))}px`);
    if (chart?.dataset) Object.assign(chart.dataset, { visibleStart: String(state.start), visibleEnd: String(state.end), visibleCount: String(state.end - state.start), activeIndex: String(state.activeIndex), period: state.period, overlay: state.overlay, enabledMa: state.enabledMA.join(',') });
  }
  function flush() {
    frame = null; if (!slot) return;
    guarded('render', () => {
      if (needsFull) theme = pageTheme();
      syncLabels();
      const domain = priceDomain(bars, state);
      // Native dataZoom already owns its gesture state; only merge its price
      // domain/readouts here so a drag is not replaced by a full option reset.
      const [kdjMin, kdjMax] = kdjDomain(bars, state);
      if (main) main.setOption(needsFull ? buildMarketChartOption(bars, state, metadata, theme) : { graphic: panelLabels(bars[state.activeIndex], theme), yAxis: [{ min: domain[0], max: domain[1] }, {}, {}, { min: kdjMin, max: kdjMax }, {}] }, needsFull);
      const chip = estimateChipDistribution(bars, state.start, state.activeIndex, domain);
      const stats = find('[data-asset-chip-stats]'); if (stats) stats.innerHTML = chipStats(chip);
      const windowLabel = find('[data-asset-chip-window]'); if (windowLabel) windowLabel.textContent = chip.startDate ? `${chip.startDate}–${chip.endDate}（${chip.validBars}条有效）` : '暂无有效窗口';
      chips?.setOption(buildChipChartOption(chip, domain, library, theme), true);
      if (needsResize) { main?.resize(); chips?.resize(); }
    });
    needsFull = needsResize = false;
  }
  function schedule(full = false, resize = false) {
    needsFull ||= full; needsResize ||= resize; if (!slot || frame !== null) return;
    if (view?.requestAnimationFrame) frame = view.requestAnimationFrame(flush); else flush();
  }
  function update(next, reason, full = false) {
    if (!Object.entries(next).some(([key, value]) => JSON.stringify(value) !== JSON.stringify(state[key]))) return false;
    state = { ...state, ...next }; schedule(full); notify(reason); return true;
  }
  function release() {
    if (frame !== null) { guarded('cancel_frame', () => view?.cancelAnimationFrame?.(frame)); frame = null; }
    for (const [node, name, handler, options] of listeners.splice(0)) guarded('remove_listener', () => node.removeEventListener(name, handler, options));
    for (const [chart, name, handler] of chartListeners.splice(0)) guarded('remove_listener', () => chart.off(name, handler));
    for (const [zr, name, handler] of zrListeners.splice(0)) guarded('remove_listener', () => zr.off(name, handler));
    if (observer) guarded('observer_dispose', () => observer.disconnect()); observer = null;
    if (main) guarded('dispose', () => main.dispose()); if (chips) guarded('dispose', () => chips.dispose());
    main = chips = null; slot = null; view = null; library = null; needsFull = needsResize = false;
  }
  function initCharts() {
    if (!slot || main || !bars.length) return;
    const mainNode = find('[data-asset-echarts]'); const chipNode = find('[data-asset-chip-chart]'); if (!mainNode || !chipNode) return;
    library = view?.echarts || globalThis.echarts;
    if (!library?.init) { mainNode.textContent = '图表资源未加载，历史数据仍可读取。'; log('library'); return; }
    mainNode.textContent = ''; chipNode.textContent = '';
    main = library.init(mainNode, null, { devicePixelRatio: view?.devicePixelRatio || 1 }); chips = library.init(chipNode, null, { devicePixelRatio: view?.devicePixelRatio || 1 });
    const on = (name, handler) => { const safe = event => guarded('interaction', () => handler(event)); main.on(name, safe); chartListeners.push([main, name, safe]); };
    on('updateAxisPointer', event => {
      const axis = event?.axesInfo?.find(a => a.axisDim === 'x' && a.axisIndex === 0) || event?.axesInfo?.find(a => a.axisDim === 'x'); if (!axis) return;
      const index = Number.isInteger(Number(axis.value)) ? Number(axis.value) : bars.findIndex(b => b.date === String(axis.value)); if (index >= 0) select(clamp(index, state.start, state.end - 1));
    });
    on('dataZoom', event => {
      const zoom = event?.batch?.[0] || event || {}; const n = bars.length;
      const index = (value, percent, fallback) => finite(value) !== null ? Math.round(Number(value)) : finite(percent) !== null ? Math.round(Number(percent) / 100 * Math.max(0, n - 1)) : fallback;
      const start = clamp(index(zoom.startValue, zoom.start, state.start), 0, n - 1); const end = clamp(index(zoom.endValue, zoom.end, state.end - 1) + 1, start + 1, n);
      update({ start, end, activeIndex: end - 1, showAll: start === 0 && end === n, crosshairY: null }, 'zoom');
    });
    const zr = main.getZr?.(); if (zr) { const leave = () => resetPointer(); zr.on('globalout', leave); zrListeners.push([zr, 'globalout', leave]); }
    if (view?.ResizeObserver) { observer = new view.ResizeObserver(() => schedule(false, true)); observer.observe(mainNode); observer.observe(chipNode); }
    else if (view?.addEventListener) listen(view, 'resize', () => schedule(false, true));
    schedule(true, true);
  }
  function configure(rows = [], key = '', nextMetadata = {}) {
    const result = guarded('configure', () => {
      if (rawRows === rows && identity === key && metadata === nextMetadata) return getState();
      const previousBars = bars; const previous = state; const previousSource = source; const changedIdentity = identity !== key; rawRows = rows; identity = key; metadata = nextMetadata || {}; source = sourceFrequency(metadata.frequency);
      const period = changedIdentity || !previousBars.length || source !== previousSource ? source : source === 'day' ? state.period : source;
      bars = displayBars(rawRows, { ...state, period }, metadata);
      if (changedIdentity || !previousBars.length || period !== previous.period) state = { overlay: 'ma', enabledMA: [...MA_PERIODS], period, showAll: false, ...initialRange(bars.length), crosshairY: null };
      else {
        const count = previous.showAll ? bars.length : Math.min(previous.end - previous.start, bars.length); const pinned = previous.end === previousBars.length;
        let start = pinned ? bars.length - count : bars.findIndex(b => b.date === previousBars[previous.start]?.date); if (start < 0) start = clamp(previous.start, 0, Math.max(0, bars.length - count));
        const end = start + count; const selectedDate = previousBars[previous.activeIndex]?.date; let activeIndex = pinned && previous.activeIndex === previousBars.length - 1 ? bars.length - 1 : bars.findIndex(b => b.date === selectedDate);
        activeIndex = bars.length ? clamp(activeIndex < 0 ? start : activeIndex, start, end - 1) : -1;
        state = { ...state, start, end, activeIndex, crosshairY: null };
      }
      if (slot) { initCharts(); schedule(true); } return getState();
    });
    if (result === false) release(); return result;
  }
  function select(index) { if (!bars.length || finite(index) === null) return false; const activeIndex = clamp(Math.round(index), 0, bars.length - 1); const count = state.end - state.start; const start = activeIndex < state.start ? activeIndex : activeIndex >= state.end ? activeIndex - count + 1 : state.start; return update({ start, end: start + count, activeIndex }, 'select', start !== state.start); }
  function pan(delta) { if (!bars.length || finite(delta) === null) return false; const count = state.end - state.start; const start = clamp(state.start + Math.round(delta), 0, bars.length - count); const end = start + count; return update({ start, end, activeIndex: clamp(state.activeIndex, start, end - 1), showAll: start === 0 && end === bars.length }, 'pan', true); }
  function zoom(factor) { if (!bars.length || finite(factor) === null || factor <= 0) return false; const count = clamp(Math.round((state.end - state.start) * factor), Math.min(10, bars.length), bars.length); const start = clamp(Math.round(state.activeIndex - count / 2), 0, bars.length - count); const end = start + count; return update({ start, end, activeIndex: clamp(state.activeIndex, start, end - 1), showAll: count === bars.length }, 'zoom', true); }
  function reset() { return update({ ...initialRange(bars.length), showAll: false, crosshairY: null }, 'reset', true); }
  function resetPointer() { return update({ activeIndex: state.end - 1, crosshairY: null }, 'leave'); }
  function cancel() {
    if (frame !== null) { guarded('cancel_frame', () => view?.cancelAnimationFrame?.(frame)); frame = null; }
    state = { ...state, activeIndex: state.end - 1, crosshairY: null };
    // Publish the restored edge after cancel so unchanged leave is consistent.
    if (slot) flush(); else needsFull = needsResize = false;
    return true;
  }
  function handle(event) {
    return guarded('interaction', () => {
      if (event?.assetChartHandled) return true;
      if (event?.type === 'mouseleave' || event?.type === 'pointerleave') return resetPointer();
      if (event?.type === 'click') {
        const button = event.target?.closest?.('[data-asset-chart-action]'); if (!button || button.disabled) return false; const action = button.dataset.assetChartAction;
        if (['overlay-ma', 'overlay-boll', 'overlay-none'].includes(action)) return update({ overlay: action.slice(8) }, 'overlay', true);
        if (/^ma-(5|10|20|60|120|250)$/.test(action)) { const n = Number(action.slice(3)); return update({ enabledMA: state.enabledMA.includes(n) ? state.enabledMA.filter(v => v !== n) : MA_PERIODS.filter(v => v === n || state.enabledMA.includes(v)) }, 'ma', true); }
        if (action.startsWith('period-')) { const period = action.slice(7); if (!['day', 'week', 'month'].includes(period) || (source !== 'day' && source !== period)) return false; bars = displayBars(rawRows, { ...state, period }, metadata); return update({ period, ...initialRange(bars.length), showAll: false }, 'period', true); }
        if (action === 'all') return update({ start: 0, end: bars.length, activeIndex: bars.length - 1, showAll: true }, 'all', true);
        if (action === 'reset') return reset(); if (action === 'zoom-in') return zoom(.75); if (action === 'zoom-out') return zoom(1.4);
        if (action === 'pan-back') return pan(-Math.max(1, Math.round((state.end - state.start) / 4))); if (action === 'pan-forward') return pan(Math.max(1, Math.round((state.end - state.start) / 4))); return false;
      }
      if (event?.type === 'keydown' && !event.altKey && !event.ctrlKey && !event.metaKey) {
        if (!event.target?.closest?.('[data-asset-chart]')) return false;
        let handled = true;
        if (event.key === 'ArrowLeft') select(state.activeIndex - 1); else if (event.key === 'ArrowRight') select(state.activeIndex + 1); else if (event.key === 'Home') select(0); else if (event.key === 'End') select(bars.length - 1); else if (['+', '='].includes(event.key)) zoom(.75); else if (['-', '−', '_'].includes(event.key)) zoom(1.4); else if (event.key === 'Escape') resetPointer(); else handled = false;
        if (handled) event.preventDefault?.(); return handled;
      }
      return false;
    });
  }
  function listen(node, name, handler, options) { node.addEventListener(name, handler, options); listeners.push([node, name, handler, options]); }
  function mount(nextSlot) {
    release(); if (!nextSlot) return false; slot = nextSlot; view = slot.ownerDocument?.defaultView || (typeof window === 'undefined' ? null : window);
    const result = guarded('mount', () => {
      slot.innerHTML = renderMarketTerminal(rawRows, state, metadata);
      const localHandle = event => { const handled = handle(event); if (handled) { event.assetChartHandled = true; event.stopPropagation?.(); } };
      listen(slot, 'click', localHandle); listen(slot, 'keydown', localHandle);
      const chartNode = find('[data-asset-echarts]'); if (chartNode) { listen(chartNode, 'mouseleave', resetPointer); listen(chartNode, 'pointerleave', resetPointer); }
      initCharts(); schedule(true); return true;
    });
    if (result === false) release(); return result;
  }
  return { configure, getState, mount, dispose: release, cancel, handle, select, pan, zoom, reset };
}
