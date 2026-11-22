import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { parseRoute } from '../../app/research_web/ui/core.mjs';
import { renderPrimaryRail } from '../../app/research_web/ui/shell.mjs';

const load = () => import('../../app/research_web/ui/progress.mjs');
const repo = 'https://github.com/Leon-Huang001208/ResearchWorkbench';
function fixture() {
  const feature = { id: 'research', module: '研究与报告', title: '研究功能', summary: '用户收益', scope: '功能范围', next: '完成核验', owner: '项目维护者', source: `${repo}/pull/264`, updated: '2026-11-05', status: 'developing', platforms: ['macos'], included: true, activation: 'unknown', limitations: '其他平台未验证', evidence: [] };
  return { schemaVersion: 1, asOf: '2026-11-05', features: [feature], releases: [] };
}
function delivered(feature) {
  feature.status = 'delivered';
  feature.evidence = [{ kind: 'merge', label: '合并记录', url: `${repo}/pull/264` }, ...['constraints','web','macos'].map(gate => ({ kind: 'validation', gate, result: 'passed', label: gate, url: `${repo}/actions/runs/41849189263` }))];
  return feature;
}

test('progress routes retain shareable filters and stable detail/month IDs', () => {
  const route = parseRoute('#/progress/changelog?kind=fix&module=研究与报告&item=release-1&month=2026-10');
  assert.equal(route.page, 'progress'); assert.equal(route.progressTab, 'changelog');
  assert.equal(route.progressKind, 'fix'); assert.equal(route.progressModule, '研究与报告');
  assert.equal(route.progressItem, 'release-1'); assert.equal(route.progressMonth, '2026-10');
  assert.equal(parseRoute('#/progress').progressTab, 'overview');
  assert.equal(parseRoute('#/progress/unknown').progressInvalid, true);
  assert.equal(parseRoute('#/progress?item=../bad&month=2026-13').progressItem, '');
});
test('progress entry exists in single-user and account footers', () => {
  for (const account of [null, { username: 'viewer', id: 'u1' }]) {
    const html = renderPrimaryRail({ page: 'progress', account });
    assert.match(html, /navigation-footer[\s\S]*href="#\/progress"/);
    assert.match(html, /title="研发进展"[^>]*aria-current="page"/);
  }
});
test('content validation rejects duplicate IDs, invalid dates and missing associations', async () => {
  const { validateProgress } = await load();
  assert.equal(validateProgress(fixture()).features.length, 1);
  const duplicate = fixture(); duplicate.features.push({ ...duplicate.features[0] });
  assert.throws(() => validateProgress(duplicate), /duplicate/);
  const numeric = fixture(); numeric.features[0].id = 123;
  assert.throws(() => validateProgress(numeric), /id/);
  const date = fixture(); date.features[0].updated = '2026-02-30';
  assert.throws(() => validateProgress(date), /date/);
  const future = fixture(); future.features[0].updated = '2026-11-06';
  assert.throws(() => validateProgress(future), /date/);
  const orphan = fixture(); orphan.releases.push({ id: 'release-1', featureId: 'missing', date: '2026-11-05', kind: 'fix', title: '修复', summary: '修复说明' });
  assert.throws(() => validateProgress(orphan), /association/);
});
test('delivered requires merge and every required acceptance gate; activation stays independent', async () => {
  const { validateProgress, renderProgress } = await load();
  const data = fixture(); data.features[0].status = 'delivered';
  assert.throws(() => validateProgress(data), /evidence/);
  delivered(data.features[0]);
  const accepted = validateProgress(data);
  const html = renderProgress({ data: accepted }, parseRoute('#/progress'));
  assert.match(html, /已交付/); assert.match(html, /启用情况[^<]*<[^>]+>未确认|启用情况[\s\S]*未确认/);
  assert.match(html, /其他平台未验证/); assert.doesNotMatch(html, /所有平台已通过|已自动启用/);
  data.features[0].evidence = data.features[0].evidence.filter(e => e.gate !== 'macos');
  assert.throws(() => validateProgress(data), /evidence/);
});
test('release events cannot turn incomplete feature acceptance into a delivery', async () => {
  const { validateProgress } = await load(); const data = fixture();
  data.releases.push({ id: 'release-1', featureId: 'research', date: '2026-11-05', kind: 'new', title: '新增功能', summary: '已交付说明' });
  assert.throws(() => validateProgress(data), /evidence/);
});
test('unsafe links and internal paths are rejected; prose is escaped', async () => {
  const { validateProgress, renderProgress } = await load();
  for (const url of ['javascript:alert(1)', 'https://evil.test/a', 'https://github.com.evil.test/x', `${repo}/pull/1?token=secret`]) {
    const data = fixture(); data.features[0].source = url; assert.throws(() => validateProgress(data), /link/);
  }
  const internal = fixture(); internal.features[0].summary = '/Users/leon/private'; assert.throws(() => validateProgress(internal), /private/);
  const data = fixture(); data.features[0].title = '<img src=x onerror=alert(1)>';
  const html = renderProgress({ data: validateProgress(data) }, parseRoute('#/progress'));
  assert.match(html, /&lt;img/); assert.doesNotMatch(html, /<img src=x/);
});
test('filters, descending dates and month links preserve each other', async () => {
  const { validateProgress, renderProgress, progressHref } = await load(); const data = fixture();
  data.features.push({ ...data.features[0], id: 'older', updated: '2026-10-31', module: '数据与资产', title: '旧功能' });
  const clean = validateProgress(data); const route = parseRoute('#/progress?status=developing');
  const html = renderProgress({ data: clean }, route);
  assert.ok(html.indexOf('2026-11-05') < html.indexOf('2026-10-31'));
  const href = progressHref(route, { month: '2026-10', item: 'older' });
  assert.match(href, /status=developing/); assert.match(href, /month=2026-10/); assert.match(href, /item=older/);
  const empty = renderProgress({ data: clean }, parseRoute('#/progress?module=不存在'));
  assert.match(empty, /没有符合筛选条件/);
  const missing = renderProgress({ data: clean }, parseRoute('#/progress?item=missing'));
  assert.match(missing, /该条目不存在或不符合当前筛选/);
});
test('static loader distinguishes network failure from invalid content and supports explicit retry', async () => {
  const { createProgressController } = await load(); let calls = 0; const events = [];
  const controller = createProgressController({ logger: name => events.push(name), fetcher: async () => { calls++; if(calls === 1) throw new Error('offline'); return { ok: true, json: async () => fixture() }; } });
  await controller.load(); assert.equal(controller.state.error, 'load_failed'); assert.equal(calls, 1);
  await controller.load({ retry: true }); assert.equal(controller.state.error, ''); assert.equal(calls, 2);
  await controller.load(); assert.equal(calls, 2); assert.ok(events.includes('progress_load_failed'));
  const invalid = createProgressController({ fetcher: async () => ({ ok: true, json: async () => ({}) }) });
  await invalid.load(); assert.equal(invalid.state.error, 'invalid_content');
});
test('body timeouts are loading failures and syntax errors are invalid content', async () => {
  const { createProgressController } = await load();
  const stalled = createProgressController({ timeoutMs: 5, fetcher: async () => ({ ok: true, json: () => new Promise(() => {}) }) });
  await stalled.load(); assert.equal(stalled.state.error, 'load_failed');
  const syntax = createProgressController({ fetcher: async () => ({ ok: true, json: async () => { throw new SyntaxError('json'); } }) });
  await syntax.load(); assert.equal(syntax.state.error, 'invalid_content');
});
test('bundled content rejects unrecognized containers and private absolute paths', async () => {
  const { validateProgress } = await load();
  const nested = fixture(); nested.features[0].debug = { privatePath: '/Users/example/private', api_key: 'SYNTHETIC' };
  assert.throws(() => validateProgress(nested), /fields/);
  for (const value of ['/private/var/tmp/report', '/tmp/private-task/file', 'C:\\Users\\example\\private']) {
    const data = fixture(); data.features[0].summary = value; assert.throws(() => validateProgress(data), /private/);
  }
});
test('URL detail navigation reopens disclosures after existing disclosure state restoration', async () => {
  const { focusProgressTarget } = await load();
  const detail = { open: false }; const target = { querySelector: () => detail, getBoundingClientRect: () => ({ top: 100 }), focus() {} };
  const main = { scrollTop: 0, getBoundingClientRect: () => ({ top: 20 }) };
  const root = { querySelector: selector => selector === '#main' ? main : selector.startsWith('#progress-item-') ? target : null };
  focusProgressTarget(root, { progressItem: 'research' });
  assert.equal(detail.open, true); assert.equal(main.scrollTop, 64);
  focusProgressTarget(root, {}); assert.equal(main.scrollTop, 0);
});
test('clicking the current detail link reopens it without requiring hashchange', async () => {
  const { createProgressWorkspace } = await load(); const previous = globalThis.window;
  const events = {}; const detail = { open: false }; let prevented = false;
  const article = { querySelector: () => detail, getBoundingClientRect: () => ({ top: 20 }), focus() {} };
  const main = { scrollTop: 10, getBoundingClientRect: () => ({ top: 0 }) };
  const hash = '#/progress?item=research';
  const root = { addEventListener: (type, handler) => { events[type] = handler; }, querySelector: selector => selector === '#main' ? main : selector.startsWith('#progress-item-') ? article : null };
  try {
    globalThis.window = { location: { hash } };
    createProgressWorkspace({ root, route: () => parseRoute(hash), notify() {}, logger() {} });
    events.click({ target: { closest: selector => selector === '[data-progress-target]' ? { hash } : null }, preventDefault: () => { prevented = true; } });
    assert.equal(prevented, true); assert.equal(detail.open, true);
    prevented = false; detail.open = false;
    events.click({ ctrlKey: true, button: 0, target: { closest: selector => selector === '[data-progress-target]' ? { hash } : null }, preventDefault: () => { prevented = true; } });
    assert.equal(prevented, false); assert.equal(detail.open, false);
  } finally { if (previous === undefined) delete globalThis.window; else globalThis.window = previous; }
});
test('changelog generation preserves historical bytes and refuses stale or broken sections', async t => {
  const { checkProductProgress } = await import('../../scripts/check_product_progress.mjs');
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'rwb-progress-doc-test-'));
  t.after(() => fs.rmSync(folder, { recursive: true }));
  fs.mkdirSync(path.join(folder, 'app/research_web/ui'), { recursive: true }); fs.mkdirSync(path.join(folder, 'docs'));
  fs.writeFileSync(path.join(folder, 'app/research_web/ui/progress-data.json'), JSON.stringify(fixture()));
  const doc = path.join(folder, 'docs/CHANGELOG.md'); const history = '\n## 旧历史\n\n原始记录和日期保持。\n';
  fs.writeFileSync(doc, '# Changelog\n' + history);
  assert.throws(() => checkProductProgress(folder), /out_of_date/);
  checkProductProgress(folder, { write: true }); assert.ok(fs.readFileSync(doc, 'utf8').endsWith(history));
  assert.equal(checkProductProgress(folder).status, 'PASS');
  fs.appendFileSync(doc, '<!-- product-progress:generated:start -->');
  assert.throws(() => checkProductProgress(folder, { write: true }), /markers_invalid/);
});
test('checked-in snapshot and generated changelog share the same delivery records', async () => {
  const { validateProgress, changelogSection } = await load();
  const data = validateProgress(JSON.parse(await readFile(new URL('../../app/research_web/ui/progress-data.json', import.meta.url), 'utf8')));
  assert.ok(data.features.length >= 4); assert.ok(data.releases.length >= 3);
  const doc = await readFile(new URL('../../docs/CHANGELOG.md', import.meta.url), 'utf8');
  assert.ok(doc.includes(changelogSection(data)));
});
