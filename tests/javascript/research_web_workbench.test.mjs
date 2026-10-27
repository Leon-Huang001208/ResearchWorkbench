import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';

const root = new URL('../../app/research_web/ui/', import.meta.url);

test('business routes retain backend sections and fall back within their module', async () => {
  const { parseRoute, isDataWorkspaceRoute } = await import(new URL('core.mjs', root));
  const cases = [
    ['#/assets', 'assets', 'assets'], ['#/assets/funds', 'assets', 'funds'],
    ['#/assets/unknown', 'assets', 'assets'], ['#/assets/funds/extra', 'assets', 'assets'],
    ['#/intel/search?kind=news', 'intel', 'market'], ['#/intel/search?kind=research', 'intel', 'industry'],
    ['#/intel/search?kind=announcements', 'intel', 'documents'], ['#/intel/search?kind=unknown', 'intel', 'market'],
    ['#/simulation/etf', 'simulation', 'etf-paper'], ['#/simulation/unknown', 'simulation', 'etf-paper'],
  ];
  for (const [hash, page, section] of cases) {
    const route = parseRoute(hash);
    assert.equal(route.page, page, hash); assert.equal(route.section, section, hash);
    assert.equal(isDataWorkspaceRoute(route), true, hash);
  }
  assert.equal(parseRoute('#/intel/search?kind=research').intelTab, 'search');
  assert.equal(parseRoute('#/intel/search?kind=research').searchKind, 'research');
  assert.equal(parseRoute('#/intel/search/unknown?kind=research').intelTab, 'overview');
  assert.equal(isDataWorkspaceRoute(parseRoute('#/intel/overview')), false);
  assert.equal(isDataWorkspaceRoute(parseRoute('#/frameworks/gold?tab=drivers')), false);
  assert.equal(parseRoute('#/frameworks/gold?tab=drivers').frameworkTab, 'drivers');
  assert.equal(parseRoute('#/workbench').section, 'assets');
  assert.equal(parseRoute('#/workbench?section=funds').page, 'workbench');
  assert.equal(parseRoute('#/workbench?section=funds').section, 'funds');
  assert.equal(parseRoute('#/workbench/funds').section, 'funds');
});

test('legacy research desk URLs redirect with unrelated parameters and hot identity intact', async () => {
  const { legacyRouteTarget, parseRoute } = await import(new URL('core.mjs', root));
  const targets = {
    assets: '#/assets', funds: '#/assets/funds', market: '#/intel/search?kind=news',
    industry: '#/intel/search?kind=research', documents: '#/intel/search?kind=announcements',
    'etf-paper': '#/simulation/etf', hot: '#/intel/hot',
  };
  assert.equal(legacyRouteTarget('#/workbench'), '#/assets');
  assert.equal(legacyRouteTarget('#/workbench/'), '#/assets');
  assert.equal(legacyRouteTarget('#/workbench/unknown?source=public'), '#/assets?source=public');
  assert.equal(legacyRouteTarget('#/workbench?section=unknown&source=public'), '#/assets?source=public');
  for (const [section, target] of Object.entries(targets)) {
    for (const old of [`#/workbench/${section}`, `#/workbench?section=${section}`]) {
      assert.equal(legacyRouteTarget(old), target, old);
      const oldWithParams = old + (old.includes('?') ? '&' : '?') + 'source=public&view=sources&event=known-event';
      const expected = target + (target.includes('?') ? '&' : '?') + 'source=public&view=sources&event=known-event';
      assert.equal(legacyRouteTarget(oldWithParams), expected, oldWithParams);
    }
  }
  assert.equal(legacyRouteTarget('#/workbench/market?section=funds&kind=research&limit=15'), '#/intel/search?kind=news&limit=15');
  assert.equal(legacyRouteTarget('#/assets'), null);
  assert.equal(legacyRouteTarget('#/reports'), null);
  assert.equal(parseRoute('#/reports').page, 'reports');
});

