import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';

const root = new URL('../../app/research_web/ui/', import.meta.url);

test('product shell keeps the compact product navigation, real recent work and searchable catalog', async () => {
  const shell = await import(new URL('shell.mjs', root));
  const sessions = [{ id: 'run-1', title: '半导体设备需求', mode: 'fingpt', status: 'running' }];
  const skills = [{ id: 'company-research', name: '公司研究', description: '基于资料完成公司研究' }];
  const html = shell.renderSidebar({ page: 'fingpt', sessionId: null, sessions, skills, collapsed: false });
  for (const expected of ['FinGPT', 'Claw', '能力中心', '历史', '设置', 'data-collapse-sidebar', '半导体设备需求', '运行任务']) assert.match(html, new RegExp(expected));
  const matches = shell.filterGlobalSearch('公司研究', sessions, skills);
  assert.deepEqual(matches.map((item) => item.kind), ['skill']);
  assert.match(shell.renderGlobalSearch('', sessions, skills), /data-global-search/);
});

test('composer provides non-submitting real Skill shortcuts and file drop/paste affordances', async () => {
  const composer = await import(new URL('composer.mjs', root));
  const skills = [
    { id: 'document-reading', name: '资料解读', description: '读取附件' },
    { id: 'company-research', name: '公司研究', description: '研究公司' },
    { id: 'industry-research', name: '行业研究', description: '研究行业' },
    { id: 'fund-evaluation', name: '基金评价', description: '评价基金' },
    { id: 'unrelated', name: '未分类', description: '不属于研究快捷入口' },
  ];
  const shortcuts = composer.researchQuickSkills(skills);
  assert.deepEqual(shortcuts.map((skill) => skill.id), skills.slice(0, 4).map((skill) => skill.id));
  const html = composer.renderComposer({ page: 'claw', draft: '', attachments: [], expectedFormats: null, skills, skillId: '', disabled: false, taskPending: false, detail: null });
  for (const expected of ['data-dropzone', 'data-slash-search', 'data-paste-support', '任务目标或补充信息']) assert.match(html, new RegExp(expected));
  assert.match(composer.renderQuickSkills(skills), /data-skill-shortcut/);
  assert.doesNotMatch(html, /fetch\(|POST \/api\/research/);
});

test('app wires shell-only interactions without changing controller routes or API selectors', async () => {
  const app = await readFile(new URL('app.mjs', root), 'utf8');
  for (const expected of ['renderSidebar', 'renderContextPanel', 'renderComposer', 'skillShortcut', 'globalSearch', 'clipboardData', 'dataTransfer']) assert.match(app, new RegExp(expected));
  assert.match(app, /#\/fingpt/);
  assert.match(app, /#\/claw/);
  assert.doesNotMatch(app, /fetch\(['"`]https?:\/\//);
});

test('right panel tabs stay scoped to the current detail and failed activity errors are visible', async () => {
  const shell = await import(new URL('shell.mjs', root));
  const views = await import(new URL('views.mjs', root));
  const detail = { id: 'only-this-session', mode: 'claw', activities: [{ id: 'failed-call', title: '真实工具', status: 'failed', error: '真实失败原因' }], datasets: [], files: [] };
  const html = shell.renderContextPanel({ detail, selectedTab: 'activity' });
  assert.match(html, /data-context-tab="datasets"/);
  assert.match(html, /真实失败原因/);
  assert.match(views.renderActivities(detail), /<details open>/);
  assert.doesNotMatch(shell.renderContextPanel({ detail, selectedTab: 'files' }), /other-session/);
});
