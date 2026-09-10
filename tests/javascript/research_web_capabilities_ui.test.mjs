import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { accessSync, constants } from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { createAPI, createController } from '../../app/research_web/ui/core.mjs';
import * as composer from '../../app/research_web/ui/composer.mjs';
import * as shell from '../../app/research_web/ui/shell.mjs';

const root = new URL('../../app/research_web/ui/', import.meta.url);
const projectRoot = fileURLToPath(new URL('../../', import.meta.url));
const cap = (extra = {}) => ({ id: 'my-skill', kind: 'skill', name: '我的研究', description: '真实资料', category: '资料研究', status: 'enabled', enabled: true, version: 2, builtin: false, metadata: { default_formats: ['md'], inputs: [{ name: 'file', label: '资料', type: 'file', required: true }], scenarios: ['研究'], required_tools: [], dependencies: [] }, ...extra });
const load = (name) => import(new URL(name, root));
const session = () => ({ id: 's1', mode: 'fingpt', status: 'idle', messages: [] });

function projectPython({ callerCwd = process.cwd(), environment = process.env } = {}) {
  const executable = process.platform === 'win32' ? path.join('Scripts', 'python.exe') : path.join('bin', 'python');
  const override = environment.RWB_TEST_PYTHON;
  if (override) {
    const resolved = path.resolve(callerCwd, override);
    try { accessSync(resolved, constants.X_OK); return resolved; }
    catch { throw new Error(`RWB_TEST_PYTHON is not an executable file: ${resolved}`); }
  }
  const candidates = [
    path.join(projectRoot, '.venv', executable),
    path.basename(path.dirname(projectRoot)) === '.worktrees'
      ? path.join(path.dirname(path.dirname(projectRoot)), '.venv', executable)
      : null,
    environment.VIRTUAL_ENV ? path.join(environment.VIRTUAL_ENV, executable) : null,
  ].filter(Boolean);
  for (const candidate of [...new Set(candidates)]) {
    try { accessSync(candidate, constants.X_OK); return candidate; }
    catch { /* Try the next explicit project environment. */ }
  }
  throw new Error(`No project Python found. Set RWB_TEST_PYTHON to an executable interpreter. Checked: ${candidates.join(', ')}`);
}

function productBuiltinResearchSkills() {
  const marker = '__RWB_CAPABILITY_CATALOG__';
  const script = [
    'import json, tempfile',
    'from pathlib import Path',
    'from app.research_web.capabilities.catalog import CapabilityCatalog',
    'with tempfile.TemporaryDirectory(prefix="rwb-ui-capabilities-") as directory:',
    '    catalog = CapabilityCatalog(Path(directory))',
    `    print(${JSON.stringify(marker)} + json.dumps(catalog.list(kind="skill"), ensure_ascii=False))`,
  ].join('\n');
  const result = spawnSync(projectPython(), ['-c', script], {
    cwd: projectRoot,
    encoding: 'utf8',
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
  });
  if (result.error || result.status !== 0) {
    throw new Error(`Product CapabilityCatalog failed (status ${result.status ?? 'spawn-error'}): ${result.error?.message || result.stderr || result.stdout}`);
  }
  const payload = result.stdout.split(/\r?\n/).find(line => line.startsWith(marker));
  if (!payload) throw new Error(`Product CapabilityCatalog returned no marked JSON payload. stdout: ${result.stdout}`);
  return JSON.parse(payload.slice(marker.length)).items;
}

test('relative Python override resolves once against the caller cwd and runs from the worktree', () => {
  const executable = process.platform === 'win32' ? path.join('Scripts', 'python.exe') : path.join('bin', 'python');
  const ownerRoot = path.basename(path.dirname(projectRoot)) === '.worktrees'
    ? path.dirname(path.dirname(projectRoot))
    : projectRoot;
  const relativeOverride = path.join('.venv', executable);
  const resolved = projectPython({
    callerCwd: ownerRoot,
    environment: { ...process.env, RWB_TEST_PYTHON: relativeOverride },
  });
  assert.equal(resolved, path.resolve(ownerRoot, relativeOverride));
  assert.equal(path.isAbsolute(resolved), true);
  const probe = spawnSync(resolved, ['-c', 'print("rwb-relative-python-ok")'], {
    cwd: projectRoot,
    encoding: 'utf8',
  });
  assert.equal(probe.error, undefined);
  assert.equal(probe.status, 0, probe.stderr);
  assert.equal(probe.stdout.trim(), 'rwb-relative-python-ok');
});

test('one catalog filters kind, source, category and Chinese search, including disabled entries for inspection', async () => {
  const { filterCapabilities, renderCapabilityCatalog } = await load('capabilities.mjs');
  const items = [cap(), cap({ id: 'builtin', builtin: true }), cap({ id: 'off', status: 'disabled', enabled: false }), cap({ id: 'wf', kind: 'workflow' })];
  assert.deepEqual(filterCapabilities(items, { kind: 'skill', source: 'mine', category: '资料研究', query: '真实' }).map(x => x.id), ['my-skill', 'off']);
  assert.match(renderCapabilityCatalog({ items, kind: 'skill', query: '不存在' }), /没有匹配/);
  assert.match(renderCapabilityCatalog({ items, kind: 'skill' }), /已停用/);
  assert.match(renderCapabilityCatalog({ items: [], error: '读取失败' }), /读取失败/);
});

