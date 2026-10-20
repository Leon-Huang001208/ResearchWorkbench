import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import { runInNewContext } from 'node:vm';
import { mountLegacyAccountMenu } from '../../app/research_web/ui/server/account-menu.mjs';

test('server fetch wrapper preserves RequestInit overrides and binds requests and streams to the page account', async () => {
  const source = fs.readFileSync(new URL('../../app/research_web/ui/server/session.mjs', import.meta.url), 'utf8').replace(/^import .*;\n/gm, '').replace("await import('/static/app.mjs');", '');
  const userId = '11111111-1111-4111-8111-111111111111';
  const sent = [];
  const window = {
    fetch: async input => {
      if (input === '/api/server/me') return { ok: true, json: async () => ({ user: { id: userId, username: 'alice', role: 'user' } }) };
      sent.push(input); return { status: 200 };
    },
    EventSource: class { constructor(url) { this.url = url; } },
  };
  const context = { window, Request, URL, mountLegacyAccountMenu, safeLog() {}, MutationObserver: class { observe() {} }, location: { href: 'https://unit.tailabc.ts.net/', origin: 'https://unit.tailabc.ts.net', replace() {} }, document: { createElement: () => ({ style: {}, setAttribute() {} }), body: { append() {} }, head: { append() {} }, querySelector: () => null } };
  await runInNewContext(`(async () => {${source}\n})()`, context);
  assert.equal(context.__RWB_ACCOUNT__.username, 'alice');
  assert.equal(context.__RWB_ACCOUNT__.role, 'user');
  assert.equal(Object.isFrozen(context.__RWB_ACCOUNT__), true);
  assert.ok(!source.includes('document.body.append'));
  const signal = AbortSignal.abort();
  const initial = new Request('https://unit.tailabc.ts.net/api/research/sessions', { method: 'POST', body: 'old' });
  await window.fetch(initial, { method: 'DELETE', headers: { 'X-Override': 'yes' }, body: 'new', signal });
  assert.equal(sent[0].method, 'DELETE');
  assert.equal(sent[0].headers.get('X-Override'), 'yes');
  assert.equal(sent[0].headers.get('X-RWB-Page-User'), userId);
  assert.equal(sent[0].signal.aborted, true);
  assert.equal(await sent[0].text(), 'new');
  const events = new window.EventSource('/api/research/sessions/example/events');
  assert.equal(new URL(events.url).searchParams.get('rwb_user'), userId);
});
