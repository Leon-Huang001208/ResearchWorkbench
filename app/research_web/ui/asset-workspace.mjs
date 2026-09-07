import { escapeHTML as e } from './markdown.mjs';

const LABELS = {
  overview: '资产概览', history: '历史行情', financials: '财务指标', activity: '资金与交易事件',
  announcements: '公告', news: '新闻', research: '研究资料',
};

const STATE_LABELS = {
  loading: '加载中', complete: '完整', partial: '部分', empty: '暂无数据', unavailable: '不可用', error: '失败',
};

const number = (value, digits = 2) => typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString('zh-CN', { maximumFractionDigits: digits }) : '—';
const finite = (value) => {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null;
  return Number.isFinite(Number(value)) ? Number(value) : null;
};
const firstValue = (source, keys) => keys.map(key => source?.[key]).find(value => finite(value) !== null);
const metric = (label, value, suffix = '') => `<div><dt>${e(label)}</dt><dd>${finite(value) === null ? '—' : `${e(number(finite(value)))}${e(suffix)}`}</dd></div>`;

const marketValue = (row, keys) => finite(firstValue(row, keys));
const clamp = (value, minimum, maximum) => Math.min(maximum, Math.max(minimum, value));

function average(values) {
  const usable = values.filter(value => value !== null);
  return usable.length ? usable.reduce((sum, value) => sum + value, 0) / usable.length : null;
}

function movingAverage(values, period, index) {
  return average(values.slice(Math.max(0, index - period + 1), index + 1));
}

function exponentialAverage(values, period) {
  const weight = 2 / (period + 1);
  let previous = null;
  return values.map((value) => {
    if (value === null) return previous;
    previous = previous === null ? value : value * weight + previous * (1 - weight);
    return previous;
  });
}

export function enrichMarketBars(rows = []) {
  const bars = rows.map(row => ({
    date: String(row.date || row.trade_date || row.datetime || row.time || ''),
    open: marketValue(row, ['open', '开盘']), high: marketValue(row, ['high', '最高']),
    low: marketValue(row, ['low', '最低']), close: marketValue(row, ['close', '收盘', 'price', 'last']),
    volume: marketValue(row, ['volume', 'vol', '成交量']), amount: marketValue(row, ['amount', '成交额']),
    turnover: marketValue(row, ['turnover', 'turnover_rate', '换手率']),
  })).filter(bar => bar.close !== null).sort((left, right) => left.date.localeCompare(right.date));
  const closes = bars.map(bar => bar.close);
  const ema12 = exponentialAverage(closes, 12); const ema26 = exponentialAverage(closes, 26);
  const dif = closes.map((_, index) => ema12[index] - ema26[index]); const dea = exponentialAverage(dif, 9);
  let k = 50; let d = 50;
  return bars.map((bar, index) => {
    const window = bars.slice(Math.max(0, index - 8), index + 1);
    const low9 = Math.min(...window.map(item => item.low ?? item.close));
    const high9 = Math.max(...window.map(item => item.high ?? item.close));
    const rsv = high9 === low9 ? 50 : ((bar.close - low9) / (high9 - low9)) * 100;
    k = (2 * k + rsv) / 3; d = (2 * d + k) / 3;
    const changeStart = Math.max(1, index - 13);
    const changes = closes.slice(changeStart, index + 1).map((value, offset) => value - closes[changeStart + offset - 1]);
    const gains = average(changes.map(value => Math.max(value, 0)));
    const losses = average(changes.map(value => Math.max(-value, 0)));
    const rsi = index === 0 ? null : losses === 0 ? 100 : 100 - (100 / (1 + gains / losses));
    const ma20 = movingAverage(closes, 20, index);
    const deviation = Math.sqrt(average(closes.slice(Math.max(0, index - 19), index + 1).map(value => (value - ma20) ** 2)) || 0);
    return {
      ...bar,
      ma5: movingAverage(closes, 5, index), ma10: movingAverage(closes, 10, index), ma20,
      bollUpper: ma20 + deviation * 2, bollLower: ma20 - deviation * 2,
      dif: dif[index], dea: dea[index], macd: (dif[index] - dea[index]) * 2,
      k, d, j: 3 * k - 2 * d, rsi,
    };
  });
}

