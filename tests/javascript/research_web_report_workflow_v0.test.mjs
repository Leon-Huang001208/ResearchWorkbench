import assert from 'node:assert/strict';
import test from 'node:test';

const root = new URL('../../app/research_web/ui/', import.meta.url);

const reportWorkflow = () => ({
  id: 'huaan-etf-weekly',
  kind: 'workflow',
  name: '华安 ETF 周报',
  description: '使用锁定模板与刷新后的 Excel 底稿生成周报。',
  category: '报告生产',
  status: 'enabled',
  enabled: true,
  version: 4,
  metadata: {
    default_formats: ['docx', 'html', 'xlsx'],
    report_workflow: {
      package_version: 4,
      published: true,
      readiness: 'ready',
      resources: [
        { kind: 'template', path: 'templates/report.docx', name: '周报 Word 模板' },
        { kind: 'workbook', path: 'workbooks/source.xlsx', name: 'Wind Excel 底稿' },
      ],
      providers: [{ id: 'wind', name: 'Wind', required: true, status: 'unverified' }],
      schedule: { kind: 'weekly', enabled: true, label: '每周五 17:00 · Asia/Shanghai' },
      runs: [{ id: 'run-1', status: 'blocked_data', created_at: '2026-09-05T09:00:00Z' }],
      artifacts: [{ id: 'file-1', name: '华安ETF周报.docx', format: 'docx' }],
      delivery: { status: 'complete' },
    },
  },
  steps: [
    { client_key: 'prepare-data', type: '取数', title: '准备数据', instruction: '形成共享快照', tools: ['datahub_get_market_bars'] },
    { client_key: 'refresh-workbook', type: '刷新底稿', title: '刷新 Excel', instruction: '刷新并完整重算', tools: ['workbook_refresh'] },
  ],
});

test('legacy report route redirects exactly to the Workflow capability view', async () => {
  const { parseRoute, legacyRouteTarget } = await import(new URL('core.mjs', root));
  assert.equal(legacyRouteTarget('#/reports'), '#/skills?kind=workflow');
  assert.equal(legacyRouteTarget('#/reports/'), '#/skills?kind=workflow');
  assert.equal(legacyRouteTarget('#/reports-old'), null);
  assert.equal(legacyRouteTarget('#/reports?project=huaan'), null);
  assert.deepEqual(parseRoute('#/skills?kind=workflow'), { page: 'skills', sessionId: null, capabilityKind: 'workflow' });
});

test('report Workflow information architecture lives inside capability detail', async () => {
  const { renderCapabilityDetail } = await import(new URL('capabilities.mjs', root));
  const html = renderCapabilityDetail(reportWorkflow());
  for (const label of ['报告 Workflow', '模板与底稿', '结构化步骤', '数据与插件要求', '版本', '一次 / 每周日程', '历史运行', '产物']) {
    assert.match(html, new RegExp(label));
  }
  assert.match(html, /templates\/report\.docx/);
  assert.match(html, /workbooks\/source\.xlsx/);
  assert.match(html, /blocked_data/);
  assert.doesNotMatch(html, /data-report-status|data-run-report-project/);
});

test('Claw landing report Workflow cards only place a locked version into draft', async () => {
  const { renderQuickSkills } = await import(new URL('composer.mjs', root));
  const html = renderQuickSkills([reportWorkflow()], { page: 'claw' });
  assert.match(html, /报告 Workflow/);
  assert.match(html, /Word 模板 · Excel 底稿/);
  assert.match(html, /锁定 v4 放入草稿/);
  assert.match(html, /data-skill-shortcut="huaan-etf-weekly"/);
  assert.doesNotMatch(html, /type="submit"|data-run-report|立即执行/);
});