test('capability workspace preserves legacy links and exposes four stable primary kinds', async () => {
  const { parseRoute } = await load('core.mjs');
  const { capabilityWorkspaceHash, capabilityWorkspaceKindKey } = await load('capability-workspace.mjs');
  assert.deepEqual(parseRoute('#/skills'), { page: 'skills', sessionId: null, capabilityView: 'library', capabilityKind: 'skill' });
  assert.deepEqual(parseRoute('#/skills?kind=tool'), { page: 'skills', sessionId: null, capabilityView: 'library', capabilityKind: 'tool' });
  assert.deepEqual(parseRoute('#/skills?view=mine&kind=workflow'), { page: 'skills', sessionId: null, capabilityView: 'mine', capabilityKind: 'workflow' });
  assert.deepEqual(parseRoute('#/skills?view=plans'), { page: 'skills', sessionId: null, capabilityView: 'plans', capabilityKind: 'workflow' });
  assert.deepEqual(parseRoute('#/skills?view=connections'), { page: 'skills', sessionId: null, capabilityView: 'connections', capabilityKind: 'tool' });
  assert.deepEqual(parseRoute('#/skills?kind=data&view=connections'), { page: 'skills', sessionId: null, capabilityView: 'connections', capabilityKind: 'data' });
  assert.deepEqual(parseRoute('#/skills?kind=tool&view=market'), { page: 'skills', sessionId: null, capabilityView: 'market', capabilityKind: 'tool' });
  assert.deepEqual(parseRoute('#/skills?kind=skill&view=market'), { page: 'skills', sessionId: null, capabilityView: 'library', capabilityKind: 'skill' });
  assert.deepEqual(parseRoute('#/skills?kind=tool&view=mine'), { page: 'skills', sessionId: null, capabilityView: 'library', capabilityKind: 'tool' });
  assert.deepEqual(parseRoute('#/skills?view=unknown'), { page: 'skills', sessionId: null, capabilityView: 'library', capabilityKind: 'skill' });
  assert.equal(capabilityWorkspaceHash('tool', 'connections'), '#/skills?kind=tool&view=connections');
  assert.equal(capabilityWorkspaceHash('tool', 'market'), '#/skills?kind=tool&view=market');
  assert.equal(capabilityWorkspaceHash('data'), '#/skills?kind=data');
  assert.deepEqual(capabilityWorkspaceKindKey('ArrowRight', 'skill'), { handled: true, kind: 'tool' });
  assert.deepEqual(capabilityWorkspaceKindKey('ArrowLeft', 'skill'), { handled: true, kind: 'data' });
  assert.deepEqual(capabilityWorkspaceKindKey('End', 'skill'), { handled: true, kind: 'data' });
  assert.deepEqual(capabilityWorkspaceKindKey('Enter', 'tool'), { handled: false });
});

test('capability workspace isolates Skill, Tool, Workflow and data into separate primary panels', async () => {
  const { collectCapabilityWorkspaceEntries, filterCapabilityWorkspaceEntries, renderCapabilityWorkspace } = await load('capability-workspace.mjs');
  const capabilities = [cap(), cap({ id: 'built', builtin: true, name: '内置能力' }), cap({ id: 'flow', kind: 'workflow', name: '我的流程', status: 'disabled', enabled: false })];
  const tools = [{ id: 'read_data', name: '读数据', description: '只读', selectable: true }];
  const dataCatalog = { summary: {}, sources: [], capabilities: [{ id: 'bars', name: '行情', description: '真实行情', category: '行情', tool_id: 'read_data', source_count: 2, callable_source_count: 1 }] };
  const entries = collectCapabilityWorkspaceEntries({ capabilities, tools, dataCatalog });
  assert.deepEqual(entries.map(item => item.kind), ['skill', 'skill', 'workflow', 'tool', 'data']);
  assert.deepEqual(filterCapabilityWorkspaceEntries(entries, { view: 'mine', kind: 'skill' }).map(item => item.id), ['my-skill']);
  assert.deepEqual(filterCapabilityWorkspaceEntries(entries, { view: 'mine', kind: 'workflow' }).map(item => item.id), ['flow']);
  assert.deepEqual(filterCapabilityWorkspaceEntries(entries, { kind: 'data', status: 'available' }).map(item => item.id), ['bars']);
  const skillHTML = renderCapabilityWorkspace({ capabilities, tools, dataCatalog, kind: 'skill' });
  const toolHTML = renderCapabilityWorkspace({ capabilities, tools, dataCatalog, kind: 'tool' });
  const workflowHTML = renderCapabilityWorkspace({ capabilities, tools, dataCatalog, kind: 'workflow' });
  const dataHTML = renderCapabilityWorkspace({ capabilities, tools, dataCatalog, kind: 'data' });
  for (const html of [skillHTML, toolHTML, workflowHTML, dataHTML]) {
    for (const label of ['Skill', 'Tool', 'Workflow', '数据']) assert.match(html, new RegExp(`>${label}<`));
    assert.doesNotMatch(html, /data-cap-kind-filter|\bNEW\b|热门|排名/);
  }
  assert.match(skillHTML, /我的研究/); assert.doesNotMatch(skillHTML, /我的流程|读数据|真实行情/);
  assert.match(toolHTML, /读数据/); assert.doesNotMatch(toolHTML, /我的研究|我的流程|真实行情/);
  assert.match(workflowHTML, /我的流程/); assert.doesNotMatch(workflowHTML, /我的研究|读数据|真实行情/);
  assert.match(dataHTML, /真实行情/); assert.doesNotMatch(dataHTML, /我的研究|我的流程|读数据/);
  assert.match(skillHTML, /能力库.*我的 Skill/s); assert.match(toolHTML, /工具目录.*MCP 市场.*连接状态/s);
  assert.match(workflowHTML, /能力库.*我的 Workflow.*运行计划/s); assert.match(dataHTML, /数据能力.*数据源与连接/s);
});

