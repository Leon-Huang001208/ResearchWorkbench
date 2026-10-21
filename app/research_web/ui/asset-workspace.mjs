import { escapeHTML as e } from './markdown.mjs';
import { renderMarketTerminal } from './asset-chart.mjs';
import { assetHref, ASSET_VIEWS, selectAssetObservation } from './asset-navigation.mjs';
import { renderAssetNews } from './asset-news.mjs';
import { safeLog } from './core.mjs';
import { projectAssetObservation } from './asset-projection.mjs';
export { projectAssetObservation } from './asset-projection.mjs';
export { enrichMarketBars, renderMarketTerminal } from './asset-chart.mjs';

const LABELS = { overview: '资产概览', history: '历史行情', financials: '财务指标', activity: '资金流', margin: '融资融券', holders: '股东与机构持仓汇总', research: '研究资料' };
const TYPE_LABELS = { stock: '股票', etf: 'ETF', index: '指数', fund: '基金', theme: '主题' };
const TOPICS = ['概览', '财务', '资金与两融', '股东', '新闻', '公告', '资料'];
const STATE_LABELS = { loading: '加载中', complete: '完整', partial: '部分', empty: '暂无数据', unavailable: '不可用', error: '失败' };
const readFailureState = count => count > 0 ? `部分记录已载入 · 读取未完成 · ${count} 条已载入` : '快照读取失败';
const finite = value => value === null || value === undefined || value === '' || typeof value === 'string' && value.trim() === '' || typeof value === 'boolean' || !Number.isFinite(Number(value)) ? null : Number(value);
const number = (value, digits = 2) => finite(value) === null ? '—' : finite(value).toLocaleString('zh-CN', { maximumFractionDigits: digits });
const display = (value, booleanAsMissing = false) => value === null || value === undefined || value === '' || (booleanAsMissing && typeof value === 'boolean') ? '—' : typeof value === 'number' ? number(value) : typeof value === 'object' ? JSON.stringify(value) : String(value);
const FIELD_LABELS = { asset: '证券代码', date: '日期', report_period: '报告期', revenue: '营业收入', net_profit: '净利润', eps: '每股收益', roe: '净资产收益率', total_assets: '总资产', operating_cost: '营业成本', gross_profit: '毛利润', gross_profit_ttm: '毛利润 TTM', gross_profit_margin: '毛利率', free_cf: '自由现金流', free_cf_per_share: '每股自由现金流', equity: '股东权益', main_force_inflow: '主力净流入', north_bound_shares: '北向持股数量', north_bound_pct: '北向持股比例', margin_balance: '融资余额', margin_buy: '融资买入', margin_repay: '融资偿还', short_balance: '融券余量', short_sell_vol: '融券卖出数量', short_repay_vol: '融券偿还数量', holder_count: '股东户数', average_holding: '户均持股', average_holding_pct: '户均持股比例', top10_pct: '前十大持股比例汇总', top10_quantity: '前十大持股数量汇总', institutional_holding: '机构持股数量', institutional_pct: '机构持股比例' };
function fieldUnit(meta, key) {
  const fields = meta?.fields;
  const field = Array.isArray(fields) ? fields.find(item => item.name === key || item.field === key) : fields?.[key];
  return [field?.unit, field?.currency].filter(Boolean).join(' · ');
}
function previewTable(rows = [], meta = {}) {
  if (!rows.length) return '<p class="muted small">这个区块没有可显示的真实记录。</p>';
  const columns = [...new Set(rows.flatMap(row => Object.keys(row)))];
  return `<div class="asset-table-wrap"><table class="asset-table"><thead><tr>${columns.map(key => `<th>${e(FIELD_LABELS[key] || key)}${fieldUnit(meta, key) ? `<small>${e(fieldUnit(meta, key))}</small>` : ''}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${columns.map(key => `<td>${e(display(row[key]))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}
function financialTable(rows, meta) {
  if (!rows.length) return previewTable(rows, meta);
  const periods = rows.map(row => row.report_period || row['报告期'] || row['截止日期'] || row['报告日期'] || row.date || '报告期未提供');
  const fields = [...new Set(rows.flatMap(row => Object.keys(row)))].filter(key => !['asset', 'code', 'report_period', '报告期', '截止日期', '报告日期', 'date'].includes(key));
  return `<p class="muted small">财务摘要指标；报告期、单位和币种按来源返回显示，不代表完整三大报表。</p><div class="asset-table-wrap"><table class="asset-table asset-financial-table"><thead><tr><th>指标 / 单位</th>${periods.map(period => `<th>${e(period)}</th>`).join('')}</tr></thead><tbody>${fields.map(key => `<tr><th>${e(FIELD_LABELS[key] || key)}<small>${e(fieldUnit(meta, key) || '单位未提供')}</small></th>${rows.map(row => `<td>${e(display(row[key], true))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}
function blockCard(name, blocks, rows, errors, busy) {
  const block = blocks[name] || { status: 'unavailable' }; const meta = block.dataset;
  const readFailed = block.failure_code === 'snapshot_read_failed'; const loadedCount = rows[name]?.length || 0;
  const retained = !readFailed && loadedCount > 0 && Boolean(meta?.dataset_id);
  return `<article class="asset-block ${e(block.status)}"><header><h2>${e(LABELS[name] || name)}</h2><span class="badge">${e(readFailed ? readFailureState(loadedCount) : STATE_LABELS[block.status] || block.status)}</span></header>${meta ? `<p class="muted small">${e(meta.provider || meta.source || '未知来源')} · 截止 ${e(meta.as_of || meta.actual_range?.end_date || '来源未提供')}</p>` : ''}${block.failure_code || errors[name] ? `<p class="notice warning" role="status">${e(errors[name] || block.failure_code)}${retained ? ' · 下方保留上次快照，不表示刷新成功。' : ''}</p>` : ''}${meta?.limitations?.length ? `<p class="muted small">${e(meta.limitations.join('；'))}</p>` : ''}${block.status === 'loading' ? '<p role="status">正在查询这个区块…</p>' : ''}${rows[name]?.length ? name === 'financials' ? financialTable(rows[name], meta) : previewTable(rows[name], meta) : `<p class="muted small">${block.status === 'empty' ? '来源返回了空结果。' : blocks[name] ? '没有可显示的快照。' : '当前观察未采集本区块，可更新资产数据后查看。'}</p>`}</article>`;
}
function personalPanel({ observation, watchlists = [], notes = [], alerts = [], notifications = [] }) {
  const asset = observation?.asset || '';
  const selectedNotes = notes.filter(item => item.asset === asset);
  const selectedAlerts = alerts.filter(item => item.asset === asset);
  return `<aside class="asset-personal"><section><div class="section-heading"><h2>自选与观察</h2><span class="muted small">本地保存</span></div>${watchlists.length ? `<form data-watchlist-item><input type="hidden" name="asset" value="${e(asset)}"><label>加入列表<select name="watchlist_id">${watchlists.map(item => `<option value="${e(item.id)}">${e(item.name)}</option>`).join('')}</select></label><button class="button small" ${asset ? '' : 'disabled'}>加入自选</button></form>` : '<p class="muted small">尚无自选列表。</p>'}<form data-asset-note><label>观察笔记<textarea name="text" maxlength="10000" required placeholder="记录判断、待验证事项和后续动作"></textarea></label><input type="hidden" name="asset" value="${e(asset)}"><button class="button small" ${asset ? '' : 'disabled'}>保存笔记</button></form>${selectedNotes.map(item => `<p class="personal-entry">${e(item.text)}</p>`).join('')}</section><section><div class="section-heading"><h2>提醒规则</h2><span class="muted small">快照到达时评估</span></div><form data-asset-alert><input type="hidden" name="asset" value="${e(asset)}"><div class="mini-form"><select name="field"><option value="price">价格</option><option value="change_pct">涨跌幅</option><option value="volume">成交量</option></select><select name="operator"><option value="gte">≥</option><option value="lte">≤</option><option value="gt">＞</option><option value="lt">＜</option></select><input name="threshold" type="number" step="any" required placeholder="阈值"></div><button class="button small" ${asset ? '' : 'disabled'}>添加提醒</button></form>${selectedAlerts.map(item => `<p class="personal-entry"><span class="tiny-dot ${item.enabled ? 'active' : ''}"></span>${e(item.field)} ${e(item.operator)} ${e(item.threshold)} · ${item.condition_active ? '已触发' : '监控中'}</p>`).join('') || '<p class="muted small">当前资产没有提醒。</p>'}${notifications.filter(item => item.asset === asset).slice(0, 3).map(item => `<p class="notice warning">已触发：${e(item.field)} = ${e(item.value)}</p>`).join('')}</section></aside>`;
}


function assetList({ observations = [], watchlists = [] }, route) {
  const seen = new Set();
  const items = [...watchlists.flatMap(item => item.items || []), ...observations].filter(item => { const key = `${item.asset_type}:${item.asset}`; if (seen.has(key)) return false; seen.add(key); return true; });
  return `<details class="asset-list-drawer" ${globalThis.matchMedia?.('(min-width:1440px)').matches ? 'open' : ''}><summary>自选与最近观察</summary><aside class="asset-watch-rail"><form data-asset-list-filter><label>筛选资产<input name="query" data-asset-list-query type="search" placeholder="输入代码筛选" autocomplete="off"></label></form><form data-asset-watchlist-create><label>新建自选列表<input name="name" required maxlength="80" placeholder="列表名称"></label><button class="button small">创建</button></form><nav aria-label="资产列表">${items.map(item => `<a class="asset-list-row ${route.asset === item.asset ? 'active' : ''}" data-asset-list-code="${e(item.asset)}" href="${e(assetHref(item.asset, item.asset_type || 'stock', route.assetView))}"><strong>${e(item.name || item.asset)}</strong><span>${e(item.asset)} · ${e(TYPE_LABELS[item.asset_type] || '股票')}</span></a>`).join('') || '<p class="muted small">输入代码选择资产，更新后可加入自选。</p>'}</nav></aside></details>`;
}

const SECTIONS = ['overview', 'history', 'valuation', 'financials', 'activity', 'margin', 'holders', 'research'];
const SOURCE_OPTIONS = [['auto', '自动选择'], ['tinysoft', '天软'], ['wind', 'Wind'], ['akshare', 'AKShare']];
const SECTION_LABELS = { ...LABELS, valuation: '估值' };
function shanghaiDate(date = new Date()) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).format(date);
}
function shiftDate(value, days) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return null;
  const date = new Date(`${value}T00:00:00+08:00`);
  if (!Number.isFinite(date.getTime())) return null;
  date.setUTCDate(date.getUTCDate() + days); return shanghaiDate(date);
}
function defaultDates() { const end = shanghaiDate(); return { start: shiftDate(end, -365), end }; }
function options(items, value) { return items.map(([id, label]) => `<option value="${e(id)}" ${value === id ? 'selected' : ''}>${e(label)}</option>`).join(''); }
function sourceDefaults(parameters, observation) {
  const saved = parameters.section_sources || {};
  // A source-only observation keeps its explicit scope until the user changes it.
  const legacy = !Object.keys(saved).length && observation && (parameters.source || observation.source);
  return Object.fromEntries(SECTIONS.map(name => [name, saved[name] || (legacy ? parameters.source || observation.source : ['overview', 'history'].includes(name) ? 'tinysoft' : name === 'valuation' ? 'wind' : 'auto')]));
}
export function readAssetObservation(form) {
  const data = new FormData(form); const type = String(data.get('asset_type') || 'stock'); const scoped = data.get('scope_mode') === 'section';
  const dates = defaultDates(); const start = String(data.get('start_date') || '') || (scoped ? dates.start : null); const end = String(data.get('end_date') || '') || (scoped ? dates.end : null);
  const sections = SECTIONS.filter(name => type === 'stock' || !['valuation', 'margin', 'holders'].includes(name));
  const request = { asset: String(data.get('asset') || '').trim().toUpperCase(), asset_type: type, source: scoped ? 'auto' : String(data.get('source') || 'auto'), start_date: start, end_date: end, frequency: String(data.get('frequency') || 'daily'), adjustment: String(data.get('adjustment') || (scoped ? 'none' : 'qfq')), sections };
  if (scoped) {
    request.section_sources = Object.fromEntries(sections.map(name => [name, String(data.get(`section_source_${name}`) || (['overview', 'history'].includes(name) ? 'tinysoft' : name === 'valuation' ? 'wind' : 'auto'))]));
    request.section_ranges = Object.fromEntries(['history', 'activity', ...(type === 'stock' ? ['margin'] : [])].map(name => [name, { start_date: String(data.get(`${name}_start_date`) || '') || (name === 'history' ? start : shiftDate(end, -59)), end_date: String(data.get(`${name}_end_date`) || '') || end }]));
  }
  return request;
}
function queryControls(selected, observation, busy) {
  const p = observation?.request_parameters || {}; const defaults = defaultDates(); const start = p.start_date || defaults.start; const end = p.end_date || defaults.end; const legacyRange = observation && !Object.keys(p.section_ranges || {}).length; const sources = sourceDefaults(p, observation);
  return `<details class="asset-query-controls"><summary>更新资产数据 · 来源与区间</summary><form class="asset-search" data-asset-observation><input type="hidden" name="scope_mode" value="section"><input type="hidden" name="source" value="auto"><label>证券代码<input name="asset" value="${e(selected.asset)}" placeholder="例如 600519.SH" pattern="[A-Za-z0-9._\\-]+" required></label><label>类型<select name="asset_type">${options(Object.entries(TYPE_LABELS), selected.assetType)}</select></label><label>起始日<input type="date" name="start_date" value="${e(start)}" required></label><label>结束日<input type="date" name="end_date" value="${e(end)}" required></label><label>周期<select name="frequency">${options([['daily', '日线'], ['weekly', '周线'], ['monthly', '月线']], p.frequency || 'daily')}</select></label><label>复权<select name="adjustment">${options([['none', '不复权'], ['qfq', '前复权'], ['hfq', '后复权']], p.adjustment || (observation ? 'qfq' : 'none'))}</select></label>${SECTIONS.filter(name => selected.assetType === 'stock' || !['valuation', 'margin', 'holders'].includes(name)).map(name => `<label>${e(SECTION_LABELS[name])}来源<select name="section_source_${name}">${options(SOURCE_OPTIONS, sources[name])}</select></label>`).join('')}<fieldset class="asset-section-ranges"><legend>各区块日期范围</legend>${['history', 'activity', ...(selected.assetType === 'stock' ? ['margin'] : [])].map(name => { const range = p.section_ranges?.[name] || {}; return `<div><span>${e(SECTION_LABELS[name])}</span><label>起始日<input type="date" name="${name}_start_date" value="${e(range.start_date || (name === 'history' || legacyRange ? start : shiftDate(end, -59)))}" required></label><label>结束日<input type="date" name="${name}_end_date" value="${e(range.end_date || end)}" required></label></div>`; }).join('')}</fieldset><button class="button primary" ${busy ? 'disabled' : ''}>${busy ? '正在更新…' : '更新资产数据'}</button></form><p class="muted small">新观察默认近一年日线、不复权；行情默认天软，估值默认 Wind。Wind 资金与两融限定最近 60 个日历日；历史、资金与两融可分别保存日期范围。旧观察保留已有来源、日期、周期和复权口径。新闻与公告独立查询。</p></details>`;
}
function cellText(cell, suffix = '') {
  const value = cell?.value; if (value === null || value === undefined || value === '') return '—';
  const unit = ({ share: '股', percent: '%', ratio: '倍', currency: '', currency_per_share: '/股' })[cell?.unit] ?? cell?.unit;
  return `${display(value)}${suffix && suffix !== unit ? suffix : ''}${unit ? `${unit === suffix ? '' : ' '}${unit}` : ''}${cell?.currency ? ` ${cell.currency}` : ''}`;
}
function metric(label, cell, id = '', suffix = '') { return `<div class="metric-item"><dt>${e(label)}</dt><dd${id ? ` id="${e(id)}"` : ''}>${e(cellText(cell, suffix))}</dd></div>`; }
function shanghaiTime(value) {
  if (!value) return '未提供';
  const date = new Date(value);
  if (!Number.isFinite(date.getTime()) || !/[T ]\d{2}:\d{2}/.test(String(value)) || !/(Z|[+-]\d{2}:?\d{2})$/i.test(String(value))) return `${display(value)}（时区未提供）`;
  return `${new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }).format(date)}（北京时间）`;
}
function identityControls(selected, observation, busy) {
  return `<div class="asset-summary-tools"><details class="asset-identity-switch"><summary>选择资产</summary><form class="asset-identity-select" data-asset-select><label>资产代码<input name="asset" value="${e(selected.asset)}" placeholder="例如 603986.SH" pattern="[A-Za-z0-9._\\-]+" required></label><label>资产类型<select name="asset_type">${options(Object.entries(TYPE_LABELS), selected.assetType)}</select></label><button class="button">选择资产</button><button class="button" type="button" data-refresh>刷新本地状态</button></form></details>${queryControls(selected, observation, busy)}</div>`;
}
function coverage(name, p, errors = {}, busy = false) {
  const b = p.blocks[name] || {}; const m = b.dataset || {}; const range = m.actual_range || b.requested_range || {}; const dates = [range.start_date, range.end_date].filter(Boolean).join(' — ');
  const row = p.coverageRows?.find(item => item.id === name); const readFailed = b.failure_code === 'snapshot_read_failed';
  return `<div class="asset-card-coverage"><span>${e(m.provider || m.source || b.requested_source || '来源未取得')} · ${e(readFailed ? readFailureState(row?.loadedRowCount || 0) : STATE_LABELS[b.status] || '未取得')} · ${e(m.as_of || dates || '时间未提供')}</span></div>${errors[name] || b.failure_code ? `<p class="notice warning" role="status">${e(errors[name] || b.failure_code)}${row?.retainedSnapshot ? ' · 下方保留上次快照，不表示刷新成功。' : ''}</p>` : ''}${m.limitations?.length ? `<p class="muted small">${e(m.limitations.join('；'))}</p>` : ''}`;
}
function basicCard(current, p, selected, observation, busy) {
  const b = p.basic; const v = p.valuation || {}; const ids = current.dataset_ids || []; const direction = finite(b.changePct.value) === null ? 'muted' : finite(b.changePct.value) >= 0 ? 'positive' : 'negative'; const meta = b.price.provider ? `${b.quoteKind} · ${b.price.provider}` : '来源未取得';
  const valuationDates = [...new Set(Object.values(v).map(cell => cell?.date).filter(Boolean))];
  const reportPeriods = [...new Set(Object.values(v).map(cell => cell?.reportPeriod).filter(Boolean))];
  const shares = v.totalShares?.unitVerified === false ? { ...v.totalShares, unit: null, currency: null } : v.totalShares;
  return `<section class="asset-basic-card asset-identity" data-asset-anchor="overview"><div class="asset-basic-header"><div class="asset-summary-name"><h1 id="asset-name">${e(b.name.value || current.asset || '资产观察')}</h1><p>${e(TYPE_LABELS[current.asset_type] || '股票')}</p></div><div class="asset-basic-price ${direction}"><strong id="asset-price">${e(cellText(b.price))}</strong><div class="asset-quote-change"><span id="asset-code-display">${e(current.asset || '选择证券代码开始')}</span><span id="asset-change">${e(cellText(b.change))}</span><span id="asset-change-pct">${b.changePct.derived ? '较昨收计算 ' : ''}${e(cellText(b.changePct, b.changePct.value === null ? '' : '%'))}</span></div></div><div class="button-row asset-summary-actions">${[['fingpt', '交给 FinGPT'], ['claw', '交给 Claw']].map(([mode, label]) => `<button class="button ${mode === 'claw' ? 'primary' : ''}" data-workbench-handoff="${mode}" data-source-session="${e(current.session_id || '')}" data-dataset-ids="${e(JSON.stringify(ids))}" ${current.session_id && ids.length ? '' : 'disabled'}>${label}</button>`).join('')}</div></div><p class="asset-quote-meta muted small">${e(meta)} · 数据日 ${e(b.price.date || '未提供')} · 读取于 ${e(shanghaiTime(p.blocks[b.quoteKind === '历史收盘' ? 'history' : 'overview'].dataset.retrieved_at))}</p>${identityControls(selected, observation, busy)}<div class="asset-summary-metrics"><section class="asset-trading-group"><h2>交易数据</h2><dl class="asset-metrics-grid">${metric('开盘', b.open)}${metric('最高', b.high)}${metric('最低', b.low)}${metric('换手率', b.turnover, 'asset-turnover')}${metric('成交量', b.volume, 'asset-volume')}${metric('成交额', b.amount, 'asset-amount')}${metric(`${b.rangeLabel}最高`, b.rangeHigh, 'asset-high-52w')}${metric(`${b.rangeLabel}最低`, b.rangeLow, 'asset-low-52w')}</dl><p class="asset-group-note">交易数据日 ${e(b.tradingDate || '未提供')}；高低覆盖 ${e(b.rangeStart || '未提供')} 至 ${e(b.rangeEnd || '未提供')}。未取得的数据以 — 表示，不跨时点补齐。</p></section><section class="asset-valuation-group"><h2>估值与股本</h2><dl class="asset-valuation-grid">${metric('PE-TTM', v.peTTM)}${metric('PB', v.pb)}${metric('PS-TTM', v.psTTM)}${metric('总股本', shares, 'asset-total-shares')}${metric('市值', v.marketCap || b.marketCap, 'asset-market-cap')}</dl><p class="asset-group-note">估值数据日 ${e(valuationDates.join('、') || '未提供')}；报告期 ${e(reportPeriods.join('、') || '未提供')}。未取得的数据以 — 表示。${e(v.totalShares?.unitNote || '单位与币种按来源显示；未提供时不猜测。')}${v.totalShares?.unitVerified === false && v.totalShares?.unit ? ` 来源声明单位 ${e(v.totalShares.unit)}，未经核实，不作换算。` : ''}</p></section></div></section>`;
}
function rangeText(range) { return range ? [range.start_date || '起始未提供', range.end_date || '结束未提供'].join(' — ') : '未提供'; }
function sourceState(row) {
  if (row.failureCode === 'snapshot_read_failed') return readFailureState(row.loadedRowCount);
  const label = STATE_LABELS[row.status] || row.status || '不可用';
  if (row.retainedSnapshot) return `${label} · 保留旧快照`;
  if (row.status === 'loading') return `${label} · ${row.hasSnapshot ? '显示上次快照' : '尚无快照'}`;
  if (row.hasSnapshot) return `${label} · ${row.loadedRowCount} 条已载入`;
  return `${label} · ${row.datasetId ? '快照尚未载入' : '尚无快照'}`;
}
function sourceSummary(current, p, errors, busy) {
  const rows = p.coverageRows || [];
  const count = rows.filter(row => row.hasSnapshot).length;
  return `<details class="asset-source-summary"><summary>来源与口径 · ${count}/8 区块有快照 · 查看详情</summary><div class="asset-source-table-wrap"><table class="asset-source-table"><thead><tr><th>区块与状态</th><th>请求与实际来源</th><th>数据时间</th><th>区间与查询口径</th><th>字段、单位与口径</th><th>限制与操作</th></tr></thead><tbody>${rows.map(row => `<tr data-asset-source-row="${e(row.id)}"><th scope="row">${e(row.label)}<span class="asset-source-state ${e(row.status)}" role="status">${e(sourceState(row))}</span></th><td><span>请求来源 ${e(row.requestedSource || '未提供')}</span><span>实际来源 ${e(row.provider || '未取得')}</span></td><td><span>数据日 ${e(row.dataDate || '未提供')}</span><span>截至 ${e(row.asOf || '未提供')}</span><span>读取于 ${e(shanghaiTime(row.retrievedAt))}</span><span>报告期 ${e(row.reportPeriods.join('、') || '未提供')}</span></td><td><span>请求区间 ${e(rangeText(row.requestedRange))}</span><span>实际区间 ${e(rangeText(row.actualRange))}</span><span>已载入区间 ${e(rangeText(row.loadedRange))}</span><span>请求周期 ${e(row.requestedFrequency || '未提供')} · 复权 ${e(row.requestedAdjustment || '未提供')}</span></td><td>${row.fields.length ? `<ul>${row.fields.map(field => `<li>${e(field.name || field.field || '未命名字段')}${[field.unit, field.currency, field.basis, field.period].filter(value => value !== null && value !== undefined && value !== '').map(value => ` · ${e(display(value))}`).join('')}</li>`).join('')}</ul>` : '字段单位与口径未提供'}</td><td>${errors[row.id] || row.failureCode ? `<p class="notice warning" role="status">${e(errors[row.id] || row.failureCode)}${row.retainedSnapshot ? ' · 下方保留上次快照，不表示刷新成功。' : ''}</p>` : ''}${row.limitations.length ? `<p>${e(row.limitations.join('；'))}</p>` : '<p>来源未声明额外限制</p>'}${current.blocks?.[row.id] ? `<button class="button small" data-asset-block-refresh="${e(row.id)}" ${busy || row.status === 'loading' ? 'disabled' : ''}>重新取数</button>` : ''}</td></tr>`).join('')}</tbody></table></div><p class="asset-source-footnote">计数只包含已载入真实记录且有数据集身份的快照；加载中或失败时显示的旧快照不表示本次更新成功。报告期、截至时间和读取时间分别保留。新闻与公告独立查询，不计入这 8 个区块。</p></details>`;
}
function capitalCard(p, rows, errors, busy) {
  const f = p.capitalFlow;
  return `<article class="asset-block capital-flow-card${f.pie ? '' : ' is-missing-pie'}" data-asset-anchor="capital"><h2>资金流向</h2><div class="capital-flow-layout"><div class="capital-flow-pie"><canvas id="chart-capital-flow" data-capital-flow-canvas aria-label="资金流向构成图" role="img" ${f.pie ? '' : 'hidden'}></canvas><p class="muted small" data-capital-flow-state>${f.pie ? '已取得同日同单位互斥资金构成。' : '资金构成图未取得：净额不能作为流入流出或饼图构成。'}</p></div><dl id="capital-flow-details" class="capital-flow-details">${[['主力流入', 'mainInflow'], ['主力流出', 'mainOutflow'], ['主力净流入', 'mainNet'], ['超大单净流入', 'superNet'], ['大单净流入', 'largeNet'], ['中单净流入', 'mediumNet'], ['小单净流入', 'smallNet'], ['北向资金', 'northbound']].map(([label, key]) => metric(label, f[key])).join('')}</dl></div>${f.northboundShares.value !== null ? `<p class="muted small">北向持股数量 ${e(cellText(f.northboundShares))}，持股数量不是现金流。</p>` : ''}${coverage('activity', p, errors, busy)}${rows.activity?.length ? `<details><summary>完整已返回资金记录</summary>${previewTable(rows.activity, p.blocks.activity.dataset)}</details>` : ''}</article>`;
}
function originalPanels(p, rows, errors, busy) {
  const f = p.financial; const sh = p.shareholders; const events = p.events.length ? p.events : [{ summary: {}, type: {}, time: {} }];
  return `<div class="asset-five-panels"><article class="asset-block panel-card" id="financial-panel" data-asset-anchor="financials"><h2>财务</h2><dl class="panel-grid">${metric('PE-TTM', f.peTTM, 'fin-pe')}${metric('PB-MRQ', f.pbMRQ, 'fin-pb')}${metric('ROE', f.roe, 'fin-roe')}${metric('营收', f.revenue, 'fin-revenue')}${metric('净利润', f.netProfit, 'fin-net-profit')}${metric('毛利率', f.grossMargin, 'fin-gross-margin')}</dl><p class="muted small">报告期 ${e(f.revenue.reportPeriod || f.roe.reportPeriod || '未提供')}；单位与币种按来源显示，未提供时不猜测。动态 PE 与未注明 MRQ 的 PB 不填入以上指标。</p>${coverage('valuation', p, errors, busy)}${coverage('financials', p, errors, busy)}${rows.financials?.length ? `<details><summary>完整已返回财务记录</summary>${financialTable(rows.financials, p.blocks.financials.dataset)}</details>` : ''}</article><article class="asset-block panel-card" id="shareholder-panel" data-asset-anchor="holders"><h2>前十大股东</h2><div class="asset-table-wrap"><table class="asset-table"><thead><tr><th>股东名称</th><th>持股比例</th><th>变动比例</th><th>国资属性</th></tr></thead><tbody>${sh.map(item => `<tr><td>${e(cellText(item.name))}</td><td>${e(cellText(item.ratio))}</td><td>${e(cellText(item.change))}</td><td>${item.stateOwned.value === true ? '是' : item.stateOwned.value === false ? '否' : e(cellText(item.stateOwned))}</td></tr>`).join('')}</tbody></table></div>${!p.shareholders.length ? '<p class="muted small">股东名单未取得；汇总比例不代表真实股东姓名与明细。</p>' : ''}${coverage('shareholders', p, errors, busy)}</article><article class="asset-block panel-card" id="industry-panel"><h2>行业</h2><dl class="panel-grid">${metric('申万一级', p.industry.sw1)}${metric('申万二级', p.industry.sw2)}${metric('行业PE', p.industry.pe)}${metric('行业PB', p.industry.pb)}</dl>${coverage('industry', p)}</article><article class="asset-block panel-card" id="events-panel"><h2>相关事件</h2><div class="event-list-panel">${events.map(item => `<dl class="asset-event-row">${metric('事件摘要', item.summary)}${metric('事件类型', item.type)}${metric('事件时间', item.time)}</dl>`).join('')}</div>${coverage('events', p)}</article><article class="asset-block panel-card" id="macro-panel"><h2>宏观</h2><table class="asset-table"><thead><tr><th>因子</th><th>方向</th><th>强度</th></tr></thead><tbody>${p.macro.map(item => `<tr><th>${e(item.label)}</th><td>${e(({ positive: '↑ 正向', negative: '↓ 负向', neutral: '中性' })[item.direction.value] || cellText(item.direction))}</td><td>${e(cellText(item.strength))}</td></tr>`).join('')}</tbody></table>${coverage('macro', p)}</article></div>`;
}

function capitalFlowTheme(canvas) {
  const fallback = { text: '#242424', surface: '#fafaf9', line: '#e8e8e5' };
  if (canvas?.nodeType !== 1 || typeof globalThis.getComputedStyle !== 'function') return fallback;
  try {
    const style = globalThis.getComputedStyle(canvas);
    return Object.fromEntries(Object.entries(fallback).map(([key, value]) => [key, style.getPropertyValue(`--${key}`).trim() || value]));
  } catch (error) {
    safeLog('asset_capital_flow_theme_read_failed', { status: 'error' });
    return fallback;
  }
}
/** Mount only genuine complete partitions; UI details always retain signed net flows. */
export function mountCapitalFlow(root, projection) {
  let chart = null; let disposed = false;
  const update = next => {
    if (disposed) return;
    if (chart) { try { chart.destroy(); } catch (error) { safeLog('asset_capital_flow_dispose_failed', { status: 'error' }); } chart = null; }
    const canvas = root?.querySelector?.('[data-capital-flow-canvas]'); const state = root?.querySelector?.('[data-capital-flow-state]'); const pie = next?.capitalFlow?.pie;
    if (!canvas) return;
    canvas.hidden = !pie;
    if (!pie) { if (state) state.textContent = '资金构成图未取得：净额不能作为流入流出或饼图构成。'; return; }
    const Chart = globalThis.window?.Chart;
    if (!Chart) { canvas.hidden = true; if (state) state.textContent = '本地资金图表组件未就绪；真实资金数值保留。'; safeLog('asset_capital_flow_chart_unavailable', { status: 'unavailable' }); return; }
    try { const theme = capitalFlowTheme(canvas); chart = new Chart(canvas, { type: 'pie', data: { labels: pie.items.map(item => item.label), datasets: [{ data: pie.items.map(item => item.value), backgroundColor: ['#ca5c55', '#d99459', '#c7b76b', '#6c9b8c', '#708fae'] }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { color: theme.text } }, tooltip: { backgroundColor: theme.surface, titleColor: theme.text, bodyColor: theme.text, borderColor: theme.line, borderWidth: 1 } } } }); if (state) state.textContent = `${pie.date} · ${pie.unit} · 同日同单位互斥构成`; }
    catch (error) { canvas.hidden = true; if (state) state.textContent = '资金构成图显示失败，真实资金数值保留。'; safeLog('asset_capital_flow_mount_failed', { status: 'error' }); }
  };
  update(projection);
  return { update, dispose() { update(null); disposed = true; } };
}

export function renderAssetWorkspace({ observation = null, rows = {}, observations = [], watchlists = [], notes = [], alerts = [], notifications = [], busy = false, route = {}, news = {}, chart = {}, errors = {} } = {}) {
  if (observation && route.asset && !selectAssetObservation([observation], route)) { observation = null; rows = {}; }
  const selected = { asset: route.asset || observation?.asset || '', assetType: route.assetType || observation?.asset_type || 'stock', assetView: route.assetView || 'overview' };
  const current = observation || { asset: selected.asset, asset_type: selected.assetType, blocks: {} }; const p = projectAssetObservation(rows, current); const view = selected.assetView;
  const newsView = view === 'announcements' ? 'announcements' : 'news'; const matchingNews = news.asset === selected.asset && news.assetType === selected.assetType && news.view === newsView;
  const metadata = { ...p.blocks.history.dataset, frequency: current.request_parameters?.frequency || 'daily', adjustment: current.request_parameters?.adjustment || 'none', asset: selected.asset, name: p.basic.name.value || selected.asset, currentQuote: p.basic };
  return `<section class="asset-observation-page" data-asset-identity="${e(`${selected.assetType}:${selected.asset}`)}" data-asset-view="${e(view)}" data-observation-id="${e(observation?.id || '')}">${assetList({ observations, watchlists }, selected)}<div class="asset-observation-main">${Object.entries(errors).filter(([key]) => ['observations', 'watchlists', 'notes', 'alerts', 'notifications'].includes(key)).map(([, error]) => `<p class="notice danger" role="alert">${e(error)}</p>`).join('')}${basicCard(current, p, selected, observation, busy)}<section class="asset-market-full"><div data-asset-chart-slot>${renderMarketTerminal(rows.history || [], chart, metadata)}</div></section>${sourceSummary(current, p, errors, busy)}<nav class="asset-topic-tabs" aria-label="资产研究专题">${ASSET_VIEWS.map((id, index) => `<a href="${e(assetHref(selected.asset, selected.assetType, id))}" ${view === id ? 'aria-current="page" class="active"' : ''}>${TOPICS[index]}</a>`).join('')}</nav>${capitalCard(p, rows, errors, busy)}${originalPanels(p, rows, errors, busy)}<section class="asset-secondary"><details class="asset-coverage-limitations"><summary>当前覆盖限制</summary><p class="muted small">财务指标与原始记录不代表完整三大报表；股东名单、行业、事件与宏观敏感性没有独立来源时保持未取得，股东汇总不填造名单。资金净额不代表流入流出构成；普通筹码为行情估算，不代表真实持仓。</p></details><article class="asset-block" data-asset-anchor="news"><span data-asset-anchor="announcements"></span><div class="section-heading"><h2>新闻与公告</h2><div class="button-row"><a class="button small" href="${e(assetHref(selected.asset, selected.assetType, 'news'))}">新闻</a><a class="button small" href="${e(assetHref(selected.asset, selected.assetType, 'announcements'))}">公告</a></div></div><div data-asset-news-slot>${renderAssetNews(matchingNews ? news : { asset: selected.asset, view: newsView, status: 'idle' })}</div></article><details class="asset-personal-details" data-asset-personal><summary>个人研究 · 自选、笔记与提醒</summary>${personalPanel({ observation: current, watchlists, notes, alerts, notifications })}<p class="muted small">交接仅包含已冻结的数据快照；阅读的新闻和公告不会自动加入研究证据。提醒只在新行情快照到达时评估。</p></details><section class="asset-supplemental">${blockCard('margin', current.blocks || {}, rows, errors, busy)}${blockCard('holders', current.blocks || {}, rows, errors, busy)}<div data-asset-anchor="materials">${blockCard('research', current.blocks || {}, rows, errors, busy)}</div></section></section></div></section>`;
}
