import test from 'node:test';
import assert from 'node:assert/strict';
import { createController } from '../../app/research_web/ui/core.mjs';
import { renderComposer } from '../../app/research_web/ui/composer.mjs';
import { renderContextPanel, renderResearchAttention } from '../../app/research_web/ui/shell.mjs';
import { renderConversation } from '../../app/research_web/ui/views.mjs';
import { renderResearchPanel } from '../../app/research_web/ui/research-report.mjs';

const session = (extra = {}) => ({ id: 's1', mode: 'fingpt', status: 'completed', messages: [], files: [], ...extra });
const report = { title: '研究报告', quality: 'checked', sections: [{ id: 'facts', heading: '事实', text: '可用结论', citations: ['doc1'] }], notes: [{ stage_id: 'facts', text: '真实工作笔记', citations: ['doc1'] }] };
const memoryStorage = () => { const values = new Map(); return { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) }; };

test('three FinGPT strategies map to the existing DSH depth and survive explicit draft reload', async () => {
  const created = []; const sent = []; const draftStorage = memoryStorage();
  const api = { detail: async () => session(), create: async body => { created.push(body); return session(); }, message: async (_id, body) => { sent.push(body); return { accepted: true }; } };
  const control = createController({ api, draftStorage, logger() {} });
  await control.open({ page: 'fingpt', sessionId: null });
  control.setResearchMode('agent'); control.setDraft('动态研究');
  const reload = createController({ api, draftStorage, logger() {} });
  await reload.open({ page: 'fingpt', sessionId: null });
  assert.equal(reload.state.researchMode, 'agent'); assert.equal(reload.state.researchDepth, 'deep');
  await reload.create('fingpt');
  assert.equal(created[0].research_mode, 'agent'); assert.equal(created[0].research_depth, 'deep');
  await reload.open({ page: 'fingpt', sessionId: 's1' });
  await reload.send();
  assert.equal(sent[0].research_mode, 'agent');
  reload.setResearchMode('quick'); assert.equal(reload.state.researchDepth, 'instant');
  reload.setResearchDepth('deep'); assert.equal(reload.state.researchMode, 'deep');
  assert.throws(() => reload.setResearchMode('unknown'), /研究模式/);
});

test('native session strategy and legacy depth are honored without contaminating Claw requests', async () => {
  for (const [native, expected] of [[{ research_mode: 'agent', research_depth: 'deep' }, 'agent'], [{ research_depth: 'deep' }, 'deep'], [{}, 'quick']]) {
    const control = createController({ draftStorage: null, logger() {}, api: { detail: async () => session(native) } });
    await control.open({ page: 'fingpt', sessionId: 's1' });
    assert.equal(control.state.researchMode, expected);
  }
  const bodies = [];
  const control = createController({ draftStorage: null, logger() {}, api: { detail: async () => session({ mode: 'claw' }), message: async (_id, body) => { bodies.push(body); return { accepted: true }; } } });
  await control.open({ page: 'claw', sessionId: 's1' }); control.setDraft('原生任务'); await control.send();
  assert.equal(Object.hasOwn(bodies[0], 'research_mode'), false);
});

test('mode selection remains usable for new turns but locks while running, stopping or admission is unknown', () => {
  const html = renderComposer({ page: 'fingpt', researchMode: 'agent', detail: session({ research_mode: 'deep' }) });
  assert.match(html, /value="quick"/); assert.match(html, /value="deep"/); assert.match(html, /value="agent" selected/);
  assert.doesNotMatch(html.match(/<select id="research-depth"[^>]*>/)[0], /disabled/);
  assert.doesNotMatch(renderComposer({ page: 'claw' }), /value="agent"/);
  for (const config of [{ stopping: true }, { busy: true }, { taskPending: true }, { detail: session({ status: 'running' }) }]) {
    const locked = renderComposer({ page: 'fingpt', ...config });
    assert.match(locked.match(/<select id="research-depth"[^>]*>/)[0], /disabled/);
    assert.match(locked.match(/<input id="research-as-of"[^>]*>/)[0], /disabled/);
  }
});

