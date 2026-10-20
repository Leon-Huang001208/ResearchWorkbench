import assert from 'node:assert/strict';
import test from 'node:test';
import { createAccountMenu, renderAccountMenu } from '../../app/research_web/ui/account-menu.mjs';
import { renderPrimaryRail } from '../../app/research_web/ui/shell.mjs';

const user = { username: 'leon', role: 'admin' };
const settle = () => new Promise(resolve => setImmediate(resolve));

function fixture(fetcher = async () => ({ ok: true })) {
  const events = new Map();
  const logs = [];
  const redirects = [];
  const requests = [];
  const document = { activeElement: null, body: { children: [], append(element) { this.children.push(element); } }, addEventListener(name, fn) { events.set(name, fn); } };
  const make = (kind, owner = null) => ({
    kind, owner, attributes: {}, style: {}, hidden: true, disabled: false,
    offsetWidth: 252, offsetHeight: 250,
    setAttribute(name, value) { this.attributes[name] = value; },
    focus() { document.activeElement = this; },
    click() { this.clicks = (this.clicks || 0) + 1; },
    closest(selector) { return selector === '[data-account-trigger]' && kind === 'trigger' || selector === '[data-account-logout]' && kind === 'logout' || selector === 'a' && ['account', 'settings'].includes(kind) ? this : null; },
    contains(element) { return element === this || element.owner === this; },
    getClientRects() { return [this.getBoundingClientRect()]; },
    getBoundingClientRect() { return { left: 12, right: 56, top: 656, bottom: 700 }; },
    querySelectorAll() { return this.items || []; },
    querySelector() { return this.items?.find(item => item.kind === 'logout'); },
    set innerHTML(value) {
      this.html = value;
      this.items = ['account', 'settings', 'logout'].map(kind => make(kind, this));
      this.items[2].disabled = value.includes('disabled aria-disabled="true"');
    },
  });
  document.createElement = () => make('menu');
  let anchor = make('trigger');
  const root = { querySelector: () => anchor };
  const windowEvents = new Map();
  const window = { innerWidth: 1280, innerHeight: 720, setTimeout, clearTimeout, location: { assign: url => redirects.push(url) }, addEventListener: (name, fn) => windowEvents.set(name, fn) };
  const controller = createAccountMenu({ root, user, document, window, fetcher: async (...args) => { requests.push(args); return fetcher(...args); }, logger: (...args) => logs.push(args) });
  const menu = document.body.children[0];
  const dispatch = (name, target, key) => { const event = { target, key, prevented: false, preventDefault() { this.prevented = true; } }; events.get(name)?.(event); return event; };
  return { controller, menu, document, window, windowEvents, logs, requests, redirects, dispatch, anchor: () => anchor, redraw() { anchor = make('trigger'); controller.sync(); } };
}

test('rail uses one real-account trigger or the original local settings entry', () => {
  const html = renderPrimaryRail({ page: 'settings', account: user });
  assert.equal((html.match(/data-account-trigger/g) || []).length, 1);
  assert.ok(!html.includes('rail-settings'));
  const local = renderPrimaryRail({ page: 'settings' });
  assert.ok(local.includes('rail-settings active'));
  assert.ok(!local.includes('data-account-trigger'));
  const menu = renderAccountMenu({ username: '<script>secret</script>', role: 'user' });
  assert.ok(!menu.includes('<script>'));
  assert.ok(menu.includes('&lt;script&gt;'));
  assert.ok(menu.includes('href="/account"'));
  assert.ok(menu.includes('href="#/settings/general"'));
  assert.ok(menu.includes('<small>用户</small>'));
  assert.ok(renderAccountMenu(user).includes('<small>管理员</small>'));
});

test('menu survives rail redraws, remains unique and restores focus on Escape', () => {
  const f = fixture();
  f.dispatch('click', f.anchor());
  assert.equal(f.menu.hidden, false);
  assert.equal(f.document.activeElement.kind, 'account');
  f.redraw();
  assert.equal(f.anchor().attributes['aria-expanded'], 'true');
  assert.equal(f.document.body.children.length, 1);
  assert.equal(f.menu.style.left, '12px');
  assert.equal(f.menu.style.bottom, '72px');
  f.dispatch('keydown', f.menu.items[0], 'End');
  assert.equal(f.document.activeElement.kind, 'logout');
  f.dispatch('keydown', f.menu.items[2], 'ArrowDown');
  assert.equal(f.document.activeElement.kind, 'account');
  f.dispatch('keydown', f.menu.items[0], 'ArrowUp');
  assert.equal(f.document.activeElement.kind, 'logout');
  f.dispatch('keydown', f.menu.items[2], 'Home');
  assert.equal(f.document.activeElement.kind, 'account');
  f.dispatch('keydown', f.menu.items[0], 'Escape');
  assert.equal(f.menu.hidden, true);
  assert.equal(f.document.activeElement, f.anchor());
});

