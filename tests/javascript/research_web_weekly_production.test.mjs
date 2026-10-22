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
  const html = renderWeeklyProductionStatus({ id: 'huaan-etf-weekly', weekly_production: {
    enabled: true, provider: { status: 'blocked_dependency' },
    latest: { quality_status: 'incomplete', finalization_status: 'blocked', delivery_status: 'complete',
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