test('real migrated report Workflows have a dedicated Claw shelf and package detail', async () => {
  const { renderReportWorkflowShelf, renderReportWorkflowDetail } = await import(new URL('report-workflows.mjs', root));
  const summary = {
    id: 'chinext-50-weekly', name: '创业板50周报', description: '基于固定 Word 模板与 Wind/iFinD 底稿生成周报。',
    status: 'enabled', current_version: 1, delivery_formats: ['docx', 'html', 'xlsx'], providers: ['wind_excel', 'ifind_excel'], latest_run: null,
  };
  const shelf = renderReportWorkflowShelf([summary]);
  for (const expected of ['创业板50周报', 'DOCX / HTML / XLSX', 'wind_excel、ifind_excel', '查看模板与底稿', '交给 Claw 执行']) assert.match(shelf, new RegExp(expected));
  assert.match(shelf, /data-report-workflow-detail="chinext-50-weekly"/);
  assert.match(shelf, /data-run-report-workflow="chinext-50-weekly"/);
  const detail = renderReportWorkflowDetail({
    ...summary,
    versions: [{ version: 1, current: true, published: true, manifest: {
      resources: [{ role: 'template', path: 'templates/report.docx', size: 1024 }, { role: 'workbook', path: 'workbooks/source.xlsx', size: 2048 }, { role: 'workbook', path: 'workbooks/创业板50周报（Wind版）.xlsx', size: 2048 }],
      providers: [{ provider: 'wind_excel', required: true }, { provider: 'ifind_excel', required: true }],
      workbook_policies: [{ workbook: 'workbooks/source.xlsx', providers: [{ provider: 'wind_excel' }, { provider: 'ifind_excel' }] }],
      excluded_workbooks: ['workbooks/创业板50周报（Wind版）.xlsx'],
      blocks: [{ kind: 'chart', title: '站位图', required: true }],
    }}],
    providers_status: [{ id: 'wind_excel', integration_state: 'ready', health: 'untested', ready: false, code: 'needs_probe' }],
    runs: [{
      id: 'run-live', status: 'delivery_incomplete', delivery_status: 'incomplete', version: 1, trigger: 'manual',
      session_id: '11111111-1111-4111-8111-111111111111', dataset_snapshot_sha256: 'a'.repeat(64),
      refresh_manifests: ['refresh-manifests/manifest.json'],
      subagents: [{ id: 'agent-1', name: '行业研究', status: 'completed' }],
      artifacts: [{ name: 'report.docx', format: 'docx', url: '/api/research/sessions/session/files/file' }],
      missing: ['block:industry'],
    }],
    schedule: { enabled: false }, historical_artifacts: [{ name: '创业板50周报.docx', size: 4096 }],
  });
  for (const expected of ['templates/report.docx', 'workbooks/source.xlsx', 'wind_excel + ifind_excel', '站位图', '创业板50周报.docx']) assert.ok(detail.includes(expected));
  for (const expected of ['保留但不运行', '检测 Wind Excel', 'data-probe-report-provider="wind_excel"', 'run-live', '失败重试']) assert.ok(detail.includes(expected));
  for (const expected of ['刷新清单 1', '共享快照', '行业研究', 'report.docx', 'block:industry', '#/claw?session=11111111-1111-4111-8111-111111111111']) assert.ok(detail.includes(expected));
});

test('report Workflow selection requires its own published ready package version', async () => {
  const { reportWorkflowEligibility, renderCapabilityCatalog, renderCapabilityDetail } = await import(new URL('capabilities.mjs', root));
  const { renderQuickSkills } = await import(new URL('composer.mjs', root));
  const ready = reportWorkflow();
  assert.deepEqual(reportWorkflowEligibility(ready), { report: ready.metadata.report_workflow, eligible: true, version: 4, reason: '' });
  for (const report of [
    { published: true, readiness: 'ready' },
    { package_version: 4, readiness: 'ready' },
    { package_version: 4, published: true, readiness: 'blocked' },
  ]) {
    const unavailable = { ...ready, metadata: { ...ready.metadata, report_workflow: report } };
    const eligibility = reportWorkflowEligibility(unavailable);
    assert.equal(eligibility.eligible, false);
    const landing = renderQuickSkills([unavailable], { page: 'claw' });
    assert.match(landing, /报告 Workflow 暂不可用/);
    assert.match(landing, /data-skill-shortcut="huaan-etf-weekly"[^>]*disabled/);
    assert.doesNotMatch(landing, /锁定 v4 放入草稿/);
    assert.match(renderCapabilityCatalog({ items: [unavailable], kind: 'workflow' }), /data-use-skill="huaan-etf-weekly" disabled/);
    assert.match(renderCapabilityDetail(unavailable), /data-use-skill="huaan-etf-weekly" disabled/);
  }
  const disabled = { ...ready, enabled: false, status: 'disabled' };
  assert.deepEqual(reportWorkflowEligibility(disabled), { report: disabled.metadata.report_workflow, eligible: false, version: 4, reason: '能力已停用' });
  for (const html of [
    renderQuickSkills([disabled], { page: 'claw' }),
    renderCapabilityCatalog({ items: [disabled], kind: 'workflow' }),
    renderCapabilityDetail(disabled),
  ]) {
    assert.match(html, /能力已停用/);
    assert.match(html, /data-(?:skill-shortcut|use-skill)="huaan-etf-weekly"[^>]*disabled/);
  }
});

