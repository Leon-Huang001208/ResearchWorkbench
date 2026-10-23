// Pure projection of frozen DataHub snapshots. No provider calls or invented dates.
const missing = value => value === null || value === undefined || value === '';
const numeric = value => !missing(value) && (typeof value === 'number' || typeof value === 'string' && value.trim() !== '') && Number.isFinite(Number(value)) ? Number(value) : null;
const dateOf = row => row?.date || row?.['时间'] || row?.as_of || null;
const reportPeriodOf = row => row?.report_period || row?.['报告期'] || row?.['截止日期'] || row?.['报告日期'] || null;
const sourceOf = meta => meta?.provider || meta?.source || null;
function fieldMeta(meta, key) {
  if (missing(key)) return {};
  return Array.isArray(meta?.fields) ? meta.fields.find(item => item.name === key || item.field === key) || {} : meta?.fields?.[key] || {};
}
const nonCurrencyKeys = new Set(['pe', 'pe_ttm', 'pb', 'pb_mrq', 'ps', 'ps_ttm', 'industry_pe', 'industry_pb', 'total_shares', 'roe', '净资产收益率', 'change_pct', 'pct_chg', '涨跌幅', 'turnover_rate_pct', 'turnover_rate', '换手率', 'share_ratio', 'holding_ratio', 'change_ratio', 'holding_change_ratio', 'gross_margin', 'gross_profit_margin', '毛利率']);
function cell(row, keys, meta = {}, block = {}, allowBoolean = false) {
  const key = keys.find(name => !missing(row?.[name]) && (allowBoolean || typeof row[name] !== 'boolean'));
  const field = fieldMeta(meta, key);
  const unit = key ? field.unit || meta.units?.[key] || null : null;
  const nonCurrency = nonCurrencyKeys.has(key) || ['ratio', 'percent', '%', '倍', 'share', 'shares', '股', '万股', '亿股'].includes(String(unit || '').toLowerCase());
  return { value: key ? row[key] : null, key: key || null, unit, currency: key && !nonCurrency ? field.currency || meta.currency || null : null, basis: field.basis || null, provider: sourceOf(meta), date: dateOf(row), reportPeriod: reportPeriodOf(row), state: block.status || (key ? 'partial' : 'unavailable') };
}
function latest(rows = []) {
  const key = row => `${reportPeriodOf(row) || dateOf(row) || ''}:${row?.published_at || ''}`;
  return rows.reduce((selected, row) => !selected || key(row) > key(selected) ? row : selected, null) || {};
}
function asBlock(observation, name) {
  const block = observation?.blocks?.[name] || {};
  return { ...block, dataset: block.dataset || {} };
}
const shareUnit = unit => ['股', 'share', 'shares'].includes(String(unit || '').toLowerCase());
const priceUnit = cell => ['currency_per_share', '元/股', 'CNY/股', 'CNY/share'].includes(cell.unit) && Boolean(cell.currency);
function sharesCell(value) {
  const unitVerified = value.provider !== 'wind' && shareUnit(value.unit);
  return { ...value, unitVerified, unitNote: value.provider === 'wind' ? '单位为来源声明，尚未核验 Wind 原始返回数量级；不据此推导市值。' : unitVerified ? null : '来源未提供可核验的股本单位；不据此推导市值。' };
}
const COVERAGE_BLOCKS = [['overview', '资产概览'], ['history', '历史行情'], ['valuation', '估值'], ['financials', '财务指标'], ['activity', '资金流'], ['margin', '融资融券'], ['holders', '股东与机构持仓汇总'], ['holder_details', '前十大股东'], ['industry', '行业'], ['events', '公告事件'], ['research', '研究资料']];
function rangeOf(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const range = Object.fromEntries(['start_date', 'end_date'].filter(key => !missing(value[key])).map(key => [key, value[key]]));
  return Object.keys(range).length ? range : null;
}
function declaredFields(meta) {
  const fields = Array.isArray(meta.fields) ? meta.fields.filter(field => field && typeof field === 'object').map(field => ({ ...field })) : Object.entries(meta.fields || {}).map(([name, field]) => ({ name, ...field }));
  for (const [name, unit] of Object.entries(meta.units || {})) {
    const field = fields.find(item => item.name === name || item.field === name);
    if (field) { if (missing(field.unit)) field.unit = unit; }
    else fields.push({ name, unit });
  }
  return fields;
}
function projectCoverage(rows, observation, blocks) {
  const request = observation.request_parameters || {};
  return COVERAGE_BLOCKS.map(([id, label]) => {
    const block = blocks[id]; const meta = block.dataset; const loaded = Array.isArray(rows[id]) ? rows[id] : [];
    const recorded = Object.hasOwn(observation.blocks || {}, id);
    const dates = [...new Set(loaded.map(dateOf).filter(value => !missing(value)))].sort((a, b) => String(a).localeCompare(String(b)));
    const periods = [...new Set(loaded.map(reportPeriodOf).filter(value => !missing(value)))].sort((a, b) => String(a).localeCompare(String(b)));
    const status = block.status || meta.status || 'unavailable'; const datasetId = meta.dataset_id || null; const hasSnapshot = loaded.length > 0 && Boolean(datasetId);
    const failureCode = block.failure_code || null;
    const unsupported = ['not_implemented', 'data_provider_not_implemented', 'tinysoft_capability_unsupported'].includes(failureCode);
    const loadState = !recorded ? 'not_loaded' : unsupported ? 'not_connected' : status === 'loading' ? hasSnapshot ? 'refreshing' : 'loading' : failureCode || ['error', 'unavailable'].includes(status) ? hasSnapshot && failureCode !== 'snapshot_read_failed' ? 'stale' : 'error' : status === 'empty' ? 'empty' : hasSnapshot ? 'ready' : 'not_loaded';
    const requestedRange = recorded ? rangeOf(block.requested_range) || rangeOf(request.section_ranges?.[id]) || rangeOf(meta.requested_range) || (['history', 'activity', 'margin'].includes(id) ? rangeOf(request) : null) : null;
    return { id, label, status, loadState, requestedSource: recorded ? block.requested_source || request.section_sources?.[id] || observation.source || meta.query?.source || null : null, provider: sourceOf(meta), datasetId, loadedRowCount: loaded.length, hasSnapshot, asOf: meta.as_of || null, retrievedAt: meta.retrieved_at || null, dataDate: dates.at(-1) || null, reportPeriods: periods, requestedRange, actualRange: rangeOf(meta.actual_range), loadedRange: dates.length ? { start_date: dates[0], end_date: dates.at(-1) } : null, requestedFrequency: recorded && id === 'history' ? request.frequency || meta.query?.parameters?.frequency || null : null, requestedAdjustment: recorded && id === 'history' ? request.adjustment || meta.query?.parameters?.adjustment || null : null, fields: declaredFields(meta), limitations: Array.isArray(meta.limitations) ? [...meta.limitations] : [], failureCode, retainedSnapshot: hasSnapshot && failureCode !== 'snapshot_read_failed' && Boolean(failureCode || ['error', 'unavailable'].includes(status)) };
  });
}
function qualifiedTTM(value, meta) {
  if (value.provider !== 'akshare') return value;
  const field = fieldMeta(meta, value.key);
  return [field.period, field.basis].some(item => String(item || '').toUpperCase() === 'TTM') ? value : { ...value, value: null, state: 'unavailable' };
}
function capitalPartition(row, meta) {
  // Net flows, absolute values, and parent aggregates never form a pie.
  const partition = row.flow_partition;
  if (!partition || partition.complete !== true || partition.mutually_exclusive !== true || !Array.isArray(partition.items) || partition.items.length < 2 || !partition.unit || !partition.date || partition.date !== dateOf(row)) return null;
  const labels = new Set(); const categories = new Set();
  const items = partition.items;
  // Only the four leaf order-size buckets can establish this partition. Main is
  // a parent aggregate and may never duplicate super-large / large slices.
  if (items.length !== 4 || !['gross_inflow', 'gross_outflow'].includes(partition.basis)) return null;
  for (const item of items) {
    if (!item.label || labels.has(item.label) || !['super_large', 'large', 'medium', 'small'].includes(item.category) || categories.has(item.category) || numeric(item.value) === null || numeric(item.value) < 0 || item.unit !== partition.unit || item.date !== partition.date || item.kind !== 'gross' || item.aggregate === true) return null;
    labels.add(item.label); categories.add(item.category);
  }
  if (!items.some(item => numeric(item.value) > 0)) return null;
  return { items: items.map(item => ({ label: item.label, value: numeric(item.value) })), unit: partition.unit, date: partition.date, provider: sourceOf(meta) };
}

