import { escapeHTML as e } from './markdown.mjs';
import { safeLog } from './core.mjs';
import { assetHref } from './asset-navigation.mjs';

const VIEWS = { overview: '总览', quotes: '沪深北行情', sectors: '板块与资金' };
const MARKET_STATES = { preopen: '盘前', auction: '集合竞价', open: '交易中', lunch: '午间休市', closed: '已收盘', non_trading: '非交易日', unknown: '交易状态待确认' };
const EXCHANGES = { all: '全部市场', SH: '上海', SZ: '深圳', BJ: '北京' };
const BOARDS = { all: '全部板块', main: '主板', star: '科创板', chinext: '创业板', beijing: '北交所' };
const PERIODS = { today: '今日', '5d': '5日', '10d': '10日' };
const BASE_SECTIONS = ['quotes', 'indices', 'industry', 'concept', 'calendar'];
const DEFAULT_FILTERS = { exchange: 'all', board: 'all', search: '', sort: 'change_pct', direction: 'desc', offset: 0, limit: 50, board_id: '' };
export const MARKET_COLUMNS = [
  ['code', '代码'], ['name', '名称'], ['price', '最新价', '元'], ['change', '涨跌额', '元'], ['change_pct', '涨跌幅', '%'],
  ['volume', '成交量', '股'], ['amount', '成交额', '元'], ['amplitude_pct', '振幅', '%'], ['turnover_rate_pct', '换手率', '%'],
  ['volume_ratio', '量比', '倍'], ['pe_dynamic', 'PE（动态）', '倍'], ['pb', 'PB', '倍'], ['total_market_cap', '总市值', '元'], ['float_market_cap', '流通市值', '元'],
];
const DEFAULT_COLUMNS = MARKET_COLUMNS.map(([key]) => key);
const finite = value => value === null || value === undefined || value === '' || typeof value === 'boolean' || typeof value === 'string' && !value.trim() || !Number.isFinite(Number(value)) ? null : Number(value);
const array = value => Array.isArray(value) ? value : [];
const boardID = value => /^BK\d{4,6}$/.test(String(value || '')) ? String(value) : '';
const object = value => value && typeof value === 'object' && !Array.isArray(value) ? value : {};
export function marketNumber(value, digits = 2) { const n = finite(value); return n === null ? '—' : n.toLocaleString('zh-CN', { maximumFractionDigits: digits }); }
export function marketSign(value) { const n = finite(value); return n === null ? 'unknown' : n > 0 ? 'up' : n < 0 ? 'down' : 'flat'; }
const pct = value => { const n = finite(value); return n === null ? '—' : `${n > 0 ? '+' : ''}${marketNumber(n)}%`; };
const money = value => { const n = finite(value); return n === null ? '—' : Math.abs(n) >= 1e8 ? `${marketNumber(n / 1e8)}亿` : Math.abs(n) >= 1e4 ? `${marketNumber(n / 1e4)}万` : marketNumber(n); };
const stamp = value => { if (!value) return '未提供'; const date = new Date(value); return Number.isFinite(date.getTime()) ? date.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) : String(value); };
const tradingDate = value => { if (!value) return ''; const date = new Date(value); return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai' }).format(date) : ''; };
const signed = (value, formatter = pct) => `<span class="market-${marketSign(value)}">${e(formatter(value))}</span>`;
const empty = (message = '暂无已取得的行情快照，可点击刷新。') => `<p class="market-empty">${e(message)}</p>`;

export function marketHref(view = 'overview', board = '') {
  const params = new URLSearchParams({ view: Object.hasOwn(VIEWS, view) ? view : 'overview' });
  if (boardID(board)) params.set('board_id', board);
  return `#/market?${params}`;
}

export function marketQuoteParams(filters = {}, snapshotID = '') {
  const params = new URLSearchParams();
  const values = { ...DEFAULT_FILTERS, ...filters };
  for (const key of ['exchange', 'board', 'search', 'sort', 'direction', 'offset', 'limit', 'board_id']) if (values[key] !== '' && values[key] !== undefined) params.set(key, String(values[key]));
  if (snapshotID) params.set('snapshot_id', snapshotID);
  return params;
}

function metadata(section = {}) {
  const rows = array(section.rows), total = finite(section.provider_total);
  const received = section.row_count ?? section.summary?.total ?? (Object.hasOwn(section, 'rows') ? rows.length : null);
  const coverage = total === null ? '覆盖数未提供' : `${marketNumber(received, 0)} / ${marketNumber(total, 0)} 条`;
  const state = section.stale ? '陈旧 · 保留上次快照' : section.complete === false || section.pagination_complete === false ? '未完整' : section.complete ? '完整' : '待采集';
  const error = typeof section.error === 'string' ? section.error : section.error?.message || section.error?.code;
  const missing = Object.entries(object(section.missing)).filter(([, value]) => value !== null && value !== 0 && value !== false).map(([key, value]) => `${key}：${typeof value === 'object' ? JSON.stringify(value) : value}`);
  return `<details class="market-metadata"><summary><span class="market-state-pill ${section.stale || section.complete === false ? 'warning' : ''}">${e(state)}</span>${section.summary?.temporal_complete === false ? '<span class="market-state-pill warning">行情日不齐</span>' : ''}<span>${e(section.provider === 'eastmoney' ? '东方财富' : section.provider || '来源待确认')} · ${e(coverage)}</span><span>行情 ${e(section.trade_date ? `${section.trade_date}（日线）` : stamp(section.as_of))}</span></summary><div><p>采集：${e(stamp(section.retrieved_at))} · 北京时间</p>${section.summary?.quote_trade_date ? `<p>统计行情日：${e(section.summary.quote_trade_date)}</p>` : ''}${section.summary?.temporal_complete === false ? '<p>存在跨日或日期缺失记录；当日合计仅在时间口径确认后发布。</p>' : ''}${section.trade_date ? `<p>行情日：${e(section.trade_date)}（日线）</p>` : ''}${section.started_at ? `<p>采集区间：${e(stamp(section.started_at))} — ${e(stamp(section.retrieved_at))}</p>` : ''}${section.snapshot_id ? `<p>快照：${e(section.snapshot_id)}</p>` : ''}${error ? `<p class="market-error">本次刷新：${e(error)}</p>` : ''}${missing.length ? `<p>缺失：${e(missing.join('；'))}</p>` : ''}${array(section.limitations).map(item => `<p>${e(item)}</p>`).join('')}</div></details>`;
}

function panel(title, content, section = {}, extra = '') {
  return `<section class="market-panel ${extra}"><header><h2>${e(title)}</h2>${section.complete === false ? '<span class="market-state-pill warning">部分覆盖</span>' : ''}</header>${content}${metadata(section)}</section>`;
}

function indicesPanel(section = {}, selected = []) {
  const rows = array(section.rows);
  const latestDay = tradingDate(section.as_of);
  const cards = rows.map(row => {
    const day = tradingDate(row.as_of), older = day && latestDay && day !== latestDay;
    return `<a class="market-index-card" href="${e(assetHref(row.asset, 'index'))}" title="行情 ${e(stamp(row.as_of))}"><span>${e(row.name || row.asset)}</span><strong>${e(marketNumber(row.price))}</strong><span class="market-index-change">${signed(row.change_pct)}<small>${e(marketNumber(row.change))}</small></span><small class="market-index-date ${older ? 'market-date-old' : ''}">${e(day || '行情日期未提供')}${older ? ' · 旧日' : ''}</small></a>`;
  }).join('');
  return panel('主要指数', cards ? `<div class="market-index-grid">${cards}</div>` : empty('12个主要指数等待采集；不可用项将保留缺口。'), section, 'market-indices') + panel('指数分时对比', indexChart(rows, selected), section, 'market-index-comparison');
}

const COLORS = ['#69a8ff', '#e8b348', '#d07ef3', '#48c0b0', '#ec8da4', '#a5b66b', '#7ec5e8', '#b68e6b', '#a9a9e5', '#e7b6d0', '#9cc3a9', '#e4c994'];
function tradingMinute(value) {
  const text = String(value || '');
  const matches = text.match(/(?:T|\s|^)(\d{2}):(\d{2})/);
  let hour, minute;
  if (matches && !/[zZ]|[+-]\d\d:\d\d$/.test(text)) { hour = Number(matches[1]); minute = Number(matches[2]); }
  else {
    const date = new Date(value); if (!Number.isFinite(date.getTime())) return null;
    const parts = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', hour12: false }).format(date).split(':');
    [hour, minute] = parts.map(Number);
  }
  const total = hour * 60 + minute;
  if (total < 570 || total > 900 || total > 690 && total < 780) return null;
  return total <= 690 ? total - 570 : total - 660;
}

function indexChart(rows, selected) {
  const eligible = rows.filter(row => array(row.series).some(item => finite(item.change_pct) !== null));
  const legend = `<div class="market-chart-legend">${eligible.map((row, index) => `<label><input type="checkbox" data-market-index="${e(row.asset)}" ${!selected.length || selected.includes(row.asset) ? 'checked' : ''}><i style="background:${COLORS[index % COLORS.length]}"></i>${e(row.name)}</label>`).join('')}</div>`;
  const visible = eligible.filter(row => !selected.length || selected.includes(row.asset));
  const series = visible.map(row => ({ ...row, points: array(row.series).map(point => ({ ...point, x: tradingMinute(point.time), y: finite(point.change_pct) })).filter(point => point.x !== null && point.y !== null) }));
  const points = series.flatMap(row => row.points);
  if (!points.length) return eligible.length ? `${legend}${empty('当前指数曲线已隐藏或缺少可绘制时点，可勾选指数查看。')}` : empty('分时对比需要真实分时数据及昨收基准；当前尚未取得，不补造曲线。');
  let low = Math.min(0, ...points.map(point => point.y)), high = Math.max(0, ...points.map(point => point.y));
  const pad = Math.max(0.2, (high - low) * 0.12); low -= pad; high += pad;
  const x = value => 48 + value / 240 * 700;
  const y = value => 208 - (value - low) / (high - low) * 186;
  const grid = [low, (low + high) / 2, high].map(value => `<line x1="48" x2="748" y1="${y(value)}" y2="${y(value)}"/><text x="40" y="${y(value) + 4}" text-anchor="end">${e(marketNumber(value))}%</text>`).join('');
  const paths = series.map(row => {
    const color = COLORS[eligible.findIndex(item => item.asset === row.asset) % COLORS.length];
    const path = row.points.map((point, index) => `${!index || point.x - row.points[index - 1].x > 1.5 ? 'M' : 'L'}${x(point.x).toFixed(2)},${y(point.y).toFixed(2)}`).join(' ');
    return `<path d="${path}" fill="none" stroke="${color}" stroke-width="1.8"><title>${e(row.name)} · ${e(pct(row.points.at(-1)?.y))}</title></path>${row.points.length === 1 ? `<circle cx="${x(row.points[0].x)}" cy="${y(row.points[0].y)}" r="2.5" fill="${color}"/>` : ''}`;
  }).join('');
  const times = [[0, '09:30'], [60, '10:30'], [120, '11:30 / 13:00'], [180, '14:00'], [240, '15:00']].map(([value, label]) => `<text x="${x(value)}" y="233" text-anchor="middle">${label}</text>`).join('');
  return `${legend}<svg class="market-intraday" viewBox="0 0 780 246" role="img" aria-label="主要指数当日涨跌幅分时对比"><g class="market-chart-grid">${grid}</g><line class="market-zero-line" x1="48" x2="748" y1="${y(0)}" y2="${y(0)}"/>${paths}<g class="market-chart-axis">${times}</g></svg><p class="market-caption">相对真实昨收的涨跌幅 · 午间休市折叠 · 缺失时点不补值</p>`;
}

function breadthPanels(section = {}) {
  const summary = object(section.summary), breadth = { ...object(summary.breadth), ...summary };
  const metrics = [['up', '上涨', 'up'], ['down', '下跌', 'down'], ['flat', '平盘', 'flat'], ['unknown', '缺报价', 'unknown']];
  for (const [key, label] of [['suspended', '停牌'], ['unlisted', '未上市']]) if (Object.hasOwn(breadth, key)) metrics.push([key, label, 'unknown']);
  const counts = metrics.map(([key]) => finite(breadth[key])); const total = counts.every(n => n !== null) ? counts.reduce((a, b) => a + b, 0) : null;
  const bars = total > 0 ? `<div class="market-breadth-bar" role="img" aria-label="${metrics.length > 4 ? '上涨、下跌、平盘、缺报价、停牌与未上市占比' : '上涨、下跌、平盘与缺报价占比'}">${metrics.map(([key, label, tone]) => `<span class="market-bg-${tone}" style="width:${Math.max(0, Number(breadth[key]) / total * 100)}%" title="${label} ${marketNumber(breadth[key], 0)}"></span>`).join('')}</div>` : '';
  const cards = `<div class="market-metric-grid">${metrics.map(([key, label, tone]) => `<div><span>${label}</span><strong class="market-${tone}">${e(marketNumber(breadth[key], 0))}<small>只</small></strong></div>`).join('')}</div>${bars}<div class="market-volume-summary"><span>沪深北成交额</span><strong>${e(money(summary.amount))}<small>元</small></strong></div><p class="market-caption">完整股票池统计，与下方筛选和分页独立。来源明确的停牌、未上市不计入平盘；缺报价指其余证券的实际报价缺口。${summary.amount_scope_count !== undefined ? `成交额覆盖已上市 ${e(marketNumber(summary.amount_scope_count, 0))} 只；未上市单列。` : ''}涨跌停及昨日同口径成交额未提供时不推算。</p>`;
  const bins = array(summary.histogram), max = Math.max(1, ...bins.map(bin => finite(bin.count) || 0));
  const histogram = bins.length ? `<div class="market-histogram" role="img" aria-label="全市场涨跌幅区间家数">${bins.map(bin => `<div class="market-bin"><span>${e(marketNumber(bin.count, 0))}</span><i class="market-bg-${marketSign(bin.lower ?? bin.min ?? (String(bin.label).includes('-') || String(bin.label).includes('−') ? -1 : 1))}" style="height:${Math.max(1, Number(bin.count || 0) / max * 150)}px"></i><small>${e(bin.label)}</small></div>`).join('')}</div>` : empty('完整股票池取得后显示涨跌幅分布。');
  return panel('市场广度与成交', cards, section) + panel('涨跌幅分布', histogram, section);
}

function boardHeatmap(section = {}, kind = 'industry') {
  const rows = [...array(section.rows)].sort((a, b) => (finite(b.change_pct) ?? -Infinity) - (finite(a.change_pct) ?? -Infinity));
  return rows.length ? `<div class="market-heatmap">${rows.map(row => `<button type="button" data-market-action="members" data-board-id="${e(row.board_id)}" data-board-name="${e(row.name)}" data-kind="${kind}" class="market-heat-cell market-heat-${marketSign(row.change_pct)}" style="--heat-strength:${Math.min(0.52, 0.09 + Math.abs(finite(row.change_pct) || 0) * 0.045)}" title="${e(row.name)} · ${e(pct(row.change_pct))} · 点击查看成分股"><span>${e(row.name)}</span><strong>${e(pct(row.change_pct))}</strong></button>`).join('')}</div>` : empty('板块数据尚未取得，不切换到其他分类口径。');
}

function movers(section = {}) {
  const summary = object(section.summary);
  const ranking = (title, rows) => `<div><h3>${title}</h3>${array(rows).length ? `<ol class="market-ranking">${array(rows).slice(0, 10).map((row, index) => `<li><span class="market-rank-number">${index + 1}</span><a href="${e(assetHref(row.asset))}"><span>${e(row.name || row.asset)}</span><small>${e(row.asset)}</small></a>${signed(row.change_pct)}</li>`).join('')}</ol>` : empty('完整行情取得后显示排行。')}</div>`;
  return panel('全市场涨跌排行', `<div class="market-movers">${ranking('涨幅前十', summary.gainers)}${ranking('跌幅前十', summary.losers)}</div>`, section);
}

function overview(state) {
  const sections = state.snapshot?.sections || {};
  return `${indicesPanel(sections.indices, state.selectedIndices || [])}<div class="market-grid">${breadthPanels(sections.quotes)}${panel('行业热力图', boardHeatmap(sections.industry, 'industry'), sections.industry)}${panel('概念热力图', boardHeatmap(sections.concept, 'concept'), sections.concept)}</div>${movers(sections.quotes)}`;
}

function fieldValue(row, key) {
  if (key === 'code') return `<a href="${e(assetHref(row.asset))}">${e(row.code || row.asset)}</a><small>${e(row.exchange || '')}</small>`;
  if (key === 'name') {
    const labels = { suspended: '停牌', unlisted: '未上市', delisted: '已退市' };
    return `<a href="${e(assetHref(row.asset))}">${e(row.name || '名称未提供')}</a>${Object.hasOwn(labels, row.trade_status) ? `<small>${e(labels[row.trade_status])}</small>` : ''}`;
  }
  if (key === 'price' && ['last_traded_reference', 'previous_close_reference', 'suspended_reference'].includes(row.price_basis)) return `${e(marketNumber(row.price))}<small>${row.price_basis === 'previous_close_reference' ? '昨收参考' : '停牌参考价'}</small>`;
  if (key.endsWith('_pct')) return e(pct(row[key]));
  if (['amount', 'total_market_cap', 'float_market_cap', 'volume'].includes(key)) return e(money(row[key]));
  return e(marketNumber(row[key]));
}

function quoteTable(state) {
  const filters = { ...DEFAULT_FILTERS, ...state.filters }, result = state.quotes || {}, section = state.snapshot?.sections?.quotes || {};
  const columns = MARKET_COLUMNS.filter(([key]) => ['code', 'name'].includes(key) || (state.columns || DEFAULT_COLUMNS).includes(key));
  const options = (source, selected) => Object.entries(source).map(([key, label]) => `<option value="${e(key)}" ${selected === key ? 'selected' : ''}>${e(label)}</option>`).join('');
  const snapshotID = result.snapshot_id || section.snapshot_id || '';
  const canExport = Boolean(snapshotID) && section.complete !== false;
  const params = marketQuoteParams(filters, snapshotID);
  const exportParams = new URLSearchParams(params); exportParams.delete('offset'); exportParams.delete('limit');
  const total = Number(result.total || 0), page = Math.floor(filters.offset / filters.limit) + 1, pages = Math.max(1, Math.ceil(total / filters.limit));
  const members = filters.board_id ? state.snapshot?.sections?.[`members:${filters.board_id}`] : null;
  const selector = `<form class="market-filters" data-market-search><label>市场<select name="exchange" data-market-filter="exchange">${options(EXCHANGES, filters.exchange)}</select></label><label>板块<select name="board" data-market-filter="board">${options(BOARDS, filters.board)}</select></label><label class="market-search"><span>代码 / 名称</span><input id="market-search" type="search" name="search" data-market-search-draft aria-label="搜索股票代码或名称" value="${e(state.draftSearch ?? filters.search)}" maxlength="80" placeholder="搜索股票代码或名称" autocomplete="off"></label><button type="submit" class="button secondary small">搜索</button><a class="button secondary small" href="/api/research/market/quotes/export?${e(exportParams.toString())}" ${canExport ? 'download' : 'aria-disabled="true" data-market-disabled title="取得完整快照后可导出"'}>导出 CSV</a><details class="market-column-menu" ${state.columnMenuOpen ? 'open' : ''}><summary class="button secondary small" data-market-action="columns">显示列</summary><fieldset><legend class="sr-only">行情列</legend>${MARKET_COLUMNS.filter(([key]) => !['code', 'name'].includes(key)).map(([key, label]) => `<label><input type="checkbox" data-market-column-toggle="${key}" ${(state.columns || DEFAULT_COLUMNS).includes(key) ? 'checked' : ''}>${label}</label>`).join('')}</fieldset></details></form>`;
  const membership = filters.board_id ? `<div class="market-board-filter"><span>成分股：${e(state.boardName || filters.board_id)} · ${e(marketNumber(total, 0))} 只已匹配</span><button type="button" class="text-button" data-market-action="clear-board">清除板块筛选</button></div>${members ? metadata(members) : '<p class="market-caption">板块成员尚未取得；来源成分与全市场证券池的匹配覆盖待确认。</p>'}` : '';
  const table = array(result.items).length ? `<div class="market-table-wrap"><table class="market-table"><thead><tr>${columns.map(([key, label, unit]) => `<th scope="col" class="market-col-${key}" aria-sort="${filters.sort === key ? filters.direction === 'asc' ? 'ascending' : 'descending' : 'none'}"><button type="button" data-market-action="sort" data-sort="${key}">${e(label)}${filters.sort === key ? filters.direction === 'asc' ? ' ↑' : ' ↓' : ''}${unit ? `<small>${e(unit)}</small>` : ''}</button></th>`).join('')}</tr></thead><tbody>${array(result.items).map(row => `<tr>${columns.map(([key]) => `<td data-market-column="${key}" class="market-col-${key} ${['price', 'change', 'change_pct'].includes(key) ? `market-${marketSign(row.change_pct)}` : ''}">${fieldValue(row, key)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>` : empty(state.loading || state.tableLoading ? '正在读取行情表…' : filters.search || filters.board_id ? '当前条件没有匹配股票。' : '尚无股票行情快照，请刷新。');
  const pagination = `<footer class="market-pagination"><span>共 ${e(marketNumber(total, 0))} 只 · ${page} / ${pages} 页${state.tableLoading ? ' · 读取中' : ''}</span><label>每页<select data-market-filter="limit">${[25, 50, 100, 200].map(size => `<option value="${size}" ${filters.limit === size ? 'selected' : ''}>${size}</option>`).join('')}</select></label><button type="button" class="button secondary small" data-market-action="prev" ${filters.offset <= 0 || state.tableLoading ? 'disabled' : ''}>上一页</button><button type="button" class="button secondary small" data-market-action="next" ${filters.offset + filters.limit >= total || state.tableLoading ? 'disabled' : ''}>下一页</button></footer>`;
  return panel('沪深北股票行情', `${selector}${membership}${table}${pagination}`, section, 'market-quotes-panel');
}

function sectorsPage(state) {
  const kind = state.kind || 'industry', period = state.period || 'today', sections = state.snapshot?.sections || {}, boards = sections[kind] || {}, flows = sections[`flows:${kind}:${period}`] || {};
  const sorted = [...array(flows.rows)].sort((a, b) => (finite(b.main_net) ?? -Infinity) - (finite(a.main_net) ?? -Infinity));
  const table = sorted.length ? `<div class="market-table-wrap market-flow-wrap"><table class="market-table market-flow-table"><thead><tr>${['板块', '涨跌幅', '主力净流入（元）', '主力净占比', '超大单（元）', '大单（元）', '中单（元）', '小单（元）'].map(name => `<th>${name}</th>`).join('')}</tr></thead><tbody>${sorted.map(row => `<tr><td><button class="text-button" type="button" data-market-action="members" data-board-id="${e(row.board_id)}" data-board-name="${e(row.name)}">${e(row.name)}</button></td><td>${signed(row.change_pct)}</td><td>${signed(row.main_net, money)}</td><td>${e(pct(row.main_ratio_pct))}</td>${['super_net', 'large_net', 'medium_net', 'small_net'].map(key => `<td>${signed(row[key], money)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>` : empty('尚无该分类与期间的资金数据，可点击刷新。');
  const marketFlow = array(flows.summary?.market_flow?.rows || flows.summary?.market_flow);
  const ownFlowMeta = object(flows.summary?.market_flow);
  const marketFlowMeta = { ...ownFlowMeta, stale: Boolean(ownFlowMeta.stale || flows.stale), error: flows.error || ownFlowMeta.error };
  return `<div class="market-section-toolbar"><div class="market-segmented" aria-label="板块分类">${[['industry', '行业'], ['concept', '概念']].map(([key, label]) => `<button type="button" data-market-action="kind" data-kind="${key}" aria-pressed="${kind === key}">${label}</button>`).join('')}</div><label>资金期间<select data-market-period>${Object.entries(PERIODS).map(([key, label]) => `<option value="${key}" ${period === key ? 'selected' : ''}>${label}</option>`).join('')}</select></label><span class="market-caption">东方财富分类 · 不与 Wind 行业口径混用</span></div>${panel(`${kind === 'industry' ? '行业' : '概念'}涨跌全景`, boardHeatmap(boards, kind), boards)}${panel(`${PERIODS[period]}板块资金流向`, table, flows)}${panel('沪深大盘资金流', marketFlow.length ? `<div class="market-market-flow">${marketFlow.slice(-10).map(row => `<div><span>${e(row.date || row.as_of)}</span>${signed(row.main_net, money)}</div>`).join('')}</div><p class="market-caption">主力净流入 · 日线 · 沪深口径，不包含北交所</p>` : empty('尚未取得沪深大盘资金流。北交所不计入此项，机构／散户资金分时未提供。'), marketFlowMeta)}`;
}

export function renderMarketPage(input = {}, route = {}) {
  const state = { ...input }, view = route.marketView || state.view || 'overview';
  state.view = Object.hasOwn(VIEWS, view) ? view : 'overview';
  const market = state.snapshot?.market_state || {}, known = MARKET_STATES[market.state] || MARKET_STATES.unknown;
  const busy = state.loading || state.refreshing;
  return `<div class="market-page" data-market-page><header class="market-page-heading"><div><p class="market-eyebrow">CHINA EQUITY MARKET</p><h1>全市场概览</h1><p class="market-subtitle">沪 · 深 · 北 A 股 <span class="market-state-pill ${market.state === 'open' ? 'active' : ''}">${e(known)}</span>${market.trade_date ? `<span>${e(market.trade_date)}</span>` : ''}</p></div><div class="market-actions"><span class="market-refresh-label">${state.paused ? '自动刷新已暂停' : market.state === 'unknown' || !market.state ? '交易日历待确认 · 手动刷新' : market.state === 'open' || market.state === 'auction' ? '行情 30秒 · 板块资金 60秒' : '交易时段自动刷新'}</span><button type="button" class="button secondary small" data-market-action="pause" aria-pressed="${Boolean(state.paused)}">${state.paused ? '恢复自动' : '暂停自动'}</button>${busy ? '<button type="button" class="button secondary small" data-market-action="cancel">取消采集</button>' : ''}<button type="button" class="button small" data-market-action="refresh" ${busy ? 'disabled' : ''}>${busy ? '更新中…' : '刷新行情'}</button></div></header><nav class="market-tabs" aria-label="全市场概览页面">${Object.entries(VIEWS).map(([key, label]) => `<a href="${e(marketHref(key))}" ${state.view === key ? 'aria-current="page" class="active"' : ''}>${label}</a>`).join('')}</nav>${state.error ? `<div class="notice warning market-error" role="alert">${e(state.error)}</div>` : ''}${state.notice ? `<p class="market-notice" role="status">${e(state.notice)}</p>` : ''}${state.loading && !state.snapshot ? '<p class="market-loading" role="status">正在读取市场快照…</p>' : ''}<div class="market-page-body" aria-busy="${Boolean(state.loading)}">${state.view === 'quotes' ? quoteTable(state) : state.view === 'sectors' ? sectorsPage(state) : overview(state)}</div><p class="market-footnote">行情按来源实际返回展示；部分覆盖、陈旧与缺失数据分别标识。页面浏览与自动刷新不会创建研究会话。</p></div>`;
}

export function createMarketController({ api, onChange = () => {}, onNavigate = hash => { globalThis.location.hash = hash; }, documentRef = globalThis.document, storage, setTimer = globalThis.setTimeout.bind(globalThis), clearTimer = globalThis.clearTimeout.bind(globalThis) } = {}) {
  if (!api?.request) throw new TypeError('market API request is required');
  const state = { view: 'overview', snapshot: null, quotes: { items: [], total: 0 }, filters: { ...DEFAULT_FILTERS }, draftSearch: '', columns: [...DEFAULT_COLUMNS], kind: 'industry', period: 'today', selectedIndices: [], loading: false, tableLoading: false, refreshing: false, paused: false, error: '', notice: '', boardName: '' };
  const preferenceKey = `rwb:${globalThis.__RWB_USER_ID__ || 'local'}:market-columns-v1`;
  if (storage === undefined) { try { storage = globalThis.localStorage; } catch { safeLog('market_preferences_unavailable', { status: 'failed' }); } }
  try { const saved = JSON.parse(storage?.getItem(preferenceKey) || 'null'); if (Array.isArray(saved)) state.columns = DEFAULT_COLUMNS.filter(key => ['code', 'name'].includes(key) || saved.includes(key)); } catch { safeLog('market_preferences_read_failed', { status: 'failed' }); }
  let generation = 0, tableGeneration = 0, boardSelectionGeneration = 0, boardAbort, active = false, disposed = false, route = {}, abort = new AbortController();
  const timers = new Set(), readers = new Set(), refreshes = new Map();
  const controller = { state, api, document: documentRef };
  const visible = () => active && !disposed && !documentRef?.hidden;
  const trading = () => ['open', 'auction'].includes(state.snapshot?.market_state?.state);
  const changed = () => { if (!disposed) onChange(); };
  function stopTimers() { for (const timer of timers) clearTimer(timer); timers.clear(); }
  function release() {
    for (const id of readers) void api.request(`/market/refresh/${encodeURIComponent(id)}`, { method: 'DELETE' }).catch(() => safeLog('market_reader_release_failed', { status: 'failed', method: 'DELETE' }));
    readers.clear();
  }
  function cancel(leave = true) { generation++; tableGeneration++; boardSelectionGeneration++; boardAbort?.abort(); boardAbort = null; stopTimers(); abort.abort(); abort = new AbortController(); release(); refreshes.clear(); state.loading = false; state.refreshing = false; state.tableLoading = false; if (leave) active = false; }
  function later(fn, ms) { let timer; timer = setTimer(() => { timers.delete(timer); void fn(); }, ms); timers.add(timer); }
  async function delay(ms, signal) {
    if (signal.aborted) throw new DOMException('读取已取消', 'AbortError');
    return new Promise((resolve, reject) => {
      const timer = setTimer(() => { signal.removeEventListener('abort', cancelled); resolve(); }, ms);
      function cancelled() { clearTimer(timer); reject(new DOMException('读取已取消', 'AbortError')); }
      signal.addEventListener('abort', cancelled, { once: true });
    });
  }
  function sectionsForView() { return state.view === 'sectors' ? [state.kind, 'flows', 'calendar'] : state.view === 'quotes' ? ['quotes', 'calendar'] : BASE_SECTIONS; }
  function schedule() {
    stopTimers(); if (!visible() || state.paused || !state.snapshot?.market_state?.state || state.snapshot.market_state.state === 'unknown') return;
    const ticket = generation;
    const clock = async () => {
      if (ticket !== generation || !visible() || state.paused) return;
      const previous = state.snapshot?.market_state?.state;
      try {
        if (!await loadSnapshot(ticket, abort.signal)) return;
        if (previous !== state.snapshot?.market_state?.state) { if (trading()) await refresh(sectionsForView()); schedule(); return; }
      } catch (error) { if (ticket === generation && error.name !== 'AbortError') { state.error = error.message || '市场时段状态读取失败。'; changed(); safeLog('market_clock_read_failed', { status: 'failed', method: 'GET' }); } }
      if (ticket === generation && visible() && !state.paused) later(clock, 60000);
    };
    later(clock, 60000);
    if (!trading()) return;
    const repeat = (chooseSections, ms) => {
      const run = async () => {
        if (ticket !== generation || !visible() || state.paused || !trading()) return;
        await refresh(chooseSections());
        if (ticket === generation && visible() && !state.paused && trading()) later(run, ms);
      };
      later(run, ms);
    };
    repeat(() => ['quotes', 'indices'], 30000);
    repeat(() => state.view === 'sectors' ? [state.kind, 'flows'] : ['industry', 'concept'], 60000);
  }
  async function loadSnapshot(ticket, signal, isCurrent = () => true) {
    const result = await api.request('/market', { signal });
    if (ticket !== generation || !visible() || !isCurrent()) return false;
    state.snapshot = result; changed(); return true;
  }
  async function loadQuotes() {
    if (!visible() || state.view !== 'quotes') return;
    const ticket = generation, tableTicket = ++tableGeneration;
    state.tableLoading = true; changed();
    const snapshotID = state.snapshot?.sections?.quotes?.snapshot_id;
    try {
      const result = await api.request(`/market/quotes?${marketQuoteParams(state.filters, snapshotID)}`, { signal: abort.signal });
      if (ticket !== generation || tableTicket !== tableGeneration || !visible()) return;
      state.quotes = result;
    } catch (error) {
      if (ticket !== generation || tableTicket !== tableGeneration || error.name === 'AbortError') return;
      state.error = error.message || '行情表读取失败。'; safeLog('market_quotes_failed', { status: 'failed', method: 'GET' });
    } finally { if (ticket === generation && tableTicket === tableGeneration) { state.tableLoading = false; changed(); } }
  }
  async function refresh(sections = sectionsForView(), extra = {}, context = {}) {
    if (!visible()) return;
    const key = `${sections.join(',')}:${state.kind}:${state.period}:${extra.board_id || ''}:${context.selection || ''}`;
    if (refreshes.has(key)) return refreshes.get(key);
    const ticket = generation, signal = context.signal ? AbortSignal.any([abort.signal, context.signal]) : abort.signal;
    const isCurrent = () => ticket === generation && visible() && !signal.aborted && (!context.isCurrent || context.isCurrent());
    const work = (async () => {
      state.refreshing = true; state.error = ''; state.notice = ''; changed();
      let id, terminal = false;
      try {
        let result = await api.request('/market/refresh', { method: 'POST', body: { sections, kind: state.kind, period: state.period, ...extra }, signal });
        id = result.request_id;
        if (!isCurrent()) { if (id) void api.request(`/market/refresh/${encodeURIComponent(id)}`, { method: 'DELETE' }).catch(() => safeLog('market_reader_release_failed', { status: 'failed' })); return false; }
        if (!id) throw new Error('刷新任务缺少编号，请核对服务状态。');
        readers.add(id);
        for (let attempt = 0; !['completed', 'failed', 'cancelled'].includes(result.status); attempt++) {
          if (attempt >= 160) throw new Error('市场采集尚未完成，请查看来源状态后重试。');
          await delay(750, signal);
          result = await api.request(`/market/refresh/${encodeURIComponent(id)}`, { signal });
          if (!isCurrent()) return false;
        }
        if (result.status === 'failed') state.error = result.error?.message || (typeof result.error === 'string' ? result.error : '') || '部分市场采集失败，请查看区块来源与缺口。';
        if (result.status === 'cancelled') state.notice = '本次采集已取消。';
        terminal = true;
        if (await loadSnapshot(ticket, signal, isCurrent)) await loadQuotes();
        safeLog('market_refresh_finished', { status: result.status, method: 'POST' });
        return isCurrent() && result.status === 'completed';
      } catch (error) {
        if (!isCurrent() || error.name === 'AbortError') return false;
        state.error = error.message || '市场刷新失败，已保留原快照。'; safeLog('market_refresh_failed', { status: 'failed', method: 'POST' });
      } finally {
        if (id && !terminal && readers.has(id)) void api.request(`/market/refresh/${encodeURIComponent(id)}`, { method: 'DELETE' }).catch(() => safeLog('market_reader_release_failed', { status: 'failed', method: 'DELETE' }));
        if (id) readers.delete(id);
        if (ticket === generation) { refreshes.delete(key); state.refreshing = refreshes.size > 0; changed(); }
      }
    })();
    refreshes.set(key, work); return work;
  }
  async function activate(nextRoute = {}) {
    if (disposed) return;
    cancel(); active = true; route = { ...nextRoute }; const ticket = generation;
    const nextView = route.marketView || route.view || route.params?.get?.('view') || 'overview';
    state.view = Object.hasOwn(VIEWS, nextView) ? nextView : 'overview';
    state.filters.board_id = boardID(route.marketBoardId || route.marketBoard || route.params?.get?.('board_id'));
    state.filters.offset = 0; state.loading = true; state.error = ''; changed();
    try {
      if (!await loadSnapshot(ticket, abort.signal)) return;
      await loadQuotes();
      if (ticket !== generation) return;
      const missing = sectionsForView().some(key => !state.snapshot?.sections?.[key === 'flows' ? `flows:${state.kind}:${state.period}` : key]?.snapshot_id);
      if (missing) await refresh();
      if (ticket === generation && state.filters.board_id && !state.snapshot?.sections?.[`members:${state.filters.board_id}`]?.snapshot_id) await refresh(['members'], { board_id: state.filters.board_id });
    } catch (error) {
      if (ticket !== generation || error.name === 'AbortError') return;
      state.error = error.message || '市场快照读取失败。'; safeLog('market_load_failed', { status: 'failed', method: 'GET' });
    } finally { if (ticket === generation) { state.loading = false; changed(); schedule(); } }
  }
  function setPaused(value) { state.paused = Boolean(value); if (state.paused) { cancel(false); state.notice = '自动刷新已暂停，仍可手动刷新。'; } else { state.notice = ''; schedule(); } changed(); }
  async function openBoard(id, name, kind) {
    if (!boardID(id)) return;
    const ticket = generation, selection = ++boardSelectionGeneration;
    boardAbort?.abort();
    const selectionAbort = new AbortController(); boardAbort = selectionAbort;
    const isCurrent = () => ticket === generation && selection === boardSelectionGeneration && visible() && !selectionAbort.signal.aborted;
    state.boardName = name || id;
    try {
      const ready = await refresh(['members'], { board_id: id, kind: ['industry', 'concept'].includes(kind) ? kind : state.kind }, { signal: selectionAbort.signal, selection, isCurrent });
      if (ready && isCurrent()) onNavigate(marketHref('quotes', id));
    } finally { if (boardAbort === selectionAbort) boardAbort = null; }
  }
  function handleClick(event) {
    const disabled = event.target?.closest?.('[data-market-disabled]'); if (disabled) { event.preventDefault(); return true; }
    const target = event.target?.closest?.('[data-market-action]'); if (!target) return false;
    event.preventDefault(); const data = target.dataset;
    if (data.marketAction === 'refresh') void refresh().then(schedule);
    else if (data.marketAction === 'pause') setPaused(!state.paused);
    else if (data.marketAction === 'columns') { state.columnMenuOpen = !state.columnMenuOpen; changed(); }
    else if (data.marketAction === 'cancel') { cancel(false); state.notice = '本页采集已取消，保留已有快照。'; changed(); schedule(); }
    else if (data.marketAction === 'members') void openBoard(data.boardId, data.boardName, data.kind);
    else if (data.marketAction === 'clear-board') { boardSelectionGeneration++; boardAbort?.abort(); boardAbort = null; state.filters.board_id = ''; state.boardName = ''; onNavigate(marketHref('quotes')); }
    else if (data.marketAction === 'kind' && ['industry', 'concept'].includes(data.kind)) { state.kind = data.kind; changed(); void refresh([state.kind, 'flows']).then(schedule); }
    else if (data.marketAction === 'sort' && DEFAULT_COLUMNS.includes(data.sort)) { state.filters.direction = state.filters.sort === data.sort && state.filters.direction === 'desc' ? 'asc' : 'desc'; state.filters.sort = data.sort; state.filters.offset = 0; void loadQuotes(); }
    else if (['prev', 'next'].includes(data.marketAction)) { state.filters.offset = Math.max(0, state.filters.offset + (data.marketAction === 'next' ? 1 : -1) * state.filters.limit); void loadQuotes(); }
    return true;
  }
  function handleChange(event) {
    const target = event.target, data = target?.dataset || {};
    if (data.marketFilter) {
      const key = data.marketFilter;
      if (key === 'exchange' && Object.hasOwn(EXCHANGES, target.value) || key === 'board' && Object.hasOwn(BOARDS, target.value)) state.filters[key] = target.value;
      else if (key === 'limit' && [25, 50, 100, 200].includes(Number(target.value))) state.filters.limit = Number(target.value);
      else return false;
      state.filters.offset = 0; void loadQuotes(); return true;
    }
    if ('marketPeriod' in data && Object.hasOwn(PERIODS, target.value)) { state.period = target.value; changed(); void refresh(['flows']).then(schedule); return true; }
    if (data.marketColumnToggle && DEFAULT_COLUMNS.includes(data.marketColumnToggle)) {
      state.columns = DEFAULT_COLUMNS.filter(key => ['code', 'name'].includes(key) || key === data.marketColumnToggle ? ['code', 'name'].includes(key) || target.checked : state.columns.includes(key));
      try { storage?.setItem(preferenceKey, JSON.stringify(state.columns)); } catch { safeLog('market_preferences_write_failed', { status: 'failed' }); }
      changed(); return true;
    }
    if (data.marketIndex) {
      const all = array(state.snapshot?.sections?.indices?.rows).map(row => row.asset);
      const current = state.selectedIndices.length ? new Set(state.selectedIndices) : new Set(all);
      if (target.checked) current.add(data.marketIndex); else current.delete(data.marketIndex);
      state.selectedIndices = current.size ? [...current] : ['__none__']; changed(); return true;
    }
    return false;
  }
  function handleSubmit(event) {
    const form = event.target; if (!form?.matches?.('[data-market-search]')) return false;
    event.preventDefault(); state.filters.search = String(form.elements?.namedItem?.('search')?.value ?? form.elements?.search?.value ?? state.draftSearch).trim().slice(0, 80); state.draftSearch = state.filters.search; state.filters.offset = 0; void loadQuotes(); return true;
  }
  function handleInput(event) { const target = event.target; if (!target?.dataset || !('marketSearchDraft' in target.dataset)) return false; state.draftSearch = String(target.value || '').slice(0, 80); return true; }
  function visibilityChanged() { if (documentRef?.hidden) { cancel(false); changed(); } else if (active && !disposed) void activate(route); }
  documentRef?.addEventListener?.('visibilitychange', visibilityChanged);
  function dispose() { cancel(); disposed = true; documentRef?.removeEventListener?.('visibilitychange', visibilityChanged); }
  Object.assign(controller, { activate, cancel, dispose, refresh, loadQuotes, handleClick, handleChange, handleSubmit, handleInput, setPaused });
  return controller;
}
