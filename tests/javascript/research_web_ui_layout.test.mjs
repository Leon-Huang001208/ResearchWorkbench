import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';

const root = new URL('../../app/research_web/ui/', import.meta.url);

test('product shell keeps the compact product navigation, real recent work and searchable catalog', async () => {
  const shell = await import(new URL('shell.mjs', root));
  const sessions = [{ id: 'run-1', title: '半导体设备需求', mode: 'fingpt', status: 'running' }];
  const skills = [{ id: 'company-research', name: '公司研究', description: '基于资料完成公司研究' }];
  const html = shell.renderSidebar({ page: 'fingpt', sessionId: null, sessions, skills, collapsed: false });
  const rail = shell.renderPrimaryRail({ page: 'fingpt' });
  for (const expected of ['FinGPT', 'Claw', '资产观察', '能力中心', '历史', '设置']) assert.match(rail, new RegExp(expected));
  assert.match(rail, /data-collapse-sidebar/);
  assert.doesNotMatch(rail, /data-theme-(?:select|option)/);
  for (const expected of ['半导体设备需求', '运行任务']) assert.match(html, new RegExp(expected));
  const matches = shell.filterGlobalSearch('公司研究', sessions, skills);
  assert.deepEqual(matches.map((item) => item.kind), ['skill']);
  assert.match(shell.renderGlobalSearch('', sessions, skills), /data-global-search/);
});

