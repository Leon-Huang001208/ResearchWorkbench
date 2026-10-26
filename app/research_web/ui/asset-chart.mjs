import {INDICATOR_IDS, INDICATOR_CATALOG, DEFAULT_FAVORITES, INDICATOR_RULES, normalizeIndicatorSettings, normalizeFavorites, calculatePanelIndicators, indicatorSeries, indicatorTitle, panelField} from './asset-indicator-library.mjs';
import {indicatorStrip, indicatorManager, indicatorParameterForm} from './asset-panel-manager.mjs';
import { formatAssetMagnitude, formatAssetVolume, assetPriceClass, assetChangeClass } from './asset-format.mjs';
import { escapeHTML as e } from './markdown.mjs';
import { safeLog } from './core.mjs';
import { createRangeController } from './asset-range-controller.mjs';
import { MA_PERIODS, finite, enrichMarketBars, aggregateMarketBars, sourceFrequency } from './asset-indicators.mjs';
import { estimateChips, normalizeChipSettings, unavailable } from './asset-chips.mjs';
import { chipPanel, chipStatistics, chipSettingsForm, chipChartOption, chipPeakLines } from './asset-chip-panel.mjs';
export { enrichMarketBars } from './asset-indicators.mjs';

const UP = '#ff4d4f'; const DOWN = '#00c896';
const CHART_THEMES = {
  dark: { seriesColors: ['#d1d5db','#ed8936','#22d3ee','#a78bfa'], text: '#d1d5db', muted: '#9ca3af', grid: 'rgba(148,163,184,.18)', surface: '#11151c', selected: 'rgba(148,163,184,.18)' },
  light: { seriesColors: ['#242424','#a5500d','#086aa6','#7552a2'], text: '#242424', muted: '#686860', grid: '#e8e8e5', surface: '#fafaf9', selected: '#e8e8e5' },
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
const PANEL_NAMES = Object.fromEntries(INDICATOR_CATALOG.map(item => [item.id,item.name]));
const DEFAULT_PANELS = ['volume', 'macd'];
const panelsFor = state => [...new Set((Array.isArray(state.panels) ? state.panels : DEFAULT_PANELS).filter(id => Object.hasOwn(PANEL_NAMES, id)))];
const historyFor = metadata => metadata.asset_history || {};
const canLoadChip = metadata => Boolean(metadata.canLoadHistory && (historyFor(metadata).source === 'tinysoft' || ((historyFor(metadata).source === 'auto' || !historyFor(metadata).source) && (metadata.provider === 'tinysoft' || metadata.source === 'tinysoft'))));
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
  const asset=typeof identity === 'string' ? identity : identity && typeof identity === 'object' ? `${identity.code || identity.asset || ''}:${identity.asset_type || identity.type || 'stock'}` : String(key || '').split(':dataset:')[0];
  return JSON.stringify([metadata.accountIdentity || 'single-user',asset,metadata.chartIdentity || '']);
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
  const bars = enrichMarketBars(rows, {timestamp: metadata.minute_k === true}); const source = sourceFrequency(metadata.frequency);
  return calculatePanelIndicators(source === 'day' && ['week', 'month'].includes(state.period) ? aggregateMarketBars(bars, state.period) : bars, state.indicatorSettings);
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
  const values = bars.slice(range.start, range.end).flatMap(b => [b[panelField('kdj','k')] ?? b.k, b[panelField('kdj','d')] ?? b.d, b[panelField('kdj','j')] ?? b.j]).filter(v => finite(v) !== null);
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
  const history = historyFor(metadata), coverage = history.coverage || {};
  const start = coverage.actual_range?.start_date || coverage.actual_range?.start || history.loaded_start || '';
  const end = coverage.actual_range?.end_date || coverage.actual_range?.end || history.loaded_end || '';
  return [`${periodLabel(sourceFrequency(metadata.frequency))}线`, adjustmentLabel(adjustmentFor(metadata)), start ? `${start}${end ? `–${end}` : ''}` : '', coverage.boundary_verified === false ? '历史起点未核实' : ''].filter(Boolean).join(' · ');
}
function readout(bar, previous, metadata = {}) {
  if (!bar) return '<span>没有可绘制的有效日期历史记录。不会生成模拟行情。</span>';
  const base = finite(previous?.close); const change = base && finite(bar.close) !== null ? (bar.close / base - 1) * 100 : null;
  const changeAmount = base !== null && finite(bar.close) !== null ? bar.close - base : null;
  const movement = change === null ? '—' : `${change > 0 ? '+' : ''}${fmt(change)}%（${changeAmount > 0 ? '+' : ''}${fmt(changeAmount)}）`;
  const amplitude = base && bar.validOHLC ? (bar.high - bar.low) / base * 100 : null;
  const volumeUnit = fieldUnit(metadata, 'volume') || '源单位'; const amountUnit = fieldUnit(metadata, 'amount') || fieldUnit(metadata, 'turnover') || '源单位';
  const volumeNote = typeof metadata.assetIdentity === 'string' && /^stock:\d{6}\.(?:SH|SZ|BJ)$/i.test(metadata.assetIdentity) && /股$/.test(volumeUnit) ? '成交量（手；1手=100股，仅展示换算）' : `成交量（${volumeUnit}；不推测未知单位）`;
  const values = [['收', fmt(bar.close), assetPriceClass(bar.close, base)], ['幅', movement, assetChangeClass(change)], ['开', fmt(bar.open), assetPriceClass(bar.open, base)], ['高', fmt(bar.high), assetPriceClass(bar.high, base)], ['低', fmt(bar.low), assetPriceClass(bar.low, base)], ['均', fmt(bar.vwap), assetPriceClass(bar.vwap, base)], ['量', formatAssetVolume(bar.volume, volumeUnit === '源单位' ? '' : volumeUnit, metadata.assetIdentity, { compact: true }), '', volumeNote], ['换', bar.turnover_rate_pct === null ? '—' : `${fmt(bar.turnover_rate_pct)}%`], ['振', amplitude === null ? '—' : `${fmt(amplitude)}%`], ['额', formatAssetMagnitude(bar.amount, amountUnit === '源单位' ? '' : amountUnit, '', { compact: true }), '', `成交额（${amountUnit}）`]];
  return `<span class="asset-history-date"><strong>${e(metadata.minute_k ? bar.date.replace('T',' ').slice(0,16) : bar.date)}</strong></span>${values.map(([label, value, tone, title]) => `<span${title ? ` title="${e(title)}"` : ''}>${e(label)} <strong${tone ? ` class="${tone}"` : ''}>${e(value)}</strong></span>`).join('')}${bar.validOHLC && !bar.gap ? '' : '<span class="asset-chart-warning">OHLC 缺失、间断或不一致，未绘制该蜡烛</span>'}`;
}
function overlayReadout(bar, state) {
  if (!bar) return '';
  const keys = state.overlay === 'boll' ? BOLL : state.overlay === 'none' ? [] : maEnabled(state).map(n => [`ma${n}`, `MA${n}`, COLORS[MA_PERIODS.indexOf(n)]]);
  return keys.map(([key, label, color]) => `<span style="--asset-series-color:${color}">${label}: ${e(fmt(bar[key]))}</span>`).join('');
}
function panelValues(id, bar = {}, metadata = {}, state = {}) {
  const settings = state.indicatorSettings || normalizeIndicatorSettings();
  return indicatorSeries(id).map(item => {
    const label = id === 'volume' && item.name === 'MA1' ? `MA${settings.volume.short}` : id === 'volume' && item.name === 'MA2' ? `MA${settings.volume.long}` : item.name;
    const value = bar[item.key] ?? (id === 'volume' && item.name === 'VOL' ? bar.volume : null);
    return { ...item, label, formatted: ['volume','obv'].includes(id) ? formatAssetVolume(value, fieldUnit(metadata,'volume') || '', metadata.assetIdentity, { compact: true }) : fmt(value, ['macd','emv'].includes(id) ? 4 : 2) };
  });
}
function panelText(id, bar = {}, metadata = {}, state = {}) {
  return `${indicatorTitle(id,state.indicatorSettings)} ${panelValues(id,bar,metadata,state).map(item=>`${item.label}:${item.formatted}`).join(' ')}`;
}
function panelReadout(id, bar, metadata, state, palette) {
  return panelValues(id,bar,metadata,state).map((item,index)=>`<span style="color:${palette.seriesColors?.[index] || item.color}">${e(item.label)}:${e(item.formatted)}</span>`).join(' ');
}
function panelLabels(bar = {}, theme = CHART_THEMES.dark, state = {}, metadata = {}) {
  const layout = chartLayout(state);
  return layout.panels.map((id, index) => ({ id: `kline-panel-label-${id}`, type: 'text', left: 10, top: layout.top + layout.mainHeight + 9 + index * layout.panelStep, silent: true, style: { opacity: state.domPanelHeaders ? 0 : 1, fill: theme.text, font: '10px SF Mono, Consolas, monospace', textAlign: 'left', textVerticalAlign: 'top', text: panelText(id, bar, metadata, state) } }));
}
function panelHeaders(state) {
  const layout = chartLayout(state);
  return layout.panels.map((id, index) => `<div class="asset-panel-header${state.activePanel===id?' is-active':''}" style="top:${layout.top + layout.mainHeight + 3 + index * layout.panelStep}px" data-asset-panel="${id}"><button type="button" class="asset-panel-name kline-btn" data-asset-chart-action="indicator-replace-${id}" aria-label="替换 ${PANEL_NAMES[id]} 副图">${e(indicatorTitle(id,state.indicatorSettings))}</button><span class="asset-panel-readout" tabindex="0" data-asset-panel-readout="${id}"></span><span class="asset-panel-tools"><button type="button" class="kline-btn" data-asset-chart-action="panel-remove-${id}" aria-label="移除 ${PANEL_NAMES[id]}" title="关闭此副图">×</button></span></div>`).join('');
}
function historyStatus(state, metadata) {
  const job = jobFor(metadata); const status = String(job.status || job.state || ''); const pending = busyHistory(metadata) || state.historyRequestPending;
  const chunks = finite(job.progress?.chunks_total); const completed = finite(job.progress?.chunks_completed);
  const progress = finite(job.progress?.percent ?? job.progress_pct ?? (typeof job.progress === 'number' ? job.progress : chunks > 0 && completed !== null ? completed / chunks * 100 : null));
  const count = finite(job.loaded_rows ?? job.progress?.loaded_rows ?? job.progress?.rows); const failed = ['failed', 'error', 'interrupted'].includes(status);
  if (pending && job.progress?.phase === 'chip_inputs') return `筹码输入 ${job.progress.chip_batches_completed || 0}/${job.progress.chip_batches_total || 0}批 · 行情仍可查看`;
  if (pending) return `${state.requestedAdjustment ? `正在生成${adjustmentLabel(state.requestedAdjustment)}，当前仍显示${adjustmentLabel(state.adjustment)}原版本 · ` : ''}加载历史${progress === null ? '…' : ` ${fmt(clamp(progress, 0, 100), 0)}%`}${count === null ? '' : ` · ${fmt(count, 0)}条`}`;
  if (failed) return `${retryableHistory(metadata) ? '历史加载失败，可重试' : '历史口径已变化，请重新加载全历史'}${job.failure_code ? ` · ${job.failure_code}` : ''}`;
  if (status === 'cancelled') return '历史加载已取消，已取得数据保留，可重试';
  if ((state.historySource || metadata.historySource) === 'unknown') return '历史来源未知 · 请核验快照';
  return completeHistory(metadata) ? '全部历史已加载' : (state.historySource || metadata.historySource || 'tinysoft') !== 'tinysoft' ? '近期不复权 · 更早/全历史请先选择固定天软' : metadata.canLoadHistory ? '可向前加载更多历史' : '旧快照 · 全历史尚未接入';
}
function controls(state, length, metadata) {
  const source = sourceFrequency(metadata.frequency); const pending = busyHistory(metadata) || state.historyRequestPending;
  const button = (action, label, active = false, disabled = false, extra = '') => `<button type="button" class="kline-btn${active ? ' active' : ''}" data-asset-chart-action="${action}" aria-pressed="${active}"${disabled ? ' disabled' : ''}${extra}>${label}</button>`;
  const periods = [['day', '日K'], ['week', '周K'], ['month', '月K']].map(([period, label]) => button(`period-${period}`, label, state.period === period, source !== 'day' && source !== period)).join('');
  const failed = retryableHistory(metadata);
  return `<div class="asset-chart-toolbar"><div class="kline-period-group" role="group" aria-label="K线周期">${periods}</div><select class="asset-chart-adjustment" data-asset-chart-adjustment aria-label="复权方式"${pending || !metadata.canLoadHistory ? ' disabled' : ''}>${[['none', '不复权'], ['qfq', '前复权'], ['hfq', '后复权']].map(([value, label]) => `<option value="${value}"${state.adjustment === value ? ' selected' : ''}>${label}</option>`).join('')}</select><span class="asset-history-status" data-asset-history-status role="status" hidden>${e(historyStatus(state, metadata))}</span>${button('history-cancel', '取消', false, false, pending ? '' : ' hidden')}${button('history-retry', '重试', false, pending || !metadata.canLoadHistory, failed ? '' : ' hidden')}<div class="asset-overlay-controls" role="group" aria-label="主图叠加指标">${button('overlay-ma', 'MA', state.overlay === 'ma')}${button('overlay-boll', 'BOLL', state.overlay === 'boll')}${button('overlay-none', '裸K', state.overlay === 'none')}</div></div>`;
}
function safeIndicatorSettings(settings) { try { return normalizeIndicatorSettings(settings || {}); } catch { safeLog('asset_indicator_settings_restore_failed', {status:'invalid'}); return normalizeIndicatorSettings(); } }
function safeFavorites(favorites) { try { return normalizeFavorites(favorites); } catch { safeLog('asset_indicator_favorites_restore_failed', {status:'invalid'}); return [...DEFAULT_FAVORITES]; } }
function safeChipSettings(settings) { try { return normalizeChipSettings(settings || {}); } catch { safeLog('asset_chip_settings_restore_failed', { status: 'invalid' }); return normalizeChipSettings(); } }
export function minuteChipInputs(reference, selectedDate) {
  if (reference?.cutoff_policy !== 'strictly_before_selected_minute_date') return [];
  return enrichMarketBars(reference.rows || []).filter(row => row.date < String(selectedDate || '').slice(0,10));
}
function canonicalChip(daily, state, metadata) {
  const input = metadata.minute_k ? minuteChipInputs(metadata.daily_reference, state.selectedDate) : daily.slice(0, nearestIndex(daily, state.selectedDate) + 1);
  const contract = (metadata.minute_k ? metadata.daily_reference?.asset_history : historyFor(metadata))?.chip_inputs;
  if (contract?.status !== 'complete' || contract.contract_version !== 'chip-turnover-1' || contract.turnover_unit !== 'percent') return unavailable('chip_inputs_not_loaded', input);
  return estimateChips(input, state.chipSettings);
}
const volumeTick = (value, metadata) => formatAssetVolume(value, fieldUnit(metadata,'volume') || '', metadata.assetIdentity, { compact: true });

