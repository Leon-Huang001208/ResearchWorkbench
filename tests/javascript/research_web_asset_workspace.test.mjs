import assert from 'node:assert/strict';
import test from 'node:test';
import { parseRoute, legacyRouteTarget } from '../../app/research_web/ui/core.mjs';
import { assetHref, selectAssetObservation } from '../../app/research_web/ui/asset-navigation.mjs';
import { createAssetNewsController, renderAssetNews } from '../../app/research_web/ui/asset-news.mjs';
import { createAssetWorkspaceController } from '../../app/research_web/ui/asset-controller.mjs';
import { renderAssetWorkspace, readAssetObservation, mountCapitalFlow } from '../../app/research_web/ui/asset-workspace.mjs';
import { enrichMarketBars, renderMarketTerminal } from '../../app/research_web/ui/asset-chart.mjs';
import { projectAssetObservation } from '../../app/research_web/ui/asset-projection.mjs';

test('both asset input patterns compile under the browser Unicode v flag', () => {
  const html = renderAssetWorkspace();
  const patterns = [...html.matchAll(/<input\b[^>]*\bname="asset"[^>]*\bpattern="([^"]+)"/g)].map(match => match[1]);
  assert.equal(patterns.length, 2, 'selection and observation forms both validate asset codes');
  for (const pattern of patterns) {
    const validate = new RegExp(`^(?:${pattern})$`, 'v');
    for (const code of ['600519.SH', 'SH603986', 'asset_code-1']) assert.equal(validate.test(code), true, code);
    for (const code of ['', '600519 SH', '<script>', 'a/b']) assert.equal(validate.test(code), false, code);
  }
});