test('capability quicklook is an accessible dialog with truthful disabled reasons and draft-only use', async () => {
  const { renderCapabilityPreviewDialog } = await load('capability-workspace.mjs');
  const available = renderCapabilityPreviewDialog({ detail: { ...cap(), draft: {} } });
  assert.match(available, /role="dialog"/); assert.match(available, /aria-modal="true"/);
  assert.match(available, /data-use-skill="my-skill"/); assert.match(available, /立即使用/);
  assert.match(available, /data-cap-manage="my-skill"/); assert.match(available, /data-cap-close/);
  const blocked = renderCapabilityPreviewDialog({ detail: { ...cap({ enabled: false, status: 'blocked_dependencies', metadata: { ...cap().metadata, dependencies: ['missing-lib'] } }), draft: {} } });
  assert.match(blocked, /依赖不足/); assert.match(blocked, /missing-lib/); assert.match(blocked, /立即使用<\/button>/);
  assert.match(blocked, /data-use-skill="my-skill" disabled/);
  assert.doesNotMatch(renderCapabilityPreviewDialog({ tool: { id: 'x', name: '<img>', description: '<script>', selectable: false } }), /<img>|<script>/);
});

test('capability center renders, filters, opens and selects every built-in Skill without a router card', async () => {
  const { filterCapabilities, renderCapabilityCatalog, renderCapabilityDetail } = await load('capabilities.mjs');
  const builtinResearchSkills = productBuiltinResearchSkills();
  assert.equal(builtinResearchSkills.length, 11);
  assert.equal(new Set(builtinResearchSkills.map(item => item.id)).size, 11);
  assert.equal(builtinResearchSkills.every(item => item.kind === 'skill' && item.builtin && item.enabled), true);

  const catalog = renderCapabilityCatalog({ items: builtinResearchSkills, kind: 'skill' });
  const selectableIDs = [...catalog.matchAll(/data-use-skill="([^"]+)"/g)].map(match => match[1]);
  assert.deepEqual(selectableIDs, builtinResearchSkills.map(item => item.id));
  for (const item of builtinResearchSkills) {
    assert.ok(catalog.includes(item.name));
    assert.ok(catalog.includes(`<option value="${item.category}"`));
  }

  for (const category of new Set(builtinResearchSkills.map(item => item.category))) {
    const expected = builtinResearchSkills.filter(item => item.category === category).map(item => item.id);
    assert.deepEqual(filterCapabilities(builtinResearchSkills, { kind: 'skill', category }).map(item => item.id), expected);
  }

  const chineseItem = builtinResearchSkills.find(item => /[\u3400-\u9fff]/u.test(item.name));
  assert.ok(chineseItem, 'real catalog must contain a Chinese Skill name');
  const chineseQuery = chineseItem.name.match(/[\u3400-\u9fff]{2,}/u)[0].slice(0, 2);
  assert.ok(filterCapabilities(builtinResearchSkills, { kind: 'skill', query: chineseQuery }).some(item => item.id === chineseItem.id));

  const technicalItem = builtinResearchSkills.find(item => item.id.includes('-'));
  assert.ok(technicalItem, 'real catalog must contain a technical Skill ID');
  assert.deepEqual(filterCapabilities(builtinResearchSkills, { kind: 'skill', query: technicalItem.id }).map(item => item.id), [technicalItem.id]);

  const detail = renderCapabilityDetail(builtinResearchSkills.find(item => item.id === 'sell-side-report-reader'));
  assert.match(detail, /研报增量分析/);
  assert.match(detail, /research_run_script、web_search/);
  assert.match(detail, /无需文件/);
  assert.match(detail, /data-use-skill="sell-side-report-reader"/);
  assert.doesNotMatch(catalog, /zhengyan-research-router/);
});

test('capability kind tabs implement roving keyboard tabs and owned panels', async () => {
  const { capabilityTabKey, renderCapabilityCatalog } = await load('capabilities.mjs');
  assert.deepEqual(capabilityTabKey('ArrowRight', 'skill'), { handled: true, kind: 'tool' });
  assert.deepEqual(capabilityTabKey('ArrowLeft', 'skill'), { handled: true, kind: 'data' });
  assert.deepEqual(capabilityTabKey('Home', 'workflow'), { handled: true, kind: 'skill' });
  assert.deepEqual(capabilityTabKey('End', 'tool'), { handled: true, kind: 'data' });
  assert.deepEqual(capabilityTabKey('Enter', 'tool'), { handled: false });
  const html = renderCapabilityCatalog({ items: [cap()], kind: 'skill' });
  assert.match(html, /id="capability-tab-skill"[^>]*tabindex="0"[^>]*aria-controls="capability-panel-skill"/);
  assert.match(html, /id="capability-tab-tool"[^>]*tabindex="-1"/);
  assert.match(html, /id="capability-panel-skill" role="tabpanel"[^>]*aria-labelledby="capability-tab-skill"/);
  const selectedTab = html.match(/<button[^>]*id="capability-tab-skill"[^>]*>/)?.[0] || '';
  assert.match(selectedTab, /aria-selected="true"/);
  assert.match(selectedTab, /class="button"/);
  assert.doesNotMatch(selectedTab, /\bprimary\b/);
});

test('capability details escape hostile content and separate builtin read-only state from editable drafts', async () => {
  const { renderCapabilityDetail } = await load('capabilities.mjs');
  const html = renderCapabilityDetail(cap({ name: '<img src=x onerror=alert(1)>', builtin: true, draft: { instructions: '<script>bad</script>', files: [], steps: [] } }));
  assert.doesNotMatch(html, /<img|<script|data-cap-edit/);
  assert.match(html, /data-cap-copy/);
  assert.match(html, /资料.*file/s);
  assert.match(html, /my-skill/);
  assert.match(renderCapabilityDetail(cap({ status: 'disabled', enabled: false })), /data-use-skill="my-skill" disabled/);
});

