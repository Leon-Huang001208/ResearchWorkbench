import assert from 'node:assert/strict';
import test from 'node:test';
import { createConversationNavigation, renderProjectEditor, readNavigationView, saveNavigationView, moveNavigationItem } from '../../app/research_web/ui/conversation-navigation.mjs';
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


test('recent conversation rows omit leading dot markers without discarding native running status', async () => {
  const { renderSessionRow } = await import('../../app/research_web/ui/shell.mjs');
  const idle = renderSessionRow({ id: 'i', mode: 'claw', title: '普通会话', status: 'completed' });
  const running = renderSessionRow({ id: 'r', mode: 'claw', title: '运行会话', status: 'running' });
  assert.doesNotMatch(idle, /tiny-dot/);
  assert.doesNotMatch(running, /tiny-dot/);
  assert.match(running, /title="运行会话 · 运行中"/);
  assert.match(running, /class="sr-only" role="status" aria-label="运行中"/);
});


test('project editor is a centered accessible create and rename dialog with safe drafts and busy errors', () => {
  assert.equal(renderProjectEditor({ editor: null }), '');
  const creating = renderProjectEditor({ editor: { name: '<草稿>' }, busy: false, error: '' });
  assert.match(creating, /role="dialog" aria-modal="true" aria-labelledby="nav-project-heading"/);
  assert.match(creating, /创建项目/);
  assert.match(creating, /value="&lt;草稿&gt;"/);
  assert.match(creating, /data-nav-editor-close aria-label="关闭创建项目"/);
  assert.doesNotMatch(creating, /type="file"|添加文件夹/);
  const failed = renderProjectEditor({ editor: { id: 'p1', name: '保留的项目名' }, error: '<保存失败>', busy: false });
  assert.match(failed, /重命名项目/);
  assert.match(failed, /role="alert">&lt;保存失败&gt;/);
  assert.match(failed, /value="保留的项目名"/);
  const busy = renderProjectEditor({ editor: { name: '项目' }, busy: true });
  assert.match(busy, /aria-busy="true"/);
  assert.match(busy, /正在保存…/);
  assert.equal((busy.match(/disabled/g) || []).length, 4);
});


test('project members only appear in their project while default and unavailable project rows remain recent', () => {
  for (const mode of ['claw', 'fingpt']) {
    const rows = [
      { id: 'member', mode, project_id: 'p1', title: '项目成员', status: 'running' },
      { id: 'default-member', mode, project_id: 'default', title: '未分组', status: 'completed' },
      { id: 'legacy', mode, project_id: 'archived', title: '已归档项目会话', status: 'completed' },
    ];
    const nav = { metadata: metadata(mode), projects: [{ id: 'p1', name: '项目一' }, { id: 'archived', archived: true }], loaded: true, view: { expanded: ['p1'], limit: 10 } };
    const html = renderSidebar({ page: mode, sessions: rows, navigation: nav });
    const recent = html.slice(html.indexOf('<section class="nav-section" aria-label="最近">'));
    assert.doesNotMatch(recent, /data-session-menu="member"/);
    assert.match(recent, /data-session-menu="default-member"/);
    assert.match(recent, /data-session-menu="legacy"/);
    assert.equal((html.match(/data-session-menu="member"/g) || []).length, 1);
    nav.view.expanded = [];
    assert.doesNotMatch(renderSidebar({ page: mode, sessions: rows, navigation: nav }), /data-session-menu="member"/);
  }
});


test('pinned project members render only in pinned without changing their project membership', () => {
  for (const mode of ['claw', 'fingpt']) {
    const row = { id: 'pinned-member', mode, project_id: 'p1', title: '置顶成员', status: 'running' };
    const nav = { metadata: { ...metadata(mode), pinned: [{ kind: 'session', id: row.id }] }, projects: [{ id: 'p1', name: '项目一' }], loaded: true, view: { expanded: ['p1'], limit: 10 } };
    const html = renderSidebar({ page: mode, sessions: [row], navigation: nav });
    assert.equal((html.match(/data-session-menu="pinned-member"/g) || []).length, 1);
    const projectStart = html.indexOf('<section class="nav-section" aria-label="项目">');
    assert.doesNotMatch(html.slice(projectStart), /data-session-menu="pinned-member"/);
    assert.equal(row.project_id, 'p1');
  }
});


test('sidebar puts schedules then project management below new chat without duplicate capability menu entry', () => {
  for (const page of ['claw', 'fingpt']) {
    const html = renderSidebar({ page, clawView: 'projects' });
    const menu = html.match(/<details class="nav-mode-menu"[^]*?<\/details>/)[0];
    assert.doesNotMatch(menu, /Agent 日程|选择能力|管理项目/);
    const shortcuts = html.match(/<nav class="nav-shortcuts"[^]*?<\/nav>/)[0];
    assert.ok(html.indexOf('nav-shortcuts') > html.indexOf('data-new'));
    assert.match(shortcuts, new RegExp(`href="#/${page}\\?view=projects&project=default" aria-current="page"`));
    if (page === 'claw') assert.ok(shortcuts.indexOf('Agent 日程') < shortcuts.indexOf('管理项目'));
    else assert.doesNotMatch(shortcuts, /Agent 日程/);
  }
});


test('default project expansion explains recent location without repeating ungrouped conversations', () => {
  const html = renderSidebar({ page: 'claw', sessions: [{ id: 'unassigned', mode: 'claw', project_id: 'default', title: '未分组' }], navigation: { metadata: metadata('claw'), projects: [{ id: 'default', name: '默认项目' }], loaded: true, view: { expanded: ['default'], limit: 10 } } });
  assert.equal((html.match(/data-session-menu="unassigned"/g) || []).length, 1);
  assert.match(html, /未分组会话显示在最近/);
});


test('revealing a moved or unpinned session opens its real section and includes old recent rows', () => {
  const nav = createConversationNavigation({ api: {} }); const s = nav.state('claw');
  const rows = Array.from({ length: 27 }, (_, index) => ({ id: `s${index}`, mode: 'claw', project_id: 'default', updated_at: 100 - index }));
  s.view.collapsedSections = ['pinned', 'projects', 'recent'];
  nav.revealSession('claw', 's26', rows);
  assert.equal(s.view.limit, 30); assert.ok(!s.view.collapsedSections.includes('recent'));
  s.projects = [{ id: 'p1' }]; rows[26].project_id = 'p1'; s.metadata.pinned = [{ kind: 'project', id: 'p1' }];
  nav.revealSession('claw', 's26', rows);
  assert.ok(!s.view.collapsedSections.includes('pinned')); assert.ok(s.view.expanded.includes('p1'));
  s.view.collapsedSections = ['pinned', 'projects', 'recent']; s.metadata.pinned = [{ kind: 'session', id: 's26' }];
  nav.revealSession('claw', 's26', rows); assert.ok(!s.view.collapsedSections.includes('pinned'));
  assert.ok(s.view.collapsedSections.includes('projects'));
});


test('conversation body keeps real status and context controls without repeating its sidebar title', async () => {
  const { readFile } = await import('node:fs/promises');
  const app = await readFile(new URL('../../app/research_web/ui/app.mjs', import.meta.url), 'utf8');
  const page = app.slice(app.indexOf('function researchPage()'), app.indexOf('function settingsPage()'));
  assert.doesNotMatch(page, /<h1>|AGENT RESEARCH|RESEARCH SESSION|detail\.title/);
  assert.match(page, /class="session-toolbar" aria-label="会话状态与资料"/);
  assert.match(page, /detail\.questions\?\.length \? 'waiting_input' : detail\.status/);
  assert.match(page, /data-toggle-context/);
});