test('original continuous indicators keep every card and missing slot on every legacy route', () => {
  for (const assetView of ['overview', 'financials', 'capital', 'holders', 'news', 'announcements', 'materials']) {
    const html = renderAssetWorkspace({ route: { asset: '600519.SH', assetType: 'stock', assetView } });
    const slots = ['asset-basic-card', 'data-asset-chart-slot', 'capital-flow-card', 'financial-panel', 'shareholder-panel', 'industry-panel', 'events-panel', 'macro-panel'];
    let last = -1;
    for (const slot of slots) { const index = html.indexOf(slot); assert.ok(index > last, slot); last = index; }
    for (const field of ['PE-TTM', 'PB-MRQ', 'ROE', '营收', '净利润', '毛利率', '股东名称', '持股比例', '变动比例', '国资属性', '申万一级', '申万二级', '行业PE', '行业PB', '事件摘要', '事件类型', '事件时间', '利率', '通胀', '汇率', '大宗商品', '流动性', '主力流入', '主力流出', '主力净流入', '超大单', '大单', '中单', '小单', '北向资金']) assert.ok(html.includes(field), field);
    assert.doesNotMatch(html, /asset-quote-panel|asset-chart-details/);
    for (const attribute of ['data-asset-select', 'data-asset-observation', 'data-asset-note', 'data-asset-alert', 'data-workbench-handoff', 'data-asset-news-slot']) assert.ok(html.includes(attribute), attribute);
  }
});
test('compact hero groups all metrics in order and keeps native controls closed', () => {
  const html = renderAssetWorkspace({ route: { asset: '600519.SH', assetType: 'stock' }, rows: { overview: [{ name: '贵州茅台', price: 10, open: 0, high: 11, low: 9, volume: 0, amount: 0, turnover_rate_pct: 0, date: '2026-10-21' }] } });
  const hero = html.slice(html.indexOf('<section class="asset-basic-card'), html.indexOf('<section class="asset-market-full"'));
  for (const className of ['asset-identity-switch', 'asset-query-controls']) assert.match(hero, new RegExp(`<details class="${className}">`));
  const trading = hero.slice(hero.indexOf('class="asset-trading-group"'), hero.indexOf('class="asset-valuation-group"'));
  let last = -1;
  for (const label of ['开盘', '最高', '最低', '换手率', '成交量', '成交额', '区间最高', '区间最低']) { const index = trading.indexOf(`<dt>${label}</dt>`); assert.ok(index > last, label); last = index; }
  const valuation = hero.slice(hero.indexOf('class="asset-valuation-group"'));
  last = -1;
  for (const label of ['PE-TTM', 'PB', 'PS-TTM', '总股本', '市值']) { const index = valuation.indexOf(`<dt>${label}</dt>`); assert.ok(index > last, label); last = index; }
  assert.match(trading, /开盘<\/dt><dd[^>]*>0<\/dd>/);
  assert.match(trading, /成交量<\/dt><dd id="asset-volume">0<\/dd>/);
  assert.match(valuation, /市值<\/dt><dd id="asset-market-cap">—<\/dd>/);
  assert.match(hero, /未取得的数据以 — 表示/);
});
test('source summary counts hydrated snapshot rows and distinguishes stale and unloaded states', () => {
  const observation = { asset: '600519.SH', asset_type: 'stock', blocks: {
    overview: { status: 'error', failure_code: 'refresh_failed', requested_source: 'auto', dataset: { dataset_id: 'old', provider: 'tinysoft' } },
    history: { status: 'complete', dataset: { dataset_id: 'not-hydrated', provider: 'wind', row_count: 10 } },
    valuation: { status: 'loading', dataset: { dataset_id: 'cached', provider: 'wind' } },
  } };
  const html = renderAssetWorkspace({ observation, rows: { overview: [{ price: 0, date: '2026-10-21' }], valuation: [{ pe_ttm: 0, date: '2026-10-20' }] } });
  const summary = html.slice(html.indexOf('<details class="asset-source-summary"'), html.indexOf('<article class="asset-block capital-flow-card'));
  assert.match(summary, /^<details class="asset-source-summary">/);
  assert.match(summary, /来源与口径 · 2\/8 区块有快照 · 查看详情/);
  assert.equal((summary.match(/data-asset-source-row=/g) || []).length, 8);
  assert.match(summary, /失败 · 保留旧快照/); assert.match(summary, /加载中 · 显示上次快照/);
  assert.match(summary, /完整 · 快照尚未载入/); assert.match(summary, /refresh_failed/);
  assert.match(summary, /新闻与公告独立查询/);
});
test('source details preserve dates ranges field units and report periods separately', () => {
  const observation = { asset: '600519.SH', asset_type: 'stock', request_parameters: { frequency: 'daily', adjustment: 'none' }, blocks: { financials: { status: 'partial', requested_source: 'auto', requested_range: { start_date: '2026-01-01', end_date: '2026-10-21' }, dataset: { dataset_id: 'finance', provider: 'wind', as_of: '2026-10-21', retrieved_at: '2026-10-21T08:00:00Z', actual_range: { start_date: '2026-06-30', end_date: '2026-10-21' }, fields: [{ name: 'revenue', unit: 'currency', currency: 'CNY', basis: 'reported' }], limitations: ['摘要口径'] } } } };
  const html = renderAssetWorkspace({ observation, rows: { financials: [{ report_period: '2026-06-30', date: '2026-10-20', revenue: 0 }] } });
  const source = html.slice(html.indexOf('data-asset-source-row="financials"'), html.indexOf('data-asset-source-row="activity"'));
  for (const value of ['请求来源', '实际来源', 'auto', 'wind', '数据日', '2026-10-20', '截至', '2026-10-21', '北京时间', '16:00:00', '报告期', '2026-06-30', '请求区间', '实际区间', '已载入区间', '2026-01-01', 'revenue', 'currency', 'CNY', 'reported', '摘要口径']) assert.ok(source.includes(value), value);
  assert.doesNotMatch(source, /报告期未提供/);
});
test('partially read new snapshots never claim old snapshots in source rows or local cards', () => {
  const observation = { asset: '600519.SH', asset_type: 'stock', blocks: Object.fromEntries(['history', 'financials', 'margin', 'holders', 'research'].map(name => [name, { status: 'partial', failure_code: 'snapshot_read_failed', dataset: { dataset_id: `new-${name}`, provider: 'wind', row_count: 320 } }])) };
  const rows = Object.fromEntries(['history', 'financials', 'margin', 'holders', 'research'].map(name => [name, [{ date: '2026-10-20', close: 10, revenue: 0 }]]));
  const html = renderAssetWorkspace({ observation, rows });
  for (const name of Object.keys(rows)) {
    const source = html.match(new RegExp(`<tr data-asset-source-row="${name}">[\\s\\S]*?</tr>`))?.[0];
    assert.ok(source, name); assert.match(source, /部分记录已载入 · 读取未完成/); assert.doesNotMatch(source, /保留旧快照|下方保留上次快照/);
  }
  assert.doesNotMatch(html, /下方保留上次快照/);
  const empty = renderAssetWorkspace({ observation });
  assert.match(empty, /快照读取失败/); assert.doesNotMatch(empty, /部分记录已载入|下方保留上次快照/);
});
test('actual provider refresh failures retain the old loaded snapshot notice in local cards', () => {
  const observation = { asset: '600519.SH', asset_type: 'stock', blocks: { margin: { status: 'error', failure_code: 'provider_timeout', dataset: { dataset_id: 'old-margin', provider: 'wind' } }, financials: { status: 'error', failure_code: 'provider_timeout', dataset: { dataset_id: 'old-finance', provider: 'wind' } } } };
  const html = renderAssetWorkspace({ observation, rows: { margin: [{ date: '2026-10-10', margin_balance: 0 }], financials: [{ report_period: '2026-06-30', revenue: 0 }] } });
  assert.match(html.slice(html.indexOf('id="financial-panel"'), html.indexOf('id="shareholder-panel"')), /下方保留上次快照，不表示刷新成功/);
  assert.match(html.slice(html.indexOf('<h2>融资融券</h2>')), /下方保留上次快照，不表示刷新成功/);
});
test('quote returns and dimensionless valuation metrics do not render price currency as their units', () => {
  const meta = { provider: 'wind', currency: 'CNY', fields: [{ name: 'price', unit: 'currency_per_share', currency: 'CNY' }, { name: 'pb', unit: 'ratio', currency: 'CNY' }, { name: 'ps_ttm', unit: 'ratio' }, { name: 'total_shares', unit: 'share' }] };
  const html = renderAssetWorkspace({ observation: { asset: '600519.SH', blocks: { overview: { dataset: meta }, valuation: { dataset: meta } } }, rows: { overview: [{ price: 10.11, yclose: 10 }], valuation: [{ pe_ttm: 9, pb: 2, ps_ttm: 3, total_shares: 0 }] } });
  assert.match(html, /id="asset-change-pct">较昨收计算 1\.1%<\/span>/);
  const valuation = html.slice(html.indexOf('class="asset-valuation-grid"'), html.indexOf('<p class="asset-group-note">估值'));
  assert.match(valuation, /PE-TTM<\/dt><dd>9<\/dd>/); assert.match(valuation, /PB<\/dt><dd>2 倍<\/dd>/); assert.match(valuation, /PS-TTM<\/dt><dd>3 倍<\/dd>/);
  assert.doesNotMatch(valuation, /CNY/);
});
test('valuation preserves zero and raw Wind shares without guessing a share scale', () => {
  const observation = { asset: '600519.SH', asset_type: 'stock', blocks: { valuation: { status: 'complete', dataset: { dataset_id: 'v', provider: 'wind', fields: [{ name: 'total_shares', unit: 'share' }, { name: 'market_cap', unit: 'currency', currency: 'CNY' }] } } } };
  const rows = { valuation: [{ date: '2026-10-20', pe_ttm: 0, pb: 0, ps_ttm: 0, total_shares: 100, close: 9 }] };
  const html = renderAssetWorkspace({ observation, rows });
  const valuation = html.slice(html.indexOf('class="asset-valuation-group"'), html.indexOf('<section class="asset-market-full"'));
  for (const label of ['PE-TTM', 'PB', 'PS-TTM']) assert.ok(valuation.includes(`<dt>${label}</dt><dd>0</dd>`), label);
  assert.match(valuation, /id="asset-total-shares">100<\/dd>/);
  assert.match(valuation, /未经核实，不作换算/);
  assert.match(valuation, /id="asset-market-cap">—<\/dd>/);
  rows.valuation[0].market_cap = 0;
  assert.match(renderAssetWorkspace({ observation, rows }), /id="asset-market-cap">0 CNY<\/dd>/);
});
test('summary leaves market terminal DOM intact and empty shareholders have no synthetic row', () => {
  const rows = { history: [{ date: '2026-10-21', open: 10, high: 12, low: 9, close: 11, volume: 0 }] };
  const observation = { asset: '600519.SH', asset_type: 'stock', blocks: { history: { dataset: { dataset_id: 'h', provider: 'tinysoft' } } } };
  const p = projectAssetObservation(rows, observation);
  const terminal = renderMarketTerminal(rows.history, {}, { ...p.blocks.history.dataset, frequency: 'daily', adjustment: 'none', asset: observation.asset, name: observation.asset, currentQuote: p.basic });
  const html = renderAssetWorkspace({ observation, rows });
  assert.ok(html.includes(`<div data-asset-chart-slot>${terminal}</div></section><details class="asset-source-summary">`));
  const shareholder = html.slice(html.indexOf('id="shareholder-panel"'), html.indexOf('id="industry-panel"'));
  assert.match(shareholder, /<tbody><\/tbody>/);
  assert.match(shareholder, /股东名单未取得/);
  assert.match(html, /capital-flow-card is-missing-pie/);
});
test('projection preserves zero and metadata without upgrading valuation or inventing flow', () => {
  const rows = { overview: [{ price: 10, date: '2026-10-21', volume: 0 }], valuation: [{ close: 9, date: '2026-10-20', total_shares: 100, pe: 12, pb: 3 }], activity: [{ date: '2026-10-20', main_force_inflow: -5, north_bound_shares: 123 }], financials: [{ report_period: '2026-06-30', revenue: 0, net_profit: null }] };
  const observation = { blocks: { overview: { dataset: { provider: 'tinysoft' } }, valuation: { dataset: { provider: 'wind', fields: [{ name: 'close', unit: '元/股', currency: 'CNY' }, { name: 'total_shares', unit: '股' }] } }, financials: { dataset: { provider: 'wind', fields: [{ name: 'revenue', unit: '元', currency: 'CNY' }] } } } };
  const frozen = JSON.stringify(rows); const p = projectAssetObservation(rows, observation);
  assert.equal(p.basic.volume.value, 0); assert.equal(p.basic.marketCap.value, null, 'unverified Wind share scale cannot derive market capitalization');
  assert.equal(p.financial.peTTM.value, null); assert.equal(p.financial.pbMRQ.value, null);
  assert.equal(p.financial.revenue.value, 0); assert.equal(p.financial.netProfit.value, null);
  assert.equal(p.financial.revenue.reportPeriod, '2026-06-30'); assert.equal(p.financial.revenue.currency, 'CNY');
  assert.equal(p.capitalFlow.mainNet.value, -5); assert.equal(p.capitalFlow.mainInflow.value, null); assert.equal(p.capitalFlow.mainOutflow.value, null);
  assert.equal(p.capitalFlow.northbound.value, null); assert.equal(p.capitalFlow.pie, null);
  assert.equal(p.basic.rangeLabel, '区间'); assert.deepEqual(p.shareholders, []); assert.equal(JSON.stringify(rows), frozen);
});
test('market cap never combines quote and shares across sources or dates', () => {
  assert.equal(projectAssetObservation({ overview: [{ turnover: 3336029501, turnover_rate_pct: null }], history: [] }).basic.amount.value, 3336029501);
  assert.equal(projectAssetObservation({ overview: [{ price: 10 }], history: [{ volume: 999, date: '2026-10-20', close: 9 }] }).basic.volume.value, null);
  assert.equal(projectAssetObservation({ overview: [{ price: 10, date: '2026-10-21' }], valuation: [{ total_shares: 100, date: '2026-10-20' }] }).basic.marketCap.value, null);
  assert.equal(projectAssetObservation({ valuation: [{ close: 9, total_shares: 100, date: '2026-10-20' }] }).basic.marketCap.value, null, 'unknown share unit cannot imply shares');
  const wind = projectAssetObservation({ overview: [{ price: 999, date: '2026-10-21' }], valuation: [{ price: 9, total_shares: 100, as_of: '2026-10-20' }] }, { blocks: { valuation: { dataset: { provider: 'wind', fields: [{ name: 'price', unit: 'currency_per_share', currency: 'CNY' }, { name: 'total_shares', unit: 'share' }] } } } });
  assert.equal(wind.basic.marketCap.value, null, 'Wind source declarations do not verify raw total-share quantity scale');
  const unqualified = { blocks: { valuation: { dataset: { provider: 'wind', fields: [{ name: 'total_shares', unit: 'share' }] } } } };
  assert.equal(projectAssetObservation({ valuation: [{ close: 9, total_shares: 100, as_of: '2026-10-20' }] }, unqualified).basic.marketCap.value, null, 'unknown close units cannot become market capitalization');
});
test('legacy AKShare dynamic PE is never relabelled TTM without explicit metadata', () => {
  const observation = { blocks: { valuation: { dataset: { provider: 'akshare', fields: [{ name: 'pe_ttm', unit: 'ratio' }] } } } };
  const rows = { valuation: [{ pe_ttm: 9, pb: 3, date: '2026-10-20' }] };
  assert.equal(projectAssetObservation(rows, observation).financial.peTTM.value, null);
  assert.equal(projectAssetObservation(rows, observation).financial.pbMRQ.value, null);
  observation.blocks.valuation.dataset.fields[0].period = 'TTM';
  assert.equal(projectAssetObservation(rows, observation).financial.peTTM.value, 9);
  const booleans = projectAssetObservation({ financials: [{ revenue: false, net_profit: 0 }], shareholders: [{ name: '真实股东', is_state_owned: false }] });
  assert.equal(booleans.financial.revenue.value, null); assert.equal(booleans.financial.netProfit.value, 0); assert.equal(booleans.shareholders[0].stateOwned.value, false);
});
const partition = () => ({ complete: true, mutually_exclusive: true, basis: 'gross_inflow', unit: 'CNY', date: '2026-10-20', items: ['super_large', 'large', 'medium', 'small'].map((category, i) => ({ category, label: category, value: i, kind: 'gross', unit: 'CNY', date: '2026-10-20' })) });
test('capital pie requires complete same-day same-unit mutually exclusive gross leaf buckets', () => {
  const project = flow_partition => projectAssetObservation({ activity: [{ date: '2026-10-20', main_net: -9, flow_partition }] }).capitalFlow;
  assert.equal(project(partition()).pie.items.length, 4);
  for (const change of [p => { p.items[0].value = -1; }, p => { p.items[0].unit = '股'; }, p => { p.items[0].date = '2026-10-19'; }, p => { p.items[0].kind = 'net'; }, p => { p.items[0].aggregate = true; }, p => { p.items[0].category = 'main'; }, p => { p.complete = false; }, p => { p.items.pop(); }]) {
    const p = partition(); change(p); assert.equal(project(p).pie, null);
  }
});
test('capital mount updates and disposes charts, net-only never invokes Chart', () => {
  const originalWindow = globalThis.window; let created = 0; let destroyed = 0; let config;
  globalThis.window = { Chart: class { constructor(canvas, input) { created++; config = input; } destroy() { destroyed++; } } };
  const canvas = {}; const state = {}; const root = { querySelector(selector) { return selector === '[data-capital-flow-canvas]' ? canvas : state; } };
  try {
    const handle = mountCapitalFlow(root, projectAssetObservation({ activity: [{ main_net: -20 }] }));
    assert.equal(created, 0); assert.equal(canvas.hidden, true); assert.match(state.textContent, /净额/);
    handle.update(projectAssetObservation({ activity: [{ date: '2026-10-20', flow_partition: partition() }] }));
    assert.equal(created, 1); assert.deepEqual(config.data.datasets[0].data, [0, 1, 2, 3]);
    assert.equal(config.options.plugins.legend.labels.color, '#242424', 'non-DOM rendering has a stable theme fallback');
    handle.update(projectAssetObservation()); assert.equal(destroyed, 1); assert.equal(canvas.hidden, true);
    handle.dispose(); handle.dispose(); assert.equal(destroyed, 1);
  } finally { globalThis.window = originalWindow; }
});
test('capital legend and tooltip read the current theme while retaining transparent canvas and real partitions', () => {
  const originalWindow = globalThis.window; const originalStyle = globalThis.getComputedStyle;
  const configurations = []; const canvas = { nodeType: 1 }; const state = {};
  let colors = { '--text': '#ecece7', '--surface': '#222220', '--line': '#343430' };
  globalThis.getComputedStyle = () => ({ getPropertyValue: key => colors[key] || '' });
  globalThis.window = { Chart: class { constructor(target, configuration) { configurations.push(configuration); } destroy() {} } };
  const root = { querySelector: selector => selector === '[data-capital-flow-canvas]' ? canvas : state };
  try {
    const projection = projectAssetObservation({ activity: [{ date: '2026-10-20', flow_partition: partition() }] });
    const handle = mountCapitalFlow(root, projection);
    assert.equal(configurations[0].options.plugins.legend.labels.color, '#ecece7');
    assert.equal(configurations[0].options.plugins.tooltip.backgroundColor, '#222220');
    assert.equal(configurations[0].options.plugins.tooltip.bodyColor, '#ecece7');
    colors = { '--text': '#242424', '--surface': '#fafaf9', '--line': '#e8e8e5' };
    handle.update(projection);
    assert.equal(configurations[1].options.plugins.legend.labels.color, '#242424');
    assert.deepEqual(configurations[1].data.datasets[0].data, [0, 1, 2, 3]);
    assert.equal(Object.hasOwn(configurations[1].options, 'backgroundColor'), false);
    assert.equal(canvas.style, undefined, 'mounting never assigns a separate canvas background');
    handle.dispose();
  } finally { globalThis.window = originalWindow; globalThis.getComputedStyle = originalStyle; }
});
test('year coverage, shareholder summaries and unknown dates cannot become verified facts', () => {
  const rows = { history: [{ date: '2025-10-21', high: 2, low: 1 }, { date: '2026-10-21', high: 4, low: 0 }], holders: [{ name: '汇总公司名称', share_ratio: 20, top10_pct: 50 }], events: [{ title: '真实事件' }] };
  assert.equal(projectAssetObservation(rows).basic.rangeLabel, '区间');
  const p = projectAssetObservation(rows, { blocks: { history: { status: 'complete', dataset: { pagination_complete: true, coverage: { full_year: true } } } } });
  assert.equal(p.basic.rangeLabel, '52周'); assert.equal(p.basic.rangeLow.value, 0); assert.equal(p.events[0].time.value, null); assert.deepEqual(p.shareholders, []);
  assert.equal(projectAssetObservation({ history: [{ date: '2020-10-21', high: 99, low: 1 }, ...rows.history] }, { blocks: { history: { status: 'complete', dataset: { pagination_complete: true, coverage: { full_year: true } } } } }).basic.rangeLabel, '区间');
  const html = renderAssetWorkspace({ observation: { asset: '600519.SH', source: 'wind', request_parameters: { start_date: '2026-09-01', end_date: '2026-10-20' } } });
  assert.match(html, /name="activity_start_date" value="2026-09-01"/);
});
test('source controls restore saved per-section mappings and ranges', () => {
  const html = renderAssetWorkspace({ observation: { asset: '600519.SH', asset_type: 'stock', source: 'auto', request_parameters: { start_date: '2025-10-21', end_date: '2026-10-21', frequency: 'daily', adjustment: 'none', section_sources: { history: 'wind', overview: 'tinysoft', valuation: 'wind' }, section_ranges: { history: { start_date: '2025-10-21', end_date: '2026-10-21' }, activity: { start_date: '2026-09-01', end_date: '2026-10-20' } } } } });
  assert.match(html, /name="section_source_history"[^]*?<option value="wind" selected/);
  assert.match(html, /name="activity_start_date" value="2026-09-01"/);
  assert.match(html, /name="adjustment"[^]*?<option value="none" selected/);
  const OriginalFormData = globalThis.FormData;
  globalThis.FormData = class { constructor(form) { this.values = new Map(Object.entries(form)); } get(key) { return this.values.get(key) ?? null; } has(key) { return this.values.has(key); } };
  try {
    const request = readAssetObservation({ asset: '600519.sh', asset_type: 'stock', scope_mode: 'section', start_date: '2025-10-21', end_date: '2026-10-21', section_source_history: 'wind', section_source_overview: 'tinysoft', section_source_valuation: 'wind' });
    assert.equal(request.source, 'auto'); assert.equal(request.adjustment, 'none'); assert.equal(request.frequency, 'daily');
    assert.equal(request.section_sources.history, 'wind'); assert.equal(request.section_sources.overview, 'tinysoft'); assert.equal(request.section_sources.valuation, 'wind');
    assert.deepEqual(request.section_ranges.history, { start_date: '2025-10-21', end_date: '2026-10-21' });
    assert.deepEqual(request.section_ranges.activity, { start_date: '2026-08-23', end_date: '2026-10-21' });
    assert.ok(request.sections.includes('valuation'));
    const legacy = readAssetObservation({ asset: '600519.SH', source: 'akshare', start_date: '2026-10-01', end_date: '2026-10-20' });
    assert.equal(legacy.source, 'akshare'); assert.equal(legacy.section_sources, undefined); assert.equal(legacy.adjustment, 'qfq');
    assert.equal(readAssetObservation({ asset: '510300.SH', asset_type: 'etf', scope_mode: 'section' }).sections.includes('valuation'), false);
  } finally { globalThis.FormData = OriginalFormData; }
});