test('tools are read-only declarations with selection only for selectable research tools', async () => {
  const { renderToolDetail } = await load('capabilities.mjs');
  const tool = { id: 'datahub_get_fund_data', name: '基金数据', selectable: true, parameters: { type: 'object' }, conditions: ['每次审批'], approval: 'native-per-call' };
  assert.match(renderToolDetail(tool), /data-use-tool="datahub_get_fund_data"/);
  assert.match(renderToolDetail(tool), /每次审批/);
  assert.doesNotMatch(renderToolDetail({ ...tool, selectable: false }), /data-use-tool/);
  assert.doesNotMatch(renderToolDetail({ ...tool, id: 'datahub_get_fund_data', selectable: false }), /data-use-tool/);
});

test('data catalog separates capabilities from sources and never turns registered code into availability', async () => {
  const { filterDataCatalog, renderDataCatalog, renderDataCapabilityDetail, renderDataSourceDetail } = await load('data-catalog.mjs');
  const readiness = { code_exists: true, integration_completed: false, configured: false, dependency_ready: false, allowed: false, callable: false, integration_state: 'disabled', health: 'untested' };
  const catalog = {
    summary: { capabilities: 1, sources: 2, callable_sources: 1, needs_configuration: 1, unavailable: 0 },
    capabilities: [{ id: 'market_bars', name: '历史行情', category: '行情', description: '历史行情', tool_id: 'datahub_get_market_bars', parameters: [], fields: ['date', 'close'], markets: ['A股'], source_count: 2, callable_source_count: 0 }],
    sources: [{ id: 'wind', name: 'Wind', family: 'formal', source_type: 'professional', description: '终端来源', auth_type: 'terminal', config_keys: [], dependencies: ['WindPy'], markets: ['A股'], fee: 'account', readiness }],
  };
  assert.deepEqual(filterDataCatalog(catalog, { view: 'capabilities', query: '行情' }).map(item => item.id), ['market_bars']);
  assert.deepEqual(filterDataCatalog(catalog, { view: 'sources', auth: 'terminal' }).map(item => item.id), ['wind']);
  const html = renderDataCatalog({ catalog });
  assert.match(html, /按数据能力/); assert.match(html, /按数据来源/); assert.match(html, /有代码.*不等于.*已适配/s);
  assert.doesNotMatch(renderDataCatalog({ catalog, showViewSwitch: false }), /data-view-switch/);
  assert.match(html, /data-cap-preview-trigger="data:market_bars"/);
  assert.match(html, /data-use-data-tool="datahub_get_market_bars" disabled/);
  const detail = renderDataCapabilityDetail({ ...catalog.capabilities[0], bindings: [{ source: catalog.sources[0], priority: 1, datasets: ['daily'] }] });
  assert.match(detail, /目前没有.*不能运行/s);
  assert.match(renderDataSourceDetail({ ...catalog.sources[0], bindings: [] }), /代码存在.*DataHub 已适配.*配置齐备/s);
});

test('completed source probes refresh the open source detail without touching another detail', async () => {
  const { refreshProbedSourceDetail } = await load('capability-controller.mjs');
  const calls = [];
  const api = { dataSource: async id => { calls.push(id); return { id, readiness: { health: 'healthy' } }; } };
  assert.equal(await refreshProbedSourceDetail(api, { id: 'wind' }, 'cls'), null);
  assert.deepEqual(await refreshProbedSourceDetail(api, { id: 'cls' }, 'cls'), { id: 'cls', readiness: { health: 'healthy' } });
  assert.deepEqual(calls, ['cls']);
});

test('workflow steps are ordered templates, never completed activity evidence', async () => {
  const { renderWorkflowPlan } = await load('capabilities.mjs');
  const html = renderWorkflowPlan({ kind: 'workflow', id: 'wf', version: 3, steps: [{ title: '核对资料', instruction: '读取来源', skill_id: 'my-skill', tools: ['research_run_script'] }] });
  assert.match(html, /预设步骤.*不代表.*执行/s);
  assert.match(html, /核对资料/);
  assert.doesNotMatch(html, /已完成|completed|data-complete/);
});

test('package editor preserves complete file bytes, removes server issues, and reorders steps explicitly', async () => {
  const { editableDraft, moveStep, renderCapabilityEditor } = await load('capability-editor.mjs');
  const draft = { kind: 'workflow', metadata: cap().metadata, instructions: '', files: [{ path: 'x.png', base64: 'raw==', sha256: 'a', size: 4 }], steps: [{ title: '一' }, { title: '二' }], reviewed_scripts: ['hash'], import_issues: ['bad'] };
  const clean = editableDraft(draft);
  assert.deepEqual(clean.files, [{ path: 'x.png', base64: 'raw==' }]);
  assert.equal(clean.import_issues, undefined);
  assert.deepEqual(moveStep(clean.steps, 1, -1).map(x => x.title), ['二', '一']);
  assert.deepEqual(draft.steps.map(x => x.title), ['一', '二']);
  assert.match(renderCapabilityEditor({ draft: clean, items: [cap()], tools: [] }), /data-step-move/);
});

test('API uses real capability lifecycle, version and single-file import endpoints', async () => {
  const calls = [];
  const api = createAPI({ fetcher: async (url, options) => { calls.push([url, options]); return new Response('{}'); }, logger() {} });
  await api.capabilities(); await api.tools(); await api.capability('a/b');
  await api.saveCapability('a/b', { kind: 'skill' });
  await api.capabilityAction('a/b', 'rollback', { version: 1 });
  await api.capabilityVersion('a/b', 1);
  await api.importCapability(new File(['raw'], 'SKILL.md'));
  assert.deepEqual(calls.slice(0, 3).map(x => x[0]), ['/api/research/capabilities', '/api/research/tools', '/api/research/capabilities/a%2Fb']);
  assert.equal(calls[3][1].method, 'PATCH');
  assert.equal(calls[4][0], '/api/research/capabilities/a%2Fb/rollback');
  assert.equal(calls[6][1].body.get('file').name, 'SKILL.md');
});

