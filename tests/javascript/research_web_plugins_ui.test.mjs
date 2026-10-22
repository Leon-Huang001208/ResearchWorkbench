import test from 'node:test';
import assert from 'node:assert/strict';
import { createPluginWorkspace, renderPluginWorkspace } from '../../app/research_web/ui/plugins-workspace.mjs';
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

test('unsupported local MCP stays blocked; offline Python and remote controls remain usable', () => {
  for (const mode of ['blocked', 'offline', 'remote']) {
    const local = mode !== 'remote';
    const blocked = mode === 'blocked';
    const view = state();
    view.items[0].review = {digest: view.selected};
    view.items[0].components = [{kind: 'mcp', key: 'server', support: local ? 'limited' : 'supported', ready: false, sandbox_available: !blocked, reason: blocked ? 'mcp_managed_local_process_isolation_required' : local ? 'mcp_offline_python_sandbox_required' : 'native_preview_confirmation_required', selection: local ? {package_index: 0} : {remote_index: 0}}];
    const html = renderPluginWorkspace(view);
    assert.ok(html.includes('macOS 受管本地 MCP 仅开放离线 Python'));
    for (const action of ['mcp-preview', 'mcp-probe', 'mcp-enable']) {
      const control = html.match(new RegExp(`data-plugin-action="${action}"[^>]*`))[0];
      assert.equal(control.includes('disabled'), blocked);
    }
  }
});

function workspaceHarness({admin = false} = {}) {
  const handlers = new Map(), requests = [];
  const shared = 'a'.repeat(64), personal = 'b'.repeat(64);
  const plugin = (digest, key) => ({digest, name: key, version: '1.0.0', review: {}, permissions: [], components: [{kind: 'mcp', key, selection: {server_version: '1.0.0', remote_index: 0}}]});
  let pending = true;
  let sharedDigest = shared;
  const panel = {isConnected: true, innerHTML: '', contains: () => true, querySelector: () => null};
  const root = {querySelector: () => panel, addEventListener: (kind, handler) => handlers.set(kind, handler)};
  const fetcher = async (path, options = {}) => {
    const body = typeof options.body === 'string' ? JSON.parse(options.body) : undefined;
    requests.push({path, body, headers: options.headers});
    let value;
    if (path === '/api/server/plugins/shared') value = {items: [plugin(sharedDigest, 'shared-component')]};
    else if (path === '/api/server/plugins/shared/preview') { sharedDigest = 'c'.repeat(64); value = {digest: sharedDigest}; }
    else if (path === '/api/server/plugins/personal') value = {items: [plugin(personal, 'personal-component')]};
    else if (path === '/api/research/plugins') value = {items: []};
    else if (path === '/api/research/sessions') value = {items: [{id: 'session-1', title: 'Own session'}]};
    else if (path === '/api/server/plugins/reviews/pending') value = {items: []};
    else if (path.endsWith('/approvals')) value = {items: pending ? [{id: 'approval-1', session_id: 'session-1', tool_name: '<unsafe>', version: '1.0.0', status: 'pending'}] : []};
    else if (path.endsWith('/decide')) { pending = false; value = {status: body.approve ? 'approved' : 'denied'}; }
    else if (path.endsWith('/preview')) value = {plan: {environment_names: []}};
    else throw new Error('Unexpected plugin request: ' + path);
    return {ok: true, json: async () => value};
  };
  const workspace = createPluginWorkspace({root, user: {id: 'current-user', role: admin ? 'admin' : 'user'}, fetcher});
  const settle = async () => {
    for (let count = 0; count < 100 && workspace.state.busy; count++) await new Promise(resolve => setImmediate(resolve));
    assert.equal(workspace.state.busy, false, 'workspace operation did not settle');
  };
  const change = (selector, value) => handlers.get('change')({target: {value, matches: text => text === selector}, stopImmediatePropagation() {}});
  const click = (action, extra = {}) => {
    const target = {dataset: {pluginAction: action, ...extra}};
    handlers.get('click')({target: {closest: () => target}, stopImmediatePropagation() {}});
  };
  workspace.sync();
  const submitImport = () => handlers.get('submit')({target: {dataset: {}, matches: selector => selector.includes('[data-plugin-import]'), querySelectorAll: () => []}, stopImmediatePropagation() {}, preventDefault() {}});
  return {workspace, panel, requests, shared, personal, settle, change, click, submitImport};
}