export function renderMarketTerminal(rows = [], state = {}, metadata = {}) {
  const source = sourceFrequency(metadata.frequency); const daily = enrichMarketBars(rows, {timestamp: metadata.minute_k === true});
  const normalized = { indicatorSettings: safeIndicatorSettings(state.indicatorSettings), favorites: safeFavorites(state.favorites), activePanel: state.activePanel || panelsFor(state).at(-1) || '', overlay: 'ma', enabledMA: [...MA_PERIODS], panels: [...DEFAULT_PANELS], period: source, showAll: false, adjustment: adjustmentFor(metadata), ...state };
  normalized.indicatorSettings = safeIndicatorSettings(state.indicatorSettings); normalized.favorites = safeFavorites(state.favorites); normalized.panels = panelsFor(normalized); normalized.chipSettings = safeChipSettings(normalized.chipSettings); normalized.chipTab ||= 'statistics';
  const bars = displayBars(rows, normalized, metadata); Object.assign(normalized, rangeFor(bars.length, normalized));
  const activeIndex = selectedIndex(bars, normalized); normalized.activeIndex = activeIndex;
  normalized.selectedDate = daily[actualDateIndex(daily, normalized.selectedDate || bars[activeIndex]?.source_end_date || bars[activeIndex]?.date)]?.date || '';
  const active = bars[activeIndex];
  const previous = bars[activeIndex - 1];
  const chip = canonicalChip(source === 'day' ? daily : [], normalized, metadata); const layout = chartLayout(normalized);
  return `<section class="asset-market-terminal" aria-label="行情与技术指标">${controls(normalized, bars.length, metadata)}<div class="asset-terminal-quote asset-history-readout" data-asset-history aria-live="off">${readout(active, previous, metadata)}</div><div class="kline-terminal-layout"><div class="asset-kline-stage"><div class="asset-main-overlay" tabindex="0" aria-label="主图指标读数，可横向滚动" data-asset-overlay-label>${overlayReadout(bars[activeIndex], normalized)}</div><div class="asset-terminal-chart" style="height:${layout.height}px" data-asset-chart data-asset-echarts role="img" tabindex="0" aria-label="K线与自定义副图；方向键选择历史交易日"></div><div class="asset-panel-headers" data-asset-panel-headers>${panelHeaders(normalized)}</div><div class="asset-panel-controls"><details class="asset-panel-legacy" hidden><summary>增加副图</summary><div data-asset-panel-choices>${Object.entries(PANEL_NAMES).map(([id,name])=>`<button type="button" data-asset-chart-action="panel-add-${id}"${normalized.panels.includes(id)?' disabled':''}>${name}</button>`).join('')}</div></details><div data-asset-indicator-strip>${indicatorStrip(normalized)}</div><span class="asset-range-summary" data-asset-range-summary>第 ${bars.length ? normalized.start + 1 : 0}–${normalized.end} 条 / 共 ${bars.length} 条</span></div></div>${chipPanel(chip, normalized.chipSettings, normalized.chipTab)}</div><dialog class="asset-indicator-dialog" data-asset-indicator-manager aria-label="指标管理"></dialog><dialog class="asset-indicator-dialog asset-indicator-parameters-dialog" data-asset-indicator-parameter-dialog aria-label="指标参数"></dialog></section>`;
}

