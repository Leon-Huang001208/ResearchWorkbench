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
const PANEL_NAMES = { volume: '成交量', macd: 'MACD', kdj: 'KDJ', rsi: 'RSI' };
const DEFAULT_PANELS = ['volume', 'macd'];
const panelsFor = state => [...new Set((Array.isArray(state.panels) ? state.panels : DEFAULT_PANELS).filter(id => Object.hasOwn(PANEL_NAMES, id)))];
const historyFor = metadata => metadata.asset_history || {};
const jobFor = metadata => metadata.historyJob || historyFor(metadata).job || {};
const completeHistory = metadata => {
  const history = historyFor(metadata); const coverage = history.coverage || {};
  if (Object.hasOwn(coverage, 'full_history')) return coverage.full_history === true;
  if (coverage.scope && coverage.scope !== 'all') return false;
  return coverage.complete === true || history.coverage_complete === true || history.complete === true;
};
const busyHistory = metadata => ['queued', 'pending', 'running', 'loading', 'fetching', 'cancelling', 'draining', 'waiting_resources'].includes(String(jobFor(metadata).status || jobFor(metadata).state || ''));
const retryableHistory = metadata => typeof jobFor(metadata).retryable === 'boolean' ? jobFor(metadata).retryable : ['failed', 'error', 'interrupted', 'cancelled'].includes(String(jobFor(metadata).status || jobFor(metadata).state || ''));
const requiresHistoryRebuild = metadata => jobFor(metadata).retryable === false && ['failed', 'error', 'interrupted'].includes(String(jobFor(metadata).status || jobFor(metadata).state || ''));
const adjustmentFor = metadata => {
  const text = String(historyFor(metadata).adjustment || metadata.adjustment || 'none');
  return ({ '不复权': 'none', '前复权': 'qfq', '后复权': 'hfq' })[text] || (['none', 'qfq', 'hfq'].includes(text) ? text : 'none');
};
const adjustmentLabel = value => ({ none: '不复权', qfq: '前复权', hfq: '后复权' })[value] || String(value || '口径未提供');
const nearestIndex = (bars, date) => {
  if (!bars.length) return -1;
  if (!date) return bars.length - 1;
  const index = bars.findIndex(bar => bar.date >= date);
  return index < 0 ? bars.length - 1 : index;
};
const actualDateIndex = (bars, date) => {
  const next = nearestIndex(bars, date);
  if (next <= 0 || !date || bars[next]?.date === date) return next;
  return Math.abs(Date.parse(bars[next - 1].date) - Date.parse(date)) <= Math.abs(Date.parse(bars[next].date) - Date.parse(date)) ? next - 1 : next;
};
const selectedIndex = (bars, state) => state.selectedDate ? nearestIndex(bars, state.selectedDate) : finite(state.activeIndex) === null ? bars.length - 1 : clamp(Math.round(state.activeIndex), 0, bars.length - 1);
const identityFor = (metadata, key) => {
  const identity = metadata.assetIdentity;
  return typeof identity === 'string' ? identity : identity && typeof identity === 'object' ? `${identity.code || identity.asset || ''}:${identity.asset_type || identity.type || 'stock'}` : String(key || '').split(':dataset:')[0];
};
function chartLayout(state = {}) {
  const panels = panelsFor(state); const top = 26; const mainHeight = 300; const panelStep = 100;
  return { panels, top, mainHeight, panelStep, height: top + mainHeight + panels.length * panelStep + 50,
    grid: [{ left: 8, right: 54, top, height: mainHeight }, ...panels.map((id, index) => ({ left: 8, right: 54, top: top + mainHeight + 28 + index * panelStep, height: 68 }))] };
}
function rangeFor(length, state = {}) {
  if (!length) return { start: 0, end: 0, activeIndex: -1 };
  const end = finite(state.end) === null || !state.end ? length : clamp(Math.floor(state.end), 1, length);
  const start = finite(state.start) === null ? Math.max(0, end - 120) : clamp(Math.floor(state.start), 0, end - 1);
  const activeIndex = finite(state.activeIndex) === null ? end - 1 : clamp(Math.round(state.activeIndex), 0, length - 1);
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
  const history = historyFor(metadata); const coverage = history.coverage || {};
  const anchor = history.anchor_verified === true || history.adjustment_anchor_verified === true ? `复权锚点已核验${history.anchor_date ? ` ${history.anchor_date}` : ''}` : history.canonical_version ? history.anchor_date ? `固定复权锚点 ${history.anchor_date}` : adjustmentFor(metadata) === 'none' ? '原始不复权日线' : '复权锚点未提供' : '原始锚点未核验';
  const source = typeof history.source === 'string' ? history.source : metadata.provider || (typeof metadata.source === 'string' ? metadata.source : metadata.source?.provider || '') || '';
  const start = coverage.actual_range?.start_date || coverage.actual_range?.start || coverage.start || history.loaded_start || '';
  const end = coverage.actual_range?.end_date || coverage.actual_range?.end || coverage.end || history.loaded_end || '';
  return `源数据频率：${periodLabel(sourceFrequency(metadata.frequency))} ${currency} ${metadata.adjustment || adjustmentLabel(adjustmentFor(metadata))} ${source} · ${anchor} · ${completeHistory(metadata) ? '全部历史已加载' : '历史覆盖未完整'}${coverage.boundary_verified === false ? '（上市边界未核验）' : ''} ${start}${end ? `–${end}` : ''} ${dataset}`;
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
function panelText(id, bar = {}) {
  return { volume: `VOL:${fmt(bar.volume, 0)} MA5:${fmt(bar.volumeMA5, 0)} MA10:${fmt(bar.volumeMA10, 0)}`, macd: `MACD(12,26,9) DIF:${fmt(bar.dif, 4)} DEA:${fmt(bar.dea, 4)} MACD:${fmt(bar.macd, 4)}`, kdj: `KDJ(9,3,3) K:${fmt(bar.k)} D:${fmt(bar.d)} J:${fmt(bar.j)}`, rsi: `RSI(14):${fmt(bar.rsi)}` }[id] || '';
}
function panelLabels(bar = {}, theme = CHART_THEMES.dark, state = {}) {
  const layout = chartLayout(state);
  return layout.panels.map((id, index) => ({ id: `kline-panel-label-${id}`, type: 'text', left: 10, top: layout.top + layout.mainHeight + 9 + index * layout.panelStep, silent: true, style: { opacity: state.domPanelHeaders ? 0 : 1, fill: theme.text, font: '10px SF Mono, Consolas, monospace', textAlign: 'left', textVerticalAlign: 'top', text: panelText(id, bar) } }));
}
function panelHeaders(state) {
  const layout = chartLayout(state);
  return layout.panels.map((id, index) => `<div class="asset-panel-header" style="top:${layout.top + layout.mainHeight + 3 + index * layout.panelStep}px" data-asset-panel="${id}"><span class="asset-panel-name">${PANEL_NAMES[id]}</span><span class="asset-panel-readout" data-asset-panel-readout="${id}"></span><button type="button" class="kline-btn" data-asset-chart-action="panel-remove-${id}" aria-label="移除 ${PANEL_NAMES[id]}" title="移除 ${PANEL_NAMES[id]}">×</button></div>`).join('');
}
function historyStatus(state, metadata) {
  const job = jobFor(metadata); const status = String(job.status || job.state || ''); const pending = busyHistory(metadata) || state.historyRequestPending;
  const chunks = finite(job.progress?.chunks_total); const completed = finite(job.progress?.chunks_completed);
  const progress = finite(job.progress?.percent ?? job.progress_pct ?? (typeof job.progress === 'number' ? job.progress : chunks > 0 && completed !== null ? completed / chunks * 100 : null));
  const count = finite(job.loaded_rows ?? job.progress?.loaded_rows ?? job.progress?.rows); const failed = ['failed', 'error', 'interrupted'].includes(status);
  if (pending) return `${state.requestedAdjustment ? `正在生成${adjustmentLabel(state.requestedAdjustment)}，当前仍显示${adjustmentLabel(state.adjustment)}原版本 · ` : ''}加载历史${progress === null ? '…' : ` ${fmt(clamp(progress, 0, 100), 0)}%`}${count === null ? '' : ` · ${fmt(count, 0)}条`}`;
  if (failed) return `${retryableHistory(metadata) ? '历史加载失败，可重试' : '历史口径已变化，请重新加载全历史'}${job.failure_code ? ` · ${job.failure_code}` : ''}`;
  if (status === 'cancelled') return '历史加载已取消，已取得数据保留，可重试';
  return completeHistory(metadata) ? '全部历史已加载' : metadata.canLoadHistory ? '可向前加载更多历史' : '旧快照 · 全历史尚未接入';
}
function controls(state, length, metadata) {
  const source = sourceFrequency(metadata.frequency); const pending = busyHistory(metadata) || state.historyRequestPending;
  const button = (action, label, active = false, disabled = false, extra = '') => `<button type="button" class="kline-btn${active ? ' active' : ''}" data-asset-chart-action="${action}" aria-pressed="${active}"${disabled ? ' disabled' : ''}${extra}>${label}</button>`;
  const periods = [['day', '日K'], ['week', '周K'], ['month', '月K']].map(([period, label]) => button(`period-${period}`, label, state.period === period, source !== 'day' && source !== period)).join('');
  const failed = retryableHistory(metadata);
  return `<div class="asset-chart-toolbar"><div class="kline-period-group" role="group" aria-label="K线周期">${periods}</div><select class="asset-chart-adjustment" data-asset-chart-adjustment aria-label="复权方式"${pending || !metadata.canLoadHistory ? ' disabled' : ''}>${[['none', '不复权'], ['qfq', '前复权'], ['hfq', '后复权']].map(([value, label]) => `<option value="${value}"${state.adjustment === value ? ' selected' : ''}>${label}</option>`).join('')}</select>${button('all', requiresHistoryRebuild(metadata) ? '重建全历史' : completeHistory(metadata) ? '全部已加载' : '全历史', state.showAll, pending || (!metadata.canLoadHistory && !completeHistory(metadata)))}<span class="asset-history-status" data-asset-history-status role="status">${e(historyStatus(state, metadata))}</span>${button('history-cancel', '取消', false, false, pending ? '' : ' hidden')}${button('history-retry', '重试', false, pending || !metadata.canLoadHistory, failed ? '' : ' hidden')}<div class="asset-overlay-controls" role="group" aria-label="主图叠加指标">${button('overlay-ma', 'MA', state.overlay === 'ma')}${button('overlay-boll', 'BOLL', state.overlay === 'boll')}${button('overlay-none', '裸K', state.overlay === 'none')}<details class="asset-chart-popover"><summary>均线⌄</summary><div class="asset-chart-popover-content" role="group" aria-label="主图均线">${MA_PERIODS.map(n => button(`ma-${n}`, `MA${n}`, maEnabled(state).includes(n))).join('')}<small>完整窗口后显示；缺失保留空档。</small></div></details></div><div class="asset-range-controls" role="group" aria-label="行情视区">${button('pan-back', '‹', false, !state.start && !metadata.canLoadHistory, ' aria-label="视区前移"')}${button('pan-forward', '›', false, state.end === length, ' aria-label="视区后移"')}${button('zoom-in', '＋', false, false, ' aria-label="放大视区"')}${button('zoom-out', '－', false, false, ' aria-label="缩小视区"')}${button('reset', '近120条')}</div></div>`;
}
function chipStats(chip) {
  const percent = value => value === null ? '—' : `${fmt(value * 100, 1)}%`;
  return [['筹码峰', fmt(chip.peak)], ['平均成本', fmt(chip.averageCost)], ['上边界', fmt(chip.upper)], ['下边界', fmt(chip.lower)], ['估算获利', percent(chip.profitFraction)], ['估算套牢', percent(chip.lockedFraction)]].map(([label, value]) => `<div><span>${label}</span><strong>${e(value)}</strong></div>`).join('');
}
function canonicalChip(daily, state) {
  return estimateChipDistribution(daily, 0, nearestIndex(daily, state.selectedDate));
}
export function renderMarketTerminal(rows = [], state = {}, metadata = {}) {
  const source = sourceFrequency(metadata.frequency); const daily = enrichMarketBars(rows);
  const normalized = { overlay: 'ma', enabledMA: [...MA_PERIODS], panels: [...DEFAULT_PANELS], period: source, showAll: false, adjustment: adjustmentFor(metadata), ...state };
  normalized.panels = panelsFor(normalized);
  const bars = displayBars(rows, normalized, metadata); Object.assign(normalized, rangeFor(bars.length, normalized));
  const activeIndex = selectedIndex(bars, normalized); normalized.activeIndex = activeIndex;
  normalized.selectedDate = daily[actualDateIndex(daily, normalized.selectedDate || bars[activeIndex]?.source_end_date || bars[activeIndex]?.date)]?.date || '';
  const active = source === 'day' ? daily[nearestIndex(daily, normalized.selectedDate)] : bars[activeIndex];
  const previous = source === 'day' ? daily[nearestIndex(daily, normalized.selectedDate) - 1] : bars[activeIndex - 1];
  const chip = canonicalChip(source === 'day' ? daily : [], normalized); const layout = chartLayout(normalized);
  return `<section class="asset-market-terminal" aria-label="行情与技术指标">${controls(normalized, bars.length, metadata)}<div class="asset-date-controls"><span>历史读数</span><button type="button" class="kline-btn" data-asset-chart-action="date-prev" aria-label="前一交易日">‹</button><input type="date" data-asset-selected-date aria-label="历史交易日期" value="${e(normalized.selectedDate)}" min="${e(daily[0]?.date || '')}" max="${e(daily.at(-1)?.date || '')}"><button type="button" class="kline-btn" data-asset-chart-action="date-next" aria-label="后一交易日">›</button><button type="button" class="kline-btn" data-asset-chart-action="latest">最新</button><span class="asset-selection-cue" data-asset-selection-cue></span><button type="button" class="kline-btn" data-asset-chart-action="locate" hidden>定位所选日</button></div><div class="asset-terminal-quote asset-history-readout" data-asset-history aria-live="off">${readout(active, previous, metadata)}</div><div class="kline-terminal-layout"><div class="asset-kline-stage"><div class="asset-main-overlay" data-asset-overlay-label>${overlayReadout(bars[activeIndex], normalized)}</div><div class="asset-terminal-chart" style="height:${layout.height}px" data-asset-chart data-asset-echarts role="img" tabindex="0" aria-label="K线与自定义副图；方向键选择历史交易日"></div><div class="asset-panel-headers" data-asset-panel-headers>${panelHeaders(normalized)}</div><div class="asset-panel-controls"><details class="asset-chart-popover"><summary>＋ 添加副图</summary><div class="asset-chart-popover-content" data-asset-panel-choices>${Object.entries(PANEL_NAMES).map(([id, name]) => `<button type="button" class="kline-btn" data-asset-chart-action="panel-add-${id}"${normalized.panels.includes(id) ? ' disabled' : ''}>${name}</button>`).join('')}</div></details><span class="asset-range-summary" data-asset-range-summary>第 ${bars.length ? normalized.start + 1 : 0}–${normalized.end} 条 / 共 ${bars.length} 条</span></div></div><aside class="asset-chip-panel"><div class="asset-chip-heading">筹码分布 <small>OHLCV估算</small></div><div class="asset-chip-chart" data-asset-chip-chart role="img" aria-label="日线累计至所选日的OHLCV估算筹码分布"></div><div class="chip-window-label" data-asset-chip-window>${chip.startDate ? e(`${chip.startDate}–${chip.endDate}`) : source !== 'day' ? '缺少日线底稿，累计筹码不可用' : '暂无有效窗口'}</div><div class="asset-chip-stats" data-asset-chip-stats>${chipStats(chip)}</div><p class="asset-chip-note">从首条已加载日线累计至所选日。按成交量均匀分配价格，不是实际持仓；未建模换手衰减。</p></aside></div><p class="asset-chart-help">滚轮缩放 · 拖动平移 · 底部滑块联动所有副图。点击 / 方向键选择交易日，视区变化保留所选日。<span data-asset-chart-metadata>${e(metadataLabel(metadata))}</span></p><details class="asset-indicator-method"><summary>指标计算与数据缺口</summary><p>MA5/10/20/60/120/250 使用完整窗口；BOLL20 为样本标准差 ±2σ。EMA12/26 首收盘价起算，DIF 第26条、DEA9 与 MACD×2 第34条显示。KDJ9 从首个有效 RSV 起算、α=1/3；RSI14 为14个实际涨跌的简单滚动均值。缺失或无效 OHLC 和明确间断重置预热，周/月先聚合 OHLCV 再重算全部指标。筹码始终使用同一版本日线的首日至所选日，视区和主图指标只改变显示价格轴。源字段单位缺失时不推测。</p></details></section>`;
}

/** One price grid and exactly the enabled lower panels; all axes share a range. */
export function buildMarketChartOption(bars, state = {}, metadata = {}, theme) {
  const palette = chartTheme(theme); const layout = chartLayout(state); const panels = layout.panels;
  const range = rangeFor(bars.length, state); const domain = priceDomain(bars, state); const dates = bars.map(bar => bar.date);
  const line = (name, key, axis, color) => ({ name, type: 'line', xAxisIndex: axis, yAxisIndex: axis, data: bars.map((bar, index) => [index, bar[key]]), smooth: false, connectNulls: false, lineStyle: { width: 1, color }, itemStyle: { color }, symbol: 'none', showSymbol: false });
  const volume = axis => ({ name: '成交量', type: 'bar', xAxisIndex: axis, yAxisIndex: axis, data: bars.map((bar, index) => [index, bar.volume, bar.validOHLC ? (bar.close >= bar.open ? 1 : -1) : 0]), barWidth: '60%', itemStyle: { color: params => params.data[2] > 0 ? UP : params.data[2] < 0 ? DOWN : palette.muted } });
  const series = [{ name: 'K线', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0, data: bars.map(bar => bar.validOHLC && !bar.gap ? [bar.open, bar.close, bar.low, bar.high] : [null, null, null, null]), itemStyle: { color: UP, color0: DOWN, borderColor: UP, borderColor0: DOWN } }, ...MA_PERIODS.map((period, index) => line(`MA${period}`, `ma${period}`, 0, COLORS[index])), ...BOLL.map(([key, name, color]) => line(name, key, 0, color))];
  panels.forEach((id, index) => {
    const axis = index + 1;
    if (id === 'volume') series.push(volume(axis));
    if (id === 'macd') series.push({ name: 'MACD柱', type: 'bar', xAxisIndex: axis, yAxisIndex: axis, data: bars.map((bar, i) => [i, bar.macd, bar.macd >= 0 ? 1 : -1]), barWidth: '60%', itemStyle: { color: params => params.data[2] > 0 ? UP : DOWN } }, line('DIF', 'dif', axis, COLORS[0]), line('DEA', 'dea', axis, COLORS[1]));
    if (id === 'kdj') series.push(line('K', 'k', axis, COLORS[0]), line('D', 'd', axis, COLORS[1]), line('J', 'j', axis, COLORS[2]));
    if (id === 'rsi') series.push({ ...line('RSI', 'rsi', axis, COLORS[2]), markLine: { silent: true, symbol: 'none', label: { color: palette.muted }, lineStyle: { type: 'dashed', width: 1, color: palette.grid }, data: [{ yAxis: 70 }, { yAxis: 30 }] } });
  });
  const selected = Object.fromEntries([...MA_PERIODS.map(period => [`MA${period}`, (state.overlay || 'ma') === 'ma' && maEnabled(state).includes(period)]), ...BOLL.map(([, name]) => [name, state.overlay === 'boll'])]);
  const [kdjMin, kdjMax] = kdjDomain(bars, state); const axes = layout.grid.map((grid, index) => index);
  const axisStyle = { axisLine: { onZero: false, lineStyle: { color: palette.grid } }, axisTick: { show: false }, splitLine: { show: false }, min: 'dataMin', max: 'dataMax' };
  return { backgroundColor: 'transparent', animation: false, legend: { show: false, selected }, tooltip: { trigger: 'axis', showContent: false, axisPointer: { type: 'cross', crossStyle: { color: palette.muted } }, backgroundColor: palette.surface, borderColor: palette.grid, textStyle: { color: palette.text, fontSize: 12 }, formatter: params => { const index = params?.[0]?.dataIndex; return index === undefined ? '' : readout(bars[index], bars[index - 1], metadata); } }, axisPointer: { link: [{ xAxisIndex: 'all' }], lineStyle: { color: palette.muted }, label: { backgroundColor: palette.surface, color: palette.text } }, graphic: panelLabels(bars[selectedIndex(bars, state)], palette, state), grid: layout.grid,
    xAxis: layout.grid.map((grid, index) => ({ ...axisStyle, type: 'category', gridIndex: index, data: dates, boundaryGap: true, axisLabel: { show: index === axes.length - 1, color: palette.muted, fontSize: 10, hideOverlap: true } })),
    yAxis: layout.grid.map((grid, index) => { const id = panels[index - 1]; return { scale: id !== 'rsi', gridIndex: index, position: 'right', ...(index === 0 ? { min: domain[0], max: domain[1] } : id === 'kdj' ? { min: kdjMin, max: kdjMax } : id === 'rsi' ? { min: 0, max: 100 } : {}), splitNumber: index === 0 ? 4 : 2, axisLabel: { color: palette.muted, fontSize: index === 0 ? 10 : 9, formatter: index === 0 ? priceFmt : undefined }, ...(index === 0 ? { axisPointer: { label: { formatter: params => priceFmt(params.value) } } } : {}), axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: id !== 'volume', lineStyle: { color: palette.grid } }, splitArea: { show: false } }; }),
    dataZoom: [{ type: 'inside', xAxisIndex: axes, startValue: range.start, endValue: Math.max(0, range.end - 1), filterMode: 'none', zoomOnMouseWheel: true, moveOnMouseMove: true, moveOnMouseWheel: false }, { type: 'slider', xAxisIndex: axes, startValue: range.start, endValue: Math.max(0, range.end - 1), filterMode: 'none', height: 18, bottom: 2, left: 8, right: 54, showDetail: false, borderColor: palette.grid, backgroundColor: 'transparent', fillerColor: palette.selected, dataBackground: { lineStyle: { color: palette.muted }, areaStyle: { color: palette.grid } }, selectedDataBackground: { lineStyle: { color: palette.muted }, areaStyle: { color: palette.selected } }, handleStyle: { color: palette.muted, borderColor: palette.surface }, moveHandleStyle: { color: palette.muted }, emphasis: { handleStyle: { color: palette.text }, moveHandleStyle: { color: palette.text } }, textStyle: { color: palette.muted, fontSize: 10 } }], series };
}

