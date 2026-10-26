import assert from 'node:assert/strict';
import test from 'node:test';

const moduleURL = new URL('../../app/research_web/ui/weekly-production.mjs', import.meta.url);

test('report visibility requires the attached primary administrator in server mode', async () => {
  const { canUseReportWorkflows } = await import(moduleURL);
  assert.equal(canUseReportWorkflows(null, null), true);
  assert.equal(canUseReportWorkflows('u', { role: 'admin', primary: true }), true);
  assert.equal(canUseReportWorkflows('u', { role: 'admin', primary: false }), false);
  assert.equal(canUseReportWorkflows('u', { role: 'user', primary: true }), false);
});

test('a completed file delivery alone never unlocks the upgraded weekly schedule', async () => {
  const { weeklyManualRunAccepted, weeklyScheduleDefaults } = await import(moduleURL);
  const detail = { id: 'huaan-etf-weekly', current_version: 4, weekly_production: { enabled: true }, runs: [
    { trigger: 'manual', version: 4, status: 'completed', delivery_status: 'complete' },
  ] };
  assert.equal(weeklyManualRunAccepted(detail), false);
  Object.assign(detail.runs[0], { quality_status: 'passed', finalization_status: 'finalized' });
  assert.equal(weeklyManualRunAccepted(detail), true);
  detail.runs[0].version = 3;
  assert.equal(weeklyManualRunAccepted(detail), false);
  assert.deepEqual(weeklyScheduleDefaults({ id: 'huaan-etf-weekly' }), {
    kind: 'weekly', enabled: false, timezone: 'Asia/Shanghai', weekday: 4, hour: 15, minute: 30,
  });
});

test('weekly status separates data, quality, delivery and finalization and escapes gaps', async () => {
  const { renderWeeklyProductionStatus } = await import(moduleURL);
  const html = renderWeeklyProductionStatus({ id: 'huaan-etf-weekly', current_version: 1, weekly_production: {
    enabled: true, data_source: 'wind_client_api', provider: { status: 'blocked_dependency' },
    latest: { version: 1, weekly_data_source: 'wind_client_api', quality_status: 'incomplete', finalization_status: 'blocked', delivery_status: 'complete',
      weekly_data_assessment: { status: 'passed' }, missing: ['<unsafe>'], weekly_cutoff: '2026-10-23T15:30:00+08:00' },
  } });
  for (const label of ['数据就绪', '内容质量', '文件交付', '正式定稿', '周五 15:30', 'incomplete', '&lt;unsafe&gt;']) {
    assert.ok(html.includes(label), label);
  }
  assert.ok(!html.includes('<unsafe>'));
  assert.ok(html.includes('2026-10-23T15:30:00+08:00'));
  assert.ok(html.includes('data-weekly-state="passed">已通过'));
  assert.equal(renderWeeklyProductionStatus({ id: 'other' }), '');
});

test('API acceptance stays historical after publishing an Excel successor', async () => {
  const { renderWeeklyProductionStatus } = await import(moduleURL);
  const old = { id: 'api-history', version: 1, weekly_data_source: 'wind_client_api', session_id: 'old-session',
    quality_status: 'passed', finalization_status: 'finalized', delivery_status: 'complete', weekly_data_assessment: { status: 'passed' } };
  const detail = { id: 'huaan-etf-weekly', current_version: 2, weekly_production: {
    enabled: true, data_source: 'wind_excel', latest: old, provider: { status: 'unverified' },
  }, runs: [old] };
  const html = renderWeeklyProductionStatus(detail);
  const current = html.match(/<dl[^>]*data-weekly-current-acceptance[^>]*>([\s\S]*?)<\/dl>/)?.[1];
  assert.ok(current, 'current acceptance must have its own explicit boundary');
  assert.ok(!current.includes('passed') && !current.includes('finalized'));
  assert.ok(html.includes('当前生产验收：v2 · Wind Excel'));
  assert.ok(html.includes('当前版本及来源尚无运行验收'));
  assert.ok(html.includes('历史运行（不计当前验收） · v1 · Wind Client API'));
  assert.ok(html.includes('#/claw?session=old-session'));
  assert.equal(detail.runs[0], old);
});

