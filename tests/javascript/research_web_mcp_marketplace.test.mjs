import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { createAPI, parseRoute } from '../../app/research_web/ui/core.mjs';
import {
  mcpMarketplaceTabKey,
  packageSupport,
  renderMCPMarketplace,
  renderMCPServerDialog,
} from '../../app/research_web/ui/mcp-marketplace.mjs';

const registries = [
  { id: 'official', name: 'Official Registry', official: true, immutable: true, auth: { type: 'none', secret_configured: false } },
  { id: 'local-private', name: '私有目录', official: false, immutable: false, auth: { type: 'bearer', secret_configured: true } },
];

const server = (extra = {}) => ({
  registry_id: 'official',
  name: 'io.example/weather',
  version: '1.2.3',
  identity: ['official', 'io.example/weather', '1.2.3'],
  title: 'Weather',
  description: 'Safe forecast tool',
  repository: { url: 'https://example.test/repo' },
  packages: [{ registry_type: 'npm', identifier: '@example/weather', version: '1.2.3', package_type_supported: true, immutable_reference: false }],
  remotes: [], status: 'active', is_latest: true,
  ...extra,
});

const deferred = () => {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
};

const flush = async () => {
  await new Promise(resolve => setImmediate(resolve));
  await new Promise(resolve => setImmediate(resolve));
};

async function createMarketplaceApp(fetchOverride = () => null) {
  const handlers = new Map(); const windowHandlers = new Map();
  const documentState = { activeElement: null, title: '' };
  const main = { scrollTop: 0, scrollTo() {} };
  let currentTrigger = null; let searchInput = null; let registrySelect = null; let tabs = {};
  const makeControl = (id, dataset, value = '') => ({
    id, dataset, value,
    focus() { documentState.activeElement = this; },
    closest: () => null,
  });
  const makeTab = view => ({
    id: `capability-tool-tab-${view}`, dataset: { mcpMarketTab: view },
    focus() { documentState.activeElement = this; },
    click() {
      location.hash = view === 'library' ? '#/skills?kind=tool' : `#/skills?kind=tool&view=${view}`;
      windowHandlers.get('hashchange')?.();
    },
  });
  const root = { _html: '', addEventListener: (name, handler) => handlers.set(name, handler), querySelectorAll: () => [], querySelector: () => null };
  Object.defineProperty(root, 'innerHTML', {
    get() { return this._html; },
    set(value) {
      this._html = value;
      tabs = Object.fromEntries(['library', 'market', 'connections'].map(view => [view, makeTab(view)]));
      searchInput = makeControl('mcp-market-search', { mcpQuery: '' });
      registrySelect = makeControl('mcp-market-registry', { mcpRegistry: '' }, 'official');
      currentTrigger = value.includes('data-mcp-server-detail')
        ? { dataset: { registryId: 'official', serverName: 'io.example/weather', serverVersion: '1.2.3', mcpServerDetail: '' }, disabled: false, getAttribute: () => null, focus() { documentState.activeElement = this; } }
        : null;
    },
  });
  const first = { focus() { documentState.activeElement = this; } }; const last = { focus() { documentState.activeElement = this; } };
  const dialog = { contains: value => value === first || value === last, querySelectorAll: () => [first, last] };
  Object.assign(documentState, {
    querySelector: selector => selector === '#app' ? root : selector === '#main' ? main : selector === '.skip-link' ? { addEventListener() {} } : selector === '.mcp-server-dialog' ? dialog : selector === '.mcp-server-dialog [data-mcp-detail-close]' ? first : selector.match(/^\[data-mcp-market-tab="(.+)"\]$/)?.[1] ? tabs[selector.match(/^\[data-mcp-market-tab="(.+)"\]$/)[1]] : null,
    querySelectorAll: selector => selector === '[data-mcp-server-detail]' && currentTrigger ? [currentTrigger] : [],
    getElementById: id => id.startsWith('capability-tool-tab-') ? tabs[id.replace('capability-tool-tab-', '')]
      : id === 'mcp-market-search' ? searchInput
        : id === 'mcp-market-registry' ? registrySelect : null,
  });
  const previous = new Map(['document', 'window', 'location', 'history', 'fetch'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  const originalLog = console.info;
  Object.defineProperty(globalThis, 'document', { configurable: true, value: documentState });
  Object.defineProperty(globalThis, 'window', { configurable: true, value: { matchMedia: () => ({ matches: true }), addEventListener: (name, handler) => windowHandlers.set(name, handler) } });
  Object.defineProperty(globalThis, 'location', { configurable: true, value: { hash: '#/skills?kind=tool&view=market' } });
  Object.defineProperty(globalThis, 'history', { configurable: true, value: { pushState(_a, _b, hash) { location.hash = hash; }, replaceState(_a, _b, hash) { location.hash = hash; } } });
  Object.defineProperty(globalThis, 'fetch', { configurable: true, value: async (url, options) => {
    const custom = fetchOverride(url, options);
    if (custom) return await custom;
    const payload = url.endsWith('/mcp/registries') ? { items: registries }
      : url.includes('/mcp/servers?') ? { items: [server()], count: 1, stale: false }
        : url.endsWith('/runtime') ? { connected: true }
          : url.endsWith('/models') ? { groups: [] } : { items: [] };
    return new Response(JSON.stringify(payload));
  } });
  console.info = () => {};
  await import(`../../app/research_web/ui/app.mjs?mcp-races=${Date.now()}-${Math.random()}`);
  return {
    handlers, windowHandlers, documentState, root,
    trigger: () => currentTrigger, tab: view => tabs[view], searchInput: () => searchInput, registrySelect: () => registrySelect,
    input(dataset, value) {
      const target = 'mcpQuery' in dataset ? searchInput : { id: '', dataset, value, closest: () => null };
      target.value = value; documentState.activeElement = target;
      handlers.get('input')({ target });
    },
    changeRegistry(value) {
      registrySelect.value = value; documentState.activeElement = registrySelect;
      return handlers.get('change')({ target: registrySelect });
    },
    submit() { return handlers.get('submit')({ preventDefault() {}, target: { matches: selector => selector === '[data-mcp-search]' } }); },
    click(button) { return handlers.get('click')({ target: { matches: () => false, closest: selector => selector === 'button' ? button : null } }); },
    async navigate(hash) { location.hash = hash; windowHandlers.get('hashchange')(); await flush(); },
    cleanup() {
      console.info = originalLog;
      for (const [key, descriptor] of previous) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key]; }
    },
  };
}