export function renderChartExplanation() { return `<p class="asset-chart-help">滚轮缩放 · 拖动平移 · 底部滑块联动所有副图。点击 / 方向键选择交易日，End 回到最新，视区变化保留所选日。</p><details class="asset-indicator-method"><summary>指标计算与数据缺口</summary><p>MA5/10/20/60/120/250 使用完整窗口；BOLL20 为样本标准差 ±2σ。EMA12/26 首收盘价起算，DIF 第26条、DEA9 与 MACD×2 第34条显示。KDJ9 从首个有效 RSV 起算、α=1/3；RSI14 为14个实际涨跌的简单滚动均值。缺失或无效 OHLC 和明确间断重置预热，周/月先聚合 OHLCV 再重算全部指标。筹码始终使用同一版本日线的首日至所选日，视区和主图指标只改变显示价格轴。源字段单位缺失时不推测。</p></details>`; }

/** One price grid and exactly the enabled lower panels; all axes share a range. */
export function buildMarketChartOption(bars, state = {}, metadata = {}, theme, chip = null) {
  const palette = chartTheme(theme); const layout = chartLayout(state); const panels = layout.panels;
  bars = calculatePanelIndicators(bars, state.indicatorSettings);
  const range = rangeFor(bars.length, state); const domain = priceDomain(bars, state); const dates = bars.map(bar => bar.date);
  const line = (name, key, axis, color) => ({ name, type: 'line', xAxisIndex: axis, yAxisIndex: axis, data: bars.map((bar, index) => [index, bar[key]]), smooth: false, connectNulls: false, lineStyle: { width: 1, color }, itemStyle: { color }, symbol: 'none', showSymbol: false });
  const volume = axis => ({ name: '成交量', type: 'bar', xAxisIndex: axis, yAxisIndex: axis, data: bars.map((bar, index) => [index, bar.volume, bar.validOHLC ? (bar.close >= bar.open ? 1 : -1) : 0]), barWidth: '60%', itemStyle: { color: params => params.data[2] > 0 ? UP : params.data[2] < 0 ? DOWN : palette.muted } });
  const series = [{ id: 'asset-kline-price', markLine: chipPeakLines(chip, palette), name: 'K线', type: 'candlestick', large: false, xAxisIndex: 0, yAxisIndex: 0, data: bars.map(bar => bar.validOHLC && !bar.gap ? [bar.open, bar.close, bar.low, bar.high] : [null, null, null, null]), itemStyle: { color: UP, color0: DOWN, borderColor: UP, borderColor0: DOWN } }, ...MA_PERIODS.map((period, index) => line(`MA${period}`, `ma${period}`, 0, COLORS[index])), ...BOLL.map(([key, name, color]) => line(name, key, 0, color))];
  panels.forEach((id, index) => {
    const axis = index + 1;
    for (const [seriesIndex,item] of indicatorSeries(id).entries()) {
      const color = palette.seriesColors?.[seriesIndex] || item.color;
      if (id === 'volume' && item.type === 'bar') { series.push(volume(axis)); continue; }
      if (id === 'macd' && item.type === 'bar') { series.push({name:'MACD柱',type:'bar',xAxisIndex:axis,yAxisIndex:axis,data:bars.map((bar,i)=>[i,bar[item.key],bar[item.key]>=0?1:-1]),barWidth:'60%',itemStyle:{color:params=>params.data[2]>0?UP:DOWN}});continue; }
      const name=id==='volume'?`VOLMA${item.name==='MA1'?(state.indicatorSettings?.volume?.short||5):(state.indicatorSettings?.volume?.long||10)}`:`${id.toUpperCase()} ${item.name}`;
      const entry = line(name,item.key,axis,color);
      if (item.type === 'scatter') Object.assign(entry,{type:'scatter',symbol:'circle',symbolSize:3});
      const levels = id === 'rsi' ? [30,70] : id === 'wr' ? [20,80] : [];
      if (levels.length && seriesIndex===0) entry.markLine={silent:true,symbol:'none',label:{color:palette.muted},lineStyle:{type:'dashed',width:1,color:palette.grid},data:levels.map(yAxis=>({yAxis}))};
      series.push(entry);
    }
  });
  const selected = Object.fromEntries([...MA_PERIODS.map(period => [`MA${period}`, (state.overlay || 'ma') === 'ma' && maEnabled(state).includes(period)]), ...BOLL.map(([, name]) => [name, state.overlay === 'boll'])]);
  const [kdjMin, kdjMax] = kdjDomain(bars, state); const axes = layout.grid.map((grid, index) => index);
  const axisStyle = { axisLine: { onZero: false, lineStyle: { color: palette.grid } }, axisTick: { show: false }, splitLine: { show: false }, min: 'dataMin', max: 'dataMax' };
  return { backgroundColor: 'transparent', animation: false, legend: { show: false, selected }, tooltip: { trigger: 'axis', showContent: false, axisPointer: { type: 'cross', crossStyle: { color: palette.muted } }, backgroundColor: palette.surface, borderColor: palette.grid, textStyle: { color: palette.text, fontSize: 12 }, formatter: params => { const index = params?.[0]?.dataIndex; return index === undefined ? '' : readout(bars[index], bars[index - 1], metadata); } }, axisPointer: { link: [{ xAxisIndex: 'all' }], lineStyle: { color: palette.muted }, label: { backgroundColor: palette.surface, color: palette.text } }, graphic: panelLabels(bars[selectedIndex(bars, state)], palette, state, metadata), grid: layout.grid,
    xAxis: layout.grid.map((grid, index) => ({ ...axisStyle, type: 'category', gridIndex: index, data: dates, boundaryGap: true, axisPointer: { label: { show: index === axes.length - 1 } }, axisLabel: { ...(metadata.minute_k ? {formatter: value => `${value.slice(5,10)} ${value.slice(11,16)}`} : {}), show: index === axes.length - 1, color: palette.muted, fontSize: 12, hideOverlap: true } })),
    yAxis: layout.grid.map((grid, index) => { const id = panels[index - 1]; return { scale: !['rsi','wr','dmi'].includes(id), gridIndex: index, position: 'right', ...(index === 0 ? { min: domain[0], max: domain[1] } : id === 'kdj' ? { min: kdjMin, max: kdjMax } : ['rsi','wr','dmi'].includes(id) ? { min: 0, max: 100 } : {}), splitNumber: index === 0 ? 4 : 2, axisLabel: { color: palette.muted, fontSize: 12, formatter: index === 0 ? priceFmt : ['volume','obv'].includes(id) ? value => volumeTick(value, metadata) : undefined }, ...(index === 0 ? { axisPointer: { label: { formatter: params => priceFmt(params.value) } } } : {}), axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: id !== 'volume', lineStyle: { color: palette.grid } }, splitArea: { show: false } }; }),
    dataZoom: [{ type: 'inside', xAxisIndex: axes, startValue: range.start, endValue: Math.max(0, range.end - 1), filterMode: 'none', zoomOnMouseWheel: true, moveOnMouseMove: true, moveOnMouseWheel: false }, { type: 'slider', xAxisIndex: axes, startValue: range.start, endValue: Math.max(0, range.end - 1), filterMode: 'none', height: 18, bottom: 2, left: 8, right: 54, showDetail: false, borderColor: palette.grid, backgroundColor: 'transparent', fillerColor: palette.selected, dataBackground: { lineStyle: { color: palette.muted }, areaStyle: { color: palette.grid } }, selectedDataBackground: { lineStyle: { color: palette.muted }, areaStyle: { color: palette.selected } }, handleStyle: { color: palette.muted, borderColor: palette.surface }, moveHandleStyle: { color: palette.muted }, emphasis: { handleStyle: { color: palette.text }, moveHandleStyle: { color: palette.text } }, textStyle: { color: palette.muted, fontSize: 12 } }], series };
}