const response = data => ({ ok: true, status: 200, json: async () => data });
test('CJPY original date, name and volume fields remain readable without guessing units', () => {
  const row = { 代码: 'SH603986', 简称: '兆易创新', 时间: '2026-10-20', open: 10, high: 12, low: 9, close: 11, amount: 2000, vol: 30 };
  const bars = enrichMarketBars([row]); assert.equal(bars.length, 1); assert.equal(bars[0].date, '2026-10-20'); assert.equal(bars[0].volume, 30);
  const html = renderAssetWorkspace({ observation: { asset: '603986.SH', asset_type: 'stock', blocks: { overview: { status: 'complete', dataset: { provider: 'tinysoft', retrieved_at: '2026-10-21T08:00:00Z' } } } }, rows: { overview: [row], history: [row] } });
  assert.match(html, /兆易创新/); assert.match(html, /数据日[^<]*2026-10-20/); assert.match(html, /成交量<\/dt><dd id="asset-volume">30<\/dd>/);
});
test('current quote changes use the same snapshot and never borrow historical trading fields', () => {
  const html = renderAssetWorkspace({ observation: { asset: '603986.SH', asset_type: 'stock', blocks: {} }, rows: { overview: [{ close: 11, yclose: 10, amount: 3000, 时间: '2026-10-21' }], history: [{ date: '2026-10-20', open: 9, high: 12, low: 8, close: 10 }] } });
  assert.match(html, /较昨收计算[^<]*10%/);
  const quote = html.slice(html.indexOf('class="asset-trading-group"'), html.indexOf('class="asset-valuation-group"'));
  assert.match(quote, /开盘<\/dt><dd>—<\/dd>/);
  assert.match(quote, /交易数据日[^<]*2026-10-21/);
});
test('Wind snapshot time cannot fall back to a different historical trading day', () => {
  const html = renderAssetWorkspace({ observation: { asset: '603986.SH', asset_type: 'stock', blocks: {} }, rows: { overview: [{ price: 100, as_of: '2026-10-21', turnover_rate_pct: 2 }], history: [{ date: '2026-10-15', open: 90, high: 95, low: 89, close: 91 }] } });
  const identity = html.slice(html.indexOf('<section class="asset-basic-card'), html.indexOf('<section class="asset-market-full"'));
  assert.match(identity, /数据日 2026-10-21/); assert.doesNotMatch(identity, /数据日 2026-10-15/);
  assert.match(html, /交易数据日 2026-10-21/);
});
test('asset page uses research topics, source-aware metrics and complete financial records', () => {
  const html = renderAssetWorkspace({ route: { asset: '600519.SH', assetType: 'stock', assetView: 'financials' }, observation: { asset: '600519.SH', asset_type: 'stock', blocks: { financials: { status: 'complete', dataset: { provider: 'wind', as_of: '2026-06-30', fields: [{ name: 'revenue', unit: 'currency', currency: 'CNY' }] } } } }, rows: { financials: [{ report_period: '2026-06-30', revenue: 0, net_profit: null }] } });
  for (const label of ['资金与两融', '股东', '新闻', '公告', '资料', '营业收入', '2026-06-30', 'CNY']) assert.match(html, new RegExp(label));
  assert.doesNotMatch(html, /52周高|十大股东明细|THEME EXPOSURE/);
  assert.match(html, /data-asset-block-refresh="financials"/);
  assert.match(html, /data-asset-personal/);
});
test('renderer refuses a previous asset snapshot and news during a route transition', () => {
  const html = renderAssetWorkspace({ route: { asset: '603986.SH', assetType: 'stock', assetView: 'news' }, observation: { asset: '600519.SH', asset_type: 'stock', session_id: 'wrong-session', dataset_ids: ['wrong-data'], blocks: {} }, rows: { overview: [{ name: '旧资产名称', price: 999999 }] }, news: { asset: '600519.SH', assetType: 'stock', view: 'news', status: 'complete', items: [{ title: '旧资产新闻' }] } });
  assert.doesNotMatch(html, /旧资产名称|旧资产新闻|wrong-session|wrong-data|999,999/);
  assert.match(html, /603986.SH/);
});
test('asset topic routes preserve identity and migrate only the two legacy columns', () => {
  const hash = assetHref('600519.SH', 'stock', 'financials');
  assert.equal(parseRoute(hash).asset, '600519.SH');
  assert.equal(parseRoute(hash).assetView, 'financials');
  assert.equal(parseRoute(hash).assetType, 'stock');
  assert.equal(legacyRouteTarget('#/intel/news?code=600519'), '#/assets?view=news&asset=600519&asset_type=stock');
  assert.equal(legacyRouteTarget('#/intel/filings'), '#/assets?view=announcements');
  assert.equal(legacyRouteTarget('#/intel/news/extra'), null);
  assert.equal(parseRoute('#/workbench/assets?asset=%3Cscript%3E&view=unknown').asset, '');
  assert.equal(parseRoute('#/workbench/assets?view=unknown').assetView, 'overview');
});
test('observation selection never borrows another security or asset type', () => {
  const items = [{ id: 'index', asset: '000001.SH', asset_type: 'index' }, { id: 'stock', asset: '000001.SZ', asset_type: 'stock' }];
  assert.equal(selectAssetObservation(items, { asset: '000001.SZ', assetType: 'stock' }).id, 'stock');
  assert.equal(selectAssetObservation(items, { asset: '000001.SH', assetType: 'stock' }), null);
  assert.equal(selectAssetObservation(items, { asset: '600519.SH', assetType: 'stock' }), null);
});
test('asset news is a lazy read-only query, isolated by code and column', async () => {
  const calls = [];
  const c = createAssetNewsController({ fetcher: async path => { calls.push(path); return response([{ title: '公告', content: '<script>x</script>', url: 'javascript:x' }]); } });
  await c.activate({ asset: '600519.SH', assetType: 'stock', assetView: 'overview' });
  assert.equal(calls.length, 0);
  await c.activate({ asset: '600519.SH', assetType: 'stock', assetView: 'news' });
  assert.deepEqual(calls, ['/api/research/intel/news?code=600519']);
  assert.match(renderAssetNews(c.state), /&lt;script&gt;/);
  assert.doesNotMatch(renderAssetNews(c.state), /href="javascript:/);
  await c.activate({ asset: '000001.SH', assetType: 'index', assetView: 'announcements' });
  assert.equal(calls.length, 1);
  assert.match(renderAssetNews(c.state), /A 股股票/);
});
test('late news cannot overwrite a different asset and malformed data is not empty success', async () => {
  let resolveOld; let signal;
  const c = createAssetNewsController({ fetcher: async (path, options) => {
    if (path.includes('600519')) { signal = options.signal; return new Promise(resolve => { resolveOld = resolve; }); }
    return response([{ title: '新资产' }]);
  } });
  const old = c.activate({ asset: '600519.SH', assetType: 'stock', assetView: 'news' });
  await c.activate({ asset: '603986.SH', assetType: 'stock', assetView: 'news' });
  assert.ok(signal.aborted);
  resolveOld(response([{ title: '旧资产' }])); await old;
  assert.match(renderAssetNews(c.state), /新资产/);
  assert.doesNotMatch(renderAssetNews(c.state), /旧资产/);
  const bad = createAssetNewsController({ fetcher: async () => response({ unexpected: [] }) });
  await bad.activate({ asset: '603986.SH', assetType: 'stock', assetView: 'news' });
  assert.equal(bad.state.status, 'error');
});
test('workspace reads all snapshot pages and marks row failures without losing personal data', async () => {
  const calls = [];
  const observation = { id: 'o', session_id: 's', asset: '600519.SH', asset_type: 'stock', blocks: { history: { status: 'complete', dataset: { dataset_id: 'd', row_count: 201 } }, financials: { status: 'complete', dataset: { dataset_id: 'bad', row_count: 1 } } } };
  const api = {
    assetObservations: async () => ({ items: [observation] }), watchlists: async () => ({ items: [{ id: 'w' }] }), assetNotes: async () => ({ items: [] }), assetAlerts: async () => ({ items: [] }), assetNotifications: async () => ({ items: [] }),
    datasetRows: async (sid, did, offset) => { calls.push([did, offset]); if (did === 'bad') throw new Error('读取失败'); return { items: Array.from({ length: offset ? 1 : 200 }, (_, i) => ({ date: String(offset + i) })) }; },
  };
  const c = createAssetWorkspaceController({ api });
  await c.load({ asset: '600519.SH', assetType: 'stock', assetView: 'overview' });
  assert.equal(c.state.rows.history.length, 201);
  assert.ok(calls.some(([id, offset]) => id === 'd' && offset === 200));
  assert.equal(c.state.observation.blocks.financials.status, 'error');
  assert.equal(c.state.watchlists.length, 1);
});