function seriesPath(bars, key, xAt, yAt) {
  let started = false;
  return bars.map((bar, index) => {
    if (finite(bar[key]) === null) return '';
    const command = started ? 'L' : 'M'; started = true;
    return `${command}${xAt(index).toFixed(1)},${yAt(bar[key]).toFixed(1)}`;
  }).filter(Boolean).join(' ');
}

function panelGrid(y, height, width, label) {
  return `<g class="asset-chart-grid"><line x1="54" y1="${y}" x2="${width - 12}" y2="${y}"/><line x1="54" y1="${y + height}" x2="${width - 12}" y2="${y + height}"/><text x="8" y="${y + 14}">${e(label)}</text></g>`;
}

export function renderMarketTerminal(rows = []) {
  const bars = enrichMarketBars(rows).slice(-120);
  if (bars.length < 2) return '<section class="asset-market-terminal"><div class="chart-empty">历史数据不足，无法绘制 K 线与技术指标。</div></section>';
  const width = 980; const height = 590; const left = 54; const right = 12; const plotWidth = width - left - right;
  const pricePanel = { y: 24, h: 220 }; const volumePanel = { y: 267, h: 54 };
  const macdPanel = { y: 344, h: 64 }; const kdjPanel = { y: 431, h: 58 }; const rsiPanel = { y: 512, h: 58 };
  const candleWidth = Math.max(1.5, Math.min(7, plotWidth / bars.length * 0.62));
  const xAt = index => left + ((index + 0.5) / bars.length) * plotWidth;
  const priceValues = bars.flatMap(bar => [bar.low, bar.high, bar.ma5, bar.ma10, bar.ma20, bar.bollUpper, bar.bollLower]).filter(value => value !== null);
  const priceMin = Math.min(...priceValues); const priceMax = Math.max(...priceValues); const priceSpan = priceMax - priceMin || 1;
  const priceY = value => pricePanel.y + ((priceMax - value) / priceSpan) * pricePanel.h;
  const volumeMax = Math.max(...bars.map(bar => bar.volume || 0), 1);
  const volumeY = value => volumePanel.y + volumePanel.h - ((value || 0) / volumeMax) * volumePanel.h;
  const macdValues = bars.flatMap(bar => [bar.macd, bar.dif, bar.dea]); const macdMax = Math.max(...macdValues.map(Math.abs), 0.0001);
  const macdY = value => macdPanel.y + macdPanel.h / 2 - (value / macdMax) * (macdPanel.h / 2);
  const boundedY = panel => value => panel.y + ((100 - clamp(value, 0, 100)) / 100) * panel.h;
  const kdjY = boundedY(kdjPanel); const rsiY = boundedY(rsiPanel);
  const candles = bars.map((bar, index) => {
    const open = bar.open ?? bar.close; const high = bar.high ?? Math.max(open, bar.close); const low = bar.low ?? Math.min(open, bar.close);
    const direction = bar.close >= open ? 'up' : 'down'; const x = xAt(index); const top = Math.min(priceY(open), priceY(bar.close));
    return `<g class="asset-candle ${direction}"><line x1="${x.toFixed(1)}" y1="${priceY(high).toFixed(1)}" x2="${x.toFixed(1)}" y2="${priceY(low).toFixed(1)}"/><rect x="${(x - candleWidth / 2).toFixed(1)}" y="${top.toFixed(1)}" width="${candleWidth.toFixed(1)}" height="${Math.max(1, Math.abs(priceY(open) - priceY(bar.close))).toFixed(1)}"/></g>`;
  }).join('');
  const volumes = bars.map((bar, index) => `<rect class="asset-volume ${bar.close >= (bar.open ?? bar.close) ? 'up' : 'down'}" x="${(xAt(index) - candleWidth / 2).toFixed(1)}" y="${volumeY(bar.volume).toFixed(1)}" width="${candleWidth.toFixed(1)}" height="${Math.max(1, volumePanel.y + volumePanel.h - volumeY(bar.volume)).toFixed(1)}"/>`).join('');
  const histogram = bars.map((bar, index) => { const y = macdY(bar.macd); const zero = macdY(0); return `<rect class="asset-macd ${bar.macd >= 0 ? 'up' : 'down'}" x="${(xAt(index) - candleWidth / 2).toFixed(1)}" y="${Math.min(y, zero).toFixed(1)}" width="${candleWidth.toFixed(1)}" height="${Math.max(1, Math.abs(zero - y)).toFixed(1)}"/>`; }).join('');
  const latest = bars.at(-1); const previous = bars.at(-2); const change = latest.close - previous.close; const changePct = previous.close ? change / previous.close * 100 : null;
  const amplitude = latest.high !== null && latest.low !== null && previous.close ? (latest.high - latest.low) / previous.close * 100 : null;
  const quote = [
    ['日期', latest.date || '—'], ['收', number(latest.close)], ['幅', changePct === null ? '—' : `${changePct >= 0 ? '+' : ''}${number(changePct)}%`],
    ['开', number(latest.open)], ['高', number(latest.high)], ['低', number(latest.low)], ['量', number(latest.volume, 0)],
    ['换', latest.turnover === null ? '—' : `${number(latest.turnover)}%`], ['振', amplitude === null ? '—' : `${number(amplitude)}%`], ['额', number(latest.amount, 0)],
  ];
  return `<section class="asset-market-terminal" aria-label="K 线与技术指标"><header><div><span class="eyebrow">MARKET TERMINAL</span><h2>K 线与技术指标</h2></div><div class="asset-terminal-period" aria-label="行情周期说明"><span>日 / 周 / 月可在上方查询条件切换</span></div></header><div class="asset-terminal-quote">${quote.map(([label, value]) => `<span>${e(label)} <strong>${e(value)}</strong></span>`).join('')}</div><div class="asset-terminal-legend"><span class="ma5">MA5</span><span class="ma10">MA10</span><span class="ma20">MA20</span><span class="boll">BOLL</span><span class="up">上涨</span><span class="down">下跌</span></div><div class="asset-chart-scroll"><svg class="asset-terminal-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="包含 K 线、成交量、MACD、KDJ 和 RSI 的行情图" preserveAspectRatio="xMidYMid meet"><title>K 线、成交量、MACD、KDJ 与 RSI</title>${panelGrid(pricePanel.y, pricePanel.h, width, 'K线')}${panelGrid(volumePanel.y, volumePanel.h, width, '成交量')}${panelGrid(macdPanel.y, macdPanel.h, width, 'MACD')}${panelGrid(kdjPanel.y, kdjPanel.h, width, 'KDJ')}${panelGrid(rsiPanel.y, rsiPanel.h, width, 'RSI')}${candles}<path class="asset-series ma5" d="${seriesPath(bars, 'ma5', xAt, priceY)}"/><path class="asset-series ma10" d="${seriesPath(bars, 'ma10', xAt, priceY)}"/><path class="asset-series ma20" d="${seriesPath(bars, 'ma20', xAt, priceY)}"/><path class="asset-series boll" d="${seriesPath(bars, 'bollUpper', xAt, priceY)}"/><path class="asset-series boll" d="${seriesPath(bars, 'bollLower', xAt, priceY)}"/>${volumes}${histogram}<path class="asset-series dif" d="${seriesPath(bars, 'dif', xAt, macdY)}"/><path class="asset-series dea" d="${seriesPath(bars, 'dea', xAt, macdY)}"/><path class="asset-series k" d="${seriesPath(bars, 'k', xAt, kdjY)}"/><path class="asset-series d" d="${seriesPath(bars, 'd', xAt, kdjY)}"/><path class="asset-series j" d="${seriesPath(bars, 'j', xAt, kdjY)}"/><line class="asset-threshold" x1="${left}" y1="${rsiY(80)}" x2="${width - right}" y2="${rsiY(80)}"/><line class="asset-threshold" x1="${left}" y1="${rsiY(20)}" x2="${width - right}" y2="${rsiY(20)}"/><path class="asset-series rsi" d="${seriesPath(bars, 'rsi', xAt, rsiY)}"/><text class="asset-axis-value" x="${width - 58}" y="${pricePanel.y + 12}">${e(number(priceMax))}</text><text class="asset-axis-value" x="${width - 58}" y="${pricePanel.y + pricePanel.h - 5}">${e(number(priceMin))}</text></svg></div></section>`;
}

