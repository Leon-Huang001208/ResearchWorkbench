import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import { mountLegacyAccountMenu, renderAccountMenu } from '../../app/research_web/ui/server/account-menu.mjs';

const source = readFileSync(new URL('../../app/research_web/ui/server/accounts.mjs', import.meta.url), 'utf8').replace(/^import .*;$/gm, '');

async function login(result, failure = false) {
  const requests = [], redirects = [], logs = [];
  let submit;
  const button = {};
  const form = { elements: { username: { value: 'synthetic' }, password: { value: 'fixture-password' } }, setAttribute() {}, querySelector: () => button, addEventListener: (_, handler) => { submit = handler; } };
  const message = {};
  vm.runInNewContext(source, {
    location: { pathname: '/auth', search: '?return_to=%2Fauthorize%3Fclient_id%3Drwb-codex-native', assign: value => redirects.push(value) },
    document: { getElementById: id => id === 'login-form' ? form : message },
    URLSearchParams,
    legacyAccountTarget: () => null,
    safeLog: (...args) => logs.push(args),
    createAccountAPI: () => async (...args) => { requests.push(args); if (failure) throw new Error('login_failed'); return result; },
  });
  submit({ preventDefault() {} });
  await new Promise(resolve => setImmediate(resolve));
  return { requests, redirects, logs, form };
}

test('existing login returns only server validated OAuth target and clears password', async () => {
  const result = await login({ return_to: '/authorize?client_id=rwb-codex-native' });
  assert.equal(result.requests[0][0], 'login');
  assert.equal(result.requests[0][2].return_to, '/authorize?client_id=rwb-codex-native');
  assert.deepEqual(result.redirects, ['/authorize?client_id=rwb-codex-native']);
  assert.equal(result.form.elements.password.value, '');
  assert.equal(JSON.stringify(result.logs).includes('fixture-password'), false);
});

test('disabled or rejected return target uses normal root; failed login never navigates', async () => {
  assert.deepEqual((await login({ user: {} })).redirects, ['/']);
  const failed = await login({}, true);
  assert.deepEqual(failed.redirects, []);
  assert.equal(failed.form.elements.password.value, '');
  assert.equal(failed.logs[0][0], 'account_login_failed');
});

test('authorized applications link appears only for explicit enabled gateway flag', () => {
  const user = { username: 'synthetic', role: 'user' };
  for (const flag of [undefined, false, 'true']) assert.equal(renderAccountMenu({ ...user, mcp_readonly_enabled: flag }).includes('/mcp/applications'), false);
  assert.equal(renderAccountMenu({ ...user, mcp_readonly_enabled: true }).includes('href="/mcp/applications"'), true);
});

test('server bootstrap preserves only exact enabled flag for the modern account menu', async () => {
  const bootstrap = readFileSync(new URL('../../app/research_web/ui/server/session.mjs', import.meta.url), 'utf8').replace(/^import .*;$/gm, '').replace("await import('/static/app.mjs');", '');
  for (const flag of [true, false, undefined, 'true']) {
    const context = { window: { fetch: async () => ({ ok: true, json: async () => ({ user: { id: 'synthetic', username: '<user>', role: 'user', mcp_readonly_enabled: flag } }) }), EventSource: class {} }, document: { createElement: () => ({}), head: { append() {} }, body: {}, querySelector: () => null }, MutationObserver: class { observe() {} }, mountLegacyAccountMenu() {}, mountLegacyAccountWorkspace() {}, safeLog() {}, location: {}, URL, Request };
    await vm.runInNewContext(`(async()=>{${bootstrap}})()`, context);
    assert.equal(renderAccountMenu(context.__RWB_ACCOUNT__).includes('/mcp/applications'), flag === true);
    assert.equal(renderAccountMenu(context.__RWB_ACCOUNT__).includes('<user>'), false);
  }
});

test('existing legacy menu adds and removes application action across identity updates without duplicate observers', () => {
  let observers = 0, reconcile, identity, links = [];
  const makeIdentity = html => ({ html, matches: () => true, replaceWith(next) { identity = next; }, focus() {} });
  identity = makeIdentity('old account');
  const actions = { append(link) { links.push(link); } };
  const menu = { dataset: {}, querySelector(selector) { return selector === '.account-identity' || selector === '.account-profile-link' ? identity : selector === '.account-actions' ? actions : null; }, querySelectorAll: () => links };
  const document = { getElementById: () => menu, createElement(tag) { if (tag === 'template') { const template = { content: {} }; Object.defineProperty(template, 'innerHTML', { set(html) { template.content.firstElementChild = makeIdentity(html); } }); return template; } return { setAttribute(name, value) { this[name] = value; }, remove() { links = links.filter(link => link !== this); } }; } };
  const root = { dataset: {} };
  const Observer = class { constructor(fn) { reconcile = fn; observers++; } observe() {} };
  const mount = user => mountLegacyAccountMenu({ root, user, document, Observer });
  mount({ id: 'first', username: 'First', role: 'user', mcp_readonly_enabled: true });
  reconcile();
  assert.equal(links.length, 1);
  assert.equal(links[0].href, '/mcp/applications');
  mount({ id: 'second', username: '<Second>', role: 'user', mcp_readonly_enabled: false });
  assert.equal(links.length, 0);
  assert.ok(identity.html.includes('&lt;Second&gt;'));
  assert.equal(identity.html.includes('First'), false);
  mount({ id: 'third', username: 'Third', role: 'user', mcp_readonly_enabled: true });
  reconcile();
  assert.equal(links.length, 1);
  assert.equal(observers, 1);
});