export function projectAssetObservation(rows = {}, observation = {}) {
  const blocks = Object.fromEntries(['overview', 'history', 'valuation', 'financials', 'activity', 'margin', 'holders', 'holder_details', 'research', 'industry', 'events', 'macro', 'shareholders'].map(name => [name, asBlock(observation, name)]));
  const overview = latest(rows.overview); const history = [...(rows.history || [])].sort((a, b) => String(dateOf(a) || '').localeCompare(String(dateOf(b) || ''))); const historical = history.at(-1) || {};
  const hasQuote = ['price', 'last', 'close', 'nav'].some(key => numeric(overview[key]) !== null);
  const quote = hasQuote ? overview : historical; const quoteBlock = hasQuote ? blocks.overview : blocks.history;
  const q = keys => cell(quote, keys, quoteBlock.dataset, quoteBlock);
  const hasOverview = (rows.overview || []).length > 0; const trading = hasOverview ? overview : historical; const tradingBlock = hasOverview ? blocks.overview : blocks.history;
  const t = keys => {
    const value = cell(trading, keys, tradingBlock.dataset, tradingBlock);
    if (keys.includes('turnover_rate_pct') && missing(value.value)) {
      const candidate = latest(rows.valuation);
      if (sourceOf(tradingBlock.dataset) && sourceOf(tradingBlock.dataset) === sourceOf(blocks.valuation.dataset) && dateOf(trading) && dateOf(trading) === dateOf(candidate)) return cell(candidate, keys, blocks.valuation.dataset, blocks.valuation);
    }
    return value;
  };
  const valuation = latest(rows.valuation); const v = keys => cell(valuation, keys, blocks.valuation.dataset, blocks.valuation);
  const financial = latest(rows.financials); const f = keys => cell(financial, keys, blocks.financials.dataset, blocks.financials);
  const price = q(['price', 'last', 'close', 'nav', '收盘']); const previous = q(['yclose', 'pre_close', '昨收']);
  const change = q(['change', 'price_change', 'change_amount', '涨跌额']); const changePct = q(['change_pct', 'pct_chg', '涨跌幅']);
  if (numeric(price.value) !== null && numeric(previous.value) > 0) {
    if (numeric(change.value) === null) { change.value = numeric(price.value) - numeric(previous.value); change.unit = price.unit; change.currency = price.currency; change.derived = true; }
    if (numeric(changePct.value) === null) { changePct.value = (numeric(price.value) / numeric(previous.value) - 1) * 100; changePct.unit = 'percent'; changePct.currency = null; changePct.derived = true; }
  }
  let marketCap = cell(overview, ['market_cap', 'total_market_cap'], blocks.overview.dataset, blocks.overview);
  if (missing(marketCap.value)) marketCap = v(['market_cap', 'total_market_cap']);
  if (missing(marketCap.value)) {
    // Wind shares have no verified raw quantity scale, even when metadata says
    // `share`. Retain their declared unit for display but never derive a cap.
    const close = v(sourceOf(blocks.valuation.dataset) === 'wind' ? ['close', 'price'] : ['close']); const shares = v(['total_shares']);
    if (shares.provider !== 'wind' && numeric(close.value) !== null && numeric(shares.value) !== null && priceUnit(close) && shareUnit(shares.unit) && close.date && close.date === shares.date && close.provider && close.provider === shares.provider) marketCap = { ...close, value: numeric(close.value) * numeric(shares.value), unit: close.unit === '元/股' ? '元' : 'currency', derived: true, derivation: '同来源同日收盘价 × 总股本' };
  }
  const highs = history.map(row => numeric(row.high ?? row['最高'])).filter(value => value !== null); const lows = history.map(row => numeric(row.low ?? row['最低'])).filter(value => value !== null);
  const rangeStart = dateOf(history[0]); const rangeEnd = dateOf(history.at(-1)); const coverage = blocks.history.dataset.coverage;
  const span = (Date.parse(rangeEnd) - Date.parse(rangeStart)) / 86400000;
  const verifiedYear = blocks.history.status === 'complete' && blocks.history.dataset.pagination_complete === true && (coverage?.complete === true || coverage?.full_year === true) && rangeStart && rangeEnd && span >= 364 && span <= 366;
  const activity = latest(rows.activity); const a = keys => cell(activity, keys, blocks.activity.dataset, blocks.activity);
  const shareholderRows = (rows.holder_details || rows.shareholders || rows.holders || []).filter(row => !missing(row.shareholder_name) || !missing(row.holder_name) || ((rows.shareholders || rows.holder_details) && !missing(row.name)));
  const shareholderBlock = rows.holder_details ? blocks.holder_details : rows.shareholders ? blocks.shareholders : blocks.holders;
  const shareholders = shareholderRows.slice(0, 10).map(row => ({ name: cell(row, ['shareholder_name', 'holder_name', 'name'], shareholderBlock.dataset, shareholderBlock), ratio: cell(row, ['share_ratio', 'holding_ratio'], shareholderBlock.dataset, shareholderBlock), change: cell(row, ['change_ratio', 'holding_change_ratio'], shareholderBlock.dataset, shareholderBlock), stateOwned: cell(row, ['is_state_owned', 'state_owned'], shareholderBlock.dataset, shareholderBlock, true) }));
  const industryRow = latest(rows.industry); const i = keys => cell(industryRow, keys, blocks.industry.dataset, blocks.industry);
  const events = (rows.events || []).map(row => ({ summary: cell(row, ['summary', 'title'], blocks.events.dataset, blocks.events), type: cell(row, ['event_type', 'type'], blocks.events.dataset, blocks.events), time: cell(row, ['publish_date', 'created_at', 'date'], blocks.events.dataset, blocks.events) }));
  const factors = [['interest', '利率'], ['inflation', '通胀'], ['fx', '汇率'], ['commodity', '大宗商品'], ['liquidity', '流动性']];
  const macro = factors.map(([id, label]) => { const row = (rows.macro || []).find(item => [id, label].includes(item.factor)) || {}; return { id, label, direction: cell(row, ['direction'], blocks.macro.dataset, blocks.macro), strength: cell(row, ['strength'], blocks.macro.dataset, blocks.macro) }; });
  const valuationPE = qualifiedTTM(v(['pe_ttm']), blocks.valuation.dataset); const financialPE = qualifiedTTM(f(['pe_ttm']), blocks.financials.dataset);
  const peTTM = valuationPE.value === null ? financialPE : valuationPE;
  return { blocks, coverageRows: projectCoverage(rows, observation, blocks), valuation: { peTTM, pb: v(['pb']), psTTM: v(['ps_ttm']), totalShares: sharesCell(v(['total_shares'])), marketCap }, basic: { name: cell(overview, ['name', '简称'], blocks.overview.dataset, blocks.overview), code: observation.asset || null, price, previousClose: previous, tradingPreviousClose: t(['yclose', 'pre_close', '昨收']), change, changePct, quoteKind: hasQuote ? '来源快照' : '历史收盘', tradingDate: dateOf(trading), tradingProvider: sourceOf(tradingBlock.dataset), volume: t(['volume', 'vol', '成交量']), amount: t(['amount', 'turnover', '成交额']), turnover: t(['turnover_rate_pct', 'turnover_rate', '换手率']), open: t(['open', '开盘']), high: t(['high', '最高']), low: t(['low', '最低']), marketCap, rangeLabel: verifiedYear ? '52周' : '区间', rangeHigh: cell({ high: highs.length ? Math.max(...highs) : null }, ['high'], blocks.history.dataset, blocks.history), rangeLow: cell({ low: lows.length ? Math.min(...lows) : null }, ['low'], blocks.history.dataset, blocks.history), rangeStart, rangeEnd }, financial: { peTTM, pbMRQ: v(['pb_mrq']).value === null ? f(['pb_mrq']) : v(['pb_mrq']), roe: f(['roe', '净资产收益率']), revenue: f(['revenue', '营业收入', '营收']), netProfit: f(['net_profit', '净利润']), grossMargin: f(['gross_margin', 'gross_profit_margin', '毛利率']) }, capitalFlow: { mainInflow: a(['main_inflow']), mainOutflow: a(['main_outflow']), mainNet: a(['main_net', 'main_force_inflow']), superNet: a(['super_net', 'super_large_net']), largeNet: a(['large_net']), mediumNet: a(['medium_net']), smallNet: a(['small_net']), northbound: a(['northbound_flow', 'north_bound_flow']), northboundShares: a(['north_bound_shares']), pie: capitalPartition(activity, blocks.activity.dataset) }, shareholders, industry: { sw1: i(['sw_level_1']), sw2: i(['sw_level_2']), pe: i(['industry_pe']), pb: i(['industry_pb']) }, events, macro };
}