test('MCP market route is valid only for Tool and keeps legacy route fallbacks', () => {
  assert.deepEqual(parseRoute('#/skills?kind=tool&view=market'), { page: 'skills', sessionId: null, capabilityView: 'market', capabilityKind: 'tool' });
  for (const kind of ['skill', 'workflow', 'data']) {
    assert.deepEqual(parseRoute(`#/skills?kind=${kind}&view=market`), { page: 'skills', sessionId: null, capabilityView: 'library', capabilityKind: kind });
  }
  assert.deepEqual(parseRoute('#/skills?view=market'), { page: 'skills', sessionId: null, capabilityView: 'market', capabilityKind: 'tool' });
  assert.deepEqual(parseRoute('#/skills?view=plans'), { page: 'skills', sessionId: null, capabilityView: 'plans', capabilityKind: 'workflow' });
  assert.deepEqual(parseRoute('#/skills?view=connections'), { page: 'skills', sessionId: null, capabilityView: 'connections', capabilityKind: 'tool' });
});

test('MCP API methods encode every path segment and query independently', async () => {
  const calls = [];
  const api = createAPI({ fetcher: async (url, options) => {
    calls.push([url, options]);
    return new Response(JSON.stringify({ items: [] }));
  }, logger() {} });
  await api.mcpRegistries();
  await api.mcpRegistry('private/id');
  await api.mcpServers({ registryId: 'private/id', search: 'a&b = c', cursor: 'next?/=', limit: 25 });
  await api.mcpSyncRegistry('private/id');
  await api.mcpServerVersion('private/id', 'org/name?x=1', '1.2.3+build');
  await api.mcpPublisherPreview({ name: 'server' });
  await api.mcpPublisherValidate({ server_json: { name: 'server' } });
  assert.deepEqual(calls.map(([url, options]) => [url, options.method]), [
    ['/api/research/mcp/registries', 'GET'],
    ['/api/research/mcp/registries/private%2Fid', 'GET'],
    ['/api/research/mcp/servers?registry_id=private%2Fid&search=a%26b+%3D+c&cursor=next%3F%2F%3D&limit=25', 'GET'],
    ['/api/research/mcp/registries/private%2Fid/sync', 'POST'],
    ['/api/research/mcp/servers/private%2Fid/org%2Fname%3Fx%3D1/versions/1.2.3%2Bbuild', 'GET'],
    ['/api/research/mcp/publisher/preview', 'POST'],
    ['/api/research/mcp/publisher/validate', 'POST'],
  ]);
});

