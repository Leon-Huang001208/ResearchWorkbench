import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';

const root = new URL('../../app/research_web/ui/', import.meta.url);

test('routes and navigation expose research desk and read-only operations', async () => {
  const { parseRoute } = await import(new URL('core.mjs', root));
  const shell = await import(new URL('shell.mjs', root));
  assert.equal(parseRoute('#/workbench?section=funds').page, 'workbench');
  assert.equal(parseRoute('#/workbench?section=funds').section, 'funds');
  assert.equal(parseRoute('#/workbench/funds').section, 'funds');
  assert.equal(parseRoute('#/operations').page, 'operations');
  const rail = shell.renderPrimaryRail({ page: 'workbench' });
  for (const label of ['研究台', '运行与用量']) assert.match(rail, new RegExp(label));
});

test('research desk renders six real-state sections and explicit handoff actions', async () => {
  const workbench = await import(new URL('workbench.mjs', root));
  const html = workbench.renderWorkbench({
    section: 'funds',
    catalog: { capabilities: [], sources: [] },
    queries: [],
    artifacts: [],
  });
  for (const label of ['市场', '资产', '基金', '产业链', '资料', '报告']) assert.match(html, new RegExp(label));
  assert.match(html, /data-workbench-handoff="fingpt"/);
  assert.match(html, /data-workbench-handoff="claw"/);
  assert.doesNotMatch(html, /演示|假数据|已完成/);
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

test('app uses dedicated workbench and operations modules', async () => {
  const source = await readFile(new URL('app.mjs', root), 'utf8');
  for (const expected of ['./workbench.mjs', './operations.mjs', 'workbenchPage', 'operationsPage']) {
    assert.ok(source.includes(expected));
  }
  assert.ok(source.includes('api.dataQueries(section)'));
  assert.ok(source.includes('api.operationsSummary(operationsRange)'));
});