export function buildChipChartOption(chip, domain, echarts = null, theme, tab = 'statistics', overlay = null) {
  return chipChartOption(chip, domain, echarts, chartTheme(theme), tab, overlay);
}

export function createAssetChartController({ onChange = () => {}, onPanelsChange = () => {}, onIndicatorPreferencesChange = null, onChipSettingsChange = () => {}, onHistoryRequest = () => {}, logger = safeLog } = {}) {
  let rawRows = []; let daily = []; let bars = []; let identity; let datasetKey = ''; let metadata = {}; let source = 'day';
  let indicatorEditor = null; let rangeController = null; let rangeHost = null;
  let state = { indicatorSettings: normalizeIndicatorSettings(), favorites: [...DEFAULT_FAVORITES], activePanel: 'macd', chipSettings: normalizeChipSettings(), chipTab: 'statistics', historySource: metadata.historySource, overlay: 'ma', enabledMA: [...MA_PERIODS], panels: [...DEFAULT_PANELS], period: 'day', adjustment: 'none', requestedAdjustment: null, selectedDate: '', historyViewAllRequested: false, showAll: false, ...initialRange(0), crosshairY: null, crosshairVisible: false, historyRequestPending: false };
  let slot = null; let main = null; let chips = null; let observer = null; let frame = null; let needsFull = false; let needsResize = false; let view = null; let library = null; let applying = false; let olderAnchor = ''; let lastHistoryScope = 'all'; let lastHistoryAdjustment = null; let pointerBlocked = false; let dragging = false; let gestureStartX = null; let historyRequestSerial = 0;
  let lastChipMarkers = ''; let theme = chartTheme(); const chipCache = new Map();
  const listeners = []; const chartListeners = []; const zrListeners = [];
  const log = method => { try { logger(`asset_chart_${method}_failed`, { status: 'error', method }); } catch { /* Diagnostics must not prevent disposal. */ } };
  const guarded = (method, fn) => { try { return fn(); } catch { log(method); return false; } };
  const outside = () => bars.length > 0 && (state.activeIndex < state.start || state.activeIndex >= state.end);
  const getState = () => ({ ...state, selectedOutsideView: outside(), enabledMA: [...state.enabledMA], panels: [...state.panels], indicatorSettings: normalizeIndicatorSettings(state.indicatorSettings), favorites: [...state.favorites], chipSettings: { ...state.chipSettings, visibleAges: [...state.chipSettings.visibleAges] } });
  const find = selector => slot?.querySelector(selector);
  const notify = reason => guarded('change', () => onChange(getState(), { reason }));
  const selectedDailyIndex = () => nearestIndex(daily, state.selectedDate);
  const currentBar = () => bars[state.activeIndex];
  function rangeContext() {
    if (metadata.minute_k) return null;
    const node = find('[data-asset-echarts]'); const hostRect = rangeHost?.getBoundingClientRect?.() || {left:0,top:0}; const rect = node?.getBoundingClientRect?.() || {left:0,top:0,width:800};
    // init() has no model until its first setOption(). Only a real grid
    // coordinate system permits ECharts conversions; layout geometry works
    // during same-slot theme restoration before that first draw.
    const coordinateSystem = main?.getModel?.()?.getComponent?.('grid',0)?.coordinateSystem;
    const grid = coordinateSystem?.getRect?.() || {x:8,y:26,width:Math.max(0,rect.width-62),height:300};
    const plot = {left:rect.left-hostRect.left+grid.x,top:rect.top-hostRect.top+grid.y,width:grid.width,height:grid.height};
    const step=plot.width/Math.max(1,state.end-state.start);
    return {daily,displayBars:bars,metadata,plot,visibleStart:state.start,visibleEnd:state.end,
      indexAt:x=>{const converted=coordinateSystem?main?.convertFromPixel?.({xAxisIndex:0},x-(rect.left-hostRect.left)):null;return finite(converted)===null?state.start+Math.floor((x-plot.left)/step):Number(converted);},
      pixelAt:index=>{const converted=coordinateSystem?main?.convertToPixel?.({xAxisIndex:0},index):null;return finite(converted)===null?plot.left+(index-state.start+.5)*step:Number(converted)+rect.left-hostRect.left;}};
  }
  function pageTheme() {
    const root = slot?.ownerDocument?.documentElement; const fallback = chartTheme(root && root.dataset?.theme !== 'dark' ? 'light' : 'dark');
    try {
      const styles = view?.getComputedStyle?.(find('.asset-market-terminal') || slot); if (!styles) return fallback;
      return { ...fallback, ...Object.fromEntries([['text', '--text'], ['muted', '--muted'], ['grid', '--line'], ['surface', '--surface'], ['selected', '--selected']].map(([key, token]) => [key, styles.getPropertyValue(token).trim() || fallback[key]])) };
    } catch { log('theme'); return fallback; }
  }
  function cumulativeChip() {
    const history = historyFor(metadata);
    const version = history.canonical_version || history.canonicalVersion || history.version || metadata.canonicalVersion || datasetKey;
    const factor = history.factor_version || history.factorVersion || metadata.factorVersion || '';
    const key = JSON.stringify([identity, version, factor, state.selectedDate, adjustmentFor(metadata), state.chipSettings]);
    if (!chipCache.has(key)) {
      chipCache.set(key, canonicalChip(source === 'day' ? daily : [], state, metadata));
      if (chipCache.size > 24) chipCache.delete(chipCache.keys().next().value);
    }
    return chipCache.get(key);
  }
  function syncLabels() {
    const meta = find('[data-asset-chart-metadata]'); if (meta) meta.textContent = metadataLabel(metadata);
    const bar = currentBar();
    const history = find('[data-asset-history]'); if (history) history.innerHTML = readout(bar, bars[state.activeIndex - 1], metadata);
    const overlay = find('[data-asset-overlay-label]'); if (overlay) overlay.innerHTML = overlayReadout(bars[state.activeIndex], state);
    const summary = find('[data-asset-range-summary]'); if (summary) summary.textContent = `第 ${bars.length ? state.start + 1 : 0}–${state.end} 条 / 共 ${bars.length} 条`;
    const date = find('[data-asset-selected-date]'); if (date) {
      if (date.value !== state.selectedDate) date.value = state.selectedDate;
      const min = daily[0]?.date || ''; const max = daily.at(-1)?.date || '';
      if (date.min !== min) date.min = min;
      if (date.max !== max) date.max = max;
    }
    const cue = find('[data-asset-selection-cue]'); if (cue) cue.textContent = outside() ? `所选日 ${state.selectedDate} 在视区外` : '';
    const adjustment = find('[data-asset-chart-adjustment]'); if (adjustment) { adjustment.value = state.adjustment; adjustment.disabled = !metadata.canLoadHistory || busyHistory(metadata) || state.historyRequestPending; }
    const historySource = find('[data-asset-history-source]'); if (historySource) { historySource.value = state.historySource || metadata.historySource || 'tinysoft'; historySource.disabled = !metadata.canLoadHistory || busyHistory(metadata) || state.historyRequestPending; }
    const status = find('[data-asset-history-status]'); if (status) { status.textContent = historyStatus(state, metadata); status.hidden = !busyHistory(metadata) && !state.historyRequestPending && !['failed', 'error', 'interrupted', 'cancelled', 'unknown'].includes(String(jobFor(metadata).status || jobFor(metadata).state || '')); }
    const pending = busyHistory(metadata) || state.historyRequestPending;
    for (const button of slot?.querySelectorAll('[data-asset-chart-action]') || []) {
      const action = button.dataset.assetChartAction; if (action.startsWith('indicator-') || action.startsWith('panel-choose-')) continue; if (action.startsWith('panel-add-') || action.startsWith('panel-remove-')) {button.removeAttribute?.('aria-pressed');continue;} if (action.startsWith('chip-')) { if (action === 'chip-load') { button.disabled = busyHistory(metadata) || state.historyRequestPending || !canLoadChip(metadata); button.title = canLoadChip(metadata) ? '使用当前天软日线口径加载逐日换手率' : '当前日线来源未支持此筹码输入'; } continue; } let pressed = false;
      if (action.startsWith('overlay-')) pressed = state.overlay === action.slice(8);
      else if (action.startsWith('ma-')) pressed = state.enabledMA.includes(Number(action.slice(3)));
      else if (action.startsWith('period-')) { const period = action.slice(7); pressed = state.period === period; button.disabled = source !== 'day' && source !== period; }
      else if (action.startsWith('panel-add-')) button.disabled = state.panels.includes(action.slice(10));
      else if (action === 'all') { pressed = state.showAll; button.disabled = pending || (state.historySource || metadata.historySource || 'tinysoft') !== 'tinysoft' || (!metadata.canLoadHistory && !completeHistory(metadata)); button.textContent = requiresHistoryRebuild(metadata) ? '重建全历史' : completeHistory(metadata) ? '全部已加载' : '全历史'; }
      else if (action === 'history-cancel') { button.hidden = !pending; button.disabled = String(jobFor(metadata).status || jobFor(metadata).state) === 'cancelling'; }
      else if (action === 'history-retry') { button.hidden = !retryableHistory(metadata); button.disabled = pending || !metadata.canLoadHistory; }
      else if (action === 'locate') button.hidden = !outside();
      else if (action === 'pan-back') button.disabled = state.start === 0 && (!metadata.canLoadHistory || completeHistory(metadata) || (state.historySource || metadata.historySource || 'tinysoft') !== 'tinysoft');
      else if (action === 'pan-forward') button.disabled = state.end === bars.length;
      button.setAttribute('aria-pressed', String(pressed)); button.classList.toggle('active', pressed);
    }
    const headers = find('[data-asset-panel-headers]');
    const headerKey = JSON.stringify([state.panels,state.activePanel,state.indicatorSettings]);
    if (headers && headers.dataset.headerKey !== headerKey) { headers.innerHTML = panelHeaders(state); headers.dataset.panels = state.panels.join(','); headers.dataset.headerKey = headerKey; }
    for (const id of state.panels) { const label = find(`[data-asset-panel-readout="${id}"]`); if (label) { label.innerHTML = panelReadout(id,bars[state.activeIndex],metadata,state,theme); } }
    const strip = find('[data-asset-indicator-strip]'); if (strip) { const html = indicatorStrip(state); if (strip.dataset?.markup !== html) {strip.innerHTML=html;if(strip.dataset)strip.dataset.markup=html;} }
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
    const narrow = view?.matchMedia?.('(max-width: 959px)')?.matches === true;
    const top = narrow ? 0 : mainRect.top + Number(rect.y ?? rect.top) - panelRect.top;
    panel.style.setProperty('--chip-plot-top', `${Math.max(0, top)}px`);
    panel.style.setProperty('--chip-plot-height', `${Number(rect.height)}px`);
    chipNode.style.height = `${narrow ? 190 : Number(rect.height)}px`;
    if (chipNode.dataset) Object.assign(chipNode.dataset, { plotTop: String(mainRect.top + Number(rect.y ?? rect.top)), plotHeight: String(rect.height), aligned: String(!narrow) });
  }
  function axisPatch(domain) {
    const [low, high] = kdjDomain(bars, state);
    return [{ min: domain[0], max: domain[1] }, ...state.panels.map(id => id === 'kdj' ? { min: low, max: high } : ['rsi','wr','dmi'].includes(id) ? { min: 0, max: 100 } : {})];
  }
  function flush() {
    frame = null; if (!slot) return;
    guarded('render', () => {
      if (needsFull) theme = pageTheme(); syncLabels();
      if (needsResize || needsFull) main?.resize({ height: chartLayout(state).height });
      const domain = priceDomain(bars, state); const chip = cumulativeChip(); const markerKey = JSON.stringify([chip.status, chip.peak, chip.peakLower, chip.peakUpper, chip.settings?.showPeak]); applying = true;
      try { main?.setOption(needsFull ? buildMarketChartOption(bars, { ...state, domPanelHeaders: true }, metadata, theme, chip) : { ...(markerKey !== lastChipMarkers ? { series: [{ id: 'asset-kline-price', markLine: chipPeakLines(chip, theme) }] } : {}), graphic: panelLabels(bars[state.activeIndex], theme, { ...state, domPanelHeaders: true }), yAxis: axisPatch(domain) }, needsFull); }
      finally { applying = false; }
      lastChipMarkers = markerKey;
      alignChips(); const chipNode = find('[data-asset-chip-chart]'); chips?.resize({ height: parseFloat(chipNode?.style.height) || 300 });
      const stats = find('[data-asset-chip-stats]'); if (stats) { const markup = chipStatistics(chip, state.chipTab); if (stats.dataset.chipMarkup !== markup) { stats.innerHTML = markup; stats.dataset.chipMarkup = markup; } }
      const windowLabel = find('[data-asset-chip-window]'); if (windowLabel) windowLabel.textContent = chip.startDate ? `${chip.startDate}–${chip.endDate} · 累计${chip.validBars}条有效日线` : source !== 'day' ? '缺少日线底稿，累计筹码不可用' : '暂无有效窗口';
      const tabs = find('[data-asset-chip-tabs]'); for (const button of tabs?.querySelectorAll('[aria-pressed]') || []) button.setAttribute('aria-pressed', String(button.dataset.assetChartAction === `chip-tab-${state.chipTab}`));
      let overlay = null;
      if (chip.status === 'ready' && state.chipSettings.overlayEnabled && !metadata.minute_k) {
        const cutoff = selectedDailyIndex() - state.chipSettings.overlayDays;
        if (cutoff >= 4) overlay = estimateChips(daily.slice(0, cutoff + 1), state.chipSettings);
      }
      chips?.setOption(buildChipChartOption(chip, domain, library, theme, state.chipTab, overlay), true);
      const note = find('.asset-chip-note'); if (note) note.textContent = `${metadata.minute_k ? '日线筹码截至所选分钟的前一交易日，未使用当日未来数据。' : ''}换手衰减估算，非实际持仓。${chip.status === 'ready' && chip.initialResidual > .01 ? `初始分布仍占 ${(chip.initialResidual * 100).toFixed(2)}%。` : ''}${state.chipSettings.overlayEnabled ? overlay?.status === 'ready' ? `历史叠加：${overlay.endDate}。` : '所选日期之前的历史不足，未绘制历史叠加。' : ''}`;
      syncLabels(); rangeController?.render();
    });
    needsFull = needsResize = false;
  }
  function schedule(full = false, resize = false) {
    needsFull ||= full; needsResize ||= resize; if (!slot || frame !== null) return;
    if (view?.requestAnimationFrame) frame = view.requestAnimationFrame(flush); else flush();
  }
  function update(next, reason, full = false) {
    if (!Object.entries(next).some(([key, value]) => JSON.stringify(value) !== JSON.stringify(state[key]))) return false;
    state = { ...state, ...next }; if(next.indicatorSettings) bars=calculatePanelIndicators(bars,state.indicatorSettings); schedule(full); notify(reason); return true;
  }
  function hidePointer() {
    guarded('pointer_hide', () => { applying = true; try { main?.dispatchAction?.({ type: 'hideTip' }); main?.dispatchAction?.({ type: 'updateAxisPointer', currTrigger: 'leave' }); } finally { applying = false; } });
    return update({ crosshairY: null, crosshairVisible: false }, 'leave');
  }
  function release() {
    rangeController?.dispose(); rangeController=null; rangeHost=null;
    closeIndicators(false);
    if (frame !== null) { guarded('cancel_frame', () => view?.cancelAnimationFrame?.(frame)); frame = null; }
    for (const [node, name, handler, options] of listeners.splice(0)) guarded('remove_listener', () => node.removeEventListener(name, handler, options));
    for (const [chart, name, handler] of chartListeners.splice(0)) guarded('remove_listener', () => chart.off(name, handler));
    for (const [zr, name, handler] of zrListeners.splice(0)) guarded('remove_listener', () => zr.off(name, handler));
    if (observer) guarded('observer_dispose', () => observer.disconnect()); observer = null;
    if (main) guarded('dispose', () => main.dispose()); if (chips) guarded('dispose', () => chips.dispose());
    main = chips = null; slot = null; view = null; library = null; needsFull = needsResize = false; pointerBlocked = dragging = false;
  }
  function requestHistory(action = 'load', scope = 'all', requestedAdjustment, requestedSource) {
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
    const selectedSource = action === 'retry' || action === 'cancel' ? jobFor(metadata).source : requestedSource || state.historySource || metadata.historySource;
    if (action === 'load' && selectedSource && selectedSource !== 'tinysoft' && (scope !== 'recent' || adjustment !== 'none')) { log('history_source_scope'); return false; }
    if (action !== 'cancel') {
      lastHistoryScope = scope; lastHistoryAdjustment = adjustment;
      update({ historySource: selectedSource || state.historySource, historyRequestPending: true, historyViewAllRequested: scope === 'all', requestedAdjustment: adjustment === state.adjustment ? null : adjustment }, 'history');
    }
    const requestSerial = ++historyRequestSerial;
    const rejected = () => {
      if (requestSerial !== historyRequestSerial) return;
      if (attemptAnchor && olderAnchor === attemptAnchor) olderAnchor = '';
      update({ historyRequestPending: false, historyViewAllRequested: false, requestedAdjustment: null }, 'history_failed');
    };
    const result = guarded('history_request', () => onHistoryRequest({ action, scope, adjustment, ...(selectedSource ? { source: selectedSource } : {}), ...((action === 'retry' ? jobFor(metadata).include_chip_inputs === true : selectedSource === 'tinysoft') ? { includeChipInputs: true } : {}) }));
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
      const choose = event => guarded('selection', () => { if(event?.event?.button===2)return; const point = [event.offsetX, event.offsetY]; const gridIndex=Array.from({length:state.panels.length+1},(_,i)=>i).find(i=>main.containPixel?.({gridIndex:i},point)!==false); if(gridIndex===undefined)return; if(gridIndex>0)update({activePanel:state.panels[gridIndex-1]},'panel-focus'); const value = main.convertFromPixel?.({ xAxisIndex: gridIndex }, point[0]); if (finite(value) !== null) select(Math.round(value), false, true); });
      zr.on('click', choose); zrListeners.push([zr, 'click', choose]);
      const gestures = { mousedown: event => { if(event?.event?.button===2)return; dragging = true; pointerBlocked = true; gestureStartX = finite(event?.offsetX); }, mouseup: () => { dragging = false; gestureStartX = null; }, mousemove: event => { if (!dragging && !event?.event?.buttons) pointerBlocked = false; else if (state.start === 0 && gestureStartX !== null && finite(event?.offsetX) !== null && event.offsetX - gestureStartX > 4) requestHistory('load', 'older'); }, mousewheel: () => { pointerBlocked = true; } };
      for (const [name, handler] of Object.entries(gestures)) { zr.on(name, handler); zrListeners.push([zr, name, handler]); }
    }
    if (view?.ResizeObserver) { observer = new view.ResizeObserver(() => schedule(false, true)); observer.observe(mainNode); }
    else if (view?.addEventListener) listen(view, 'resize', () => schedule(false, true));
    schedule(true, true);
  }
  function configure(rows = [], key = '', nextMetadata = {}, preferences) {
    const result = guarded('configure', () => {
      const indicatorSettings = safeIndicatorSettings(preferences ? preferences.indicator_settings : state.indicatorSettings); const favorites = safeFavorites(preferences ? preferences.favorites : state.favorites);
      const nextIdentity = identityFor(nextMetadata || {}, key); const changedIdentity = identity !== nextIdentity;
      if (rawRows === rows && datasetKey === key && metadata === nextMetadata && !preferences) return getState();
      const previousBars = bars; const previous = state; const previousSource = source; const previousHistorySource = metadata.historySource; const changedRows = rawRows !== rows || datasetKey !== key;
      const rangeVersion = value => JSON.stringify([value.asset_history?.canonical_version,value.asset_history?.factor_version,value.canonicalVersion,value.factorVersion,adjustmentFor(value)]);
      if(changedIdentity || changedRows || rangeVersion(metadata)!==rangeVersion(nextMetadata||{}))rangeController?.clear(false);
      rawRows = rows; identity = nextIdentity; datasetKey = key; metadata = nextMetadata || {}; source = sourceFrequency(metadata.frequency);
      daily = enrichMarketBars(rawRows, {timestamp: metadata.minute_k === true});
      const period = changedIdentity || !previousBars.length || source !== previousSource ? source : source === 'day' ? state.period : source;
      bars = source === 'day' && ['week', 'month'].includes(period) ? aggregateMarketBars(daily, period) : daily;
      if (changedIdentity) {
        chipCache.clear(); olderAnchor = ''; lastHistoryAdjustment = null; historyRequestSerial++;
        state = { indicatorSettings, favorites, activePanel: panelsFor(preferences || previous).at(-1) || '', chipSettings: safeChipSettings(preferences ? preferences.chip_settings : previous.chipSettings), chipTab: previous.chipTab || 'statistics', historySource: metadata.historySource, overlay: 'ma', enabledMA: [...MA_PERIODS], panels: preferences ? panelsFor(preferences) : [...previous.panels], period, adjustment: adjustmentFor(metadata), requestedAdjustment: null, selectedDate: daily.at(-1)?.date || '', historyViewAllRequested: false, showAll: false, ...initialRange(bars.length), crosshairY: null, crosshairVisible: false, historyRequestPending: false };
      } else {
        if (changedRows) chipCache.clear();
        const startDate = previousBars[previous.start]?.source_start_date || previousBars[previous.start]?.date;
        const endDate = previousBars[previous.end - 1]?.date;
        const firstRows = !previousBars.length && bars.length > 0;
        const start = firstRows ? initialRange(bars.length).start : previous.showAll ? 0 : Math.max(0, nearestIndex(bars, startDate));
        const end = firstRows ? bars.length : bars.length ? previous.showAll ? bars.length : Math.max(start + 1, nearestIndex(bars, endDate) + 1) : 0;
        const selectedDate = daily[actualDateIndex(daily, previous.selectedDate)]?.date || '';
        state = { ...previous, historySource: previousHistorySource !== metadata.historySource ? metadata.historySource : previous.historySource, period, selectedDate, start, end, adjustment: adjustmentFor(metadata), historyRequestPending: busyHistory(metadata) ? previous.historyRequestPending : changedRows || ['completed', 'complete', 'succeeded', 'failed', 'error', 'cancelled', 'interrupted'].includes(String(jobFor(metadata).status || jobFor(metadata).state || '')) ? false : previous.historyRequestPending, crosshairY: null, crosshairVisible: false };
        if (preferences) { state.panels = panelsFor(preferences); state.chipSettings = safeChipSettings(preferences.chip_settings); }
        state.indicatorSettings=indicatorSettings; state.favorites=favorites;
        if (changedRows && adjustmentFor(metadata) === previous.requestedAdjustment) state.requestedAdjustment = null;
        if (changedRows && previous.historyViewAllRequested && completeHistory(metadata)) state = { ...state, start: 0, end: bars.length, showAll: true, historyViewAllRequested: false };
        if (['failed', 'error', 'cancelled', 'interrupted'].includes(String(jobFor(metadata).status || jobFor(metadata).state || ''))) {
          state.historyViewAllRequested = false; state.requestedAdjustment = null; olderAnchor = '';
        }
        state.activeIndex = selectedIndex(bars, state);
      }
      bars = calculatePanelIndicators(bars,state.indicatorSettings);
      if (!state.panels.includes(state.activePanel)) state.activePanel=state.panels.at(-1)||'';
      if (changedIdentity) closeIndicators(false);
      if (slot) { initCharts(); schedule(true, true); } return getState();
    });
    if (result === false) release(); return result;
  }
  function setPreferences(preferences = {}) { if (!Array.isArray(preferences.panels)) return false; return update({ panels: panelsFor(preferences), chipSettings: safeChipSettings(preferences.chip_settings), indicatorSettings:safeIndicatorSettings(preferences.indicator_settings), favorites:safeFavorites(preferences.favorites) }, 'preferences', true); }
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
  function reset() { hidePointer(); const { start, end } = initialRange(bars.length); return update({ start, end, historyViewAllRequested: false, showAll: false, crosshairY: null, crosshairVisible: false }, 'reset', true); }
  function latest() { hidePointer(); return update({ ...initialRange(bars.length), selectedDate: daily.at(-1)?.date || '', historyViewAllRequested: false, showAll: false, crosshairY: null, crosshairVisible: false }, 'reset', true); }
  function locate() { if (!bars.length) return false; const count = state.end - state.start; const start = clamp(state.activeIndex - Math.floor(count / 2), 0, bars.length - count); return update({ start, end: start + count }, 'locate', true); }
  function cancel() {
    dragging=false; gestureStartX=null;
    if (frame !== null) { guarded('cancel_frame', () => view?.cancelAnimationFrame?.(frame)); frame = null; }
    hidePointer(); if (frame !== null) { guarded('cancel_frame', () => view?.cancelAnimationFrame?.(frame)); frame = null; }
    if (slot) flush(); else needsFull = needsResize = false; return true;
  }
  function changePeriod(period) {
    if (!['day', 'week', 'month'].includes(period) || (source !== 'day' && source !== period)) return false;
    const old = bars; const startDate = old[state.start]?.source_start_date || old[state.start]?.date; const endDate = old[state.end - 1]?.date;
    bars = calculatePanelIndicators(period === 'day' ? daily : aggregateMarketBars(daily, period), state.indicatorSettings);
    const start = state.showAll ? 0 : Math.max(0, nearestIndex(bars, startDate)); const end = bars.length ? Math.max(start + 1, state.showAll ? bars.length : nearestIndex(bars, endDate) + 1) : 0;
    return update({ period, start, end, activeIndex: nearestIndex(bars, state.selectedDate), crosshairVisible: false }, 'period', true);
  }
  function persistPanels(next = {}) {
    const panels = next.panels || state.panels;
    const changed = update({ ...next, panels, activePanel: next.activePanel ?? (panels.includes(state.activePanel) ? state.activePanel : panels.at(-1) || '') }, 'panels', true);
    if (changed) guarded('panels_change', () => typeof onIndicatorPreferencesChange === 'function'
      ? onIndicatorPreferencesChange({ panels:[...state.panels], favorites:[...state.favorites], indicator_settings:normalizeIndicatorSettings(state.indicatorSettings) })
      : onPanelsChange([...state.panels]));
    return changed;
  }
  function closeIndicators(focus = true) {
    find('[data-asset-indicator-parameter-dialog]')?.close?.();
    find('[data-asset-indicator-manager]')?.close?.(); indicatorEditor=null;
    if (focus) find('[data-asset-echarts]')?.focus?.({preventScroll:true});
  }
  function renderIndicators(keepSearch = false) {
    const dialog=find('[data-asset-indicator-manager]'); if (!dialog || !indicatorEditor) return false;
    const input=dialog.querySelector('[data-asset-indicator-search]'); const cursor=input?.selectionStart;
    dialog.innerHTML=indicatorManager(indicatorEditor);
    if (keepSearch) {const next=dialog.querySelector('[data-asset-indicator-search]');next?.focus?.({preventScroll:true});try {next?.setSelectionRange?.(cursor,cursor);} catch { /* Search inputs can omit text selection support. */ }}
    return true;
  }
  function openIndicators(mode='manage',anchor=state.activePanel) {
    indicatorEditor={mode,anchor,group:'全部',query:'',favorites:[...state.favorites],settings:normalizeIndicatorSettings(state.indicatorSettings)};
    if (!renderIndicators()) return false;
    find('[data-asset-indicator-manager]')?.showModal?.(); return true;
  }
  function choosePanel(id,mode='replace',anchor=state.activePanel,draft=null) {
    if (!Object.hasOwn(PANEL_NAMES,id)) return false;
    let panels=[...state.panels];
    if (!panels.includes(id)) {
      const index=panels.indexOf(anchor);
      if (mode==='replace' && index>=0) panels.splice(index,1,id);
      else panels.splice(index<0?panels.length:index+1,0,id);
    }
    const next={panels,activePanel:id,...(draft?{favorites:[...draft.favorites],indicatorSettings:normalizeIndicatorSettings(draft.settings)}:{})};
    closeIndicators(); return persistPanels(next);
  }
  const modalOwnsEscape = event => event?.type==='keydown' && event.key==='Escape' && Boolean(event.target?.closest?.('dialog[open], [aria-modal="true"]') || slot?.ownerDocument?.activeElement?.closest?.('dialog[open], [aria-modal="true"]'));
  function handle(event) {
    return guarded('interaction', () => {
      if (event?.assetChartHandled) return true;
      if (event?.type==='keydown' && event.key==='Escape') {
        const selector='[data-asset-indicator-manager], [data-asset-indicator-parameter-dialog]';
        const dialog=event.target?.closest?.(selector)||slot?.ownerDocument?.activeElement?.closest?.(selector);
        if(dialog?.open && (dialog===find('[data-asset-indicator-manager]')||dialog===find('[data-asset-indicator-parameter-dialog]'))) {
          // Owned dialogs cannot rely on the browser cancel default: the app
          // root also handles Escape. During composition leave the IME default
          // intact while keeping this event away from that root catchall.
          if(event.isComposing){event.stopPropagation?.();return true;}
          event.preventDefault?.();
          if(dialog===find('[data-asset-indicator-parameter-dialog]'))dialog.close?.();else closeIndicators();
          return true;
        }
      }
      if (modalOwnsEscape(event)) return false;
      if(rangeController?.handle(event))return true;
      if (event?.type === 'mouseleave' || event?.type === 'pointerleave') return hidePointer();
      if (event?.type === 'input' && event.target?.matches?.('[data-asset-indicator-search]') && indicatorEditor) {
        indicatorEditor.query=event.target.value; return renderIndicators(true);
      }
      if (event?.type === 'cancel' && event.target?.matches?.('[data-asset-indicator-manager]')) { event.preventDefault?.(); closeIndicators(); return true; }
      if (event?.type === 'cancel' && event.target?.matches?.('[data-asset-indicator-parameter-dialog]')) { event.preventDefault?.(); event.target.close(); return true; }
      if (event?.type === 'submit' && event.target?.matches?.('[data-asset-indicator-parameters]') && indicatorEditor) {
        event.preventDefault();
        try {
          const data=new view.FormData(event.target); const id=data.get('indicator_id'); if (!Object.hasOwn(INDICATOR_RULES,id)) throw new Error('invalid');
          const parameters=Object.fromEntries(Object.keys(INDICATOR_RULES[id]).map(key=>{const value=String(data.get(key)??'').trim();if (!value) throw new Error('empty');return [key,Number(value)];}));
          indicatorEditor.settings=normalizeIndicatorSettings({...indicatorEditor.settings,[id]:parameters});
          find('[data-asset-indicator-parameter-dialog]')?.close(); renderIndicators();
        } catch {const error=event.target.querySelector('[data-asset-indicator-parameter-error]');if(error){error.hidden=false;error.textContent='请检查参数范围和周期顺序。';}log('indicator_parameters');}
        return true;
      }
      if (event?.type === 'change') {
        if (event.target?.matches?.('[data-asset-history-source]')) {
          const selected = event.target.value; if (!['auto', 'tinysoft', 'wind', 'akshare', 'baostock'].includes(selected) || !metadata.canLoadHistory || busyHistory(metadata) || state.historyRequestPending) return false;
          state = { ...state, historySource: selected };
          return requestHistory('load', 'recent', 'none', selected);
        }
        if (event.target?.matches?.('[data-asset-selected-date]')) return selectDate(event.target.value);
        if (event.target?.matches?.('[data-asset-chart-adjustment]')) {
          const adjustment = event.target.value; if (!['none', 'qfq', 'hfq'].includes(adjustment) || !metadata.canLoadHistory || busyHistory(metadata) || state.historyRequestPending) return false;
          if (adjustment === state.adjustment) return false;
          return requestHistory('load', completeHistory(metadata) ? 'all' : 'recent', adjustment, adjustment === 'none' ? state.historySource || metadata.historySource : 'tinysoft');
        }
      }
      if (event?.type === 'submit' && event.target?.matches?.('[data-asset-chip-settings-form]')) {
        event.preventDefault();
        const form = event.target;
        try {
          const data = new view.FormData(form); const value = key => { const text = String(data.get(key) ?? '').trim(); if (!text) throw new Error('empty'); return Number(text); };
          const settings = normalizeChipSettings({ algorithm: data.get('algorithm'), decay: value('decay'), peakUpperPct: value('peakUpperPct'), peakLowerPct: value('peakLowerPct'), ageShort: value('ageShort'), ageMiddle: value('ageMiddle'), ageLong: value('ageLong'), overlayDays: value('overlayDays'), showPeak: data.has('showPeak'), overlayEnabled: data.has('overlayEnabled'), visibleAges: ['long', 'middle', 'short', 'ultra'].filter(id => data.has(`age-${id}`)) });
          chipCache.clear(); update({ chipSettings: settings }, 'chip-settings', true); find('[data-asset-chip-settings]')?.close();
          guarded('chip_preferences', () => onChipSettingsChange(settings));
        } catch { const message = form.querySelector('[data-chip-settings-error]'); if (message) { message.hidden = false; message.textContent = '请检查数值范围，并保持短线起点＜中线起点＜长线起点。'; } log('chip_settings'); }
        return true;
      }
      if (event?.type === 'click') {
        const group=event.target?.closest?.('[data-asset-indicator-group]');
        if (group && indicatorEditor) {indicatorEditor.group=group.dataset.assetIndicatorGroup;return renderIndicators();}
        const button = event.target?.closest?.('[data-asset-chart-action]'); if (!button || button.disabled) return false; const action = button.dataset.assetChartAction;
        if(action==='range-open') {const menu=button.closest?.('.asset-more-menu');if(menu)menu.open=false;return rangeController?.open()||false;}
        if (action === 'indicator-manager' || action === 'indicator-add') return openIndicators(action==='indicator-add'?'add':'manage');
        if (action.startsWith('indicator-add-after-')) return openIndicators('add',action.slice(20));
        if (action.startsWith('indicator-replace-')) return openIndicators('replace',action.slice(18));
        if (action.startsWith('panel-choose-')) return choosePanel(action.slice(13));
        if (action==='indicator-cancel') {closeIndicators();return true;}
        if (action==='indicator-parameters-cancel') {find('[data-asset-indicator-parameter-dialog]')?.close();return true;}
        if (indicatorEditor && action.startsWith('indicator-')) {
          const draft=indicatorEditor;
          if (action==='indicator-save') {const next={favorites:[...draft.favorites],indicatorSettings:normalizeIndicatorSettings(draft.settings)};closeIndicators();return persistPanels(next);}
          if (action==='indicator-default') {draft.favorites=[...DEFAULT_FAVORITES];draft.settings=normalizeIndicatorSettings();return renderIndicators();}
          if (action.startsWith('indicator-select-')) return choosePanel(action.slice(17),draft.mode==='add'?'add':'replace',draft.anchor,draft);
          if (action.startsWith('indicator-parameters-')) {const id=action.slice(21);if(!Object.hasOwn(PANEL_NAMES,id))return false;const dialog=find('[data-asset-indicator-parameter-dialog]');if(dialog){dialog.innerHTML=indicatorParameterForm(id,draft.settings);dialog.showModal();}return true;}
          if (action.startsWith('indicator-favorite-')) {const id=action.slice(19);if(!Object.hasOwn(PANEL_NAMES,id))return false;draft.favorites=draft.favorites.includes(id)?draft.favorites.filter(value=>value!==id):[...draft.favorites,id];return renderIndicators();}
          const reorder=/^indicator-(up|down)-(.+)$/.exec(action);
          if(reorder){const index=draft.favorites.indexOf(reorder[2]);const other=index+(reorder[1]==='up'?-1:1);if(index>=0&&other>=0&&other<draft.favorites.length)[draft.favorites[index],draft.favorites[other]]=[draft.favorites[other],draft.favorites[index]];return renderIndicators();}
        }
        if (action === 'chip-tab-statistics' || action === 'chip-tab-age') return update({ chipTab: action.slice(9) }, 'chip-tab', true);
        if (action === 'chip-settings-open') { const dialog = find('[data-asset-chip-settings]'); if (dialog) { dialog.innerHTML = chipSettingsForm(state.chipSettings); dialog.showModal(); } return true; }
        if (action === 'chip-settings-cancel') { find('[data-asset-chip-settings]')?.close(); return true; }
        if (action === 'chip-settings-default') { const dialog = find('[data-asset-chip-settings]'); if (dialog) dialog.innerHTML = chipSettingsForm(normalizeChipSettings()); return true; }
        if (action === 'chip-load') return canLoadChip(metadata) && requestHistory('load', completeHistory(metadata) ? 'all' : 'recent', state.adjustment, 'tinysoft');
        if (['overlay-ma', 'overlay-boll', 'overlay-none'].includes(action)) return update({ overlay: action.slice(8) }, 'overlay', true);
        if (/^ma-(5|10|20|60|120|250)$/.test(action)) { const period = Number(action.slice(3)); return update({ enabledMA: state.enabledMA.includes(period) ? state.enabledMA.filter(value => value !== period) : MA_PERIODS.filter(value => value === period || state.enabledMA.includes(value)) }, 'ma', true); }
        if (action.startsWith('panel-add-') || action.startsWith('panel-remove-')) {
          const add = action.startsWith('panel-add-'); const id = action.slice(add ? 10 : 13); if (!Object.hasOwn(PANEL_NAMES, id) || add === state.panels.includes(id)) return false;
          const panels = add ? [...state.panels, id] : state.panels.filter(value => value !== id);
          return persistPanels({panels,activePanel:add?id:panels.at(-1)||''});
        }
        if (action.startsWith('period-')) return changePeriod(action.slice(7));
        if (action === 'all') {
          if (completeHistory(metadata) && !requiresHistoryRebuild(metadata)) return update({ start: 0, end: bars.length, showAll: true }, 'all', true);
          return requestHistory('load', 'all');
        }
        if (action === 'history-cancel') return requestHistory('cancel', jobFor(metadata).scope || lastHistoryScope);
        if (action === 'history-retry') return retryableHistory(metadata) && requestHistory('retry', jobFor(metadata).scope || lastHistoryScope);
        if (action === 'date-prev' || action === 'date-next') return selectDate(daily[clamp(selectedDailyIndex() + (action === 'date-prev' ? -1 : 1), 0, daily.length - 1)]?.date);
        if (action === 'latest') return latest(); if (action === 'reset') return reset(); if (action === 'locate') return locate();
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
    const preservedRange=nextSlot===slot?rangeController?.getState():null;
    release(); if (!nextSlot) return false; slot = nextSlot; view = slot.ownerDocument?.defaultView || (typeof window === 'undefined' ? null : window);
    const result = guarded('mount', () => {
      const rangeLayer='<div class="asset-range-layer" data-asset-range-layer hidden><div class="asset-range-selection" data-asset-range-selection hidden></div><section class="asset-range-card" data-asset-range-card role="region" aria-label="区间统计" hidden></section></div>';
      slot.innerHTML = renderMarketTerminal(rawRows, state, metadata).replace('<div class="asset-panel-controls">',`${rangeLayer}<div class="asset-panel-controls">`);
      rangeHost=find('.asset-kline-stage')||slot;
      rangeController=metadata.minute_k ? null : createRangeController({host:rangeHost,getContext:rangeContext,logger});
      const capture=event=>rangeController?.capture(event);
      for(const name of ['pointerdown','mousedown','contextmenu','click','lostpointercapture'])listen(slot,name,capture,true);
      for(const name of ['pointermove','mousemove','pointerup','mouseup','pointercancel','blur'])if(view?.addEventListener)listen(view,name,capture,true);
      if(view?.addEventListener)listen(view,'keydown',event=>{if(event.key==='Escape'&&!modalOwnsEscape(event))rangeController?.handle(event);},true);
      for(const name of ['resize','scroll'])if(view?.addEventListener)listen(view,name,()=>rangeController?.render(),true);
      listen(slot,'toggle',event=>{if(event.target?.matches?.('.asset-range-method'))rangeController?.render();},true);
      const localHandle = event => { const handled = handle(event); if (handled) { event.assetChartHandled = true; event.stopPropagation?.(); } };
      listen(slot, 'click', localHandle); listen(slot, 'keydown', localHandle); listen(slot, 'change', localHandle); listen(slot, 'input', localHandle); listen(slot, 'submit', localHandle);
      for (const selector of ['[data-asset-indicator-manager]','[data-asset-indicator-parameter-dialog]']) {const dialog=find(selector);if(dialog)listen(dialog,'cancel',localHandle);}
      for (const selector of ['[data-asset-echarts]', '[data-asset-chip-chart]']) { const node = find(selector); if (node) { listen(node, 'mouseleave', hidePointer); listen(node, 'pointerleave', hidePointer); } }
      initCharts(); rangeController?.restore(preservedRange); schedule(true); return true;
    });
    if (result === false) release(); return result;
  }
  return { configure, getState, setPreferences, mount, dispose: release, cancel, handle, select, selectDate, pan, zoom, reset, locate };
}