test('market CSS preserves the 4/3/2/1 grid, mobile dialog, theme tokens and reduced motion', async () => {
  const css = await readFile(new URL('../../app/research_web/ui/appearance.css', import.meta.url), 'utf8');
  assert.match(css, /\.mcp-market-grid\s*\{[^}]*repeat\(3,/s);
  assert.match(css, /@media \(min-width: 1400px\)[\s\S]*?\.mcp-market-grid\s*\{[^}]*repeat\(4,/);
  assert.match(css, /@media \(max-width: 1100px\)[\s\S]*?\.mcp-market-grid\s*\{[^}]*repeat\(2,/);
  assert.match(css, /@media \(max-width: 600px\)[\s\S]*?\.mcp-market-grid\s*\{[^}]*grid-template-columns:\s*1fr/);
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*?\.capability-preview-dialog\s*\{[^}]*width:\s*100vw[^}]*height:\s*100dvh/);
  assert.match(css, /\.mcp-server-card\s*\{[^}]*var\(--line\)[^}]*var\(--surface\)/s);
  assert.match(css, /:root\[data-theme='dark'\][\s\S]*?--surface:/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)[\s\S]*?transition:\s*none !important/);
});

test('market renderer keeps third-party content text-only and never hotlinks icons', () => {
  const malicious = server({
    name: '<img src=x onerror=alert(1)>', title: '<script>alert(1)</script>',
    description: '" autofocus onfocus=alert(1)', repository: { url: 'https://evil.test/icon.svg' },
    packages: [{ registry_type: 'future-package', identifier: '<b>bad</b>', version: 'latest', package_type_supported: false, immutable_reference: false }],
  });
  const html = renderMCPMarketplace({ registries, selectedRegistryId: 'official', page: { registry_id: 'official', items: [malicious], count: 1, stale: false } });
  assert.doesNotMatch(html, /<script\b|<img\b/i);
  assert.doesNotMatch(html, /src=["']https?:/i);
  assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  assert.match(html, /客户端暂不支持此包类型/);
  assert.match(html, /official · &lt;img/);
  assert.equal(packageSupport(malicious.packages).clientSupported, false);
  assert.equal(packageSupport(malicious.packages).artifactVerified, false);
});

test('package support trusts the normalized capability fields and stays conservative when absent', () => {
  assert.deepEqual(packageSupport([{ registry_type: 'npm', supported: true, identifier: 'legacy', version: '1.0.0' }]), {
    clientSupported: false,
    artifactVerified: false,
    types: ['npm'],
    unsupported: ['npm'],
  });
  assert.deepEqual(packageSupport([{ registry_type: 'mcpb', package_type_supported: true, immutable_reference: true }]), {
    clientSupported: true,
    artifactVerified: true,
    types: ['mcpb'],
    unsupported: [],
  });
  const html = renderMCPMarketplace({ registries, selectedRegistryId: 'official', page: { items: [server()], count: 1, stale: false } });
  assert.match(html, /客户端支持包类型/);
  assert.match(html, /制品尚未验证/);
  assert.doesNotMatch(html, /支持安装|可安装/);
});

test('market renders loading, empty, error, stale and offline states without demo records', () => {
  const loading = renderMCPMarketplace({ loading: true, registries: [], page: null });
  assert.match(loading, /正在读取 MCP 目录/); assert.match(loading, /disabled/);
  const empty = renderMCPMarketplace({ registries, selectedRegistryId: 'official', page: { items: [], count: 0, stale: false } });
  assert.match(empty, /没有匹配的 MCP Server/); assert.doesNotMatch(empty, /Weather/);
  const failed = renderMCPMarketplace({ registries, selectedRegistryId: 'official', error: '功能尚未开启', page: null });
  assert.match(failed, /role="alert"/); assert.match(failed, /重新读取/);
  const stale = renderMCPMarketplace({ registries, selectedRegistryId: 'official', page: { items: [server()], count: 1, stale: true, failure_code: 'registry_timeout' } });
  assert.match(stale, /离线缓存/); assert.match(stale, /registry_timeout/); assert.match(stale, /Weather/);
});

test('real marketplace dialog traps focus and restores its card after backdrop and Escape close', async () => {
  const handlers = new Map();
  const documentState = { activeElement: null, title: '' };
  const trigger = { dataset: { registryId: 'official', serverName: 'io.example/weather', serverVersion: '1.2.3', mcpServerDetail: '' }, disabled: false, getAttribute: () => null, focus() { documentState.activeElement = this; } };
  const first = { focus() { documentState.activeElement = this; } };
  const last = { focus() { documentState.activeElement = this; } };
  const dialog = { contains: value => value === first || value === last, querySelectorAll: () => [first, last] };
  const main = { scrollTop: 0, scrollTo() {} };
  const root = { innerHTML: '', addEventListener: (name, handler) => handlers.set(name, handler), querySelectorAll: () => [], querySelector: () => null };
  Object.assign(documentState, {
    querySelector: selector => selector === '#app' ? root : selector === '#main' ? main : selector === '.skip-link' ? { addEventListener() {} } : selector === '.mcp-server-dialog' ? dialog : selector === '.mcp-server-dialog [data-mcp-detail-close]' ? first : null,
    querySelectorAll: selector => selector === '[data-mcp-server-detail]' ? [trigger] : [],
    getElementById: () => null,
  });
  const previous = new Map(['document', 'window', 'location', 'history', 'fetch'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  const originalLog = console.info;
  try {
    Object.defineProperty(globalThis, 'document', { configurable: true, value: documentState });
    Object.defineProperty(globalThis, 'window', { configurable: true, value: { matchMedia: () => ({ matches: true }), addEventListener() {} } });
    Object.defineProperty(globalThis, 'location', { configurable: true, value: { hash: '#/skills?kind=tool&view=market' } });
    Object.defineProperty(globalThis, 'history', { configurable: true, value: { pushState(_a, _b, hash) { location.hash = hash; }, replaceState(_a, _b, hash) { location.hash = hash; } } });
    Object.defineProperty(globalThis, 'fetch', { configurable: true, value: async (url) => {
      const payload = url.endsWith('/mcp/registries') ? { items: registries }
        : url.includes('/mcp/servers/official/io%2Fexample%2Fweather/versions/1.2.3') ? server()
          : url.includes('/mcp/servers?') ? { items: [server()], count: 1, stale: false }
            : url.endsWith('/runtime') ? { connected: true }
              : url.endsWith('/models') ? { groups: [] } : { items: [] };
      return new Response(JSON.stringify(payload));
    } });
    console.info = () => {};
    await import(`../../app/research_web/ui/app.mjs?mcp-dialog=${Date.now()}`);
    assert.match(root.innerHTML, /data-mcp-server-detail/);
    await handlers.get('click')({ target: { closest: selector => selector === 'button' ? trigger : null, matches: () => false } });
    assert.match(root.innerHTML, /class="capability-preview-dialog mcp-server-dialog"/);
    assert.equal(documentState.activeElement, first);
    documentState.activeElement = last;
    let trapped = false;
    handlers.get('keydown')({ key: 'Tab', shiftKey: false, target: { dataset: {} }, preventDefault() { trapped = true; } });
    assert.equal(trapped, true);
    assert.equal(documentState.activeElement, first);
    await handlers.get('click')({ target: { matches: selector => selector === '[data-mcp-dialog-backdrop]', closest: () => null } });
    assert.doesNotMatch(root.innerHTML, /mcp-server-dialog/);
    assert.equal(documentState.activeElement, trigger);
    await handlers.get('click')({ target: { closest: selector => selector === 'button' ? trigger : null, matches: () => false } });
    let escaped = false;
    handlers.get('keydown')({ key: 'Escape', target: { dataset: {} }, preventDefault() { escaped = true; } });
    assert.equal(escaped, true);
    assert.doesNotMatch(root.innerHTML, /mcp-server-dialog/);
    assert.equal(documentState.activeElement, trigger);
  } finally {
    console.info = originalLog;
    for (const [key, descriptor] of previous) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key]; }
  }
});

test('market dialog is accessible, escapes details and disables unsupported install handoff', () => {
  const detail = server({ title: '<svg onload=alert(1)>', packages: [{ registry_type: 'unknown', identifier: 'bad', package_type_supported: false, immutable_reference: false }] });
  const html = renderMCPServerDialog(detail);
  assert.match(html, /role="dialog"/); assert.match(html, /aria-modal="true"/);
  assert.match(html, /data-mcp-detail-close/); assert.match(html, /data-mcp-dialog-backdrop/);
  assert.match(html, /客户端暂不支持此包类型/); assert.match(html, /disabled/);
  assert.doesNotMatch(html, /<svg\b/i);
});

test('market dialog truthfully reports an independently stale detail response', () => {
  const page = renderMCPMarketplace({ registries, selectedRegistryId: 'official', page: { items: [server()], count: 1, stale: false } });
  const html = renderMCPServerDialog(server({ stale: true, failure_code: '<detail_timeout>' }));
  assert.doesNotMatch(page, /离线缓存/);
  assert.match(html, /role="status"/);
  assert.match(html, /离线缓存/);
  assert.match(html, /&lt;detail_timeout&gt;/);
  assert.doesNotMatch(html, /<detail_timeout>/);
});

test('Tool subview tabs expose stable ids for focus restoration after route rendering', async () => {
  const source = await readFile(new URL('../../app/research_web/ui/capability-workspace.mjs', import.meta.url), 'utf8');
  assert.match(source, /id="capability-tool-tab-\$\{value\}"/);
});

test('deferred catalog results are query-bound and leaving market makes a later retry possible', async () => {
  const old = deferred(); const abandoned = deferred(); let abandonedCalls = 0;
  const app = await createMarketplaceApp(url => {
    if (url.includes('search=old')) return old.promise;
    if (url.includes('search=new')) return new Response(JSON.stringify({ items: [server({ title: 'New result' })], count: 1, stale: false }));
    if (url.includes('search=abandoned')) {
      abandonedCalls += 1;
      return abandonedCalls === 1 ? abandoned.promise : new Response(JSON.stringify({ items: [server({ title: 'Retry result' })], count: 1, stale: false }));
    }
    return null;
  });
  try {
    app.input({ mcpQuery: '' }, 'old');
    const pending = app.submit(); await flush();
    app.input({ mcpQuery: '' }, 'new');
    old.resolve(new Response(JSON.stringify({ items: [server({ title: 'Old result' })], count: 1, stale: false })));
    await pending;
    assert.doesNotMatch(app.root.innerHTML, /Old result/);
    await app.submit();
    assert.match(app.root.innerHTML, /New result/);

    app.input({ mcpQuery: '' }, 'abandoned');
    const leaving = app.submit(); await flush();
    await app.navigate('#/fingpt');
    abandoned.resolve(new Response(JSON.stringify({ items: [server({ title: 'Abandoned result' })], count: 1, stale: false })));
    await leaving;
    await app.navigate('#/skills?kind=tool&view=market');
    assert.match(app.root.innerHTML, /Retry result/);
    assert.doesNotMatch(app.root.innerHTML, /正在读取 MCP 目录/);
  } finally { app.cleanup(); }
});

test('publisher preview response is bound to the exact source revision', async () => {
  const preview = deferred();
  const app = await createMarketplaceApp(url => url.endsWith('/mcp/publisher/preview') ? preview.promise : null);
  try {
    app.input({ mcpPublisherSource: '' }, '{"name":"A"}');
    const pending = app.click({ dataset: { mcpPublisherAction: 'preview' }, disabled: false, getAttribute: () => null });
    await flush();
    app.input({ mcpPublisherSource: '' }, '{"name":"B"}');
    preview.resolve(new Response(JSON.stringify({ valid: true, sha256: 'SHA_FOR_A', canonical_json: '{"name":"A"}', argv: { validate: ['validate-A'], publish: ['publish-A'] }, executed: false })));
    await pending;
    assert.match(app.root.innerHTML, /\{&quot;name&quot;:&quot;B&quot;\}/);
    assert.doesNotMatch(app.root.innerHTML, /SHA_FOR_A|validate-A|publish-A/);
  } finally { app.cleanup(); }
});

test('late detail response cannot survive navigation away from the market', async () => {
  const detail = deferred();
  const app = await createMarketplaceApp(url => url.includes('/versions/1.2.3') ? detail.promise : null);
  try {
    const pending = app.click(app.trigger()); await flush();
    await app.navigate('#/fingpt');
    detail.resolve(new Response(JSON.stringify(server({ title: 'Late detail' }))));
    await pending;
    await app.navigate('#/skills?kind=tool&view=market');
    assert.doesNotMatch(app.root.innerHTML, /mcp-server-dialog|Late detail/);
  } finally { app.cleanup(); }
});

test('query changes invalidate a pending detail and preserve search focus', async () => {
  const detail = deferred();
  const app = await createMarketplaceApp(url => url.includes('/versions/1.2.3') ? detail.promise : null);
  try {
    const pending = app.click(app.trigger()); await flush();
    app.input({ mcpQuery: '' }, 'new context');
    assert.equal(app.documentState.activeElement, app.searchInput());
    detail.resolve(new Response(JSON.stringify(server({ title: 'Late detail' }))));
    await pending;
    assert.doesNotMatch(app.root.innerHTML, /mcp-server-dialog|Late detail|正在读取 MCP 目录/);
    assert.equal(app.documentState.activeElement, app.searchInput());
  } finally { app.cleanup(); }
});

test('registry changes invalidate a pending detail and preserve selector focus', async () => {
  const detail = deferred();
  const app = await createMarketplaceApp(url => url.includes('/versions/1.2.3') ? detail.promise : null);
  try {
    const pending = app.click(app.trigger()); await flush();
    const changing = app.changeRegistry('local-private'); await flush();
    detail.resolve(new Response(JSON.stringify(server({ title: 'Late detail' }))));
    await pending; await changing;
    assert.doesNotMatch(app.root.innerHTML, /mcp-server-dialog|Late detail|正在读取 MCP 目录/);
    assert.equal(app.documentState.activeElement, app.registrySelect());
  } finally { app.cleanup(); }
});

test('failed detail restores focus to the visible replacement card trigger', async () => {
  const app = await createMarketplaceApp(url => url.includes('/versions/1.2.3')
    ? new Response(JSON.stringify({ error: { code: 'registry_timeout', message: '读取失败' } }), { status: 503 })
    : null);
  try {
    const detached = app.trigger();
    await app.click(detached);
    assert.notEqual(app.trigger(), detached);
    assert.equal(app.documentState.activeElement, app.trigger());
  } finally { app.cleanup(); }
});

test('roving Tool tab focus lands on the newly rendered route tab', async () => {
  const routeLoad = deferred(); let deferRoute = false;
  const app = await createMarketplaceApp(url => deferRoute && url.includes('/mcp/servers?') ? routeLoad.promise : null);
  try {
    await app.navigate('#/skills?kind=tool');
    deferRoute = true;
    const oldLibrary = app.tab('library');
    app.documentState.activeElement = oldLibrary;
    app.handlers.get('keydown')({ key: 'ArrowRight', target: oldLibrary, preventDefault() {} });
    await flush();
    routeLoad.resolve(new Response(JSON.stringify({ items: [server()], count: 1, stale: false })));
    await flush();
    assert.equal(location.hash, '#/skills?kind=tool&view=market');
    assert.equal(app.documentState.activeElement, app.tab('market'));
    assert.equal(app.documentState.activeElement.id, 'capability-tool-tab-market');
  } finally { app.cleanup(); }
});

test('market tabs retain roving keyboard behavior', () => {
  assert.deepEqual(mcpMarketplaceTabKey('ArrowRight', 'library'), { handled: true, view: 'market' });
  assert.deepEqual(mcpMarketplaceTabKey('ArrowLeft', 'library'), { handled: true, view: 'connections' });
  assert.deepEqual(mcpMarketplaceTabKey('Home', 'connections'), { handled: true, view: 'library' });
  assert.deepEqual(mcpMarketplaceTabKey('End', 'market'), { handled: true, view: 'connections' });
  assert.deepEqual(mcpMarketplaceTabKey('Enter', 'market'), { handled: false });
});