test('selected capability version and tool intent survive drafts, send retries and explicit format precedence', async () => {
  const bodies = []; const keys = [];
  const controller = createController({ api: { detail: async () => session(), message: async (_id, body, key) => { bodies.push(body); keys.push(key); throw new Error('活动回合冲突'); } }, makeID: () => 'stable' });
  await controller.open({ page: 'fingpt', sessionId: 's1' });
  controller.setCapability(cap()); controller.setTools(['datahub_get_fund_data']); controller.setDraft('问题'); controller.setFormats([]);
  await controller.open({ page: 'history', sessionId: null }); await controller.open({ page: 'fingpt', sessionId: 's1' });
  await controller.send(); await controller.send();
  assert.equal(bodies[0].capability_id, 'my-skill'); assert.equal(bodies[0].capability_version, 2);
  assert.deepEqual(bodies[0].tool_ids, ['datahub_get_fund_data']); assert.deepEqual(bodies[0].expected_formats, []);
  assert.deepEqual(keys, ['stable', 'stable']); assert.equal(controller.state.draft, '问题');
  controller.setFormats(null); await controller.send(); assert.equal('expected_formats' in bodies[2], false);
});

test('creation session only adopts the returned draft and never sends a model request', async () => {
  let sends = 0; const navigations = [];
  const controller = createController({ api: { createCapabilitySession: async () => ({ ...session(), draft: '制作真实候选包' }), detail: async () => session(), message: async () => { sends++; } }, onNavigate: hash => navigations.push(hash) });
  await controller.createCapabilitySession('skill', '目标');
  await controller.open({ page: 'fingpt', sessionId: 's1' });
  assert.equal(controller.state.draft, '制作真实候选包'); assert.equal(sends, 0); assert.equal(navigations.length, 1);
});

test('slash keyboard selection consumes arrows, Enter and Escape without accidental submission', () => {
  assert.deepEqual(composer.slashKey('ArrowDown', 0, [cap()]), { handled: true, index: 0 });
  assert.deepEqual(composer.slashKey('Enter', 0, [cap()]), { handled: true, select: 'my-skill' });
  assert.deepEqual(composer.slashKey('Escape', 0, []), { handled: true, close: true });
  assert.deepEqual(composer.slashKey('Enter', 0, []), { handled: true });
});

test('shell has visible navigation, explicit mobile search/close and no empty landing panel', () => {
  const rail = shell.renderPrimaryRail({ page: 'fingpt' });
  assert.match(rail, /class="rail-label">FinGPT/);
  assert.match(rail, /rail-mobile-close.*aria-label="关闭导航"/);
  assert.match(shell.renderTopbar({}), /data-toggle-search/);
  assert.match(shell.renderSidebar({ page: 'fingpt', collapsed: true, mobileOpen: true }), /sidebar-collapse.*aria-label="折叠 FinGPT 二级侧栏"/);
  assert.equal(shell.renderContextPanel({}), '');
});

test('composer defaults derive from selected catalog metadata, not parallel IDs', () => {
  const html = composer.renderComposer({ skills: [cap()], skillId: 'my-skill', capability: cap(), expectedFormats: null });
  assert.match(html, /自动 · MD/);
  assert.match(html, /v2/);
  assert.doesNotMatch(composer.renderComposer({ skills: [cap({ status: 'disabled', enabled: false })], slashOpen: true }), /data-skill-shortcut/);
});

test('invalid imports and missing dependencies remain inspectable without fake publication success', async () => {
  const { createCapabilityController } = await load('capability-controller.mjs');
  const events = []; const imported = cap({ status: 'invalid', enabled: false, version: 0, draft: { kind: 'skill', metadata: {}, instructions: 'raw', files: [], steps: [], reviewed_scripts: [] }, checks: { valid: false, status: 'blocked_dependencies', issues: [{ code: 'missing_dependency', message: '缺少库', path: 'scripts/run.py' }] } });
  const control = createCapabilityController({ api: { importCapability: async () => imported, capabilityAction: async () => { throw Object.assign(new Error('活动回合冲突'), { code: 'active_turn' }); } }, logger: event => events.push(event) });
  await control.import(new File(['raw'], 'SKILL.md'));
  assert.equal(control.state.detail.checks.valid, false); assert.match(control.state.success, /检查未通过/);
  await control.action('publish');
  assert.match(control.state.error, /active_turn.*活动回合冲突/); assert.equal(control.state.success, ''); assert.equal(control.state.detail, imported);
  assert.deepEqual(events, ['capability_operation_failed']);
});

test('saved drafts survive a fresh capability controller; failed writes preserve exact edited bytes', async () => {
  const { createCapabilityController } = await load('capability-controller.mjs');
  let saved = cap({ draft: { kind: 'skill', metadata: cap().metadata, instructions: '原稿', files: [{ path: 'x.md', content: '原字节' }], steps: [], reviewed_scripts: [] } });
  let fail = true;
  const api = { capability: async () => structuredClone(saved), saveCapability: async (_id, draft) => { if (fail) throw new Error('存储不可用'); saved = { ...saved, draft }; return structuredClone(saved); } };
  const control = createCapabilityController({ api, logger() {} }); await control.open('my-skill'); control.edit();
  control.state.editor.instructions = '用户编辑'; await control.save();
  assert.equal(control.state.editor.instructions, '用户编辑'); assert.equal(control.state.form, 'editor');
  fail = false; await control.save();
  const reloaded = createCapabilityController({ api }); await reloaded.open('my-skill');
  assert.equal(reloaded.state.detail.draft.instructions, '用户编辑'); assert.equal(reloaded.state.detail.draft.files[0].content, '原字节');
});