test('quality, execution and file states stay separate while incomplete reports remain readable and downloadable', () => {
  const detail = session({ research_report: report, research_quality: { status: 'incomplete', repair_count: 1, issues: ['尚缺行业对比'], requirements: ['财务与行业比较'] }, delivery: { status: 'completed', required_formats: ['pdf'] }, files: [{ id: 'f1', name: '研究.pdf', kind: 'outputs', url: '/api/research/sessions/s1/files/f1/download' }] });
  const html = renderResearchPanel(detail, 'report');
  assert.match(html, /质量未通过/); assert.match(html, /尚缺行业对比/); assert.match(html, /财务与行业比较/); assert.match(html, /可用结论/);
  assert.doesNotMatch(html, /质量检查已通过/);
  assert.match(renderContextPanel({ detail, selectedTab: 'files' }), /href="\/api\/research\/sessions\/s1\/files\/f1\/download"/);
  const attention = renderResearchAttention(detail);
  assert.match(attention, /执行：执行已结束/); assert.match(attention, /质量：未通过/); assert.match(attention, /文件：已检查/);
  assert.match(attention, /data-continue-research/);
});

test('integrity invalid hides output exports without hiding actual Store input downloads, previews or Markdown links', () => {
  const output = { id: 'a'.repeat(24), kind: 'outputs', name: '研究.docx', url: `/api/research/sessions/s1/files/${'a'.repeat(24)}/download`, preview_url: `/api/research/sessions/s1/files/${'a'.repeat(24)}/preview` };
  const upload = { id: 'upload1', kind: 'inputs', name: '资料.pdf', url: '/api/research/sessions/s1/files/upload1/download', preview_url: '/api/research/sessions/s1/files/upload1/preview' };
  const detail = session({ research_report: report, research_quality: { status: 'invalid', issues: ['source_mismatch'] }, files: [output, upload], messages: [{ id: 'u1', role: 'user', text: '研究' }, { id: 'a1', role: 'assistant', text: `[报告](${output.url}) [资料](${upload.url})` }] });
  const panel = renderContextPanel({ detail, selectedTab: 'files', selectedPreview: output.id });
  assert.doesNotMatch(panel, /data-document-open|<iframe|href="[^\"]*aaaaaaaaaaaaaaaaaaaaaaaa/);
  assert.match(panel, /href="\/api\/research\/sessions\/s1\/files\/upload1\/download"/);
  assert.match(renderResearchPanel(detail, 'report'), /完整性检查未通过/);
  assert.doesNotMatch(renderResearchPanel(detail, 'report'), /来源身份与声明章节已检查|质量检查已通过|可用结论/);
  assert.doesNotMatch(renderConversation(detail), /href="[^\"]*aaaaaaaaaaaaaaaaaaaaaaaa/);
  assert.match(renderConversation(detail), /href="\/api\/research\/sessions\/s1\/files\/upload1\/download"/);
  assert.match(renderContextPanel({ detail, selectedTab: 'files', selectedPreview: upload.id }), /<iframe[^>]*src="\/api\/research\/sessions\/s1\/files\/upload1\/preview"/);
});

test('native reasoning and tools retain their real records and Todo completion is never quality acceptance', () => {
  const detail = session({ research_plan: { status: 'available', turn: 1, seq: 8, history_complete: true, items: [{ content: '取证', status: 'completed' }] }, messages: [{ id: 'u1', role: 'user', text: '研究问题', seq: 1 }, { id: 'a1', role: 'assistant', text: '结果', reasoning: '真实原生推理' }], activities: [{ id: 'call1', type: 'tool', seq: 2, title: '真实检索', status: 'completed', arguments: { query: '财报' }, result: { source: '官网' } }] });
  assert.match(renderResearchPanel(detail, 'plan'), /不代表研究或文件交付完成/);
  assert.doesNotMatch(renderResearchAttention(detail), /质量：已通过/);
  assert.match(renderConversation(detail), /真实检索/);
});

test('uncertain admission preserves the selected strategy, draft and idempotency key across retry', async () => {
  const calls = []; let fail = true;
  const control = createController({ draftStorage: null, logger() {}, makeID: () => 'one-admission-key', api: { detail: async () => session({ research_mode: 'agent' }), message: async (_id, body, key) => { calls.push({ body, key }); if (fail) throw new Error('受理结果未知'); return { accepted: true }; } } });
  await control.open({ page: 'fingpt', sessionId: 's1' }); control.setDraft('请继续核验');
  await control.send(); assert.equal(control.state.draft, '请继续核验'); assert.equal(control.state.researchMode, 'agent');
  fail = false; await control.send();
  assert.equal(calls.length, 2); assert.equal(calls[0].key, calls[1].key); assert.deepEqual(calls[0].body, calls[1].body); assert.equal(control.state.draft, '');
});

test('report versions preserve original quality and notes without binding historical stage controls to the new report', () => {
  const { quality: _rawQuality, ...rawReport } = report;
  const old = { ...rawReport, title: '<旧报告>', notes: [{ stage_id: 'facts', text: '前轮笔记', citations: ['doc1'] }] };
  const html = renderResearchPanel(session({ research_report: { ...report, title: '新报告' }, research_quality: { status: 'passed', issues: [] }, research_report_versions: [{ task_id: 'original-turn', report: old, quality: { status: 'incomplete', issues: [{ code: '<缺口>' }] } }] }), 'report');
  assert.match(html, /新报告/); assert.match(html, /&lt;旧报告&gt;/); assert.match(html, /original-turn/); assert.match(html, /前轮笔记/); assert.match(html, /&lt;缺口&gt;/);
  assert.equal((html.match(/data-report-stage=/g) || []).length, 1);
  assert.doesNotMatch(html, /<旧报告>|<缺口>/);
  const currentAndDraft = renderResearchPanel(session({research_report:report,research_quality:{status:'incomplete',issues:[]},research_report_versions:[
    {version_id:'v-current',is_current:true,report,quality:{status:'incomplete',issues:[]},quality_binding:'host_check'},
    {version_id:'v-draft',is_current:false,report:old,quality:{status:'invalid',issues:['report_version_quality_unbound']},quality_binding:'unbound'},
  ]}), 'report');
  assert.match(currentAndDraft,/当前版本 · [^<]*v-current/);
  assert.match(currentAndDraft,/历史版本 · [^<]*v-draft · 检查未绑定/);
  assert.match(currentAndDraft,/完整性检查未通过/);
  assert.doesNotMatch(currentAndDraft,/质量检查已通过/);
});

test('Host passed projection exposes current report body and notes and bounds the actual verification scope', () => {
  const detail = session({ research_report: { ...report, quality: 'passed' }, research_quality: { status: 'passed', repair_count: 1, verification_scope: 'observed_quotes_and_deterministic_numeric_claims' } });
  const html = renderResearchPanel(detail, 'report');
  assert.match(html, /质量检查已通过/); assert.match(html, /class="notice success"/); assert.match(html, /可用结论/); assert.match(html, /补查许可：1 次/);
  assert.match(html, /实际来源摘录及可复算数字；未核实的改写保留缺口/);
  assert.match(renderResearchPanel(detail, 'notes'), /真实工作笔记/);
});

test('historical readability trusts Host quality snapshots instead of arbitrary raw payload quality', () => {
  for (const status of ['passed', 'incomplete']) {
    const html = renderResearchPanel(session({ research_report_versions: [{ task_id: 'old', report: { ...report, quality: 'invalid' }, quality: { status } }] }), 'report');
    assert.match(html, /可用结论/); assert.match(html, /真实工作笔记/);
  }
  const invalid = renderResearchPanel(session({ research_report_versions: [{ task_id: 'bad', report: { ...report, quality: 'passed' }, quality: { status: 'invalid' } }] }), 'report');
  assert.doesNotMatch(invalid, /可用结论|真实工作笔记|质量检查已通过/);
});

test('refresh restores a pending request for explicit same-body retry without sending automatically or reusing keys across body/session', async () => {
  const draftStorage = memoryStorage(); const calls = []; let keyNumber = 0;
  const options = { draftStorage, logger() {}, makeID: () => `pending-${++keyNumber}`, api: { detail: async id => session({ id, research_mode: 'agent' }), message: async (id, body, key) => { calls.push({ id, body, key }); throw new Error('受理未知'); } } };
  const first = createController(options);
  await first.open({ page: 'fingpt', sessionId: 's1' }); first.setDraft('核验资料'); first.setTools(['public-tool']); first.setFormats(['pdf']); first.setCapability({ id: 'company-research', version: 2, name: '公司研究', enabled: true }); await first.send();
  const reload = createController(options); await reload.open({ page: 'fingpt', sessionId: 's1' });
  assert.equal(calls.length, 1); assert.equal(reload.state.draft, '核验资料');
  await reload.send(); assert.equal(calls[1].key, calls[0].key); assert.deepEqual(calls[1].body, calls[0].body);
  reload.setDraft('另一个问题'); await reload.send(); assert.notEqual(calls[2].key, calls[0].key);
  await reload.open({ page: 'fingpt', sessionId: 's2' }); reload.setDraft('核验资料'); await reload.send();
  assert.notEqual(calls[3].key, calls[0].key);
});

test('confirmed acceptance removes persisted retry state and copied pending state cannot bind another session', async () => {
  const values = new Map(); const draftStorage = { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) };
  const calls = []; let keyNumber = 0; let accepted = false;
  const options = { draftStorage, logger() {}, makeID: () => `durable-${++keyNumber}`, api: { detail: async id => session({ id }), message: async (id, body, key) => { calls.push({ id, body, key }); if (!accepted) throw new Error('未知'); return { accepted: true }; } } };
  const first = createController(options); await first.open({ page: 'fingpt', sessionId: 's1' }); first.setDraft('原问题'); await first.send();
  const key = id => `research-web:explicit-draft:v1:${id}`;
  assert.equal(JSON.parse(values.get(key('s1'))).pending.key, calls[0].key);
  values.set(key('s2'), values.get(key('s1')));
  const other = createController(options); await other.open({ page: 'fingpt', sessionId: 's2' });
  assert.match(other.state.error, /重试凭据/); assert.equal(other.state.draft, '原问题'); await other.send();
  assert.notEqual(calls[1].key, calls[0].key);
  accepted = true;
  const reload = createController(options); await reload.open({ page: 'fingpt', sessionId: 's1' }); await reload.send();
  assert.equal(calls[2].key, calls[0].key); assert.equal(JSON.parse(values.get(key('s1'))).pending, undefined);
  const after = createController(options); await after.open({ page: 'fingpt', sessionId: 's1' }); assert.equal(after.state.draft, '');
  after.setDraft('原问题'); await after.send(); assert.notEqual(calls[3].key, calls[0].key);
});

test('failure to persist retry identity keeps the draft and prevents an unprotected network submission', async () => {
  let sends = 0; let saved;
  const draftStorage = { getItem: () => saved, setItem: (_key, value) => { if (JSON.parse(value).pending) throw new Error('quota'); saved = value; } };
  const control = createController({ draftStorage, logger() {}, api: { detail: async () => session(), message: async () => { sends++; return { accepted: true }; } } });
  await control.open({ page: 'fingpt', sessionId: 's1' }); control.setDraft('保留问题'); await control.send();
  assert.equal(sends, 0); assert.equal(control.state.draft, '保留问题'); assert.match(control.state.error, /尚未发送/);
});

test('historical cutoff remains an explicit FinGPT draft and pending request choice across reload', async () => {
  const draftStorage = memoryStorage(); const calls = [];
  const options = { draftStorage, logger() {}, makeID: () => 'historical-retry', api: { detail: async () => session({ research_quality: { as_of: '2026-10-16', status: 'incomplete' } }), message: async (_id, body, key) => { calls.push({ body, key }); throw new Error('受理未知'); } } };
  const first = createController(options); await first.open({ page: 'fingpt', sessionId: 's1' });
  assert.equal(first.state.researchAsOf, '2026-10-16');
  first.setResearchAsOf('2024-02-29'); first.setDraft('按历史时点研究'); await first.send();
  assert.equal(calls[0].body.research_as_of, '2024-02-29');
  const reload = createController(options); await reload.open({ page: 'fingpt', sessionId: 's1' });
  assert.equal(calls.length, 1); assert.equal(reload.state.researchAsOf, '2024-02-29'); await reload.send();
  assert.deepEqual(calls[1], calls[0]);
  assert.throws(() => reload.setResearchAsOf('2023-02-29'), /截止日期/);
  assert.throws(() => reload.setResearchAsOf('2024-2-9'), /截止日期/);
  const html = renderComposer({ page: 'fingpt', researchAsOf: reload.state.researchAsOf });
  assert.match(html, /研究截止日期/); assert.match(html, /新研究默认今日，续研沿用原截止日期/); assert.match(html, /id="research-as-of"[^>]*type="date"[^>]*value="2024-02-29"/);
  assert.doesNotMatch(renderComposer({ page: 'claw', researchAsOf: '2024-02-29' }), /research-as-of/);
});

test('explicit blank cutoff stays blank after reload and leaves cutoff default to Host without adding Claw fields', async () => {
  const draftStorage = memoryStorage(); const bodies = [];
  const api = { detail: async () => session({ research_quality: { as_of: '2026-10-16' } }), message: async (_id, body) => { bodies.push(body); return { accepted: true }; } };
  const first = createController({ api, draftStorage, logger() {} }); await first.open({ page: 'fingpt', sessionId: 's1' }); first.setResearchAsOf(''); first.setDraft('使用服务端今天');
  const reload = createController({ api, draftStorage, logger() {} }); await reload.open({ page: 'fingpt', sessionId: 's1' });
  assert.equal(reload.state.researchAsOf, ''); await reload.send(); assert.equal(Object.hasOwn(bodies[0], 'research_as_of'), false);
  const claw = createController({ draftStorage: null, logger() {}, api: { ...api, detail: async () => session({ mode: 'claw', research_quality: { as_of: '2026-10-16' } }) } });
  await claw.open({ page: 'claw', sessionId: 's1' }); assert.equal(claw.state.researchAsOf, '');
  claw.setResearchAsOf('2024-02-29'); claw.setDraft('Claw 原任务'); await claw.send(); assert.equal(Object.hasOwn(bodies[1], 'research_as_of'), false);
});

test('pending records from before the cutoff control preserve an omitted date for exact retry', async () => {
  const body = { text: '旧待确认问题', research_mode: 'quick' }; const writes = [];
  const stored = JSON.stringify({ draft: body.text, attachments: [], researchMode: 'quick', pending: { session_id: 's1', key: 'old-pending-key', signature: JSON.stringify(body), selection: { skillId: '', capability: null, toolIds: [], methodIds: [], expectedFormats: null, tabbitTabs: [] } } });
  const control = createController({ draftStorage: { getItem: () => stored, setItem() {} }, logger() {}, api: { detail: async () => session({ research_quality: { as_of: '2026-10-16' } }), message: async (_id, request, key) => { writes.push({ request, key }); return { accepted: true }; } } });
  await control.open({ page: 'fingpt', sessionId: 's1' }); assert.equal(control.state.researchAsOf, ''); assert.equal(writes.length, 0);
  await control.send(); assert.deepEqual(writes, [{ request: body, key: 'old-pending-key' }]);
});