function previewTable(rows = [], limit = 8) {
  const values = rows.slice(0, limit);
  if (!values.length) return '<p class="muted small">这个区块没有可显示的真实记录。</p>';
  const columns = [...new Set(values.flatMap(row => Object.keys(row)))].slice(0, 6);
  return `<div class="asset-table-wrap"><table class="asset-table"><thead><tr>${columns.map(column => `<th>${e(column)}</th>`).join('')}</tr></thead><tbody>${values.map(row => `<tr>${columns.map(column => `<td>${e(row[column] ?? '—')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}

function blockCard(name, block = { status: 'loading' }, rows = []) {
  const status = block.status || 'loading';
  const meta = block.dataset;
  return `<article class="asset-block ${e(status)}"><header><div><span class="eyebrow">${e(name.toUpperCase())}</span><h2>${e(LABELS[name] || name)}</h2></div><span class="badge ${status === 'complete' ? 'live' : ['error', 'unavailable'].includes(status) ? 'danger' : ''}">${e(STATE_LABELS[status] || status)}</span></header>${meta ? `<p class="muted small">${e(meta.provider || meta.source || '未知来源')} · 截止 ${e(meta.as_of || meta.actual_range?.end_date || '来源未提供')}</p>` : ''}${block.failure_code ? `<p class="notice warning">${e(block.failure_code)}</p>` : ''}${['complete', 'partial'].includes(status) ? previewTable(rows) : status === 'loading' ? '<div class="asset-skeleton" role="status">正在查询这个区块…</div>' : status === 'empty' ? '<p class="muted small">来源成功响应，但没有匹配记录。</p>' : ''}</article>`;
}

function assetHeader(observation, rows) {
  const history = rows?.history || [];
  const latest = history.at(-1) || {};
  const snapshot = { ...latest, ...(rows?.overview?.[0] || {}) };
  const datasets = observation?.dataset_ids || [];
  const price = firstValue(snapshot, ['price', 'last', 'close', 'nav', '收盘']);
  const changePct = firstValue(snapshot, ['change_pct', 'pct_chg', '涨跌幅']);
  return `<section class="asset-identity"><div><span class="eyebrow">ASSET WORKSPACE</span><h1>${e(snapshot.name || observation?.asset || '资产观察')}</h1><p>${e(observation?.asset || '输入证券代码开始')} · ${e(observation?.asset_type || '股票 / ETF / 指数 / 基金 / 主题')}</p></div><div class="asset-price"><strong>${e(number(price))}</strong><span class="${changePct === null || changePct >= 0 ? 'positive' : 'negative'}">${changePct !== null ? `${changePct >= 0 ? '+' : ''}${number(changePct)}%` : '涨跌未知'}</span></div><div class="button-row"><button class="button" data-workbench-handoff="fingpt" data-source-session="${e(observation?.session_id || '')}" data-dataset-ids="${e(JSON.stringify(datasets))}" ${observation?.session_id && datasets.length ? '' : 'disabled'}>交给 FinGPT</button><button class="button primary" data-workbench-handoff="claw" data-source-session="${e(observation?.session_id || '')}" data-dataset-ids="${e(JSON.stringify(datasets))}" ${observation?.session_id && datasets.length ? '' : 'disabled'}>交给 Claw</button></div></section>`;
}

function marketMetrics(rows = {}) {
  const history = rows.history || [];
  const latest = history.at(-1) || {};
  const overview = rows.overview?.[0] || {};
  const source = { ...latest, ...overview };
  const closes = history.map(row => finite(firstValue(row, ['close', '收盘']))).filter(value => value !== null);
  const high52 = closes.length ? Math.max(...closes.slice(-252)) : null;
  const low52 = closes.length ? Math.min(...closes.slice(-252)) : null;
  return `<dl class="asset-market-metrics" aria-label="资产核心指标">${metric('开盘', firstValue(source, ['open', '开盘']))}${metric('最高', firstValue(source, ['high', '最高']))}${metric('最低', firstValue(source, ['low', '最低']))}${metric('成交量', firstValue(source, ['volume', '成交量']), '')}${metric('成交额', firstValue(source, ['amount', '成交额']), '')}${metric('换手率', firstValue(source, ['turnover', 'turnover_rate', '换手率']), '%')}${metric('52周高', high52)}${metric('52周低', low52)}</dl>`;
}

function personalPanel({ observation, watchlists = [], notes = [], alerts = [], notifications = [] }) {
  const asset = observation?.asset || '';
  const selectedNotes = notes.filter(item => item.asset === asset);
  const selectedAlerts = alerts.filter(item => item.asset === asset);
  return `<aside class="asset-personal"><section><div class="section-heading"><h2>自选与观察</h2><span class="muted small">本地保存</span></div>${watchlists.length ? `<form data-watchlist-item><input type="hidden" name="asset" value="${e(asset)}"><label>加入列表<select name="watchlist_id">${watchlists.map(item => `<option value="${e(item.id)}">${e(item.name)}</option>`).join('')}</select></label><button class="button small" ${asset ? '' : 'disabled'}>加入自选</button></form>` : '<p class="muted small">尚无自选列表。</p>'}<form data-asset-note><label>观察笔记<textarea name="text" maxlength="10000" required placeholder="记录判断、待验证事项和后续动作"></textarea></label><input type="hidden" name="asset" value="${e(asset)}"><button class="button small" ${asset ? '' : 'disabled'}>保存笔记</button></form>${selectedNotes.map(item => `<p class="personal-entry">${e(item.text)}</p>`).join('')}</section><section><div class="section-heading"><h2>提醒规则</h2><span class="muted small">快照到达时评估</span></div><form data-asset-alert><input type="hidden" name="asset" value="${e(asset)}"><div class="mini-form"><select name="field"><option value="price">价格</option><option value="change_pct">涨跌幅</option><option value="volume">成交量</option></select><select name="operator"><option value="gte">≥</option><option value="lte">≤</option><option value="gt">＞</option><option value="lt">＜</option></select><input name="threshold" type="number" step="any" required placeholder="阈值"></div><button class="button small" ${asset ? '' : 'disabled'}>添加提醒</button></form>${selectedAlerts.map(item => `<p class="personal-entry"><span class="tiny-dot ${item.enabled ? 'active' : ''}"></span>${e(item.field)} ${e(item.operator)} ${e(item.threshold)} · ${item.condition_active ? '已触发' : '监控中'}</p>`).join('') || '<p class="muted small">当前资产没有提醒。</p>'}${notifications.filter(item => item.asset === asset).slice(0, 3).map(item => `<p class="notice warning">已触发：${e(item.field)} = ${e(item.value)}</p>`).join('')}</section></aside>`;
}

function researchContext(observation) {
  const blocks = observation?.blocks || {};
  const sources = Object.entries(blocks).map(([name, block]) => ({
    name: LABELS[name] || name,
    status: block?.status || 'unavailable',
    provider: block?.dataset?.provider || block?.dataset?.source || '未取得',
    asOf: block?.dataset?.as_of || block?.dataset?.actual_range?.end_date || '未提供',
  }));
  return `<section class="asset-research-context" aria-label="资产研究上下文"><article><span class="eyebrow">PEERS</span><h2>同类比较</h2><p class="muted small">当前 DataHub 尚未返回可核对的同类集合；不使用静态排名或虚构估值填充。</p></article><article><span class="eyebrow">THEME EXPOSURE</span><h2>主题暴露</h2><p class="muted small">当前资产尚无来自真实数据源的主题暴露结果；待产业链/持仓 Provider 接入后显示。</p></article><article class="asset-source-matrix"><span class="eyebrow">SOURCES & COVERAGE</span><h2>来源与口径</h2>${sources.length ? `<ul>${sources.map(item => `<li><strong>${e(item.name)}</strong><span>${e(item.provider)}</span><span>${e(STATE_LABELS[item.status] || item.status)} · ${e(item.asOf)}</span></li>`).join('')}</ul>` : '<p class="muted small">查询资产后，这里会按区块列出实际数据源、截止时间和覆盖状态。</p>'}</article></section>`;
}

export function readAssetObservation(form) {
  const data = new FormData(form);
  return {
    asset: String(data.get('asset') || '').trim().toUpperCase(),
    asset_type: String(data.get('asset_type') || 'stock'),
    source: String(data.get('source') || 'auto'),
    start_date: String(data.get('start_date') || '') || null,
    end_date: String(data.get('end_date') || '') || null,
    frequency: String(data.get('frequency') || 'daily'),
    adjustment: String(data.get('adjustment') || 'qfq'),
    sections: ['overview', 'history', 'financials', 'activity', 'announcements', 'news', 'research'],
  };
}

export function renderAssetWorkspace({ observation = null, rows = {}, watchlists = [], notes = [], alerts = [], notifications = [], busy = false } = {}) {
  const blocks = observation?.blocks || Object.fromEntries(Object.keys(LABELS).map(key => [key, { status: 'empty' }]));
  const today = new Date().toISOString().slice(0, 10);
  const start = new Date(); start.setFullYear(start.getFullYear() - 1);
  return `<header class="page-header"><div><div class="eyebrow">ASSET OBSERVATION</div><h1>资产观察</h1><p class="muted">行情、财务、事件、公告与资料分别取数；每个区块独立显示真实状态。</p></div><button class="button" data-refresh>刷新本地状态</button></header><form class="asset-search" data-asset-observation><label>证券代码<input name="asset" value="${e(observation?.asset || '')}" placeholder="例如 600519.SH" pattern="[A-Za-z0-9._-]+" required></label><label>类型<select name="asset_type">${[['stock', '股票'], ['etf', 'ETF'], ['index', '指数'], ['fund', '基金'], ['theme', '主题']].map(([id, label]) => `<option value="${id}" ${observation?.asset_type === id ? 'selected' : ''}>${label}</option>`).join('')}</select></label><label>起始日<input type="date" name="start_date" value="${start.toISOString().slice(0, 10)}" required></label><label>结束日<input type="date" name="end_date" value="${today}" required></label><label>周期<select name="frequency"><option value="daily">日线</option><option value="weekly">周线</option><option value="monthly">月线</option></select></label><label>复权<select name="adjustment"><option value="qfq">前复权</option><option value="none">不复权</option><option value="hfq">后复权</option></select></label><button class="button primary" ${busy ? 'disabled' : ''}>${busy ? '正在更新…' : '更新全部区块'}</button></form>${assetHeader(observation, rows)}${marketMetrics(rows)}${renderMarketTerminal(rows.history || [])}${researchContext(observation)}<div class="asset-workspace-grid"><div class="asset-blocks">${Object.entries(blocks).map(([name, block]) => blockCard(name, block, rows[name] || [])).join('')}</div>${personalPanel({ observation, watchlists, notes, alerts, notifications })}</div>`;
}
