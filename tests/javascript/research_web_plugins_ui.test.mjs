import test from 'node:test';
import assert from 'node:assert/strict';
import { renderPluginWorkspace } from '../../app/research_web/ui/plugins-workspace.mjs';
import { parseRoute } from '../../app/research_web/ui/core.mjs';

function state(extra = {}) {
  const digest = 'a'.repeat(64);
  return {items: [{digest, name: '<script>unsafe</script>', version: '1.0.0', enabled: false, review: null, permissions: ['skills:read'], components: [{kind: 'skill', key: 'read', support: 'limited', ready: false, reason: 'native_discovery_pending'}, {kind: 'hook', key: 'http', support: 'unsupported', ready: false, reason: 'unsupported_event'}], file_inventory: []}], runtimeItems: [], selected: digest, grants: new Set(), sessions: [], pending: [], busy: false, message: '', error: '', user: null, sourcePrefix: '/api/research/plugins', ...extra};
}

test('plugin route preserves the existing capability-center contract', () => {
  assert.equal(parseRoute('#/skills?kind=plugin').capabilityKind, 'plugin');
  assert.equal(parseRoute('#/skills?kind=data').capabilityKind, 'data');
});

test('plugin preview never presents pending or unsupported components as loaded', () => {
  const html = renderPluginWorkspace(state());
  assert.ok(html.includes('native_discovery_pending'));
  assert.ok(html.includes('unsupported_event'));
  assert.ok(!html.includes('Host 已加载并授权'));
  assert.match(html, /data-plugin-action="review"[^>]*disabled/u);
  assert.ok(html.includes('&lt;script&gt;unsafe&lt;/script&gt;'));
  assert.ok(!html.includes('<script>unsafe'));
  const busy = renderPluginWorkspace(state({busy: true}));
  assert.ok(busy.includes('aria-busy="true"'));
});

test('consumer UI has source visibility without pretending to have admin management rights', () => {
  const html = renderPluginWorkspace(state({user: {id: 'fixture', role: 'user'}}));
  assert.ok(!html.includes('data-plugin-import'));
  assert.ok(!html.includes('data-plugin-action="review"'));
  assert.ok(!html.includes('data-plugin-action="uninstall"'));
  assert.ok(html.includes('仅管理员可导入、审核和分发插件'));
  assert.ok(html.includes('data-plugin-action="refresh-runtime"'));
});

test('local MCP stays visibly blocked while remote fixed endpoints retain controls', () => {
  for (const local of [true, false]) {
    const view = state();
    view.items[0].review = {digest: view.selected};
    view.items[0].components = [{kind: 'mcp', key: 'server', support: local ? 'limited' : 'supported', ready: false, reason: local ? 'mcp_managed_local_process_isolation_required' : 'native_preview_confirmation_required', selection: local ? {package_index: 0} : {remote_index: 0}}];
    const html = renderPluginWorkspace(view);
    assert.ok(html.includes('缺少操作系统进程隔离保持停用'));
    for (const action of ['mcp-preview', 'mcp-probe', 'mcp-enable']) {
      const control = html.match(new RegExp(`data-plugin-action="${action}"[^>]*`))[0];
      assert.equal(control.includes('disabled'), local);
    }
  }
});
