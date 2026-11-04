import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import { renderAccountMenu } from '../../app/research_web/ui/server/account-menu.mjs';

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