export function buildChipChartOption(chip, domain, echarts = null, theme) {
  const palette = chartTheme(theme);
  const markers = [['筹码峰', chip.peak, '#eab308'], ['上边界', chip.upper, '#f59e0b'], ['下边界', chip.lower, '#f59e0b'], ['参考收盘', chip.referenceClose, COLORS[0]], ['均本', chip.averageCost, COLORS[1]]].filter(([, value]) => finite(value) !== null).map(([name, value, color]) => ({ yAxis: value, name, lineStyle: { color, width: name === '筹码峰' ? 2 : 1.5, type: name === '筹码峰' ? 'solid' : 'dashed' }, label: { formatter: name, color: palette.text, fontSize: 10 } }));
  return { backgroundColor: 'transparent', animation: false, tooltip: { trigger: 'axis', axisPointer: { type: 'shadow', shadowStyle: { color: palette.selected } }, backgroundColor: palette.surface, borderColor: palette.grid, textStyle: { color: palette.text, fontSize: 11 }, formatter: p => p?.[0] ? `OHLCV估算<br>价格：${e(fmt(p[0].data[1]))}<br>占比：${e(fmt(p[0].data[0]))}%` : '' }, grid: { left: 0, right: 3, top: 0, bottom: 0, containLabel: false }, xAxis: { type: 'value', axisLabel: { color: palette.muted, fontSize: 9 }, axisLine: { show: false }, axisTick: { show: false }, splitLine: { lineStyle: { color: palette.grid } }, max: v => v.max ? v.max * 1.25 : 1 }, yAxis: { type: 'value', min: domain[0], max: domain[1], axisLabel: { color: palette.muted, fontSize: 9, formatter: v => fmt(v) }, axisLine: { lineStyle: { color: palette.grid } }, axisTick: { show: false }, splitLine: { show: false } }, graphic: chip.points.length ? [] : [{ type: 'text', left: 'center', top: 'middle', style: { text: '需至少5条有效OHLCV\n暂无筹码估算', fill: palette.muted, font: '11px sans-serif', textAlign: 'center' } }], series: [{ name: 'OHLCV估算筹码分布', type: 'custom', data: chip.points.map(p => [p.concentration_pct, p.price]), renderItem: (params, api) => { const concentration = api.value(0); const price = api.value(1); const start = api.coord([0, price]); const end = api.coord([concentration, price]); const height = Math.max(1, Math.min(3, Math.abs(api.size([0, (chip.bucketWidth || .01) * .72])[1]))); const rect = { x: start[0], y: start[1] - height / 2, width: Math.max(1, end[0] - start[0]), height }; const shape = echarts?.graphic?.clipRectByRect ? echarts.graphic.clipRectByRect(rect, params.coordSys) : rect; return shape ? { type: 'rect', shape, style: api.style({ fill: price > chip.referenceClose ? '#22c55e' : UP }) } : null; }, markLine: { silent: true, symbol: 'none', label: { position: 'end', fontSize: 9, color: palette.muted }, data: markers } }] };
}

