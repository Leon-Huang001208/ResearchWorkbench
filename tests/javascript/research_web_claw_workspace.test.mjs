import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { parseRoute, createController } from '../../app/research_web/ui/core.mjs';
import { renderClawProject, renderAutomationDrafts, automationDraftBody, clawNavigationCurrent, renderClawNavigation } from '../../app/research_web/ui/claw-workspace.mjs';

test('Claw borders and cards use declared product theme tokens', async () => {
  const styles = await readFile(new URL('../../app/research_web/ui/styles.css', import.meta.url), 'utf8');
  const appearance = await readFile(new URL('../../app/research_web/ui/appearance.css', import.meta.url), 'utf8');
  const declared = new Set([...`${styles}\n${appearance}`.matchAll(/(--[a-z0-9-]+)\s*:/g)].map(m => m[1]));
  const rules = [...styles.matchAll(/\.claw[^{}]*\{([^{}]*)\}/g)].map(m => m[1]).join('\n');
  const used = [...rules.matchAll(/var\((--[a-z0-9-]+)\)/g)].map(m => m[1]);
  assert.ok(used.length > 0);
  assert.deepEqual([...new Set(used.filter(token => !declared.has(token)))], []);
});

test('Claw routes select explicit project and view without replacing session identity', () => {
  const route = parseRoute('#/claw?view=projects&project=default&session=abc');
  assert.equal(route.clawView, 'projects'); assert.equal(route.projectId, 'default'); assert.equal(route.sessionId, 'abc');
  assert.equal(parseRoute('#/claw?view=bad&project=../../outside').clawView, 'sessions');
  assert.equal(parseRoute('#/claw?project=../../outside').projectId, 'default');
});

test('Session navigation returns to its owned project instead of the default project', () => {
  const project = 'project-' + 'a'.repeat(32);
  const html = renderClawNavigation('sessions', 'session-one', project);
  assert.match(html, new RegExp(`view=projects&project=${project}&session=session-one`));
  assert.match(html, /view=sessions&session=session-one/);
});

test('Project files retain provenance and require an explicit receiver', () => {
  const html = renderClawProject({ projects: [{ id: 'default', name: '我的研究' }], detail: { id: 'default', name: '研究', sessions: [{ id: 's1', title: '<source>' }], files: [{ id: 'f1', name: '<report>.md', session_id: 's1', session_title: '<source>', sha256: 'a'.repeat(64), url: '/download', preview_url: '/preview' }], datasets: [] } });
  assert.match(html, /选择接收会话/); assert.match(html, /data-claw-reference="f1"/);
  assert.match(html, /&lt;source&gt;/); assert.doesNotMatch(html, /<report>/);
  assert.doesNotMatch(renderClawProject({ detail: { id: 'p1', name: '归档', archived: true, sessions: [], files: [] } }), /data-claw-new-session/);
});

test('Schedule draft confirmation preserves locks and does not enable a task', () => {
  const body = { name: '计划', target_kind: 'skill', target_id: 'real', target_version: 2, target_sha256: 'a'.repeat(64), input_template: '研究', schedule: { kind: 'daily', timezone: 'Asia/Shanghai', hour: 9, minute: 0 }, mcp_tools: [], delivery: { channel_ids: [], include_attachments: false } };
  const form = new Map([['name','改名'],['input_template','新目标'],['kind','weekly'],['timezone','Asia/Shanghai'],['time','10:30'],['weekday','2']]);
  const result = automationDraftBody(body, form);
  assert.equal(result.target_sha256, body.target_sha256); assert.equal(result.schedule.weekday, 2); assert.equal(result.schedule.hour, 10);
  assert.equal(result.enabled, undefined);
  const html = renderAutomationDrafts([{ id:'d1',status:'proposed',body }]);
  assert.match(html, /确认保存/); assert.match(html, /默认停用/); assert.match(html, /data-claw-draft-dismiss/);
});

test('Explicit receiver survives re-render and stale navigation cannot reclaim the page', () => {
  const html = renderClawProject({ targetSession: 'receiver', detail: { id:'default',name:'研究',sessions:[{id:'receiver',title:'接收会话'}],files:[] } });
  assert.match(html, /value="receiver" selected/);
  assert.equal(clawNavigationCurrent(3,4),false);
  assert.equal(clawNavigationCurrent(3,3),true);
  const stale = renderClawProject({ targetSession:'outside',detail:{id:'default',name:'研究',sessions:[],files:[]} });
  assert.doesNotMatch(stale, /value="outside"/);
});

test('SSE redraw can restore draft focus and preserve project rename text', () => {
  const body = { name:'计划',target_id:'real',target_version:1,input_template:'研究',schedule:{kind:'daily',timezone:'Asia/Shanghai',hour:9,minute:0} };
  const html = renderAutomationDrafts([{id:'draft-one',status:'proposed',body}]);
  assert.match(html, /id="claw-draft-draft-one-name"/);
  assert.match(html, /id="claw-draft-draft-one-input_template"/);
  const project = renderClawProject({ renameEdits:new Map([['project-one','未保存名称']]),detail:{id:'project-one',name:'原名称',sessions:[],files:[]} });
  assert.match(project, /value="未保存名称"/);
});

test('A late file reference belongs to its original session draft, never the current page', async () => {
  const api = { detail: async id => ({id,mode:'claw',messages:[],files:[],status:'idle'}) };
  const controller = createController({api});
  await controller.open({page:'claw',sessionId:'receiver'}); controller.setDraft('保留研究问题');
  await controller.open({page:'claw',sessionId:'elsewhere'}); controller.setDraft('另一个问题');
  controller.addAttachmentsForSession('receiver',[{id:'reference',name:'copy.md'}]);
  assert.equal(controller.state.route.sessionId,'elsewhere'); assert.deepEqual(controller.state.attachments,[]);
  await controller.open({page:'claw',sessionId:'receiver'});
  assert.equal(controller.state.draft,'保留研究问题'); assert.equal(controller.state.attachments[0].id,'reference');
});
