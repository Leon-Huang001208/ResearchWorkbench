import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { parseRoute, legacyRouteTarget } from '../../app/research_web/ui/core.mjs';
import { renderPrimaryRail } from '../../app/research_web/ui/shell.mjs';
import { reportHref, selectReportRun, reportRunStatus, renderReportWorkspace } from '../../app/research_web/ui/report-workspace.mjs';

const detail = { id: 'huaan-etf-weekly', name: '华安ETF周报', status: 'enabled', current_version: 6, delivery_formats: ['docx'], versions: [{ current: true, version: 6, manifest: { resources: [], blocks: [] } }], runs: [
  { id: 'a'.repeat(32), version: 6, status: 'failed', execution_purpose: 'historical_acceptance', quality_status: 'pending', finalization_status: 'blocked' },
  { id: 'b'.repeat(32), version: 5, status: 'cancelled', research_submission_state: 'unknown', monitoring_disposition: 'ended_by_user', quality_status: 'invalid', finalization_status: 'invalidated', artifacts: [{ url: '/api/research/files/old.docx', name: 'old.docx' }] },
] };
test('report routes restore project, tab, run and directory filters', () => {
  const route = parseRoute(reportHref(detail.id, 'history', detail.runs[1].id));
  assert.equal(route.page, 'reports'); assert.equal(route.reportProjectId, detail.id);
  assert.equal(legacyRouteTarget('#/reports'), null);
  assert.equal(route.reportTab, 'history'); assert.equal(route.reportRunId, detail.runs[1].id);
  assert.equal(parseRoute('#/reports?q=ETF&status=needs_attention').reportQuery, 'ETF');
  assert.equal(parseRoute('#/reports/../../x').reportInvalid, true);
});
test('report navigation keeps existing primary-admin restriction', () => {
  assert.match(renderPrimaryRail({ page: 'reports' }), /href="#\/reports"[^>]*aria-current="page"/);
  assert.doesNotMatch(renderPrimaryRail({ account: { id: 'user', role: 'user', primary: false } }), /href="#\/reports"/);
});
test('run selection never substitutes a different run for a missing ID', () => {
  assert.equal(selectReportRun(detail, '').id, detail.runs[0].id);
  assert.equal(selectReportRun(detail, detail.runs[1].id).version, 5);
  assert.equal(selectReportRun(detail, 'c'.repeat(32)), null);
  assert.match(reportRunStatus(detail.runs[1]), /未知.*监控已结束/);
});
test('directory counts and filters actual projects without inventing a new project', () => {
  const items = [detail, { id: 'ai-weekly', name: '<AI>', status: 'needs_attention' }];
  const html = renderReportWorkspace({ allowed: true, items, route: { reportStatus: 'needs_attention' } });
  assert.match(html, /1 个报告项目/); assert.match(html, /&lt;AI&gt;/);
  assert.doesNotMatch(html, /data-run-report-workflow|华安ETF周报|新建报告/);
});
test('selected historical run keeps its own version, quality and invalid-file block', () => {
  const html = renderReportWorkspace({ allowed: true, detail, route: { reportProjectId: detail.id, reportRunId: detail.runs[1].id, reportTab: 'production' } });
  assert.match(html, /v5/); assert.match(html, /无效|完整性/); assert.match(html, /受理未知/);
  assert.doesNotMatch(html, /href="\/api\/research\/files\/old.docx"/);
  assert.doesNotMatch(html, /data-retry-report-run="bbbb/);
});
test('missing run and forbidden project do not render another record or operation', () => {
  assert.match(renderReportWorkspace({ allowed: true, detail, route: { reportProjectId: detail.id, reportRunId: 'c'.repeat(32) } }), /记录不存在/);
  const forbidden = renderReportWorkspace({ allowed: false, detail, items: [detail], route: {} });
  assert.match(forbidden, /权限/); assert.doesNotMatch(forbidden, /华安ETF|data-run-/);
});
test('preview and download use backend-bound valid files only', () => {
  const files = [
    { name: 'valid', valid: true, url: '/api/research/files/good', preview_url: '/api/research/files/good/preview' },
    { name: 'changed', valid: false, url: '/api/research/files/changed' },
    { name: '<external>', url: 'https://example.com/bad', preview_url: 'javascript:bad' },
  ];
  const html = renderReportWorkspace({ allowed: true, detail: { ...detail, runs: [{ ...detail.runs[0], artifacts: files }] }, route: { reportProjectId: detail.id } });
  assert.match(html, /href="\/api\/research\/files\/good\/preview"/);
  assert.match(html, /href="\/api\/research\/files\/good"/);
  assert.doesNotMatch(html, /href="\/api\/research\/files\/changed"|href="https:|href="javascript:/);
  assert.match(html, /&lt;external&gt;/);
});

test('invalidated quality blocks the same file in production and raw evidence', () => {
  const run = { ...detail.runs[0], quality_status: 'invalidated', artifacts: [{ valid: true, name: 'bad.docx', url: '/api/research/files/bad' }] };
  const html = renderReportWorkspace({ allowed: true, detail: { ...detail, runs: [run] }, route: { reportProjectId: detail.id } });
  assert.doesNotMatch(html, /href="\/api\/research\/files\/bad"/);
});

async function mutationHarness(kind, api) {
  const source = await readFile(new URL('../../app/research_web/ui/app.mjs', import.meta.url), 'utf8');
  const start = source.indexOf(kind === 'run' ? "  if ('runReportWorkflow' in data ||" : "  if ('cancelReportRun' in data) {");
  const end = source.indexOf(kind === 'run' ? "  if ('probeReportProvider' in data) {" : "  if ('retryReportRun' in data) {", start);
  assert.ok(start > 0 && end > start);
  const helper = source.slice(source.indexOf('async function refreshReportMutation('), source.indexOf('async function loadReportPage('));
  return new Function('api', 'reportHref', `
    let pageGeneration=1; let reportWorkflowDetail={id:'a'}; let reportWorkflowBusy=false;
    const reportWorkflowsAllowed=true; let success=''; const state={error:'',route:{page:'reports',reportProjectId:'a'}};
    const navigations=[]; const history={pushState(...args){navigations.push(args)}};
    const render=()=>{}; const safeLog=()=>{}; const loadCatalog=async()=>{}; const showRoute=async()=>{};
    ${helper}
    return {execute:async(data)=>{${source.slice(start,end)}},
      move(){pageGeneration++;reportWorkflowDetail={id:'b'};state.route.reportProjectId='b'},
      snapshot(){return {detail:reportWorkflowDetail,success,navigations,busy:reportWorkflowBusy}}};
  `)(api, reportHref);
}

test('a late production response neither navigates away from another project nor submits twice', async () => {
  let resolve; let calls=0;
  const pending = new Promise(done => {resolve=done});
  const harness = await mutationHarness('run', {runReportWorkflow(){calls++;return pending}});
  const first = harness.execute({runReportWorkflow:'a'});
  await harness.execute({runReportWorkflow:'a'}); assert.equal(calls,1);
  harness.move(); resolve({workflow_id:'a',id:'c'.repeat(32),status:'running',session_id:'owned'});
  await first; const result=harness.snapshot();
  assert.equal(result.detail.id,'b'); assert.equal(result.success,''); assert.deepEqual(result.navigations,[]);
});

test('a late detail read following cancellation cannot replace another project', async () => {
  let resolve;
  const harness = await mutationHarness('cancel', {cancelReportRun:async()=>({status:'needs_attention'}), reportWorkflow:()=>new Promise(done=>{resolve=done})});
  const action=harness.execute({cancelReportRun:'old'});
  await Promise.resolve(); assert.equal(typeof resolve,'function');
  harness.move(); resolve({id:'a'}); await action;
  assert.equal(harness.snapshot().detail.id,'b'); assert.equal(harness.snapshot().success,'');
});
