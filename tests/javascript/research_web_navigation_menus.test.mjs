import assert from 'node:assert/strict';
import test from 'node:test';
import { sessionMenuPosition, projectMenuPosition, renderProjectActionsMenu, renderSessionMenu } from '../../app/research_web/ui/conversation-menus.mjs';

const session = { id: 'session-1', status: 'completed', project_id: 'research', mode: 'claw' };
const navigation = {
  loaded: true, busy: false, metadata: { pinned: [{ kind: 'session', id: 'session-1' }] },
  projects: [{ id: 'default', name: '默认项目' }, { id: 'research', name: '研究项目' }, { id: 'archived', name: '已归档', archived: true }],
};
const render = options => renderSessionMenu({ session, position: { left: 20, top: 30 }, navigation, ...options });

test('session menu preserves action contracts and opens a custom project chooser on request', () => {
  const closed = render();
  assert.match(closed, /role="menu" aria-label="会话操作"/);
  assert.match(closed, /data-menu-rename="session-1"/);
  assert.match(closed, /data-nav-pin="session" data-nav-id="session-1"/);
  assert.match(closed, /data-nav-order="-1" data-nav-group="pinned" data-nav-entity="session"/);
  assert.match(closed, /data-nav-move-menu="session-1" aria-haspopup="menu" aria-expanded="false"/);
  assert.doesNotMatch(closed, /session-project-menu/);
  const opened = render({ move: { left: 232, top: 30, width: 232 } });
  assert.match(opened, /aria-expanded="true"/);
  assert.match(opened, /role="menu" aria-label="选择项目"/);
  assert.doesNotMatch(opened, /session-project-menu-header|data-nav-move-close/);
  assert.equal((opened.match(/>移动到项目</g) || []).length, 1);
  assert.doesNotMatch(opened, /<(select|option)\b|已归档/);
});

test('project choices expose current membership and escape full long names in both title and label', () => {
  const name = '超长研究项目'.repeat(30) + '"><img src=x onerror=alert(1)>';
  const html = render({ navigation: { ...navigation, projects: [{ id: 'research', name }, { id: 'other', name: '其他' }] }, move: { left: 8, top: 8 } });
  assert.match(html, /role="menuitemradio" aria-checked="true" data-nav-move-target="research" data-nav-session="session-1"/);
  assert.match(html, /role="menuitemradio" aria-checked="false" data-nav-move-target="other"/);
  assert.match(html, /title="超长研究项目/);
  assert.match(html, /&quot;&gt;&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.doesNotMatch(html, /<img|<select|<option/);
  assert.equal((html.match(/m5 12 4 4L19 6/g) || []).length, 1);
});

test('empty project chooser is truthful and busy choices cannot mutate', () => {
  assert.match(render({ navigation: { ...navigation, projects: [] }, move: {} }), /role="status">暂无可用项目/);
  const html = render({ navigation: { ...navigation, busy: true }, move: {} });
  assert.match(html, /data-nav-move-target="research"[^>]+disabled/);
  assert.match(render({ navigation: { ...navigation, loaded: false } }), /data-nav-pin="session"[^>]+disabled/);
});

test('running and waiting sessions cannot be deleted; completed sessions can', () => {
  for (const status of ['running', 'queued', 'waiting_input', 'waiting_approval']) {
    const html = render({ session: { ...session, status } });
    assert.match(html, /data-menu-delete="session-1" disabled[^>]+aria-describedby="session-delete-reason"/);
    assert.match(html, /id="session-delete-reason"/);
  }
  assert.doesNotMatch(render(), /data-menu-delete="session-1" disabled|id="session-delete-reason"/);
});

test('project submenu prefers right, flips left, clamps vertically and overlays on mobile', () => {
  assert.deepEqual(projectMenuPosition({ left: 20, right: 228, top: 40 }, { width: 1200, height: 800 }), { left: 232, top: 40, width: 232 });
  assert.deepEqual(projectMenuPosition({ left: 900, right: 1108, top: 760 }, { width: 1200, height: 800 }), { left: 664, top: 492, width: 232 });
  assert.deepEqual(projectMenuPosition({ left: 16, right: 224, top: 100 }, { width: 390, height: 844 }), { left: 16, top: 100, width: 232 });
  for (const [width, height] of [[240, 240], [320, 500], [640, 600], [800, 600], [1200, 800]]) {
    for (const left of [-50, 8, width - 220, width + 20]) {
      const result = projectMenuPosition({ left, right: left + 208, top: height + 100 }, { width, height });
      assert.ok(result.left >= 8 && result.left + result.width <= width - 8);
      assert.ok(result.top >= 8 && result.top <= Math.max(8, height - 308));
    }
  }
});

test('project menu retains exact actions, protects default project, and scopes project files to the current mode', () => {
  const html = renderProjectActionsMenu({ project: { id: 'research', name: '研究' }, position: { left: 10, top: 20 }, pinned: true, group: 'pinned', busy: true });
  for (const attr of ['data-nav-pin="project"', 'data-nav-project-rename="research"', 'data-nav-project-archive="research"', 'data-nav-new-in-project="research"', 'data-nav-group="pinned"']) assert.ok(html.includes(attr));
  assert.match(html, /role="menuitem" href="#\/claw\?view=projects&project=research"/);
  const defaultMenu = renderProjectActionsMenu({ project: { id: 'default' }, mode: 'fingpt' });
  assert.doesNotMatch(defaultMenu, /data-nav-project-rename|data-nav-project-archive|href="#\/claw/);
  assert.match(defaultMenu, /href="#\/fingpt\?view=projects&project=default"/);
});


test('row menus open to the right, flip when necessary and avoid covering the source row on narrow screens', () => {
  const row = { left: 78, right: 338, top: 120, bottom: 164 };
  assert.deepEqual(sessionMenuPosition(row, { width: 1440, height: 900 }), { left: 344, top: 120, width: 208 });
  assert.deepEqual(sessionMenuPosition({ left: 1000, right: 1260, top: 120, bottom: 164 }, { width: 1280, height: 900 }), { left: 786, top: 120, width: 208 });
  const narrow = sessionMenuPosition(row, { width: 390, height: 900 });
  assert.ok(narrow.top >= row.bottom + 6);
  assert.ok(narrow.left + narrow.width <= 382);
});
