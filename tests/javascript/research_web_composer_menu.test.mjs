import test from 'node:test';
import assert from 'node:assert/strict';
import { renderComposer } from '../../app/research_web/ui/composer.mjs';
import { composerMenuRows, composerMenuKey, openComposerMenu, composerSlashQuery, consumeComposerSlash, nextComposerFormats } from '../../app/research_web/ui/composer-menu.mjs';

const skills = Array.from({ length: 12 }, (_, i) => ({ id: `s${i}`, name: `研究能力${i}`, kind: i % 2 ? 'workflow' : 'skill', enabled: true, version: 1 }));
test('Claw uses one menu with drilldown; FinGPT retains existing controls', () => {
  const claw = renderComposer({ page: 'claw', composerMenu: openComposerMenu('add') });
  assert.match(claw, /claw-composer-menu/);
  assert.doesNotMatch(claw, /composer-more-panel|class="format-options"|method-picker/);
  assert.match(renderComposer({ page: 'fingpt' }), /class="format-options"/);
});
test('add and slash roots expose only existing actions, slash searches every eligible capability', () => {
  assert.deepEqual(composerMenuRows(openComposerMenu('add')).map(x => x.key), ['upload', 'capabilities', 'methods', 'formats']);
  assert.equal(composerMenuRows(openComposerMenu('slash')).length, 5);
  const rows = composerMenuRows(openComposerMenu('slash', 'root', '研究能力'), { skills });
  assert.equal(rows.length, 12);
  assert.deepEqual(rows.map(x => x.group), [...Array(6).fill('Skill'), ...Array(6).fill('Workflow')]);
  assert.equal(composerMenuRows(openComposerMenu('slash', 'root', 'model'))[0].value, 'models');
  assert.equal(composerMenuRows(openComposerMenu('add', 'capabilities'), { skills: null }).length, 0);
});
test('keyboard skips disabled items and never submits an empty result', () => {
  const rows = [{ disabled: true }, { value: 'first' }, { value: 'last' }];
  assert.equal(composerMenuKey('Home', 0, rows).index, 1);
  assert.equal(composerMenuKey('End', 1, rows).index, 2);
  assert.equal(composerMenuKey('ArrowDown', 2, rows).index, 1);
  assert.equal(composerMenuKey('ArrowUp', 0, rows).index, 2);
  assert.equal(composerMenuKey('ArrowUp', 0, [{ disabled: true }, { value: 'only' }]).index, 1);
  assert.equal(composerMenuKey('Enter', 0, rows).select, null);
  assert.deepEqual(composerMenuKey('Enter', 0, []), { handled: true, select: null });
  assert.equal(composerMenuKey('Escape', 0, []).back, true);
});
test('slash consumption preserves ordinary multiline draft and cancellation needs no mutation', () => {
  const draft = ' /能力\n保留研究目标\n以及附件说明';
  assert.equal(composerSlashQuery(draft), '能力');
  assert.equal(consumeComposerSlash(draft), '保留研究目标\n以及附件说明');
  assert.equal(consumeComposerSlash('研究 / 正文'), '研究 / 正文');
  assert.equal(composerSlashQuery('https://example.com'), null);
});
test('method cap permits deselection, while formats preserve auto and explicit-none semantics', () => {
  const methods = skills.slice(0, 4);
  const rows = composerMenuRows(openComposerMenu('add', 'methods'), { methods, methodIds: ['s0', 's1', 's2'] });
  assert.equal(rows[0].disabled, false); assert.equal(rows[3].disabled, true);
  assert.deepEqual(nextComposerFormats(null, 'md'), ['md']);
  assert.deepEqual(nextComposerFormats(['md', 'pdf'], 'md'), ['pdf']);
  assert.equal(nextComposerFormats(['md'], 'auto'), null);
  assert.deepEqual(nextComposerFormats(null, 'none'), []);
});
test('restricted execution exposes no new controls and busy actions stay disabled', () => {
  const restricted = renderComposer({ page: 'claw', detail: { execution_context: {} }, composerMenu: openComposerMenu('slash') });
  assert.doesNotMatch(restricted, /id="claw-composer-menu"/);
  assert.ok(composerMenuRows(openComposerMenu('slash', 'capabilities'), { skills, busy: true }).every(x => x.disabled));
  const blockedUpload = composerMenuRows(openComposerMenu('add'), { uploadsAllowed: false });
  assert.equal(blockedUpload[0].disabled, true);
  assert.equal(blockedUpload[1].disabled, false);
  assert.ok(composerMenuRows(openComposerMenu('add', 'formats'), { disabled: true }).every(x => x.disabled));
});
