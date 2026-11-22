import test from 'node:test';
import assert from 'node:assert/strict';
import { renderMCPCredentials } from '../../app/research_web/ui/mcp-credentials.mjs';
import { createPluginWorkspace } from '../../app/research_web/ui/plugins-workspace.mjs';

const endpoint = 'https://seek-alpha.cn/mcp/rpc';
const component = {kind: 'mcp', key: 'seek', selection: {server_version: '1.0.0', remote_index: 0}, credential_support: {resource: endpoint, slot: 'static_bearer'}};

test('personal static credentials show only configured state and evaluation remains explicit', () => {
  assert.equal(renderMCPCredentials({}, {}), '');
  const html = renderMCPCredentials({busy: false, mcpCredential: {configured: true}, sessions: []}, component);
  assert.match(html, /已配置/u);
  assert.match(html, /type="password"/u);
  assert.doesNotMatch(html, /value="secret/u);
  assert.match(html, /18 次调用，最高 54 子弹/u);
  assert.match(html, /不能冒充历史数据/u);
  assert.doesNotMatch(html, /data-plugin-evaluation-authorize/u);
  const busy = renderMCPCredentials({busy: true, sessions: [], mcpEvaluationPreview: {cutoff: '2026-10-23', entries: [{subject: '<unsafe>', query: 'risk_alerts', tool_name: 'query_risk_alerts', arguments: {query: '600519'}, credits: 3}], calls: 18, max_credits: 54}}, component);
  assert.match(busy, /data-plugin-evaluation-authorize/u);
  assert.match(busy, /name="confirmed" required disabled/u);
  assert.match(busy, /&lt;unsafe&gt;/u);
  assert.doesNotMatch(busy, /<unsafe>/u);
});

test('credential submission uses current managed tenant route, clears secret before await and never stores it', async () => {
  const digest = 'a'.repeat(64), requests = [], logged = [], handlers = new Map();
  const item = {digest, name: 'seek', version: '1.0.0', review: {}, permissions: [], components: [component]};
  const panel = {isConnected: true, innerHTML: '', contains: () => true, querySelector: () => null};
  const root = {querySelector: () => panel, addEventListener: (kind, handler) => handlers.set(kind, handler)};
  const fetcher = async (path, options = {}) => {
    const body = typeof options.body === 'string' ? JSON.parse(options.body) : undefined;
    requests.push({path, body, headers: options.headers});
    const value = path.endsWith('/credential-save') ? {configured: true, resource: endpoint, slot: 'static_bearer'}
      : path === '/api/research/sessions' ? {items: [{id: 'owned', title: 'Owned'}]}
      : {items: [item]};
    return {ok: true, json: async () => value};
  };
  const workspace = createPluginWorkspace({root, user: {id: 'current-user', role: 'user'}, fetcher, logger: (...args) => logged.push(args)});
  const settle = async () => {for (let index = 0; index < 100 && workspace.state.busy; index++) await new Promise(resolve => setImmediate(resolve)); assert.equal(workspace.state.busy, false);};
  workspace.sync(); await settle();
  const input = {value: 'private-test-token'};
  const form = {matches: selector => selector.includes('[data-plugin-credential]'), querySelectorAll: () => [input]};
  const OriginalFormData = globalThis.FormData;
  globalThis.FormData = class {
    constructor() {this.values = new Map([['token', input.value]]);}
    get(name) {return this.values.get(name);}
    delete(name) {this.values.delete(name);}
  };
  try {
    handlers.get('submit')({target: form, stopImmediatePropagation() {}, preventDefault() {}});
    assert.equal(input.value, '', 'secret must clear synchronously before awaiting network');
    await settle();
    const sent = requests.find(row => row.path.endsWith('/credential-save'));
    assert.equal(sent.path, `/api/server/plugins/mcp/${digest}/seek/credential-save`);
    assert.deepEqual(sent.body, {resource: endpoint, slot: 'static_bearer', token: 'private-test-token'});
    assert.equal(sent.headers['X-RWB-Page-User'], 'current-user');
    assert.equal(JSON.stringify(workspace.state).includes('private-test-token'), false);
    assert.equal(JSON.stringify(logged).includes('private-test-token'), false);
    assert.equal(panel.innerHTML.includes('private-test-token'), false);
    assert.equal(requests.some(row => row.path.startsWith('/api/research/mcp')), false);
  } finally {globalThis.FormData = OriginalFormData;}
});