test('outside click, Tab, focus departure and route changes close the menu', () => {
  const f = fixture();
  f.dispatch('keydown', f.anchor(), 'ArrowUp');
  assert.equal(f.document.activeElement.kind, 'logout');
  f.dispatch('keydown', f.menu.items[2], 'Tab');
  assert.equal(f.menu.hidden, true);
  assert.equal(f.document.activeElement, f.anchor());
  f.dispatch('click', f.anchor());
  f.dispatch('click', { closest: () => null });
  assert.equal(f.menu.hidden, true);
  f.dispatch('click', f.anchor());
  f.dispatch('focusin', { closest: () => null });
  assert.equal(f.menu.hidden, true);
  f.dispatch('click', f.anchor());
  f.windowEvents.get('hashchange')();
  assert.equal(f.menu.hidden, true);
});

test('link menu items activate on Space and leave native Enter activation intact', () => {
  const f = fixture();
  f.dispatch('click', f.anchor());
  for (const item of f.menu.items.slice(0, 2)) {
    assert.equal(f.dispatch('keydown', item, ' ').prevented, true);
    assert.equal(item.clicks, 1);
    assert.equal(f.dispatch('keydown', item, 'Enter').prevented, false);
    assert.equal(item.clicks, 1);
  }
});

test('menu clamps to narrow/short viewports and closes when navigation leaves the screen', () => {
  const f = fixture();
  f.window.innerWidth = 260; f.window.innerHeight = 300;
  f.dispatch('click', f.anchor());
  // The trigger is outside this viewport, as with a closed mobile drawer.
  assert.equal(f.menu.hidden, true);
  f.anchor().getBoundingClientRect = () => ({ left: 200, right: 244, top: 250, bottom: 294 });
  f.dispatch('click', f.anchor());
  assert.equal(f.menu.hidden, false);
  assert.equal(f.menu.style.left, '8px');
  assert.equal(f.menu.style.bottom, '42px');
});

test('logout posts once with the cookie and redirects only after success', async () => {
  let finish;
  const f = fixture(() => new Promise(resolve => { finish = resolve; }));
  f.dispatch('click', f.anchor());
  f.dispatch('click', f.menu.items[2]);
  assert.ok(f.menu.items[2].disabled);
  assert.ok(f.menu.html.includes('正在退出…'));
  f.dispatch('click', f.menu.items[2]);
  assert.equal(f.requests.length, 1);
  assert.deepEqual(f.redirects, []);
  assert.equal(f.requests[0][0], '/api/server/logout');
  assert.equal(f.requests[0][1].method, 'POST');
  assert.equal(f.requests[0][1].credentials, 'same-origin');
  finish({ ok: true }); await settle();
  assert.deepEqual(f.redirects, ['/auth']);
});

test('logout failure stays visible, logs no identity/response and allows an explicit retry', async () => {
  let calls = 0;
  const f = fixture(async () => { if (++calls === 1) throw Error('sensitive response'); return { ok: true }; });
  f.dispatch('click', f.anchor());
  f.dispatch('click', f.menu.items[2]); await settle();
  assert.deepEqual(f.redirects, []);
  assert.ok(f.menu.html.includes('role="alert"'));
  assert.ok(f.menu.html.includes('退出未完成'));
  assert.equal(f.menu.items[2].disabled, false);
  assert.equal(f.document.activeElement.kind, 'logout');
  assert.ok(!JSON.stringify(f.logs).includes('sensitive'));
  assert.ok(!JSON.stringify(f.logs).includes(user.username));
  assert.equal(f.requests.length, 1);
  f.dispatch('click', f.menu.items[2]); await settle();
  assert.deepEqual(f.redirects, ['/auth']);
});

test('HTTP rejection is retryable; an already expired login returns to authentication', async () => {
  for (const status of [500, 401]) {
    const f = fixture(async () => ({ ok: false, status }));
    f.dispatch('click', f.anchor()); f.dispatch('click', f.menu.items[2]); await settle();
    assert.deepEqual(f.redirects, status === 401 ? ['/auth'] : []);
    assert.equal(f.menu.html.includes('role="alert"'), status === 500);
  }
});

test('logout timeout aborts the request and enables explicit retry without automatic resubmission', async () => {
  let expire;
  const f = fixture((url, options) => new Promise((resolve, reject) => options.signal.addEventListener('abort', () => reject(Error('timeout')))));
  f.window.setTimeout = (callback, delay) => { assert.equal(delay, 15000); expire = callback; return 123; };
  f.window.clearTimeout = id => assert.equal(id, 123);
  f.dispatch('click', f.anchor()); f.dispatch('click', f.menu.items[2]);
  expire(); await settle();
  assert.ok(f.requests[0][1].signal.aborted);
  assert.equal(f.requests.length, 1);
  assert.equal(f.menu.items[2].disabled, false);
  assert.ok(f.menu.html.includes('退出未完成'));
  assert.deepEqual(f.redirects, []);
});

test('local mode does not mount a menu or register account handlers', () => {
  const calls = [];
  const controller = createAccountMenu({ document: { createElement: () => calls.push('unexpected') } });
  controller.sync();
  assert.deepEqual(calls, []);
});