test('server plugin approvals use the current plugin route and exact selected session', async () => {
  for (const approve of [true, false]) {
    const h = workspaceHarness(); await h.settle();
    h.change('[data-plugin-approval-session]', 'session-1');
    h.click('mcp-approvals'); await h.settle();
    assert.match(h.panel.innerHTML, /data-plugin-action="mcp-call-approve"/u);
    assert.match(h.panel.innerHTML, /&lt;unsafe&gt;/u);
    assert.doesNotMatch(h.panel.innerHTML, /<unsafe>/u);
    h.click(approve ? 'mcp-call-approve' : 'mcp-call-deny', {approval: 'approval-1'}); await h.settle();
    const decision = h.requests.find(row => row.path.endsWith('/decide'));
    assert.ok(decision, 'pending call has no usable decision handler');
    assert.equal(decision.path, '/api/server/plugins/mcp/' + h.shared + '/shared-component/decide');
    assert.deepEqual(decision.body, {session_id: 'session-1', approval_id: 'approval-1', approve});
    assert.equal(decision.headers['X-RWB-Page-User'], 'current-user');
    assert.equal(h.requests.some(row => row.path.startsWith('/api/research/mcp')), false);
    assert.equal(h.workspace.state.mcpApprovals.length, 0);
  }
});

test('scope changes and automatic plugin selection cannot reuse an obsolete MCP key', async () => {
  const h = workspaceHarness(); await h.settle();
  h.change('[data-plugin-mcp]', 'shared-component');
  h.change('[data-plugin-scope]', 'personal'); await h.settle();
  h.click('mcp-preview'); await h.settle();
  assert.equal(h.requests.filter(row => row.path.endsWith('/preview')).at(-1).path, '/api/server/plugins/mcp/' + h.personal + '/personal-component/preview');
  h.workspace.state.selected = 'missing-old-version';
  h.workspace.state.mcpKey = 'shared-component';
  h.workspace.state.mcpSnapshot = {fingerprint: {schemas: 'old'}};
  h.workspace.state.mcpApprovals = [{id: 'old-approval', status: 'pending'}];
  h.click('reload'); await h.settle();
  assert.equal(h.workspace.state.selected, h.personal);
  assert.equal(h.workspace.state.mcpKey, '');
  assert.equal(h.workspace.state.mcpSnapshot, null);
  assert.deepEqual(h.workspace.state.mcpApprovals, []);
});

test('a late decision event cannot approve another session or an obsolete pending row', async () => {
  const h = workspaceHarness(); await h.settle();
  h.workspace.state.approvalSessionId = 'session-1';
  h.workspace.state.mcpApprovals = [{id: 'foreign-approval', session_id: 'session-2', status: 'pending'}];
  h.click('mcp-call-approve', {approval: 'foreign-approval'}); await h.settle();
  assert.equal(h.requests.some(row => row.path.endsWith('/decide')), false);
  assert.match(h.workspace.state.error, /待审调用已变化/u);
});

test('successful import clears the previous plugin MCP approval and confirmation context', async () => {
  const original = globalThis.FormData;
  globalThis.FormData = class {
    constructor() { this.values = new Map(); }
    get(key) { return this.values.get(key); }
    set(key, value) { this.values.set(key, value); }
  };
  try {
    const h = workspaceHarness({admin: true}); await h.settle();
    Object.assign(h.workspace.state, {file: {size: 10, name: 'new.zip'}, mcpKey: 'shared-component', mcpPreview: {confirmation_token: 'old-test-confirmation'}, mcpSnapshot: {fingerprint: {schemas: 'old'}}, approvalSessionId: 'session-1', mcpApprovals: [{id: 'old-approval', status: 'pending'}]});
    h.submitImport(); await h.settle();
    assert.equal(h.workspace.state.selected, 'c'.repeat(64));
    assert.equal(h.workspace.state.mcpKey, '');
    assert.equal(h.workspace.state.mcpPreview, null);
    assert.equal(h.workspace.state.mcpSnapshot, null);
    assert.equal(h.workspace.state.approvalSessionId, '');
    assert.deepEqual(h.workspace.state.mcpApprovals, []);
  } finally { globalThis.FormData = original; }
});
