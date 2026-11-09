import assert from 'node:assert/strict';
import test from 'node:test';
import {readFileSync} from 'node:fs';
import {createKnowledgeSettings, knowledgePanelHTML, mountKnowledgeSettings, safeKnowledgeManagementURL} from '../../app/research_web/ui/knowledge-settings.mjs';
import {createAPI} from '../../app/research_web/ui/core.mjs';

const settle = () => new Promise(resolve => setImmediate(resolve));
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return {promise, resolve, reject}; };
const configured = {enabled: true, configured: true, user_id: 'user-1', workspace_id: '7', connectivity: 'not_verified', live_acceptance: false, management_url: 'https://knowledge.example.test/'};

function fixture(request = async () => configured) {
  const requests = [], logs = [], handlers = new Map();
  const element = {
    html: '', renders: 0, removed: false,
    set innerHTML(value) {
      this.html = value; this.renders++;
      this.token = {value: ''};
      this.workspace = {value: value.match(/name="workspace_id"[^>]*value="([^"]*)"/)?.[1] || ''};
    },
    get innerHTML() { return this.html; },
    addEventListener(name, handler) { handlers.set(name, handler); },
    removeEventListener(name, handler) { if (handlers.get(name) === handler) handlers.delete(name); },
    querySelector(selector) { return selector === '[name="token"]' ? this.token : null; },
    remove() { this.removed = true; },
  };
  const api = {request(path, options = {}) { requests.push({path, ...options, body: options.body ? {...options.body} : undefined}); return request(path, options); }};
  const document = {createElement: () => element};
  const controller = createKnowledgeSettings({api, document, logger: event => logs.push(event)});
  function submit(token = 'synthetic-jwt-secret', workspace = '7') {
    const input = element.token; input.value = token; element.workspace.value = workspace;
    const form = {matches: selector => selector === '[data-knowledge-binding]', elements: {namedItem: name => name === 'token' ? input : element.workspace}};
    handlers.get('submit')?.({target: form, preventDefault() {}, stopPropagation() {}});
    return input;
  }
  function click(action) {
    const target = {disabled: false, dataset: {knowledgeAction: action}};
    handlers.get('click')?.({target: {closest: () => target}, preventDefault() {}, stopPropagation() {}});
  }
  return {controller, element, api, document, requests, logs, handlers, submit, click};
}

test('knowledge links only allow absolute HTTP(S) without credential URLs', () => {
  for (const url of ['javascript:alert(1)', 'data:text/html,canary', '//evil.test/', '/relative', 'https://user:secret@example.test/', 'https://example.test/\ncanary']) assert.equal(safeKnowledgeManagementURL(url), '');
  assert.equal(safeKnowledgeManagementURL('http://127.0.0.1:8095/'), 'http://127.0.0.1:8095/');
  assert.equal(safeKnowledgeManagementURL('https://knowledge.example.test/'), 'https://knowledge.example.test/');
});