test('primary navigation exposes one active entry per business module in the agreed order', async () => {
  const { parseRoute } = await import(new URL('core.mjs', root));
  const shell = await import(new URL('shell.mjs', root));
  assert.equal(parseRoute('#/operations').page, 'operations');
  const labels = ['FinGPT', 'Claw', '报告生产', '全市场概览', '资产观察', '研究情报', 'AI 资讯', '研究框架', '策略模拟', '能力中心', '运行与用量'];
  const rail = shell.renderPrimaryRail(parseRoute('#/assets'));
  assert.deepEqual([...rail.matchAll(/class="rail-label">([^<]+)<\/span>/g)].map(item => item[1]).slice(0, labels.length), labels);
  for (const [hash, activeHref] of [
    ['#/assets', '#/assets'], ['#/assets/funds', '#/assets'], ['#/intel/search?kind=research', '#/intel/overview'],
    ['#/intel/hot', '#/intel/overview'], ['#/frameworks/gold', '#/frameworks'], ['#/simulation/etf', '#/simulation/etf'],
    ['#/workbench/assets', '#/assets'], ['#/workbench/industry', '#/intel/overview'], ['#/workbench/etf-paper', '#/simulation/etf'],
  ]) {
    const html = shell.renderPrimaryRail(parseRoute(hash));
    const active = [...html.matchAll(/href="([^"]+)" class="rail-link active"/g)].map(item => item[1]);
    assert.deepEqual(active, [activeHref], hash);
  }
  assert.doesNotMatch(rail, /研究台|报告工作室|#\/workbench/);
});

test('asset module keeps only its two views and all four fund datasets with callable sources', async () => {
  const workbench = await import(new URL('workbench.mjs', root));
  const html = workbench.renderWorkbench({
    section: 'funds',
    catalog: {
      capabilities: [{ id: 'fund_data', description: '基金真实数据', source_count: 2, callable_source_count: 1 }],
      sources: [{ id: 'callable', name: '可调用来源', readiness: { callable: true } }, { id: 'pending', name: '待配置来源', readiness: { callable: false } }],
      bindings: [{ capability_id: 'fund_data', source_id: 'callable' }, { capability_id: 'fund_data', source_id: 'pending' }],
    },
  });
  for (const label of ['资产观察', '行情与基本面', '基金数据', '基本资料', '历史净值', '分红', '披露持仓']) assert.match(html, new RegExp(label));
  for (const dataset of ['profile', 'nav', 'distributions', 'holdings']) assert.match(html, new RegExp(`option value="${dataset}"`));
  assert.match(html, /name="source"/); assert.match(html, /option value="auto"/); assert.match(html, /option value="callable"/);
  assert.doesNotMatch(html, /option value="pending"/);
  assert.match(html, /name="start_date"/); assert.match(html, /name="end_date"/);
  assert.match(html, /data-capability="fund_data"/);
  assert.match(html, /href="#\/assets\/funds" class="active"[^>]+aria-current="page"/);
  assert.doesNotMatch(html, /#\/intel\/|#\/simulation\/|#\/workbench\/|研究台|上下游结构/);
  assert.match(html, /查询只在提交后联网/);
  assert.match(html, /data-workbench-handoff="fingpt"/);
  assert.match(html, /data-workbench-handoff="claw"/);
  assert.doesNotMatch(html, /演示|假数据|已完成/);
  const assets = workbench.renderWorkbench({ section: 'assets' });
  assert.match(assets, /href="#\/assets" class="active"[^>]+aria-current="page"/);
  assert.match(assets, /基金数据/);
});

test('topic search has intelligence navigation, three query tabs and no cross-session artifacts', async () => {
  const { renderWorkbench } = await import(new URL('workbench.mjs', root));
  const artifact = { name: 'other-session.pdf', size: 100, url: '/files/other', preview_url: '/preview/other' };
  for (const [section, kind, capability] of [['market', 'news', 'search_news'], ['industry', 'research', 'search_research'], ['documents', 'announcements', 'search_announcements']]) {
    const html = renderWorkbench({ section, artifacts: [artifact], catalog: { capabilities: [{ id: capability, callable_source_count: 1 }] } });
    assert.match(html, /研究情报/); assert.match(html, /主题检索/);
    for (const label of ['新闻', '研报', '公告']) assert.match(html, new RegExp(`>${label}</a>`));
    assert.match(html, new RegExp(`href="#/intel/search\\?kind=${kind}" class="active"[^>]+aria-current="page"`));
    assert.match(html, /href="#\/intel\/search" class="active"/);
    assert.doesNotMatch(html, /artifact-grid|other-session\.pdf|#\/assets\/|#\/workbench\/|上下游结构/);
    assert.match(html, new RegExp(`data-capability="${capability}"`));
    if (section === 'industry') assert.match(html, /行业与主题检索/);
  }
});

test('query results keep cutoff, missing data, failure states and explicit handoff snapshots', async () => {
  const { renderWorkbench } = await import(new URL('workbench.mjs', root));
  const html = renderWorkbench({ section: 'funds', queries: [{ section: 'funds', session_id: 'source-session', created_at: 1, status: 'completed', dataset: { dataset_id: 'snapshot-1', provider: 'provider', status: 'partial', row_count: 4, as_of: '2026-10-20', missing: ['持仓披露日期'], limitations: ['报告期不等于披露日期'] } }] });
  for (const text of ['provider', 'partial', '2026-10-20', '缺失：持仓披露日期', '限制：报告期不等于披露日期']) assert.ok(html.includes(text));
  assert.match(html, /data-source-session="source-session"/);
  assert.match(html, /data-dataset-ids="\[&quot;snapshot-1&quot;\]"/);
  const failed = renderWorkbench({ section: 'documents', queries: [{ section: 'documents', status: 'failed', failure_code: 'source_unavailable' }] });
  assert.match(failed, /查询失败：source_unavailable/);
  const disabled = renderWorkbench({ section: 'funds', busy: true, catalog: { capabilities: [{ id: 'fund_data', callable_source_count: 0 }] } });
  assert.match(disabled, /type="submit" disabled>当前没有可调用来源/);
  assert.match(disabled, /data-workbench-handoff="claw"[^>]*disabled/);
  const pending = renderWorkbench({ section: 'funds', queries: [{ section: 'funds', session_id: 'pending-session', status: 'running' }] });
  assert.match(pending, /查询执行中/);
  assert.match(pending, /data-workbench-handoff="claw"[^>]*disabled/);
});

test('snapshot manifest lookup is a read-only encoded request and propagates a missing snapshot', async () => {
  const { createAPI } = await import(new URL('core.mjs', root));
  const calls = [];
  const api = createAPI({ logger: () => {}, fetcher: async (path, options) => {
    calls.push({ path, options });
    return { ok: true, status: 200, json: async () => ({ dataset_id: 'snapshot', query: { code: '000001', dataset: 'holdings' } }) };
  } });
  assert.deepEqual((await api.datasetManifest('source/session', 'snapshot?1')).query, { code: '000001', dataset: 'holdings' });
  assert.equal(calls[0].path, '/api/research/sessions/source%2Fsession/datasets/snapshot%3F1');
  assert.equal(calls[0].options.method, 'GET');
  assert.equal(calls[0].options.body, undefined);
  const failed = createAPI({ logger: () => {}, fetcher: async () => ({ ok: false, status: 404, json: async () => ({ error: { code: 'dataset_not_found', message: '快照不存在' } }) }) });
  await assert.rejects(failed.datasetManifest('source', 'missing'), error => error.code === 'dataset_not_found' && error.message === '快照不存在');
});

test('query draft restores source, fund dataset and parameters after status rerenders', async () => {
  const { renderWorkbench } = await import(new URL('workbench.mjs', root));
  const catalog = {
    capabilities: [{ id: 'fund_data', callable_source_count: 1 }, { id: 'search_research', callable_source_count: 1 }],
    sources: [{ id: 'fund-source', name: '基金来源', readiness: { callable: true } }],
    bindings: [{ capability_id: 'fund_data', source_id: 'fund-source' }],
  };
  const html = renderWorkbench({ section: 'funds', catalog, queryDraft: { source: 'fund-source', parameters: { code: '510300', dataset: 'holdings', start_date: '2026-01-01', end_date: '2026-10-20' } } });
  assert.match(html, /option value="fund-source" selected/);
  assert.match(html, /name="code"[^>]*value="510300"/);
  assert.match(html, /option value="holdings" selected/);
  assert.match(html, /name="start_date" value="2026-01-01"/);
  assert.match(html, /name="end_date" value="2026-10-20"/);
  const search = renderWorkbench({ section: 'industry', catalog, queryDraft: { source: 'auto', parameters: { query: '<光模块>', limit: 7 } } });
  assert.match(search, /name="query"[^>]*value="&lt;光模块&gt;"/);
  assert.match(search, /name="limit"[^>]*value="7"/);
  const unavailable = renderWorkbench({ section: 'funds', catalog, queryDraft: { source: 'retired-source' } });
  assert.match(unavailable, /此前选择的来源当前不可调用/);
  assert.match(unavailable, /option value="auto" selected/);
  assert.doesNotMatch(unavailable, /option value="retired-source"/);
});

test('fund query reads its capability attribute even when the dataset field shadows form.dataset', async () => {
  const { readWorkbenchQuery } = await import(new URL('workbench.mjs', root));
  const form = {
    // Named form controls shadow built-in properties in the browser.
    dataset: { name: 'dataset', value: 'holdings' },
    getAttribute: name => name === 'data-capability' ? 'fund_data' : null,
  };
  const entries = [['source', 'fund-source'], ['code', '000001'], ['dataset', 'holdings'], ['start_date', '2026-01-01'], ['end_date', ''], ['limit', '20']];
  const OriginalFormData = globalThis.FormData;
  globalThis.FormData = class {
    constructor(target) { assert.equal(target, form); }
    entries() { return entries[Symbol.iterator](); }
    get(key) { return entries.find(([name]) => name === key)?.[1] ?? null; }
  };
  try {
    assert.deepEqual(readWorkbenchQuery(form), {
      capability: 'fund_data', source: 'fund-source',
      parameters: { code: '000001', dataset: 'holdings', start_date: '2026-01-01', limit: 20 },
    });
  } finally { globalThis.FormData = OriginalFormData; }
});

test('strategy simulation renders the existing ETF component without former research desk tabs', async () => {
  const { renderWorkbench } = await import(new URL('workbench.mjs', root));
  const html = renderWorkbench({ section: 'etf-paper', etfState: { readiness: { status: 'BLOCKED', gaps: ['真实数据待验证'] } } });
  assert.match(html, /ETF/);
  assert.match(html, /BLOCKED/);
  assert.doesNotMatch(html, /workbench-tabs|研究台|#\/workbench\//);
});

test('asset workspace renders independent states, native chart and personal observation tools', async () => {
  const assets = await import(new URL('asset-workspace.mjs', root));
  const observation = {
    id: 'observation-1', session_id: 'session-1', asset: '600519.SH', asset_type: 'stock',
    status: 'partial', dataset_ids: ['dataset-1'],
    blocks: {
      overview: { status: 'complete', dataset: { provider: 'akshare', as_of: '2026-09-05' } },
      history: { status: 'complete', dataset: { provider: 'akshare', as_of: '2026-09-05' } },
      financials: { status: 'error', failure_code: 'query_failed', dataset: null },
    },
  };
  const html = assets.renderAssetWorkspace({
    observation,
    rows: {
      overview: [{ asset: '600519.SH', name: '贵州茅台', price: 1500, change_pct: 2.1 }],
      history: [
        { date: '2026-09-04', open: 1482, high: 1498, low: 1476, close: 1490, volume: 10, turnover_rate: 0.42 },
        { date: '2026-09-05', open: 1492, high: 1512, low: 1488, close: 1500, volume: 12, turnover_rate: 0.51 },
      ],
    },
    watchlists: [{ id: 'w1', name: '核心观察', items: [] }], notes: [], alerts: [], notifications: [],
  });
  for (const label of ['资产概览', '历史行情', '财务指标', '开盘', '最高', '成交量', '换手率', '区间最高', '行情与技术指标', 'MACD', 'KDJ', 'RSI', 'BOLL', '当前覆盖限制', '筹码分布', '自选与观察', '提醒规则', '交给 FinGPT', '交给 Claw']) assert.match(html, new RegExp(label));
  assert.match(assets.renderAssetWorkspace({ observation, route: { assetView: 'holders' } }), /股东名称/);
  assert.match(assets.renderAssetWorkspace({ observation, route: { assetView: 'materials' } }), /行业PE/);
  assert.doesNotMatch(html, /macro-panel|各区块日期范围/);
  assert.match(html, /akshare/); assert.match(html, /2026-09-05/);
  assert.match(html, /data-asset-echarts[^>]+aria-label="K线与自定义副图；方向键选择历史交易日"/);
  assert.match(html, /data-asset-chip-chart[^>]+aria-label="同版本日线与逐日换手率估算筹码分布"/);
  assert.match(html, /换 <strong>0\.51%<\/strong>/);
  assert.match(html, /query_failed/);
  assert.doesNotMatch(html, /https?:\/\/[^" ]*(?:cdn|unpkg)|演示/);
});

test('asset terminal derives technical indicators only from supplied market bars', async () => {
  const { enrichMarketBars } = await import(new URL('asset-workspace.mjs', root));
  const rows = Array.from({ length: 40 }, (_, index) => ({
    date: new Date(Date.UTC(2026, 7, 1 + index)).toISOString().slice(0, 10),
    open: 100 + index, high: 102 + index, low: 99 + index, close: 101 + index,
    volume: 1000 + index * 10, turnover: 100000 + index * 1000,
    turnover_rate_pct: 1 + index / 100,
  }));
  const bars = enrichMarketBars(rows);
  const latest = bars.at(-1);
  assert.equal(bars.length, 40);
  for (const key of ['ma5', 'ma10', 'ma20', 'bollUpper', 'bollLower', 'dif', 'dea', 'macd', 'k', 'd', 'j', 'rsi']) {
    assert.equal(Number.isFinite(latest[key]), true, `${key} should be calculated`);
  }
  assert.equal(latest.amount, 139000);
  assert.ok(Math.abs(latest.turnover_rate_pct - 1.39) < 1e-12);
});
test('asset refresh actions remain unique inside the native source disclosure', async () => {
  const { renderAssetWorkspace } = await import(new URL('asset-workspace.mjs', root));
  const names = ['overview', 'history', 'valuation', 'financials', 'activity', 'margin', 'holders', 'research'];
  const observation = { asset: '600519.SH', asset_type: 'stock', blocks: Object.fromEntries(names.map(name => [name, { status: name === 'financials' ? 'loading' : 'complete', dataset: { dataset_id: name } }])) };
  const html = renderAssetWorkspace({ observation });
  const start = html.indexOf('<details class="asset-source-summary">');
  const source = html.slice(start, html.indexOf('</details>', start) + 10);
  assert.match(source, /已取得 0 · 待加载 11 · 查询失败 0 · 未接入 0/);
  for (const name of names.filter(name => name !== 'history')) {
    assert.equal((html.match(new RegExp(`data-asset-block-load="${name}"`, 'g')) || []).length, name === 'financials' ? 2 : 1, name);
    assert.ok(source.includes(`data-asset-block-load="${name}"`), name);
  }
  assert.doesNotMatch(source, /data-asset-block-load="history"/);
  assert.match(source, /历史行情使用上方图表控件更新/);
  assert.match(source, /data-asset-block-load="financials" disabled/);
  assert.match(source, /加载中 · 尚无快照/);
});

test('asset metrics keep canonical turnover amount separate from turnover rate', async () => {
  const assets = await import(new URL('asset-workspace.mjs', root));
  const html = assets.renderAssetWorkspace({
    observation: { asset: '600519.SH', asset_type: 'stock', blocks: {} },
    rows: { overview: [{ turnover: 3336029501, turnover_rate_pct: null }], history: [] },
  });
  assert.match(html, /成交额<\/dt><dd[^>]*>33\.36亿<\/dd>/);
  assert.match(html, /换手率<\/dt><dd[^>]*>—<\/dd>/);
  assert.doesNotMatch(html, /3,336,029,501%/);
});

test('asset workspace never turns absent market values into zero', async () => {
  const assets = await import(new URL('asset-workspace.mjs', root));
  const html = assets.renderAssetWorkspace({
    observation: { asset: '600519', asset_type: 'stock', blocks: {} },
    rows: { overview: [], history: [] },
  });
  for (const label of ['开盘', '最高', '最低', '成交量', '成交额', '换手率', '区间最高', '区间最低']) {
    assert.match(html, new RegExp(`${label}</dt><dd[^>]*>—</dd>`));
  }
});

test('asset financial table renders legacy boolean missing sentinels as unknown', async () => {
  const assets = await import(new URL('asset-workspace.mjs', root));
  const html = assets.renderAssetWorkspace({
    observation: {
      asset: '600519', asset_type: 'stock',
      blocks: {
        financials: { status: 'complete', dataset: { provider: 'akshare' } },
        activity: { status: 'complete', dataset: { provider: 'custom' } },
      },
    },
    rows: {
      financials: [{ 报告期: '1998-12-31', 净利润: '1.47亿', 净利润同比增长率: false }],
      activity: [{ provider_boolean: false }],
    },
  });
  const financials = assets.renderAssetWorkspace({ observation: { asset: '600519', asset_type: 'stock', blocks: { financials: { status: 'complete', dataset: { provider: 'akshare' } } } }, route: { assetView: 'financials' }, rows: { financials: [{ 报告期: '1998-12-31', 净利润: '1.47亿', 净利润同比增长率: false }] } });
  const activity = assets.renderAssetWorkspace({ observation: { asset: '600519', asset_type: 'stock', blocks: { activity: { status: 'complete', dataset: { provider: 'custom' } } } }, route: { assetView: 'capital' }, rows: { activity: [{ provider_boolean: false }] } });
  assert.match(financials, /<td>—<\/td>/);
  assert.doesNotMatch(financials, /<td>false<\/td>/);
  assert.match(activity, /<td>false<\/td>/);
});

test('operations page makes unknown usage and missing pricing explicit', async () => {
  const operations = await import(new URL('operations.mjs', root));
  const html = operations.renderOperations({
    usage: { tokens: { known: false }, cost: { status: 'not_configured' }, sessions: 0, turns: 0, models: [] },
    tools: { calls: 0, approvals: { approved: 0, denied: 0, cancelled: 0 }, running: [] },
    datahub: { calls: 0, outcomes: {}, sources: [], snapshots: { count: 0, bytes: 0 } },
    services: { services: [] },
    storage: { categories: [] },
  });
  for (const label of ['模型用量', 'Agent 与工具', 'DataHub', '服务状态', '存储占用']) assert.match(html, new RegExp(label));
  assert.match(html, /未知/);
  assert.match(html, /费用未配置/);
  assert.doesNotMatch(html, /data-restart|data-stop|data-delete|清库/);
});

test('app uses dedicated workbench, operations and report production modules', async () => {
  const source = await readFile(new URL('app.mjs', root), 'utf8');
  for (const expected of ['./workbench.mjs', './operations.mjs', './report-workspace.mjs', 'workbenchPage', 'operationsPage']) {
    assert.ok(source.includes(expected));
  }
  for (const removed of ['./report-studio.mjs', 'reportStudioPage']) assert.equal(source.includes(removed), false);
  assert.ok(source.includes('api.dataQueries(section)'));
  assert.ok(source.includes('loadAssetWorkspace'));
  assert.ok(source.includes('api.operationsSummary(operationsRange)'));
});

test('business pages never load or display the retired cross-session artifact catalog', async () => {
  const source = await readFile(new URL('app.mjs', root), 'utf8');
  assert.match(source, /if \(name === 'artifacts'\) return false/);
  assert.match(source, /if \(isDataWorkspaceRoute\(state\.route\)\) return workbenchPage\(\)/);
  const loader = source.slice(source.indexOf('async function loadWorkbench('), source.indexOf('async function loadAssetWorkspace('));
  assert.match(loader, /delete catalog\.errors\.artifacts/);
  assert.match(loader, /loadAssetWorkspace\(current\)/);
  assert.doesNotMatch(loader, /loadCatalog\(\['artifacts'|api\.artifacts\(/);
});