test('capability operation lock prevents duplicate publish; raw API errors never mark success', async () => {
  const { createCapabilityController } = await load('capability-controller.mjs');
  let resolve; let publishes = 0;
  const detail = cap({ draft: { files: [], metadata: {} } });
  const control = createCapabilityController({ api: { capability: async () => detail, capabilityAction: async () => { publishes++; return new Promise(done => { resolve = done; }); } } });
  await control.open('my-skill'); const first = control.action('publish'); await control.action('publish');
  assert.equal(publishes, 1); assert.equal(control.state.busy, true); resolve(detail); await first; assert.equal(control.state.busy, false);
});

test('only dedicated creation sessions expose actual output packages for review', async () => {
  const { creationArtifacts, renderCreationArtifacts } = await load('capabilities.mjs');
  const files = [{ id: 'out', kind: 'outputs', name: 'SKILL.md' }, { id: 'upload', kind: 'uploads', name: 'SKILL.md' }, { id: 'zip', kind: 'outputs', name: 'candidate.zip' }, { id: 'report', kind: 'outputs', name: 'report.md' }];
  assert.deepEqual(creationArtifacts({ purpose: 'research', files }), []);
  assert.deepEqual(creationArtifacts({ purpose: 'capability_creation', files }).map(x => x.id), ['out', 'zip']);
  assert.match(renderCreationArtifacts({ purpose: 'capability_creation', files }, true), /data-cap-artifact="out" disabled/);
});

test('complete editor payload captures inputs, ordered steps, explicit formats, and invalidates modified script review', async () => {
  const { readEditor, editableDraft } = await load('capability-editor.mjs');
  const previous = { kind: 'workflow', metadata: { inputs: [{ name: 'question' }] }, steps: [{ title: 'old' }], files: [{ path: 'scripts/run.py', content: 'print(1)', sha256: 'old-hash' }], reviewed_scripts: ['old-hash'] };
  const values = new FormData();
  for (const [key, value] of Object.entries({ name: '流程', slug: 'flow', description: '研究流程', category: '研究', scenarios: '研究\n交付', 'input-0-name': 'question', 'input-0-label': '问题', 'input-0-type': 'text', 'input-0-required': 'on', 'step-0-title': '核对', 'step-0-instruction': '核对来源', 'step-0-skill': 'my-skill', 'step-0-tools': 'research_run_script', 'file-0-path': 'scripts/run.py', 'file-0-content': 'print(2)' })) values.append(key, value);
  const draft = readEditor(values, previous);
  assert.deepEqual(draft.reviewed_scripts, []); assert.equal(draft.files[0].sha256, undefined);
  assert.deepEqual(draft.metadata.default_formats, []); assert.equal(draft.metadata.inputs[0].required, true);
  assert.equal(draft.steps[0].skill_id, 'my-skill'); assert.deepEqual(draft.steps[0].tools, ['research_run_script']);
  assert.deepEqual(editableDraft(draft).files, [{ path: 'scripts/run.py', content: 'print(2)' }]);
});

test('version exports use fixed local paths and never backend-provided arbitrary URLs', async () => {
  const { exportURL } = await load('capabilities.mjs');
  assert.equal(exportURL('my-skill', 2), '/api/research/capabilities/my-skill/versions/2/export');
  for (const id of ['../../runtime', 'https://evil.test', 'a%2fb']) assert.equal(exportURL(id, 2), null);
  assert.equal(exportURL('my-skill', -1), null);
});

test('catalog cards expose scenarios, required inputs and formats before opening detail', async () => {
  const { renderCapabilityCatalog } = await load('capabilities.mjs');
  const html = renderCapabilityCatalog({ items: [cap()] });
  assert.match(html, /场景：研究/); assert.match(html, /输入：资料（file · 必填）/); assert.match(html, /输出：md/);
});

test('offline runtime keeps draft editable and capability browsing available but disables real send', () => {
  const html = composer.renderComposer({ draft: '可继续准备', skills: [cap()], runtimeReady: false });
  assert.doesNotMatch(html, /<textarea[^>]*disabled/);
  assert.match(html, /type="submit"[^>]*disabled/);
  assert.match(html, /运行时未就绪/);
});