test('knowledge metadata and library titles cannot create markup or saved token fields', () => {
  const html = knowledgePanelHTML({...configured, user_id: '<img src=x onerror=canary>', token: 'saved-secret', management_url: 'javascript:canary'}, {basesLoaded: true, bases: [{name: '<script>canary</script>'}]});
  assert.doesNotMatch(html, /<img|<script|saved-secret|href="javascript:/);
  assert.match(html, /&lt;img/); assert.match(html, /&lt;script/);
  assert.match(html, /name="token"[^>]*type="password"/);
  assert.doesNotMatch(html, /name="token"[^>]*value=/);
  assert.match(html, /检索待核验/);
});

test('status is the only automatic request; listing libraries needs explicit action', async () => {
  const f = fixture(async path => path.endsWith('/bases') ? {items: [{id: 'kb-1', name: '<img src=x>'}]} : configured);
  await settle(); assert.deepEqual(f.requests.map(row => row.path), ['/knowledge']);
  f.click('bases'); await settle();
  assert.deepEqual(f.requests.map(row => row.path), ['/knowledge', '/knowledge/bases']);
  assert.match(f.element.html, /&lt;img src=x&gt;/); assert.doesNotMatch(f.element.html, /<img/);
  f.controller.dispose();
});

test('binding clears JWT immediately, sends userAction, rejects duplicate and hides remote failure', async () => {
  const operation = deferred();
  const f = fixture(path => path.endsWith('/binding') ? operation.promise : Promise.resolve(configured));
  await settle();
  const input = f.submit();
  assert.equal(input.value, '');
  const post = f.requests.find(row => row.path.endsWith('/binding'));
  assert.deepEqual(post.body, {token: 'synthetic-jwt-secret', workspace_id: '7'});
  assert.equal(post.method, 'POST'); assert.equal(post.userAction, true);
  const duplicate = f.submit('second-secret'); assert.equal(duplicate.value, '');
  assert.equal(f.requests.filter(row => row.method === 'POST').length, 1);
  operation.reject(Error('raw body includes synthetic-jwt-secret and private-user'));
  await settle();
  assert.match(f.element.html, /绑定结果尚未确认/);
  assert.doesNotMatch(f.element.html, /synthetic-jwt-secret|second-secret|private-user|raw body/);
  assert.deepEqual(f.logs, ['knowledge_settings_operation_completed', 'knowledge_settings_operation_failed']);
  f.controller.dispose();
});

test('invalid workspace and unavailable entry never submit and clear any typed secret', async () => {
  const f = fixture(); await settle();
  for (const value of ['0', '-1', '1.5', '01', '99999999999999999999']) assert.equal(f.submit('secret', value).value, '');
  assert.equal(f.requests.filter(row => row.method === 'POST').length, 0);
  const disabled = fixture(async () => ({enabled: false, configured: false})); await settle();
  assert.equal(disabled.submit().value, ''); disabled.click('bases'); await settle();
  assert.equal(disabled.requests.length, 1);
  assert.match(disabled.element.html, /入口未启用/);
  f.controller.dispose(); disabled.controller.dispose();
});

test('the actual API serializes JWT once with the explicit user-action header', async () => {
  const requests = [];
  const api = createAPI({fetcher: async (url, options) => {
    requests.push({url, ...options});
    return {ok: true, status: 200, json: async () => configured};
  }, logger: () => {}});
  const f = fixture((path, options) => api.request(path, options));
  await settle(); f.submit(); await settle();
  const post = requests.find(row => row.method === 'POST');
  assert.equal(post.url, '/api/research/knowledge/binding');
  assert.equal(post.credentials, 'same-origin');
  assert.equal(post.headers['X-Research-User-Action'], '?1');
  assert.deepEqual(JSON.parse(post.body), {token: 'synthetic-jwt-secret', workspace_id: '7'});
  assert.equal(f.element.token.value, '');
  f.controller.dispose();
});

test('credential editing stays inside the card instead of entering global draft handlers', async () => {
  const f = fixture(); await settle();
  for (const name of ['input', 'change', 'keydown', 'compositionstart', 'compositionend']) {
    let stopped = false;
    f.handlers.get(name)({stopPropagation() { stopped = true; }});
    assert.equal(stopped, true);
  }
  f.controller.dispose();
});

test('dispose aborts the request, clears secrets and ignores late responses', async () => {
  const operation = deferred(); const f = fixture(() => operation.promise);
  f.element.token.value = 'typed-secret'; const input = f.element.token;
  const renders = f.element.renders;
  f.controller.dispose();
  assert.equal(input.value, ''); assert.equal(f.requests[0].signal.aborted, true);
  assert.equal(f.handlers.size, 0); assert.equal(f.element.removed, true);
  operation.resolve({...configured, user_id: 'late-user'}); await settle();
  assert.equal(f.element.renders, renders); assert.deepEqual(f.logs, []);
});

test('mount reuses the panel across redraw and disposes when leaving settings/data', async () => {
  const requests = []; const f = fixture(); await settle(); f.controller.dispose();
  let mounted = null, present = true;
  const root = {querySelector: () => present ? {replaceWith: element => { mounted = element; }} : null};
  const options = {api: {request: async path => { requests.push(path); return configured; }}, document: f.document};
  let panel = mountKnowledgeSettings(root, null, options); await settle();
  assert.equal(mounted, panel.element);
  assert.equal(mountKnowledgeSettings(root, panel, options), panel);
  assert.equal(requests.length, 1);
  present = false; panel = mountKnowledgeSettings(root, panel, options);
  assert.equal(panel, null); assert.equal(f.element.removed, true);
});

test('settings mount is adjacent to warehouse and app stays within existing byte budget', () => {
  const settings = readFileSync(new URL('../../app/research_web/ui/settings.mjs', import.meta.url), 'utf8');
  const app = readFileSync(new URL('../../app/research_web/ui/app.mjs', import.meta.url));
  assert.match(settings, /data-research-warehouse-root><\/div><div data-research-knowledge-root/);
  assert.match(app.toString(), /knowledgeSettingsPanel = mountKnowledgeSettings\(root,knowledgeSettingsPanel/);
  assert.ok(app.length <= 262144, `app.mjs ${app.length} exceeds fixed 256 KiB limit`);
});