test('Claw session summary is read-only and does not claim execution evidence', async () => {
  const { renderLockedWorkflowSummary } = await import(new URL('shell.mjs', root));
  const html = renderLockedWorkflowSummary({
    mode: 'claw',
    capability: { id: 'huaan-etf-weekly', version: 4, name: '华安 ETF 周报' },
    report_workflow: { workflow_id: 'huaan-etf-weekly', version: 4, delivery_status: 'validating' },
  });
  assert.match(html, /锁定 Workflow/);
  assert.match(html, /华安 ETF 周报/);
  assert.match(html, /v4/);
  assert.match(html, /交付校验中/);
  assert.match(html, /只读摘要/);
  assert.doesNotMatch(html, /已完成步骤|data-complete/);
});

test('workflow editor keeps stable client keys and focus feedback while rows move', async () => {
  const { ensureStepKeys, moveStep, moveStepWithFeedback, readEditor, renderCapabilityEditor } = await import(new URL('capability-editor.mjs', root));
  const steps = ensureStepKeys([{ title: '取数', type: '取数' }, { title: '刷新', type: '刷新底稿' }], (() => { let id = 0; return () => `step-${++id}`; })());
  assert.deepEqual(steps.map(step => step.client_key), ['step-1', 'step-2']);
  const moved = moveStep(steps, 1, -1);
  assert.deepEqual(moved.map(step => step.client_key), ['step-2', 'step-1']);
  const feedback = moveStepWithFeedback(steps, 1, -1);
  assert.deepEqual(feedback.steps.map(step => step.client_key), ['step-2', 'step-1']);
  assert.equal(feedback.focusId, 'cap-step-step-2-move-up');
  assert.match(feedback.announcement, /刷新.*第 1 步/);
  const html = renderCapabilityEditor({ draft: { kind: 'workflow', metadata: {}, files: [], steps: moved }, announcement: feedback.announcement });
  assert.match(html, /data-step-key="step-2"/);
  assert.match(html, /id="cap-step-step-2-move-up"/);
  assert.match(html, /aria-label="上移步骤 刷新"/);
  assert.match(html, /aria-live="polite"[^>]*>刷新已移动到第 1 步/);
  assert.match(html, /步骤类型/);
  for (const type of ['取数', '刷新底稿', '检索', '分析', '段落', '图表', '表格', '文件组装', '交付检查']) assert.match(html, new RegExp(type));

  const values = new FormData();
  values.append('step-0-title', '刷新');
  values.append('step-0-type', '刷新底稿');
  values.append('step-0-instruction', '刷新并校验');
  const read = readEditor(values, { kind: 'workflow', metadata: {}, files: [], steps: moved });
  assert.equal(read.steps[0].client_key, 'step-2');
  assert.equal(read.steps[0].type, '刷新底稿');
});

test('standalone report studio front-end and unreachable adapters are removed', async () => {
  const fs = await import('node:fs');
  assert.equal(fs.existsSync(new URL('report-studio.mjs', root)), false);
  const core = fs.readFileSync(new URL('core.mjs', root), 'utf8');
  for (const dead of ['reportProjects:', 'createReportProject:', 'runReportProject:']) assert.equal(core.includes(dead), false);
  assert.match(core, /saveReportSchedule:/);
  const css = fs.readFileSync(new URL('styles.css', root), 'utf8');
  assert.doesNotMatch(css, /report-studio-layout|report-project-card|report-overview-grid/);
});