test('current acceptance requires matching version and an explicit matching frozen source', async () => {
  const { renderWeeklyProductionStatus } = await import(moduleURL);
  const currentRun = { id: 'excel-current', version: 2, weekly_data_source: 'wind_excel', quality_status: 'incomplete', finalization_status: 'blocked' };
  const html = renderWeeklyProductionStatus({ id: 'huaan-etf-weekly', current_version: 2,
    weekly_production: { enabled: true, data_source: 'wind_excel' }, runs: [
      { id: 'wrong-source', version: 2, weekly_data_source: 'wind_client_api', quality_status: 'passed', finalization_status: 'finalized' },
      { id: 'unknown-source', version: 2, quality_status: 'passed', finalization_status: 'finalized' }, currentRun,
    ] });
  const current = html.match(/<dl[^>]*data-weekly-current-acceptance[^>]*>([\s\S]*?)<\/dl>/)?.[1];
  assert.ok(current?.includes('incomplete') && current.includes('blocked'));
  assert.ok(!current.includes('passed') && !current.includes('finalized'));
  assert.ok(html.includes('当前验收运行：excel-current · v2 · Wind Excel'));
  assert.ok(html.includes('历史运行（不计当前验收） · v2 · 来源未记录'));
  assert.ok(html.includes('历史运行（不计当前验收） · v2 · Wind Client API'));
});

test('explicit Excel policy displays its source and leaves API successor preparation available', async () => {
  const { renderWeeklyProductionStatus } = await import(moduleURL);
  const excel = renderWeeklyProductionStatus({ id: 'huaan-etf-weekly', weekly_production: {
    enabled: true, data_source: 'wind_excel', provider: { status: 'unverified' },
  } });
  assert.ok(excel.includes('Wind Excel（原始导出与工作表取数）'));
  assert.ok(excel.includes('依赖就绪不代表数据已核验'));
  assert.ok(excel.includes('既有 Excel 实例中新建任务专用临时工作簿'));
  assert.ok(!excel.includes('data-prepare-weekly-production'));
  assert.equal((await import(moduleURL)).weeklyManualRunAccepted({ id: 'huaan-etf-weekly', current_version: 1,
    weekly_production: { enabled: true, data_source: 'wind_excel' }, runs: [{ version: 1, trigger: 'manual', status: 'completed', delivery_status: 'complete', quality_status: 'passed', finalization_status: 'finalized' }] }), false);
  assert.ok(excel.includes('暂不支持启用定时'));
  const api = renderWeeklyProductionStatus({ id: 'huaan-etf-weekly', weekly_production: {
    enabled: true, data_source: 'wind_client_api',
  } });
  assert.ok(api.includes('Wind Client API'));
  assert.ok(api.includes('data-prepare-weekly-production'));
});

test('explicit historical acceptance remains separate from current formal acceptance', async () => {
  const { renderWeeklyProductionStatus, weeklyManualRunAccepted } = await import(moduleURL);
  const historical = { id: 'historical', version: 4, weekly_data_source: 'wind_excel',
    execution_purpose: 'historical_acceptance', trigger: 'manual', status: 'historical_acceptance',
    quality_status: 'passed', delivery_status: 'complete', finalization_status: 'not_eligible_historical' };
  const detail = { id: 'huaan-etf-weekly', current_version: 4, weekly_production: {
    enabled: true, data_source: 'wind_excel', latest: historical }, runs: [historical] };
  const html = renderWeeklyProductionStatus(detail);
  const current = html.match(/<dl[^>]*data-weekly-current-acceptance[^>]*>([\s\S]*?)<\/dl>/)?.[1];
  assert.ok(!current.includes('passed'));
  assert.ok(html.includes('data-run-historical-report-workflow="huaan-etf-weekly"'));
  assert.ok(html.includes('历史验收稿（不得作为正式定稿）'));
  assert.equal(weeklyManualRunAccepted(detail), false);
  // Even a dishonest passed/finalized row cannot contribute a historical run.
  Object.assign(historical, { status: 'completed', finalization_status: 'finalized' });
  detail.weekly_production.data_source = 'wind_client_api';
  assert.equal(weeklyManualRunAccepted(detail), false);
});
