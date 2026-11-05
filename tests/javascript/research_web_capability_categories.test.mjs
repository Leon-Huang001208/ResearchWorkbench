import test from 'node:test';
import assert from 'node:assert/strict';
import { createCapabilityController } from '../../app/research_web/ui/capability-controller.mjs';
import { renderPrimaryRail } from '../../app/research_web/ui/shell.mjs';
import { parseRoute, createController } from '../../app/research_web/ui/core.mjs';
import { renderCapabilityWorkspace, capabilityWorkspaceKindKey, filterCapabilityWorkspaceEntries, collectCapabilityWorkspaceEntries } from '../../app/research_web/ui/capability-workspace.mjs';
import { composerMenuRows, openComposerMenu } from '../../app/research_web/ui/composer-menu.mjs';
import { renderComposer, skillMatches } from '../../app/research_web/ui/composer.mjs';

const capabilities = ['skill', 'workflow', 'method'].map(kind => ({ id: `${kind}-one`, name: `${kind}名称`, kind, enabled: true, status: 'enabled', version: 1, metadata: {} }));
test('three primary categories keep legacy route context and plans', () => {
  assert.equal(capabilityWorkspaceKindKey('ArrowRight', 'skill').kind, 'connector');
  for (const kind of ['method', 'workflow']) {
    const route = parseRoute(`#/skills?kind=${kind}`);
    assert.equal(route.capabilityKind, 'skill');
    assert.equal(route.capabilityContext, kind);
  }
  for (const kind of ['tool', 'data']) assert.equal(parseRoute(`#/skills?kind=${kind}`).capabilityKind, 'connector');
  assert.equal(parseRoute('#/skills?view=plans').capabilityView, 'plans');
  assert.equal(parseRoute('#/skills?kind=tool&view=market').capabilityView, 'market');
  const html = renderCapabilityWorkspace({ capabilities });
  assert.equal((html.match(/data-cap-kind-nav=/g) || []).length, 3);
  for (const label of ['技能', '连接器', '插件']) assert.ok(html.includes(`>${label}</a>`));
  for (const item of capabilities) assert.ok(html.includes(item.name));
  assert.match(html, /data-use-method="method-one"/);
  assert.match(html, /定时任务/);
});
test('unified skill search and picker preserve legacy method selection semantics', () => {
  assert.equal(filterCapabilityWorkspaceEntries(collectCapabilityWorkspaceEntries({ capabilities }), { kind: 'skill' }).length, 3);
  assert.equal(skillMatches('', capabilities).length, 3);
  const rows = composerMenuRows(openComposerMenu('add', 'capabilities'), { skills: capabilities, methodIds: [] });
  assert.equal(rows.length, 3);
  assert.equal(rows.find(row => row.value === 'method-one').action, 'method');
  assert.ok(!composerMenuRows(openComposerMenu('add')).some(row => row.key === 'methods'));
  const html = renderComposer({ skills: capabilities, methods: [capabilities[2]], methodIds: ['method-one'] });
  assert.doesNotMatch(html, /method-picker|data-method-id=/);
  assert.match(html, /method名称.*用户选择/s);
});

test('timer navigation reuses the existing plans without a new scheduler', () => {
  assert.equal(parseRoute('#/automations').capabilityView, 'plans');
  const rail = renderPrimaryRail({ page: 'skills', capabilityView: 'plans' });
  assert.match(rail, /href="#\/automations" class="rail-link active"/);
  assert.match(renderCapabilityWorkspace({ view: 'plans' }), /<h2>定时任务<\/h2>/);
});

test('legacy method selection never replaces the primary capability or its history', () => {
  const controller = createController({ logger: () => {} });
  controller.setCapability(capabilities[0]);
  controller.setCapability(capabilities[2]);
  assert.equal(controller.state.capability.id, 'skill-one');
  assert.deepEqual(controller.state.methodIds, ['method-one']);
  controller.setMethods(['one', 'two', 'three']);
  assert.throws(() => controller.setCapability(capabilities[2]), /最多选择三个/);
  assert.deepEqual(controller.state.methodIds, ['one', 'two', 'three']);
});

test('connector defaults show service identities and leave naked tools to legacy context', () => {
  const state = { tools: [{ id: 'guard', name: '内部控制', selectable: false }], connections: { sources: [{ id: 'local-one', name: '本机集成', group: 'local', callable: false }] }, mcpMarketplace: { installations: [{ id: 'install-one', runtime_status: 'disabled', active: false, plan: { registry_id: 'registry', server_name: 'MCP One', server_version: '1' } }] } };
  const html = renderCapabilityWorkspace({ ...state, kind: 'connector' });
  assert.match(html, /MCP One/);
  assert.match(html, /data-server-name="MCP One"/);
  assert.doesNotMatch(html, /data-tool-detail="guard"|<span class="badge">已启用/);
  assert.equal((html.match(/data-cap-query/g) || []).length, 1);
  const legacy = renderCapabilityWorkspace({ ...state, kind: 'connector', context: 'tool' });
  assert.match(legacy, /data-tool-detail="guard"/);
  assert.doesNotMatch(legacy, /data-use-tool="guard"/);
});
test('creating after inspecting a legacy method creates an ordinary skill', async () => {
  const controller = createCapabilityController({ api: { capability: async () => ({ ...capabilities[2], draft: {} }) } });
  await controller.open('method-one');
  controller.create('manual');
  assert.equal(controller.state.editor.kind, 'skill');
});

test('local connector search uses the connection-center display label', () => {
  const html = renderCapabilityWorkspace({ kind: 'connector', query: 'Excel', connections: { sources: [{ id: 'office_local', label: 'Excel 与本机工作流', group: 'local' }] } });
  assert.match(html, /<strong>Excel 与本机工作流<\/strong>/);
  assert.doesNotMatch(html, /没有匹配的本机集成/);
});