test('global search opens report Workflows through their real package detail', async () => {
  const shell = await import(new URL('shell.mjs', root));
  const html = shell.renderGlobalSearch('创业板', [], [{
    id: 'chinext-50-weekly',
    kind: 'report-workflow',
    name: '创业板50周报',
    description: '固定模板报告',
  }]);
  assert.match(html, /data-global-result="report-workflow"/);
  assert.match(html, /data-report-workflow-detail="chinext-50-weekly"/);
  assert.doesNotMatch(html, /data-skill-shortcut="chinext-50-weekly"/);
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

test('Claw landing shows enabled catalog Workflow templates while FinGPT keeps its four Skill shortcuts', async () => {
  const { renderQuickSkills } = await import(new URL('composer.mjs', root));
  const skills = ['document-reading', 'company-research', 'industry-research', 'fund-evaluation'].map(id => ({ id, kind: 'skill', name: id, enabled: true }));
  const workflow = { id: 'real-workflow', kind: 'workflow', name: '真实研究模板', enabled: true, metadata: { scenarios: ['资料研究'], inputs: [{ label: '主题', type: 'text', required: true }], default_formats: ['html'] } };
  const catalog = [...skills, workflow, { ...workflow, id: 'my-workflow', name: '我的模板' }, { ...workflow, id: 'disabled-workflow', enabled: false }, { ...workflow, id: 'draft-workflow', enabled: undefined }];
  const claw = renderQuickSkills(catalog, { page: 'claw' });
  assert.match(claw, /<h2>研究步骤模板<\/h2>/);
  assert.deepEqual([...claw.matchAll(/data-skill-shortcut="([^"]+)"/g)].map(match => match[1]), ['real-workflow', 'my-workflow']);
  for (const expected of ['场景：资料研究', '输入：主题（text · 必填）', '输出：html', '上方能力选择', 'Skill']) assert.ok(claw.includes(expected));
  assert.doesNotMatch(claw, /type="submit"|data-run|已完成步骤/);
  assert.deepEqual([...renderQuickSkills(catalog).matchAll(/data-skill-shortcut="([^"]+)"/g)].map(match => match[1]), skills.map(skill => skill.id));
  assert.match(renderQuickSkills(skills, { page: 'claw' }), /尚无已启用的研究步骤模板/);
  assert.doesNotMatch(renderQuickSkills(skills, { page: 'claw' }), /data-skill-shortcut/);
});

test('landing category filters derive from the displayed catalog kind and escape category labels', async () => {
  const { renderQuickSkills } = await import(new URL('composer.mjs', root));
  const catalog = [
    { id: 'document-reading', kind: 'skill', name: '资料解读', category: '资料研究', enabled: true },
    { id: 'company-research', kind: 'skill', name: '公司研究', category: '<风险>', enabled: true },
    { id: 'flow', kind: 'workflow', name: '流程', category: '步骤分类', enabled: true },
  ];
  const html = renderQuickSkills(catalog, { page: 'fingpt', category: '资料研究' });
  assert.match(html, /id="quick-category"[^>]*data-quick-category/);
  assert.match(html, /<label[^>]*for="quick-category"/);
  assert.match(html, /value="资料研究" selected/);
  assert.match(html, /&lt;风险&gt;/);
  assert.doesNotMatch(html, /<风险>|步骤分类|data-skill-shortcut="company-research"/);
  assert.match(html, /data-skill-shortcut="document-reading"/);
  assert.match(renderQuickSkills(catalog, { category: 'obsolete' }), /data-skill-shortcut="company-research"/);
  const claw = renderQuickSkills(catalog, { page: 'claw' });
  assert.match(claw, /步骤分类/);
  assert.doesNotMatch(claw, /value="资料研究"/);
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

test('primary rail stays independent while only the secondary session sidebar collapses', async () => {
  const shell = await import(new URL('shell.mjs', root));
  assert.equal(typeof shell.renderPrimaryRail, 'function');
  const rail = shell.renderPrimaryRail({ page: 'fingpt', secondaryOpen: true });
  const secondary = shell.renderSidebar({ page: 'fingpt', sessions: [], collapsed: true });
  assert.match(rail, /primary-rail/);
  assert.match(rail, /data-toggle-sidebar/);
  assert.match(rail, /FinGPT/);
  assert.match(secondary, /secondary-sidebar/);
  assert.doesNotMatch(secondary, /main-nav/);
});

test('a collapsed desktop secondary sidebar becomes an exposed narrow-screen drawer when opened', async () => {
  const shell = await import(new URL('shell.mjs', root));
  const drawer = shell.renderSidebar({ page: 'fingpt', sessions: [], collapsed: true, mobileOpen: true });
  assert.match(drawer, /secondary-sidebar mobile-open collapsed/);
  assert.doesNotMatch(drawer.match(/<aside[^>]*>/)[0], /aria-hidden="true"/);
});

test('Claw switches session and current-workspace projections without mixing other sessions', async () => {
  const shell = await import(new URL('shell.mjs', root));
  const detail = { id: 'claw-current', mode: 'claw', datasets: [{ name: '当前资料' }], files: [{ name: '当前产物.docx' }] };
  const workspace = shell.renderSidebar({ page: 'claw', detail, clawSidebarView: 'workspace', sessions: [{ id: 'other', title: '其他会话' }] });
  assert.match(workspace, /data-claw-sidebar-view="workspace"/);
  assert.match(workspace, /当前资料/);
  assert.match(workspace, /当前产物\.docx/);
  assert.doesNotMatch(workspace, /href="#\/fingpt\?session=other"/);
});

test('Claw workspace tab renders current-session datasets and safe file actions in the main canvas', async () => {
  const shell = await import(new URL('shell.mjs', root));
  const detail = {
    id: 'claw-current', mode: 'claw', title: '当前 Claw',
    datasets: [{ id: 'dataset-1', name: '当前资料', status: 'complete', files: [] }],
    files: [{ id: 'file-1', name: '当前产物.docx', size: 10, url: '/api/research/sessions/claw-current/files/file-1/download', preview_url: '/api/research/sessions/claw-current/files/file-1/preview' }],
  };
  assert.equal(typeof shell.renderClawWorkspaceCanvas, 'function');
  const workspace = shell.renderClawWorkspaceCanvas({ detail, selectedPreview: 'file-1' });
  assert.match(workspace, /当前资料/);
  assert.match(workspace, /datasets\/dataset-1\/files\/rows\.csv/);
  assert.match(workspace, /当前产物\.docx/);
  assert.match(workspace, /sandbox=""/);
  const app = await readFile(new URL('app.mjs', root), 'utf8');
  assert.match(app, /detail\.mode === 'claw' && clawSidebarView === 'workspace'/);
  assert.match(app, /renderClawWorkspaceCanvas/);
});

test('a lone slash lists every enabled real Skill without submitting a model request', async () => {
  const composer = await import(new URL('composer.mjs', root));
  const skills = [{ id: 'enabled-one', name: '已启用一', description: '' }, { id: 'disabled', name: '已禁用', description: '', enabled: false }, { id: 'enabled-two', name: '已启用二', description: '' }];
  assert.deepEqual(composer.skillMatches('', skills).map((skill) => skill.id), ['enabled-one', 'enabled-two']);
  const html = composer.renderComposer({ page: 'fingpt', draft: '/', skills, slashOpen: true });
  assert.match(html, /已启用一/);
  assert.match(html, /已启用二/);
  assert.doesNotMatch(html, /已禁用|fetch\(|POST \/api\/research/);
});

test('running tasks are selected from the complete real session catalog before recent sessions are capped', async () => {
  const shell = await import(new URL('shell.mjs', root));
  const sessions = Array.from({ length: 11 }, (_, index) => ({ id: `session-${index}`, title: `会话 ${index}`, status: index === 10 ? 'running' : 'idle', mode: 'fingpt' }));
  const html = shell.renderSidebar({ page: 'fingpt', sessions });
  assert.match(html, /会话 10/);
  assert.match(html, /运行任务[\s\S]*会话 10/);
});