test('real app event handlers close/select slash, search and drawers without any model or tool write', async () => {
  const handlers = new Map(); const calls = []; const logs = [];
  const rootElement = { innerHTML: '', addEventListener: (name, handler) => handlers.set(name, handler), querySelectorAll: () => [], querySelector: () => null };
  const main = { scrollTop: 0, scrollTo() {}, focus() {} };
  const prompt = { id: 'prompt', focus() {} };
  const selectors = { '#app': rootElement, '#main': main, '#prompt': prompt, '#global-search': { focus() {} }, '.skip-link': { addEventListener() {} } };
  const previous = new Map(['document', 'window', 'location', 'history', 'fetch'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  const originalLog = console.info;
  const builtinResearchSkills = productBuiltinResearchSkills();
  const selectedSkill = builtinResearchSkills.find(item => item.id === 'sell-side-report-reader');
  assert.ok(selectedSkill, 'real product catalog must contain the report specialist');
  const detail = { ...selectedSkill, draft: { kind: 'skill', metadata: selectedSkill.metadata, instructions: '真实候选', files: [], steps: [] } };
  try {
    Object.defineProperty(globalThis, 'document', { configurable: true, value: { querySelector: key => selectors[key] || null, getElementById: () => null, activeElement: null, title: '' } });
    Object.defineProperty(globalThis, 'window', { configurable: true, value: { matchMedia: () => ({ matches: true }), addEventListener() {} } });
    Object.defineProperty(globalThis, 'location', { configurable: true, value: { hash: '#/fingpt' } });
    Object.defineProperty(globalThis, 'history', { configurable: true, value: { pushState: (_a, _b, hash) => { globalThis.location.hash = hash; } } });
    Object.defineProperty(globalThis, 'fetch', { configurable: true, value: async (url, options) => {
      calls.push([url, options.method]);
      const payload = url.endsWith('/runtime') ? { connected: true, credential_configured: true } : url.endsWith('/models') ? { groups: [] } : url.endsWith(`/capabilities/${selectedSkill.id}`) ? detail : { items: url.endsWith('/capabilities') ? builtinResearchSkills : [] };
      return new Response(JSON.stringify(payload));
    } });
    console.info = (...args) => logs.push(args);
    await load(`app.mjs?capabilities-integration=${Date.now()}`);
    const input = async (id, value, dataset = {}) => handlers.get('input')({ target: { id, value, dataset, closest: () => null } });
    const click = async (dataset) => handlers.get('click')({ target: { closest: () => ({ dataset, disabled: false }) } });
    const key = async (key) => handlers.get('keydown')({ key, target: { id: 'prompt' }, preventDefault() {}, isComposing: false });
    await input('prompt', '/'); assert.match(rootElement.innerHTML, /id="slash-options"/);
    await key('Escape'); assert.doesNotMatch(rootElement.innerHTML, /id="slash-options"/);
    await click({ useSkill: selectedSkill.id });
    assert.match(rootElement.innerHTML, new RegExp(`capability-chips.*${selectedSkill.name} · v${selectedSkill.version}`, 's'));
    assert.match(rootElement.innerHTML, new RegExp(`<option value="${selectedSkill.id}" selected>`));
    assert.match(rootElement.innerHTML, /<textarea id="prompt"[^>]*><\/textarea>/);
    await click({ toggleSidebar: '' }); assert.match(rootElement.innerHTML, /secondary-sidebar mobile-open/);
    await click({ toggleSidebar: '' }); assert.doesNotMatch(rootElement.innerHTML, /secondary-sidebar mobile-open/);
    await click({ toggleSearch: '' }); assert.match(rootElement.innerHTML, /topbar search-open/);
    await key('Escape'); assert.doesNotMatch(rootElement.innerHTML, /topbar search-open/);
    await click({ skillDetail: selectedSkill.id }); assert.equal(globalThis.location.hash, '#/skills');
    assert.match(rootElement.innerHTML, /role="dialog"[^>]*aria-modal="true"/);
    await click({ capClose: '' }); assert.match(rootElement.innerHTML, /role="tablist" aria-label="能力类型"/);
    assert.match(rootElement.innerHTML, /data-cap-kind-nav="skill"/);
    assert.doesNotMatch(rootElement.innerHTML, /data-cap-kind-filter/);
    assert.equal(calls.some(([, method]) => method !== 'GET'), false);
    assert.doesNotMatch(JSON.stringify(logs), /真实候选|sell-side-report-reader|\/api\/research/);
  } finally {
    console.info = originalLog;
    for (const [key, descriptor] of previous) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key]; }
  }
});

test('real landing modes filter catalog categories and select Workflow or Skill drafts without writes', async () => {
  const handlers = new Map(); const windowHandlers = new Map(); const calls = [];
  const rootElement = { innerHTML: '', addEventListener: (name, handler) => handlers.set(name, handler), querySelectorAll: () => [], querySelector: () => null };
  const selectors = { '#app': rootElement, '#main': { scrollTop: 0, scrollTo() {} }, '#prompt': { focus() {} }, '.skip-link': { addEventListener() {} } };
  const previous = new Map(['document', 'window', 'location', 'history', 'fetch'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  const originalLog = console.info;
  const skillIDs = ['document-reading', 'company-research', 'industry-research', 'fund-evaluation'];
  const items = [...skillIDs.map(id => cap({ id })), cap({ id: 'flow-one', kind: 'workflow', name: '公司研究步骤', category: '公司' }), cap({ id: 'flow-two', kind: 'workflow', name: '行业研究步骤', category: '行业' })];
  try {
    Object.defineProperty(globalThis, 'document', { configurable: true, value: { querySelector: key => selectors[key] || null, getElementById: () => null, activeElement: null, title: '' } });
    Object.defineProperty(globalThis, 'window', { configurable: true, value: { matchMedia: () => ({ matches: false }), addEventListener: (name, handler) => windowHandlers.set(name, handler) } });
    Object.defineProperty(globalThis, 'location', { configurable: true, value: { hash: '#/claw' } });
    Object.defineProperty(globalThis, 'history', { configurable: true, value: { pushState: (_a, _b, hash) => { globalThis.location.hash = hash; } } });
    Object.defineProperty(globalThis, 'fetch', { configurable: true, value: async (url, options) => {
      calls.push([url, options.method]);
      const payload = url.endsWith('/runtime') ? { connected: true, credential_configured: true } : url.endsWith('/models') ? { groups: [] } : { items: url.endsWith('/capabilities') ? items : [] };
      return new Response(JSON.stringify(payload));
    } });
    console.info = () => {};
    await load(`app.mjs?landing-integration=${Date.now()}`);
    const quickIDs = () => [...rootElement.innerHTML.matchAll(/data-skill-shortcut="([^"]+)"/g)].map(match => match[1]);
    const change = (id, value, dataset = {}) => handlers.get('change')({ target: { id, value, dataset, closest: () => null } });
    assert.match(rootElement.innerHTML, /<h2>研究步骤模板<\/h2>/);
    assert.deepEqual(quickIDs(), ['flow-one', 'flow-two']);
    const reads = calls.length;
    await change('quick-category', '公司', { quickCategory: '' });
    assert.deepEqual(quickIDs(), ['flow-one']); assert.equal(calls.length, reads);
    await handlers.get('click')({ target: { closest: () => ({ dataset: { skillShortcut: 'flow-one' }, disabled: false }) } });
    assert.equal(globalThis.location.hash, '#/claw');
    assert.match(rootElement.innerHTML, /capability-chips.*公司研究步骤 · v2/s);
    await change('skill-select', 'document-reading');
    assert.match(rootElement.innerHTML, /capability-chips.*我的研究 · v2/s);
    globalThis.location.hash = '#/fingpt'; windowHandlers.get('hashchange')();
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(quickIDs(), skillIDs);
    assert.match(rootElement.innerHTML, /从真实研究 Skill 开始/);
    assert.equal(calls.some(([, method]) => method !== 'GET'), false);
  } finally {
    console.info = originalLog;
    for (const [key, descriptor] of previous) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key]; }
  }
});

