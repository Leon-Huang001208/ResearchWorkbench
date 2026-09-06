import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';

const root = new URL('../../app/research_web/ui/', import.meta.url);

test('routes and navigation expose research desk and read-only operations without a report studio', async () => {
  const { parseRoute } = await import(new URL('core.mjs', root));
  const shell = await import(new URL('shell.mjs', root));
  assert.equal(parseRoute('#/workbench?section=funds').page, 'workbench');
  assert.equal(parseRoute('#/workbench?section=funds').section, 'funds');
  assert.equal(parseRoute('#/workbench/funds').section, 'funds');
  assert.equal(parseRoute('#/operations').page, 'operations');
  const rail = shell.renderPrimaryRail({ page: 'workbench' });
  for (const label of ['资产观察', '研究台', '运行与用量']) assert.match(rail, new RegExp(label));
  const assetRail = shell.renderPrimaryRail({ page: 'workbench', section: 'assets' });
  assert.match(assetRail, /href="#\/workbench\/assets" class="rail-link active"[^>]*aria-current="page"/);
  assert.doesNotMatch(assetRail, /href="#\/workbench" class="rail-link active"/);
  assert.doesNotMatch(rail, /报告工作室|#\/reports/);
});

test('research desk renders five real-state sections and gives reports a dedicated module', async () => {
  const workbench = await import(new URL('workbench.mjs', root));
  const html = workbench.renderWorkbench({
    section: 'funds',
    catalog: { capabilities: [], sources: [] },
    queries: [],
    artifacts: [],
  });
  for (const label of ['市场', '资产', '基金', '产业链', '资料']) assert.match(html, new RegExp(label));
  assert.doesNotMatch(html, />报告</);
  assert.match(html, /data-workbench-handoff="fingpt"/);
  assert.match(html, /data-workbench-handoff="claw"/);
  assert.doesNotMatch(html, /演示|假数据|已完成/);
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
      history: [{ date: '2026-09-04', close: 1490, volume: 10 }, { date: '2026-09-05', close: 1500, volume: 12 }],
    },
    watchlists: [{ id: 'w1', name: '核心观察', items: [] }], notes: [], alerts: [], notifications: [],
  });
  for (const label of ['资产概览', '历史行情', '财务指标', '开盘', '最高', '成交量', '52周高', '同类比较', '主题暴露', '来源与口径', '自选与观察', '提醒规则', '交给 FinGPT', '交给 Claw']) assert.match(html, new RegExp(label));
  assert.match(html, /akshare · 截止 2026-09-05/);
  assert.match(html, /<svg[^>]+aria-label="历史收盘价走势"/);
  assert.match(html, /query_failed/);
  assert.doesNotMatch(html, /echarts|chart\.js|unpkg|演示/);
});

test('asset workspace never turns absent market values into zero', async () => {
  const assets = await import(new URL('asset-workspace.mjs', root));
  const html = assets.renderAssetWorkspace({
    observation: { asset: '600519', asset_type: 'stock', blocks: {} },
    rows: { overview: [], history: [] },
  });
  for (const label of ['开盘', '最高', '最低', '成交量', '成交额', '换手率', '52周高', '52周低']) {
    assert.match(html, new RegExp(`${label}</dt><dd>—</dd>`));
  }
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

test('app uses dedicated workbench and operations modules without a report studio route', async () => {
  const source = await readFile(new URL('app.mjs', root), 'utf8');
  for (const expected of ['./workbench.mjs', './operations.mjs', 'workbenchPage', 'operationsPage']) {
    assert.ok(source.includes(expected));
  }
  for (const removed of ['./report-studio.mjs', 'reportStudioPage', "state.route.page === 'reports'"]) assert.equal(source.includes(removed), false);
  assert.ok(source.includes('api.dataQueries(section)'));
  assert.ok(source.includes('loadAssetWorkspace'));
  assert.ok(source.includes('api.operationsSummary(operationsRange)'));
});
