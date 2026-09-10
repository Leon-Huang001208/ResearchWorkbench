import assert from 'node:assert/strict';
import test from 'node:test';

import { createAPI, createController } from '../../app/research_web/ui/core.mjs';
import { renderComposer, tabbitKey, tabbitMentionQuery } from '../../app/research_web/ui/composer.mjs';

const session = { id: 's1', title: '研究', mode: 'fingpt', status: 'idle', messages: [], activities: [], subagents: [], files: [], approvals: [], questions: [] };

test('@ query and keyboard navigation coexist with slash commands', () => {
  assert.equal(tabbitMentionQuery('看看 @github'), 'github');
  assert.equal(tabbitMentionQuery('@'), '');
  assert.equal(tabbitMentionQuery('/company'), null);
  assert.deepEqual(tabbitKey('ArrowDown', 1, [1, 2, 3]), { handled: true, index: 2 });
  assert.deepEqual(tabbitKey('Escape', 0, []), { handled: true, close: true });
  assert.deepEqual(tabbitKey('Enter', 0, [{ tab_id: 7 }]), { handled: true, select: 7 });
});

test('composer renders accessible candidates, loading state, and removable chips', () => {
  const html = renderComposer({
    page: 'fingpt', draft: '比较 @research', tabbitOpen: true, tabbitLoading: false,
    tabbitIndex: 0,
    tabbitCandidates: [{ tab_id: 7, instance_id: 'ABCDEF0123456789', title: 'Research', url: 'https://example.test' }],
    tabbitTabs: [{ tab_id: 8, instance_id: 'ABCDEF0123456789', title: 'Form page', url: 'https://form.test' }],
  });
  assert.match(html, /id="tabbit-options"/);
  assert.match(html, /role="listbox"/);
  assert.match(html, /data-tabbit-select="7"/);
  assert.match(html, /data-remove-tabbit="8"/);
  assert.match(html, /实时标签页 1\/8/);
  assert.match(renderComposer({ page: 'fingpt', tabbitOpen: true, tabbitLoading: true }), /正在读取可用标签页/);
});

test('API exposes status, settings, access, and lazy tab inventory routes', async () => {
  const calls = [];
  const api = createAPI({ fetcher: async (url, options) => { calls.push([url, options]); return new Response(JSON.stringify({ accepted: true })); }, logger() {} });
  await api.tabbitStatus();
  await api.configureTabbit({ browser_enabled: true, web_fetch_enabled: false });
  await api.tabbitAccess('s/1', 'approve');
  await api.tabbitTabs('s/1', 'github', 50);
  assert.deepEqual(calls.map(([url]) => url), [
    '/api/research/runtime/tabbit',
    '/api/research/runtime/tabbit',
    '/api/research/sessions/s%2F1/tabbit-access',
    '/api/research/sessions/s%2F1/tabbit-tabs?q=github&limit=50',
  ]);
  assert.equal(calls[1][1].method, 'PUT');
});

test('controller confirms live claim, sends at most eight references, and preserves failures', async () => {
  const bodies = [];
  let fail = true;
  const controller = createController({
    api: {
      detail: async () => session,
      message: async (_id, body) => { bodies.push(body); if (fail) throw new Error('claim failed'); return { accepted: true }; },
    },
    confirmTabbit: async () => true,
    makeID: () => 'stable',
  });
  await controller.open({ page: 'fingpt', sessionId: 's1' });
  controller.setDraft('真实问题');
  for (let id = 1; id <= 8; id += 1) controller.addTabbit({ tab_id: id, instance_id: 'ABCDEF0123456789', title: `Tab ${id}`, url: `https://${id}.test` });
  assert.throws(() => controller.addTabbit({ tab_id: 9, instance_id: 'ABCDEF0123456789', title: 'Too many', url: 'https://9.test' }), /最多.*8/);
  await controller.send();
  assert.equal(controller.state.draft, '真实问题');
  assert.equal(controller.state.tabbitTabs.length, 8);
  assert.equal(bodies[0].tabbit_live_confirmed, true);
  assert.equal(bodies[0].tabbit_tabs.length, 8);
  fail = false;
  await controller.send();
  assert.equal(controller.state.draft, '');
  assert.equal(controller.state.tabbitTabs.length, 0);
});

test('cancelled second confirmation leaves draft and chips untouched without sending', async () => {
  let sent = 0;
  const controller = createController({
    api: { detail: async () => session, message: async () => { sent += 1; } },
    confirmTabbit: async () => false,
  });
  await controller.open({ page: 'fingpt', sessionId: 's1' });
  controller.setDraft('不要丢失');
  controller.addTabbit({ tab_id: 1, instance_id: 'ABCDEF0123456789', title: 'Page', url: 'https://example.test' });
  await controller.send();
  assert.equal(sent, 0);
  assert.equal(controller.state.draft, '不要丢失');
  assert.equal(controller.state.tabbitTabs.length, 1);
});