test('cached running session summaries do not indefinitely prevent backend-checked capability publication', async () => {
  const { renderCapabilityDetail } = await load('capabilities.mjs');
  const html = renderCapabilityDetail(cap({ draft: {}, checks: { valid: true } }), { running: true });
  assert.match(html, /data-cap-action="publish">/);
  assert.match(html, /会话列表.*后端.*全局活动/s);
});

test('live session summaries replace stale running status without copying transcripts', async () => {
  const { reconcileSessionSummary } = await load('core.mjs');
  const result = reconcileSessionSummary([{ id: 's1', status: 'running', title: '研究', mode: 'fingpt' }], { id: 's1', status: 'completed', can_cancel: false, title: '研究', mode: 'fingpt', messages: [{ text: '私有正文' }] });
  assert.equal(result[0].status, 'completed'); assert.equal(result[0].can_cancel, false); assert.equal(result[0].messages, undefined);
});

test('publication adopts the confirmed mutation response instead of risking an unnecessary failed readback', async () => {
  const { createCapabilityController } = await load('capability-controller.mjs');
  let reads = 0; const draft = { kind: 'skill', metadata: {}, files: [], steps: [] };
  const control = createCapabilityController({ api: { capability: async () => { if (reads++) throw new Error('只读连接中断'); return cap({ draft }); }, capabilityAction: async () => cap({ version: 3, draft }) }, logger() {} });
  await control.open('my-skill'); await control.action('publish');
  assert.equal(control.state.detail.version, 3); assert.equal(control.state.error, ''); assert.equal(reads, 1);
});

test('failed workflow version reads retry on explicit refresh and clear only the recovered version error', async () => {
  const handlers = new Map(); const calls = []; let versionReads = 0;
  const rootElement = { innerHTML: '', addEventListener: (name, handler) => handlers.set(name, handler), querySelectorAll: () => [], querySelector: () => null };
  const main = { scrollTop: 0, scrollTo() {}, focus() {} };
  const selectors = { '#app': rootElement, '#main': main, '.skip-link': { addEventListener() {} } };
  const previous = new Map(['document', 'window', 'location', 'history', 'fetch', 'EventSource'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  const originalLog = console.info;
  const detail = { ...session(), capability: { id: 'wf', kind: 'workflow', version: 2 } };
  try {
    Object.defineProperty(globalThis, 'document', { configurable: true, value: { querySelector: key => selectors[key] || null, getElementById: () => null, activeElement: null, title: '' } });
    Object.defineProperty(globalThis, 'window', { configurable: true, value: { matchMedia: () => ({ matches: false }), addEventListener() {} } });
    Object.defineProperty(globalThis, 'location', { configurable: true, value: { hash: '#/fingpt?session=s1' } });
    Object.defineProperty(globalThis, 'history', { configurable: true, value: { pushState() {} } });
    Object.defineProperty(globalThis, 'EventSource', { configurable: true, value: class { addEventListener() {} close() {} } });
    Object.defineProperty(globalThis, 'fetch', { configurable: true, value: async (url, options) => {
      calls.push([url, options.method]);
      if (url.endsWith('/capabilities/wf/versions/2')) {
        if (++versionReads === 1) return new Response(JSON.stringify({ error: { code: 'temporary_failure', message: '暂时不可用' } }), { status: 503 });
        return new Response(JSON.stringify({ id: 'wf', version: 2, steps: [{ title: '版本恢复后的步骤', instruction: '仅显示模板' }] }));
      }
      const payload = url.endsWith('/sessions/s1') ? detail : url.endsWith('/runtime') ? { connected: true } : url.endsWith('/models') ? { groups: [] } : { items: [] };
      return new Response(JSON.stringify(payload));
    } });
    console.info = () => {};
    await load(`app.mjs?workflow-retry=${Date.now()}`);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(versionReads, 1); assert.match(rootElement.innerHTML, /未能读取本次 Workflow/);
    assert.doesNotMatch(rootElement.innerHTML, /版本恢复后的步骤/);
    await handlers.get('click')({ target: { closest: () => ({ dataset: { refresh: '' }, disabled: false }) } });
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(versionReads, 2, 'explicit refresh must retry the failed immutable-version read');
    assert.doesNotMatch(rootElement.innerHTML, /版本恢复后的步骤/, 'research panel is collapsed by default');
    await handlers.get('click')({ target: { closest: () => ({ dataset: { toggleContext: '' }, disabled: false }) } });
    assert.match(rootElement.innerHTML, /版本恢复后的步骤/);
    assert.doesNotMatch(rootElement.innerHTML, /未能读取本次 Workflow/);
    await handlers.get('click')({ target: { closest: () => ({ dataset: { refresh: '' }, disabled: false }) } });
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(versionReads, 2, 'successfully loaded immutable versions stay cached');
    assert.equal(calls.some(([, method]) => method !== 'GET'), false);
  } finally {
    console.info = originalLog;
    for (const [key, descriptor] of previous) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key]; }
  }
});
