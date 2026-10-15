import assert from 'node:assert/strict';
import test from 'node:test';
import { createConversationNavigation, readNavigationView, saveNavigationView, moveNavigationItem } from '../../app/research_web/ui/conversation-navigation.mjs';
import { renderSidebar } from '../../app/research_web/ui/shell.mjs';

const metadata = mode => ({ mode, revision: 1, pinned: [], project_order: [] });
test('navigation save failures preserve confirmed pins and revisions; a mode cannot overwrite another', async () => {
  let fail = false; const saved = [];
  const nav = createConversationNavigation({ api: {
    navigation: async mode => metadata(mode), projects: async () => ({ items: [] }),
    saveNavigation: async (mode, body) => { if (fail) throw new Error('写入失败'); saved.push([mode, body]); return { mode, ...body, revision: body.revision + 1 }; },
  } });
  await Promise.all([nav.load('fingpt'), nav.load('claw')]);
  await nav.pin('claw', { kind: 'session', id: 'c' }); fail = true;
  await nav.pin('claw', { kind: 'session', id: 'other' });
  assert.deepEqual(nav.state('claw').metadata.pinned, [{ kind: 'session', id: 'c' }]);
  assert.equal(nav.state('claw').metadata.revision, 2);
  assert.deepEqual(nav.state('fingpt').metadata.pinned, []);
  assert.match(nav.state('claw').error, /写入失败/);
  assert.equal(saved.length, 1);
});

test('stale navigation revisions reload authoritative state without replaying the rejected mutation', async () => {
  let revision = 1, writes = 0;
  const nav = createConversationNavigation({ api: {
    navigation: async mode => ({ ...metadata(mode), revision }), projects: async () => ({ items: [] }),
    saveNavigation: async () => { writes++; revision = 2; throw Object.assign(new Error('导航已变化'), { code: 'navigation_changed' }); },
  } });
  await nav.load('claw'); await nav.pin('claw', { kind: 'session', id: 'c' });
  assert.equal(writes, 1); assert.equal(nav.state('claw').metadata.revision, 2);
  assert.deepEqual(nav.state('claw').metadata.pinned, []);
});

test('sorting rejects absent objects and preserves all items at boundaries', () => {
  const items = ['a', 'b', 'c'].map(id => ({ kind: 'session', id }));
  assert.deepEqual(moveNavigationItem(items, items[0], -1), items);
  assert.deepEqual(moveNavigationItem(items, { kind: 'project', id: 'a' }, 1), items);
  assert.deepEqual(moveNavigationItem(items, items[2], 0).map(x => x.id), ['c', 'a', 'b']);
});

test('sidebar rendering uses mode-scoped real rows, hides deleted references and paginates recent sessions', () => {
  const sessions = Array.from({ length: 13 }, (_, i) => ({ id: `c${i}`, mode: 'claw', title: `会话${i}`, updated_at: i, status: 'completed' }));
  const html = renderSidebar({ page: 'claw', sessions: [...sessions, { id: 'f', mode: 'fingpt', title: '不得串入' }, { id: 'gone', mode: 'claw', title: '已删除', deleted_at: 1 }], navigation: { metadata: { ...metadata('claw'), pinned: [{ kind: 'session', id: 'c0' }, { kind: 'session', id: 'gone' }] }, projects: [], loaded: true, view: { limit: 10, expanded: [] } } });
  assert.doesNotMatch(html, /不得串入|已删除|claw-sidebar-tabs/);
  assert.match(html, /置顶/); assert.match(html, /data-nav-more/);
  assert.equal((html.match(/data-session-menu=/g) || []).length, 11);
  assert.equal((html.match(/data-session-menu="c0"/g) || []).length, 1);
  assert.match(html, /新聊天/);
});

test('view preferences survive reload independently for each mode and tolerate storage failures', () => {
  const rows = new Map(); const storage = { getItem: key => rows.get(key), setItem: (key, value) => rows.set(key, value) };
  saveNavigationView('claw', { collapsed: true, expanded: ['p'], limit: 20 }, storage);
  assert.equal(readNavigationView('claw', storage).collapsed, true);
  assert.equal(readNavigationView('fingpt', storage).collapsed, false);
  assert.deepEqual(readNavigationView('claw', { getItem() { throw new Error('blocked'); } }).expanded, []);
});


test('ordinary mobile pages never create research preferences or throw when toggling navigation', () => {
  const nav = createConversationNavigation({ api: {} });
  for (const mode of ['settings', 'history', 'workbench', 'operations', 'frameworks']) {
    assert.doesNotThrow(() => nav.view(mode, { collapsed: true }));
    assert.equal(nav.state(mode), undefined);
  }
});

test('three sidebar sections expose keyboard buttons and remembered independent expansion states', () => {
  const html = renderSidebar({ page: 'fingpt', navigation: { metadata: metadata('fingpt'), projects: [], loaded: true, view: { expanded: [], limit: 10, collapsedSections: ['pinned', 'recent'] } } });
  assert.match(html, /data-nav-section="pinned" aria-expanded="false"/);
  assert.match(html, /data-nav-section="projects" aria-expanded="true"/);
  assert.match(html, /data-nav-section="recent" aria-expanded="false"/);
  assert.match(html, /id="nav-section-fingpt-recent" class="nav-section-body" hidden/);
  const rows = new Map(); const storage = { getItem: key => rows.get(key), setItem: (key, value) => rows.set(key, value) };
  saveNavigationView('fingpt', { collapsedSections: ['recent'], expanded: [], limit: 10 }, storage);
  assert.deepEqual(readNavigationView('fingpt', storage).collapsedSections, ['recent']);
  assert.deepEqual(readNavigationView('claw', storage).collapsedSections, []);
});