export function createAssetChartController({ onChange = () => {}, onPanelsChange = () => {}, onHistoryRequest = () => {}, logger = safeLog } = {}) {
  let rawRows = []; let daily = []; let bars = []; let identity; let datasetKey = ''; let metadata = {}; let source = 'day';
  let state = { overlay: 'ma', enabledMA: [...MA_PERIODS], panels: [...DEFAULT_PANELS], period: 'day', adjustment: 'none', requestedAdjustment: null, selectedDate: '', historyViewAllRequested: false, showAll: false, ...initialRange(0), crosshairY: null, crosshairVisible: false, historyRequestPending: false };
  let slot = null; let main = null; let chips = null; let observer = null; let frame = null; let needsFull = false; let needsResize = false; let view = null; let library = null; let applying = false; let olderAnchor = ''; let lastHistoryScope = 'all'; let lastHistoryAdjustment = null; let pointerBlocked = false; let dragging = false; let gestureStartX = null; let historyRequestSerial = 0;
  let theme = chartTheme(); const chipCache = new Map();
  const listeners = []; const chartListeners = []; const zrListeners = [];
  const log = method => { try { logger(`asset_chart_${method}_failed`, { status: 'error', method }); } catch { /* Diagnostics must not prevent disposal. */ } };
  const guarded = (method, fn) => { try { return fn(); } catch { log(method); return false; } };
  const outside = () => bars.length > 0 && (state.activeIndex < state.start || state.activeIndex >= state.end);
  const getState = () => ({ ...state, selectedOutsideView: outside(), enabledMA: [...state.enabledMA], panels: [...state.panels] });
  const find = selector => slot?.querySelector(selector);
  const notify = reason => guarded('change', () => onChange(getState(), { reason }));
  const selectedDailyIndex = () => nearestIndex(daily, state.selectedDate);
  const currentBar = () => source === 'day' ? daily[selectedDailyIndex()] : bars[state.activeIndex];
  function pageTheme() {
    const root = slot?.ownerDocument?.documentElement; const fallback = chartTheme(root && root.dataset?.theme !== 'dark' ? 'light' : 'dark');
    try {
      const styles = view?.getComputedStyle?.(find('.asset-market-terminal') || slot); if (!styles) return fallback;
      return Object.fromEntries([['text', '--text'], ['muted', '--muted'], ['grid', '--line'], ['surface', '--surface'], ['selected', '--selected']].map(([key, token]) => [key, styles.getPropertyValue(token).trim() || fallback[key]]));
    } catch { log('theme'); return fallback; }
  }
  function cumulativeChip() {
    const history = historyFor(metadata);
    const version = history.canonical_version || history.canonicalVersion || history.version || metadata.canonicalVersion || datasetKey;
    const factor = history.factor_version || history.factorVersion || metadata.factorVersion || '';
    const key = JSON.stringify([identity, version, factor, state.selectedDate, adjustmentFor(metadata)]);
    if (!chipCache.has(key)) {
      chipCache.set(key, estimateChipDistribution(source === 'day' ? daily : [], 0, selectedDailyIndex()));
      if (chipCache.size > 24) chipCache.delete(chipCache.keys().next().value);
    }
    return chipCache.get(key);
  }
  function syncLabels() {
    const meta = find('[data-asset-chart-metadata]'); if (meta) meta.textContent = metadataLabel(metadata);
    const bar = currentBar(); const index = source === 'day' ? selectedDailyIndex() : state.activeIndex;
    const history = find('[data-asset-history]'); if (history) history.innerHTML = readout(bar, (source === 'day' ? daily : bars)[index - 1], metadata);
    const overlay = find('[data-asset-overlay-label]'); if (overlay) overlay.innerHTML = overlayReadout(bars[state.activeIndex], state);
    const summary = find('[data-asset-range-summary]'); if (summary) summary.textContent = `第 ${bars.length ? state.start + 1 : 0}–${state.end} 条 / 共 ${bars.length} 条`;
    const date = find('[data-asset-selected-date]'); if (date) { date.value = state.selectedDate; date.min = daily[0]?.date || ''; date.max = daily.at(-1)?.date || ''; }
    const cue = find('[data-asset-selection-cue]'); if (cue) cue.textContent = outside() ? `所选日 ${state.selectedDate} 在视区外` : '';
    const adjustment = find('[data-asset-chart-adjustment]'); if (adjustment) { adjustment.value = state.adjustment; adjustment.disabled = !metadata.canLoadHistory || busyHistory(metadata) || state.historyRequestPending; }
    const status = find('[data-asset-history-status]'); if (status) status.textContent = historyStatus(state, metadata);
    const pending = busyHistory(metadata) || state.historyRequestPending;
    for (const button of slot?.querySelectorAll('[data-asset-chart-action]') || []) {
      const action = button.dataset.assetChartAction; let pressed = false;
      if (action.startsWith('overlay-')) pressed = state.overlay === action.slice(8);
      else if (action.startsWith('ma-')) pressed = state.enabledMA.includes(Number(action.slice(3)));
      else if (action.startsWith('period-')) { const period = action.slice(7); pressed = state.period === period; button.disabled = source !== 'day' && source !== period; }
      else if (action.startsWith('panel-add-')) button.disabled = state.panels.includes(action.slice(10));
      else if (action === 'all') { pressed = state.showAll; button.disabled = pending || (!metadata.canLoadHistory && !completeHistory(metadata)); button.textContent = requiresHistoryRebuild(metadata) ? '重建全历史' : completeHistory(metadata) ? '全部已加载' : '全历史'; }
      else if (action === 'history-cancel') { button.hidden = !pending; button.disabled = String(jobFor(metadata).status || jobFor(metadata).state) === 'cancelling'; }
      else if (action === 'history-retry') { button.hidden = !retryableHistory(metadata); button.disabled = pending || !metadata.canLoadHistory; }
      else if (action === 'locate') button.hidden = !outside();
      else if (action === 'pan-back') button.disabled = state.start === 0 && (!metadata.canLoadHistory || completeHistory(metadata));
      else if (action === 'pan-forward') button.disabled = state.end === bars.length;
      button.setAttribute('aria-pressed', String(pressed)); button.classList.toggle('active', pressed);
    }
    const headers = find('[data-asset-panel-headers]');
    if (headers && headers.dataset.panels !== state.panels.join(',')) { headers.innerHTML = panelHeaders(state); headers.dataset.panels = state.panels.join(','); }
    for (const id of state.panels) { const label = find(`[data-asset-panel-readout="${id}"]`); if (label) label.textContent = panelText(id, bars[state.activeIndex]); }
    const chart = find('[data-asset-echarts]'); if (chart) {
      chart.style.height = `${chartLayout(state).height}px`;
      if (chart.dataset) Object.assign(chart.dataset, { visibleStart: String(state.start), visibleEnd: String(state.end), visibleCount: String(state.end - state.start), activeIndex: String(state.activeIndex), selectedDate: state.selectedDate, selectedOutsideView: String(outside()), period: state.period, overlay: state.overlay, enabledMa: state.enabledMA.join(','), panels: state.panels.join(','), adjustment: state.adjustment });
    }
  }
  function alignChips() {
    const mainNode = find('[data-asset-echarts]'); const chipNode = find('[data-asset-chip-chart]'); const panel = find('.asset-chip-panel');
    if (!mainNode || !chipNode || !panel) return;
    // Read the resolved ECharts coordinate rectangle after layout/resize. Both
    // canvases use zero internal vertical padding, so equal prices share pixels.
    const rect = main?.getModel?.().getComponent?.('grid', 0)?.coordinateSystem?.getRect?.() || chartLayout(state).grid[0];
    const mainRect = mainNode.getBoundingClientRect(); const panelRect = panel.getBoundingClientRect();
    const narrow = view?.matchMedia?.('(max-width: 760px)')?.matches === true;
    const top = narrow ? 0 : mainRect.top + Number(rect.y ?? rect.top) - panelRect.top;
    panel.style.setProperty('--chip-plot-top', `${Math.max(0, top)}px`);
    panel.style.setProperty('--chip-plot-height', `${Number(rect.height)}px`);
    chipNode.style.height = `${narrow ? 190 : Number(rect.height)}px`;
    if (chipNode.dataset) Object.assign(chipNode.dataset, { plotTop: String(mainRect.top + Number(rect.y ?? rect.top)), plotHeight: String(rect.height), aligned: String(!narrow) });
  }
  function axisPatch(domain) {
    const [low, high] = kdjDomain(bars, state);
    return [{ min: domain[0], max: domain[1] }, ...state.panels.map(id => id === 'kdj' ? { min: low, max: high } : id === 'rsi' ? { min: 0, max: 100 } : {})];
  }
  function flush() {
    frame = null; if (!slot) return;
    guarded('render', () => {
      if (needsFull) theme = pageTheme(); syncLabels();
      if (needsResize || needsFull) main?.resize({ height: chartLayout(state).height });
      const domain = priceDomain(bars, state); applying = true;
      try { main?.setOption(needsFull ? buildMarketChartOption(bars, { ...state, domPanelHeaders: true }, metadata, theme) : { graphic: panelLabels(bars[state.activeIndex], theme, { ...state, domPanelHeaders: true }), yAxis: axisPatch(domain) }, needsFull); }
      finally { applying = false; }
      alignChips(); const chipNode = find('[data-asset-chip-chart]'); chips?.resize({ height: parseFloat(chipNode?.style.height) || 300 });
      const chip = cumulativeChip(); const stats = find('[data-asset-chip-stats]'); if (stats) stats.innerHTML = chipStats(chip);
      const windowLabel = find('[data-asset-chip-window]'); if (windowLabel) windowLabel.textContent = chip.startDate ? `${chip.startDate}–${chip.endDate} · 累计${chip.validBars}条有效日线` : source !== 'day' ? '缺少日线底稿，累计筹码不可用' : '暂无有效窗口';
      chips?.setOption(buildChipChartOption(chip, domain, library, theme), true);
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
  function hidePointer() {
    guarded('pointer_hide', () => { applying = true; try { main?.dispatchAction?.({ type: 'hideTip' }); main?.dispatchAction?.({ type: 'updateAxisPointer', currTrigger: 'leave' }); } finally { applying = false; } });
    return update({ crosshairY: null, crosshairVisible: false }, 'leave');
  }
  function release() {
    if (frame !== null) { guarded('cancel_frame', () => view?.cancelAnimationFrame?.(frame)); frame = null; }
    for (const [node, name, handler, options] of listeners.splice(0)) guarded('remove_listener', () => node.removeEventListener(name, handler, options));
    for (const [chart, name, handler] of chartListeners.splice(0)) guarded('remove_listener', () => chart.off(name, handler));
    for (const [zr, name, handler] of zrListeners.splice(0)) guarded('remove_listener', () => zr.off(name, handler));
    if (observer) guarded('observer_dispose', () => observer.disconnect()); observer = null;
    if (main) guarded('dispose', () => main.dispose()); if (chips) guarded('dispose', () => chips.dispose());
    main = chips = null; slot = null; view = null; library = null; needsFull = needsResize = false; pointerBlocked = dragging = false;
  }
  function requestHistory(action = 'load', scope = 'all', requestedAdjustment) {
    if (!metadata.canLoadHistory) return false;
    if (action !== 'cancel' && (busyHistory(metadata) || state.historyRequestPending)) return false;
    if (action === 'load' && scope === 'older' && !historyFor(metadata).canonical_version) scope = 'recent';
    let attemptAnchor = '';
    if (action === 'load' && scope === 'older') {
      if (completeHistory(metadata)) return false;
      attemptAnchor = `${identity}:${daily[0]?.date}:${historyFor(metadata).canonical_version || datasetKey}`;
      if (olderAnchor === attemptAnchor) return false; olderAnchor = attemptAnchor;
    }
    const previousTarget = jobFor(metadata).adjustment || lastHistoryAdjustment || state.adjustment;
    const adjustment = requestedAdjustment || (action === 'retry' || action === 'cancel' ? previousTarget : state.adjustment);
    if (action !== 'cancel') {
      lastHistoryScope = scope; lastHistoryAdjustment = adjustment;
      update({ historyRequestPending: true, historyViewAllRequested: scope === 'all', requestedAdjustment: adjustment === state.adjustment ? null : adjustment }, 'history');
    }
    const requestSerial = ++historyRequestSerial;
    const rejected = () => {
      if (requestSerial !== historyRequestSerial) return;
      if (attemptAnchor && olderAnchor === attemptAnchor) olderAnchor = '';
      update({ historyRequestPending: false, historyViewAllRequested: false, requestedAdjustment: null }, 'history_failed');
    };
    const result = guarded('history_request', () => onHistoryRequest({ action, scope, adjustment }));
    if (result === false) { rejected(); return false; }
    if (result && typeof result.then === 'function') result.then(accepted => {
      if (requestSerial !== historyRequestSerial) return;
      if (accepted === false) { rejected(); return; }
      state = { ...state, historyRequestPending: false }; schedule();
    }, () => { if (requestSerial !== historyRequestSerial) return; log('history_request'); rejected(); });
    return true;
  }
  function reachedLeft(previousStart) { if (state.start === 0 && previousStart > 0) requestHistory('load', 'older'); }
  function initCharts() {
    if (!slot || main || !bars.length) return;
    const mainNode = find('[data-asset-echarts]'); const chipNode = find('[data-asset-chip-chart]'); if (!mainNode || !chipNode) return;
    library = view?.echarts || globalThis.echarts;
    if (!library?.init) { mainNode.textContent = '图表资源未加载，历史数据仍可读取。'; log('library'); return; }
    mainNode.textContent = ''; chipNode.textContent = '';
    main = library.init(mainNode, null, { devicePixelRatio: view?.devicePixelRatio || 1 }); chips = library.init(chipNode, null, { devicePixelRatio: view?.devicePixelRatio || 1 });
    const on = (name, handler) => { const safe = event => guarded('interaction', () => handler(event)); main.on(name, safe); chartListeners.push([main, name, safe]); };
    on('updateAxisPointer', event => {
      if (applying || pointerBlocked || dragging || event?.currTrigger === 'leave') return;
      const axis = event?.axesInfo?.find(item => item.axisDim === 'x'); if (!axis) return;
      const index = Number.isInteger(Number(axis.value)) ? Number(axis.value) : bars.findIndex(bar => bar.date === String(axis.value));
      if (index >= 0) select(clamp(index, state.start, state.end - 1), false, true);
    });
    on('dataZoom', event => {
      if (applying || !bars.length) return; pointerBlocked = true;
      const zoom = event?.batch?.[0] || event || {}; const count = bars.length;
      const index = (value, percent, fallback) => finite(value) !== null ? Math.round(Number(value)) : finite(percent) !== null ? Math.round(Number(percent) / 100 * Math.max(0, count - 1)) : fallback;
      const start = clamp(index(zoom.startValue, zoom.start, state.start), 0, count - 1); const end = clamp(index(zoom.endValue, zoom.end, state.end - 1) + 1, start + 1, count); const previousStart = state.start;
      update({ start, end, showAll: start === 0 && end === count, crosshairY: null }, 'zoom'); reachedLeft(previousStart);
    });
    const zr = main.getZr?.(); if (zr) {
      const leave = () => hidePointer(); zr.on('globalout', leave); zrListeners.push([zr, 'globalout', leave]);
      const choose = event => guarded('selection', () => { const point = [event.offsetX, event.offsetY]; if (main.containPixel?.({ gridIndex: 0 }, point) === false) return; const value = main.convertFromPixel?.({ xAxisIndex: 0 }, point[0]); if (finite(value) !== null) select(Math.round(value), false, true); });
      zr.on('click', choose); zrListeners.push([zr, 'click', choose]);
      const gestures = { mousedown: event => { dragging = true; pointerBlocked = true; gestureStartX = finite(event?.offsetX); }, mouseup: () => { dragging = false; gestureStartX = null; }, mousemove: event => { if (!dragging && !event?.event?.buttons) pointerBlocked = false; else if (state.start === 0 && gestureStartX !== null && finite(event?.offsetX) !== null && event.offsetX - gestureStartX > 4) requestHistory('load', 'older'); }, mousewheel: () => { pointerBlocked = true; } };
      for (const [name, handler] of Object.entries(gestures)) { zr.on(name, handler); zrListeners.push([zr, name, handler]); }
    }
    if (view?.ResizeObserver) { observer = new view.ResizeObserver(() => schedule(false, true)); observer.observe(mainNode); }
    else if (view?.addEventListener) listen(view, 'resize', () => schedule(false, true));
    schedule(true, true);
  }
  function configure(rows = [], key = '', nextMetadata = {}, preferences) {
    const result = guarded('configure', () => {
      const nextIdentity = identityFor(nextMetadata || {}, key); const changedIdentity = identity !== nextIdentity;
      if (rawRows === rows && datasetKey === key && metadata === nextMetadata && !preferences) return getState();
      const previousBars = bars; const previous = state; const previousSource = source; const changedRows = rawRows !== rows || datasetKey !== key;
      rawRows = rows; identity = nextIdentity; datasetKey = key; metadata = nextMetadata || {}; source = sourceFrequency(metadata.frequency);
      daily = enrichMarketBars(rawRows);
      const period = changedIdentity || !previousBars.length || source !== previousSource ? source : source === 'day' ? state.period : source;
      bars = source === 'day' && ['week', 'month'].includes(period) ? aggregateMarketBars(daily, period) : daily;
      if (changedIdentity || !previousBars.length) {
        chipCache.clear(); olderAnchor = ''; lastHistoryAdjustment = null; historyRequestSerial++;
        state = { overlay: 'ma', enabledMA: [...MA_PERIODS], panels: preferences ? panelsFor(preferences) : [...previous.panels], period, adjustment: adjustmentFor(metadata), requestedAdjustment: null, selectedDate: daily.at(-1)?.date || '', historyViewAllRequested: false, showAll: false, ...initialRange(bars.length), crosshairY: null, crosshairVisible: false, historyRequestPending: false };
      } else {
        if (changedRows) chipCache.clear();
        const startDate = previousBars[previous.start]?.source_start_date || previousBars[previous.start]?.date;
        const endDate = previousBars[previous.end - 1]?.date;
        const start = previous.showAll ? 0 : Math.max(0, nearestIndex(bars, startDate));
        const end = bars.length ? previous.showAll ? bars.length : Math.max(start + 1, nearestIndex(bars, endDate) + 1) : 0;
        const selectedDate = daily[actualDateIndex(daily, previous.selectedDate)]?.date || '';
        state = { ...previous, period, selectedDate, start, end, adjustment: adjustmentFor(metadata), historyRequestPending: busyHistory(metadata) ? previous.historyRequestPending : changedRows || ['completed', 'complete', 'succeeded', 'failed', 'error', 'cancelled', 'interrupted'].includes(String(jobFor(metadata).status || jobFor(metadata).state || '')) ? false : previous.historyRequestPending, crosshairY: null, crosshairVisible: false };
        if (preferences) state.panels = panelsFor(preferences);
        if (changedRows && adjustmentFor(metadata) === previous.requestedAdjustment) state.requestedAdjustment = null;
        if (changedRows && previous.historyViewAllRequested && completeHistory(metadata)) state = { ...state, start: 0, end: bars.length, showAll: true, historyViewAllRequested: false };
        if (['failed', 'error', 'cancelled', 'interrupted'].includes(String(jobFor(metadata).status || jobFor(metadata).state || ''))) {
          state.historyViewAllRequested = false; state.requestedAdjustment = null; olderAnchor = '';
        }
        state.activeIndex = selectedIndex(bars, state);
      }
      if (slot) { initCharts(); schedule(true, true); } return getState();
    });
    if (result === false) release(); return result;
  }
  function setPreferences(preferences = {}) { if (!Array.isArray(preferences.panels)) return false; return update({ panels: panelsFor(preferences) }, 'preferences', true); }
  function select(index, reveal = true, pointer = false) {
    if (!bars.length || finite(index) === null) return false;
    const activeIndex = clamp(Math.round(index), 0, bars.length - 1); const selectedDate = bars[activeIndex].source_end_date || bars[activeIndex].date;
    const count = state.end - state.start; const start = reveal ? activeIndex < state.start ? activeIndex : activeIndex >= state.end ? Math.max(0, activeIndex - count + 1) : state.start : state.start;
    return update({ start, end: start + count, activeIndex, selectedDate, crosshairVisible: pointer }, 'select', start !== state.start);
  }
  function selectDate(date, reveal = false) {
    if (!daily.length || !/^\d{4}-\d{2}-\d{2}$/.test(String(date)) || !Number.isFinite(Date.parse(date)) || new Date(date).toISOString().slice(0, 10) !== date) return false;
    const selectedDate = daily[actualDateIndex(daily, date)].date; const activeIndex = nearestIndex(bars, selectedDate);
    const count = state.end - state.start; const start = reveal && (activeIndex < state.start || activeIndex >= state.end) ? clamp(activeIndex - Math.floor(count / 2), 0, bars.length - count) : state.start;
    return update({ selectedDate, activeIndex, start, end: start + count, crosshairVisible: false }, 'date', start !== state.start);
  }
  function pan(delta) {
    if (!bars.length || finite(delta) === null) return false;
    const count = state.end - state.start; const previousStart = state.start; const start = clamp(state.start + Math.round(delta), 0, bars.length - count); const end = start + count;
    const result = update({ start, end, showAll: start === 0 && end === bars.length }, 'pan', true);
    reachedLeft(previousStart); if (delta < 0 && previousStart === 0) requestHistory('load', 'older'); return result;
  }
  function zoom(factor) {
    if (!bars.length || finite(factor) === null || factor <= 0) return false;
    const count = clamp(Math.round((state.end - state.start) * factor), Math.min(10, bars.length), bars.length);
    const start = clamp(Math.round((state.start + state.end) / 2 - count / 2), 0, bars.length - count); const end = start + count; const previousStart = state.start;
    const result = update({ start, end, showAll: count === bars.length }, 'zoom', true); reachedLeft(previousStart); return result;
  }
  function reset() { hidePointer(); return update({ ...initialRange(bars.length), selectedDate: daily.at(-1)?.date || '', historyViewAllRequested: false, showAll: false, crosshairY: null, crosshairVisible: false }, 'reset', true); }
  function locate() { if (!bars.length) return false; const count = state.end - state.start; const start = clamp(state.activeIndex - Math.floor(count / 2), 0, bars.length - count); return update({ start, end: start + count }, 'locate', true); }
  function cancel() {
    if (frame !== null) { guarded('cancel_frame', () => view?.cancelAnimationFrame?.(frame)); frame = null; }
    hidePointer(); if (frame !== null) { guarded('cancel_frame', () => view?.cancelAnimationFrame?.(frame)); frame = null; }
    if (slot) flush(); else needsFull = needsResize = false; return true;
  }
  function changePeriod(period) {
    if (!['day', 'week', 'month'].includes(period) || (source !== 'day' && source !== period)) return false;
    const old = bars; const startDate = old[state.start]?.source_start_date || old[state.start]?.date; const endDate = old[state.end - 1]?.date;
    bars = period === 'day' ? daily : aggregateMarketBars(daily, period);
    const start = state.showAll ? 0 : Math.max(0, nearestIndex(bars, startDate)); const end = bars.length ? Math.max(start + 1, state.showAll ? bars.length : nearestIndex(bars, endDate) + 1) : 0;
    return update({ period, start, end, activeIndex: nearestIndex(bars, state.selectedDate), crosshairVisible: false }, 'period', true);
  }
  function handle(event) {
    return guarded('interaction', () => {
      if (event?.assetChartHandled) return true;
      if (event?.type === 'mouseleave' || event?.type === 'pointerleave') return hidePointer();
      if (event?.type === 'change') {
        if (event.target?.matches?.('[data-asset-selected-date]')) return selectDate(event.target.value);
        if (event.target?.matches?.('[data-asset-chart-adjustment]')) {
          const adjustment = event.target.value; if (!['none', 'qfq', 'hfq'].includes(adjustment) || !metadata.canLoadHistory || busyHistory(metadata) || state.historyRequestPending) return false;
          if (adjustment === state.adjustment) return false;
          return requestHistory('load', 'recent', adjustment);
        }
      }
      if (event?.type === 'click') {
        const button = event.target?.closest?.('[data-asset-chart-action]'); if (!button || button.disabled) return false; const action = button.dataset.assetChartAction;
        if (['overlay-ma', 'overlay-boll', 'overlay-none'].includes(action)) return update({ overlay: action.slice(8) }, 'overlay', true);
        if (/^ma-(5|10|20|60|120|250)$/.test(action)) { const period = Number(action.slice(3)); return update({ enabledMA: state.enabledMA.includes(period) ? state.enabledMA.filter(value => value !== period) : MA_PERIODS.filter(value => value === period || state.enabledMA.includes(value)) }, 'ma', true); }
        if (action.startsWith('panel-add-') || action.startsWith('panel-remove-')) {
          const add = action.startsWith('panel-add-'); const id = action.slice(add ? 10 : 13); if (!Object.hasOwn(PANEL_NAMES, id) || add === state.panels.includes(id)) return false;
          const panels = add ? [...state.panels, id] : state.panels.filter(value => value !== id);
          const changed = update({ panels }, 'panels', true); if (changed) guarded('panels_change', () => onPanelsChange([...panels])); return changed;
        }
        if (action.startsWith('period-')) return changePeriod(action.slice(7));
        if (action === 'all') {
          if (completeHistory(metadata) && !requiresHistoryRebuild(metadata)) return update({ start: 0, end: bars.length, showAll: true }, 'all', true);
          return requestHistory('load', 'all');
        }
        if (action === 'history-cancel') return requestHistory('cancel', jobFor(metadata).scope || lastHistoryScope);
        if (action === 'history-retry') return retryableHistory(metadata) && requestHistory('retry', jobFor(metadata).scope || lastHistoryScope);
        if (action === 'date-prev' || action === 'date-next') return selectDate(daily[clamp(selectedDailyIndex() + (action === 'date-prev' ? -1 : 1), 0, daily.length - 1)]?.date);
        if (action === 'latest' || action === 'reset') return reset(); if (action === 'locate') return locate();
        if (action === 'zoom-in') return zoom(.75); if (action === 'zoom-out') return zoom(1.4);
        if (action === 'pan-back') return pan(-Math.max(1, Math.round((state.end - state.start) / 4))); if (action === 'pan-forward') return pan(Math.max(1, Math.round((state.end - state.start) / 4))); return false;
      }
      if (event?.type === 'keydown' && !event.altKey && !event.ctrlKey && !event.metaKey) {
        if (!event.target?.closest?.('[data-asset-chart]')) return false;
        let handled = true;
        if (event.key === 'ArrowLeft') select(state.activeIndex - 1); else if (event.key === 'ArrowRight') select(state.activeIndex + 1); else if (event.key === 'Home') select(0); else if (event.key === 'End') select(bars.length - 1); else if (['+', '='].includes(event.key)) zoom(.75); else if (['-', '−', '_'].includes(event.key)) zoom(1.4); else if (event.key === 'Escape') hidePointer(); else handled = false;
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
      listen(slot, 'click', localHandle); listen(slot, 'keydown', localHandle); listen(slot, 'change', localHandle);
      for (const selector of ['[data-asset-echarts]', '[data-asset-chip-chart]']) { const node = find(selector); if (node) { listen(node, 'mouseleave', hidePointer); listen(node, 'pointerleave', hidePointer); } }
      initCharts(); schedule(true); return true;
    });
    if (result === false) release(); return result;
  }
  return { configure, getState, setPreferences, mount, dispose: release, cancel, handle, select, selectDate, pan, zoom, reset, locate };
}
