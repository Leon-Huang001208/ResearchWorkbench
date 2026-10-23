import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import { createAPI, createController, parseRoute } from '../../app/research_web/ui/core.mjs';
import { createDossierController, dossierHref, dossierSessionHref, isDossierRoute, renderDossiers, filterDossierSignals, dossierDateInput, dossierWatchDate, dossierQuality } from '../../app/research_web/ui/dossiers.mjs';
import { renderWorkbench } from '../../app/research_web/ui/workbench.mjs';
import { renderIntelligenceNavigation } from '../../app/research_web/ui/intel.mjs';
import { renderCapabilityDetail } from '../../app/research_web/ui/capabilities.mjs';
import { dossierMethods } from '../../app/research_web/ui/dossier-methods.mjs';

const contract = JSON.parse(await readFile(new URL('../fixtures/research_web_dossier_contract.json', import.meta.url), 'utf8'));
const id = contract.dossier.id;
const other = '2'.repeat(32);
const sourceSessionID = contract.source_session_id;
const otherSessionID = '22222222-2222-4222-8222-222222222222';
const evidenceID = contract.dossier.evidence[0].id;
const recordID = contract.dossier.records[0].id;
const route = key => parseRoute(dossierHref(key));
const detail = (key = id, revision = 3) => ({ ...structuredClone(contract.dossier), id: key, title: '公司长期判断', subject: { kind: 'company', key: '600519.SH', label: '贵州茅台' }, revision, archived: false, records: [], evidence: [], links: [], tracking: { enabled: false, eligible: false, reason: '尚未完成手动闭环' } });
function setup(overrides = {}, extras = {}) {
  let counter = 0;
  return createDossierController({ logger: () => {}, makeID: () => `attempt-${++counter}`, api: {
    dossiers: async () => ({ items: [detail()], next_cursor: null }), dossier: async key => detail(key),
    dossierTimeline: async () => ({ items: [] }), dossierSignals: async () => ({ items: [], missing: ['盈利预测缺失'] }),
    ...overrides,
  }, ...extras });
}

test('dossier and signal routes preserve the old asset views and primary navigation', () => {
  assert.equal(route(id).dossierId, id); assert.equal(route(id).assetView, 'dossiers');
  assert.equal(parseRoute('#/assets?view=dossiers&dossier=../x').dossierId, null);
  assert.equal(parseRoute('#/assets?view=financials').assetView, 'financials');
  assert.equal(parseRoute('#/assets/funds').section, 'funds');
  assert.equal(parseRoute('#/intel/signals').intelTab, 'signals');
  assert.ok(isDossierRoute(route(id))); assert.ok(isDossierRoute(parseRoute('#/intel/signals')));
  assert.match(renderWorkbench(), /href="#\/assets\?view=dossiers"/);
  assert.match(renderIntelligenceNavigation('signals'), /href="#\/intel\/signals" class="active"/);
  assert.equal(dossierSessionHref({ source_mode: 'claw', source_session_id: sourceSessionID }), `#/claw?session=${sourceSessionID}`);
  assert.equal(dossierSessionHref({ source_mode: 'javascript:alert(1)', source_session_id: sourceSessionID }), '#/history');
});

test('API uses the dossier domain, cancellation, expected revision body and encoded identities', async () => {
  const calls = [];
  const api = createAPI({ logger: () => {}, fetcher: async (url, options) => { calls.push([url, options]); return { ok: true, status: 200, json: async () => ({ items: [] }) }; } });
  const abort = new AbortController();
  await api.dossiers({ includeArchived: true, cursor: 'a/b', signal: abort.signal });
  await api.addDossierLink(id, { expected_revision: 3, idempotency_key: 'key', type: 'report', source_session_id: 'session' });
  await api.dossierEvidence(id, 'a/b');
  await api.dossierTimeline(id, { cursor: 'next/row' });
  assert.match(calls[0][0], /^\/api\/research\/dossiers\?include_archived=true&cursor=a%2Fb$/);
  assert.equal(calls[1][1].method, 'POST');
  assert.equal(JSON.parse(calls[1][1].body).expected_revision, 3);
  assert.match(calls[2][0], /evidence\/a%2Fb$/);
  assert.match(calls[3][0], /timeline\?cursor=next%2Frow$/);
  assert.ok(calls[0][1].signal instanceof AbortSignal);
});

test('a late response cannot replace another object; route cancellation aborts transport', async () => {
  let resolveOld, oldSignal;
  const controller = setup({ dossier: (key, { signal }) => {
    if (key === id) { oldSignal = signal; return new Promise(resolve => { resolveOld = resolve; }); }
    return Promise.resolve(detail(key));
  } });
  const first = controller.activate(route(id));
  await controller.activate(route(other));
  resolveOld(detail(id)); await first;
  assert.equal(oldSignal.aborted, true); assert.equal(controller.state.detail.id, other);
});

test('account switch clears old rows, forms and late mutations even when transport ignores abort', async () => {
  let owner = 'first', finish;
  const controller = setup({ addDossierRecord: () => new Promise(resolve => { finish = resolve; }) }, { getAccount: () => owner });
  await controller.activate(route(id));
  const pending = controller.submit('record', { kind: 'opinion', title: '第一账户', body: '私有正文', reason: '新证据', state: 'open' });
  owner = 'second'; await controller.activate(route(other)); finish(detail(id, 4)); await pending;
  assert.equal(controller.state.detail.id, other); assert.deepEqual(controller.state.forms, {});
  assert.doesNotMatch(renderDossiers(controller.state), /私有正文/);
});

test('conflict retains all edited text, never overwrites old state or retries itself', async () => {
  let writes = 0;
  const controller = setup({ addDossierRecord: async () => { writes++; throw Object.assign(new Error('conflict'), { status: 409 }); } });
  await controller.activate(route(id));
  const values = { kind: 'opinion', title: '修订标题', body: '新的观点', reason: '反证', state: 'refuted', record_id: recordID };
  await controller.submit('record', values);
  assert.equal(writes, 1); assert.equal(controller.state.detail.revision, 3);
  assert.equal(controller.state.forms.record.body, '新的观点'); assert.match(controller.state.error, /输入已保留/);
});

test('an explicit retry after unknown transport result reuses key AND expected revision', async () => {
  const writes = []; let unavailable = true;
  const controller = setup({ addDossierRecord: async (_id, body) => { writes.push(body); if (unavailable) throw new Error('结果未知'); return detail(id, 4); }, dossier: async key => detail(key, unavailable ? 3 : 4) });
  await controller.activate(route(id));
  const values = { kind: 'opinion', title: '标题', body: '正文', reason: '原因', state: 'open' };
  await controller.submit('record', values); unavailable = false;
  await controller.loadDetail(); await controller.submit('record', values);
  assert.equal(writes.length, 2); assert.equal(writes[0].idempotency_key, writes[1].idempotency_key);
  assert.equal(writes[1].expected_revision, 3); assert.equal(controller.state.detail.revision, 4);
});

test('record form is scoped by dossier and preserved across route round trips', async () => {
  const controller = setup({ addDossierRecord: async () => { throw new Error('offline'); } });
  await controller.activate(route(id));
  await controller.submit('record', { kind: 'risk', title: '风险', body: '保留我的输入', reason: '检查', state: 'open' });
  await controller.activate(route(other)); assert.equal(controller.state.forms.record, undefined);
  await controller.activate(route(id)); assert.equal(controller.state.forms.record.body, '保留我的输入');
});

test('opening and preparing frozen context never creates or sends a model session', async () => {
  const calls = [], drafts = [];
  const controller = setup({ dossierHandoff: async (_key, body) => { calls.push(body); return { prompt: '冻结档案与证据句柄', mode: body.mode, auto_send: false, dossier_revision: 4, context: { handoff_id: 'c'.repeat(32), dossier_id: id, revision: 3, evidence_handles: ['dossier:ev'], sha256: 'a'.repeat(64) } }; } }, { onDraft: async value => drafts.push(value) });
  await controller.activate(route(id)); assert.equal(calls.length, 0);
  await controller.prepare({ mode: 'claw', action: 'check_risk' });
  assert.equal(calls.length, 1); assert.equal(calls[0].expected_revision, 3);
  assert.equal(drafts.length, 1); assert.equal(drafts[0].auto_send, false);
  const app = await readFile(new URL('../../app/research_web/ui/app.mjs', import.meta.url), 'utf8');
  const handoff = app.slice(app.indexOf('const dossierController'), app.indexOf('const marketController'));
  assert.match(handoff, /controller\.setDossierDraft/); assert.doesNotMatch(handoff, /\.send\(|\.createSession\(|\.handoff\(/);
});

test('invalid frozen identity or auto_send response cannot become a research draft', async () => {
  let drafts = 0;
  const controller = setup({ dossierHandoff: async () => ({ prompt: 'bad', mode: 'claw', auto_send: true, context: { dossier_id: other, revision: 3, sha256: 'x' } }) }, { onDraft: async () => { drafts++; } });
  await controller.activate(route(id)); await controller.prepare({ mode: 'claw', action: 'company' });
  assert.equal(drafts, 0); assert.match(controller.state.error, /上下文不完整/);
});

test('evidence rechecks every time, exposes missing or revoked source, and never refetches it', async () => {
  let calls = 0;
  const controller = setup({ dossierEvidence: async () => { calls++; throw Object.assign(new Error('来源已撤权'), { status: 403 }); } });
  await controller.activate(route(id)); await controller.evidence(evidenceID); await controller.evidence(evidenceID);
  assert.equal(calls, 2); assert.match(controller.state.error, /撤权/); assert.equal(controller.state.preview, null);
});

test('five sections and supplier text are escaped; quality, unknown PIT, stale and coverage gaps remain visible', async () => {
  const malicious = '<img src=x onerror=alert(1)>';
  const value = detail(); value.records = [{ id: recordID, kind: 'opinion', title: malicious, body: malicious, state: 'open', evidence_ids: [] }];
  value.evidence = [{ id: evidenceID, title: malicious, sha256: 'abc', published_at: null }];
  value.links = [{ title: '报告', type: 'report', quality: { status: 'incomplete' } }];
  const controller = setup({ dossier: async () => value }); await controller.activate(route(id));
  const html = renderDossiers(controller.state);
  for (const section of ['当前判断', '观点时间线', '证据', '催化剂与风险', '研究成果']) assert.ok(html.includes(section));
  assert.doesNotMatch(html, /<img/); assert.match(html, /&lt;img/); assert.match(html, /incomplete/);
  assert.match(html, /未知，不具历史可知资格/); assert.match(html, /data-dossier-action="tracking" disabled/);
  await controller.activate(parseRoute('#/intel/signals'));
  controller.state.signals = [{ dossier_id: id, title: malicious, kind: 'risk', stale: true, evidence_ids: [] }];
  const signals = renderDossiers(controller.state); assert.match(signals, /数据已过期/); assert.match(signals, /盈利预测缺失/); assert.doesNotMatch(signals, /<img/);
});

test('denied details hide the old body; cancelled pages never render former account content', async () => {
  let denied = false;
  const controller = setup({ dossier: async () => { if (denied) throw Object.assign(new Error('forbidden'), { status: 403 }); return detail(); } });
  await controller.activate(route(id)); denied = true; await controller.loadDetail();
  assert.doesNotMatch(renderDossiers(controller.state), /公司长期判断/);
  assert.match(renderDossiers(controller.state), /没有权限/);
  controller.cancel(); assert.doesNotMatch(renderDossiers(controller.state), /贵州茅台/);
});

test('signal filters do not start scanning and preserve missing-data distinction', () => {
  const items = [{ title: '现金流修复', body: '待核验', kind: 'opportunity' }, { title: '减持', kind: 'risk' }];
  assert.equal(filterDossierSignals(items, '现金', 'opportunity').length, 1);
  assert.equal(filterDossierSignals(items, '', 'risk')[0].title, '减持');
  assert.equal(filterDossierSignals(items, '不存在').length, 0);
});

test('method explanations reuse existing published capabilities without granting tools or changing report quality', () => {
  assert.equal(dossierMethods.length, 6);
  const html = renderCapabilityDetail({ id: 'earnings-consensus-research', name: '业绩与一致预期', kind: 'skill', builtin: true, version: 7, enabled: true });
  assert.match(html, /输出结构/); assert.match(html, /缺可靠一致预期/); assert.match(html, /v7/);
  assert.match(html, /原“查看版本”入口/); assert.doesNotMatch(html, /自动授予|已通过质量/);
});

test('link references use the Host contract and do not accept client quality assertions', async () => {
  let saved;
  const controller = setup({ addDossierLink: async (_key, body) => { saved = body; return detail(id, 4); }, dossier: async () => detail(id, saved ? 4 : 3) });
  await controller.activate(route(id));
  await controller.submit('link', { source_session_id: sourceSessionID, type: 'report', reference_id: '', quality_status: 'passed' });
  assert.equal(saved.type, 'report'); assert.equal(saved.source_session_id, sourceSessionID);
  assert.equal(saved.reference, undefined); assert.equal(saved.quality_status, undefined);
  assert.equal(controller.state.items[0].revision, 4);
});

const receiptContext = (dossierID = id) => ({ dossier_id: dossierID, handoff_id: 'c'.repeat(32) });
const memoryStorage = () => { const entries = new Map(); return { getItem: key => entries.get(key) ?? null, setItem: (key, value) => entries.set(key, value) }; };
test('create never carries a receipt; only the user-triggered prompt carries the explicit Host receipt', async () => {
  const calls = [];
  const session = { id: sourceSessionID, mode: 'claw', messages: [], status: 'ready' };
  const api = createAPI({ logger: () => {}, fetcher: async (path, options) => {
    calls.push({ path, method: options.method, body: options.body ? JSON.parse(options.body) : null });
    return { ok: true, status: 200, json: async () => path.endsWith('/messages') ? { accepted: true } : session };
  } });
  api.events = undefined;
  const controller = createController({ api, draftStorage: memoryStorage(), logger: () => {}, makeID: () => 'request-key' });
  await controller.open({ page: 'claw', sessionId: null });
  controller.setDossierDraft('原始研究问题', receiptContext());
  assert.equal(calls.length, 0, 'preparing a draft cannot create a session');
  await controller.create('claw');
  assert.equal(calls[0].body.dossier_handoff_id, undefined);
  assert.equal(controller.state.dossierHandoff.id, 'c'.repeat(32), 'pre-creating a session cannot consume the pending receipt');
  await controller.open({ page: 'claw', sessionId: sourceSessionID });
  assert.equal(controller.state.dossierHandoff.id, 'c'.repeat(32));
  controller.addAttachments([{ id: 'a'.repeat(24), name: 'offline-upload.txt' }]);
  assert.equal(controller.state.dossierHandoff.id, 'c'.repeat(32), 'upload preparation cannot consume the pending receipt');
  assert.equal(calls.filter(item => item.path.endsWith('/messages')).length, 0);
  await controller.send();
  const submission = calls.find(item => item.path.endsWith('/messages'));
  assert.equal(submission.body.dossier_handoff_id, 'c'.repeat(32));
  assert.equal(submission.body.text, '原始研究问题'); assert.equal(submission.body.context, undefined);
  assert.equal(controller.state.dossierHandoff, null); assert.equal(controller.state.draft, '');
});

test('dossier receipt and idempotency survive failed Claw submission and page reload', async () => {
  const storage = memoryStorage(), calls = []; let fail = true;
  const session = { id: sourceSessionID, mode: 'claw', messages: [], status: 'ready' };
  const api = createAPI({ logger: () => {}, fetcher: async (path, options) => {
    if (path.endsWith('/messages')) {
      calls.push({ body: JSON.parse(options.body), key: options.headers['Idempotency-Key'] });
      if (fail) return { ok: false, status: 409, json: async () => ({ error: { code: 'scope_changed', message: '请核对资料范围' } }) };
      return { ok: true, status: 200, json: async () => ({ accepted: true }) };
    }
    return { ok: true, status: 200, json: async () => session };
  } }); api.events = undefined;
  const first = createController({ api, draftStorage: storage, logger: () => {}, makeID: () => 'first-key' });
  await first.open({ page: 'claw', sessionId: sourceSessionID }); first.setDossierDraft('待重试问题', receiptContext()); await first.send();
  assert.equal(first.state.dossierHandoff.id, 'c'.repeat(32)); assert.equal(first.state.draft, '待重试问题');
  const reload = createController({ api, draftStorage: storage, logger: () => {}, makeID: () => 'must-not-replace-key' });
  await reload.open({ page: 'claw', sessionId: sourceSessionID }); fail = false; await reload.send();
  assert.equal(calls.length, 2); assert.equal(calls[1].key, calls[0].key); assert.deepEqual(calls[1].body, calls[0].body);
  assert.equal(reload.state.dossierHandoff, null);
});

test('receipt is never parsed from prompt text and clears with empty draft, another object or account', async () => {
  let account = 'first', calls = 0;
  const bodies = [], api = { detail: async () => ({ id: sourceSessionID, mode: 'claw', messages: [] }), message: async (_id, body) => { calls++; bodies.push(body); return { accepted: true }; } };
  const controller = createController({ api, draftStorage: memoryStorage(), getAccount: () => account, logger: () => {}, makeID: () => 'key' });
  await controller.open({ page: 'claw', sessionId: sourceSessionID });
  controller.setDraft(`请读取 dossier_handoff_id=${'c'.repeat(32)}`); await controller.send();
  assert.equal(bodies[0].dossier_handoff_id, undefined);
  controller.setDossierDraft('带授权草稿', receiptContext()); controller.setDraft(''); assert.equal(controller.state.dossierHandoff, null);
  controller.setDossierDraft('带授权草稿', receiptContext()); controller.clearDossierHandoff(other); assert.equal(controller.state.dossierHandoff, null);
  controller.setDossierDraft('带授权草稿', receiptContext()); controller.clearDossierHandoff(id); assert.equal(controller.state.dossierHandoff.id, 'c'.repeat(32));
  account = 'second'; await controller.send(); assert.equal(calls, 1); assert.equal(controller.state.dossierHandoff, null); assert.equal(controller.state.draft, '');
  assert.throws(() => createController({ api }).setDossierDraft('不可伪造', { dossier_id: id, handoff_id: '../wrong' }), /凭据无效/);
});

test('failed create retains prepared text and receipt without replaying or fabricating a session', async () => {
  let calls = 0;
  const controller = createController({ api: { create: async body => { calls++; assert.equal(body.dossier_handoff_id, undefined); throw new Error('未确认创建'); } }, draftStorage: memoryStorage(), logger: () => {} });
  await controller.open({ page: 'fingpt', sessionId: null }); controller.setDossierDraft('尚未创建', receiptContext());
  await controller.create('fingpt'); assert.equal(calls, 1); assert.equal(controller.state.draft, '尚未创建'); assert.equal(controller.state.dossierHandoff.id, 'c'.repeat(32)); assert.equal(controller.state.detail, null);
});

test('a lost successful create response and an explicit retry never bind or replace the pending receipt', async () => {
  const created = [], messages = [];
  const controller = createController({ api: {
    create: async body => { assert.equal(body.dossier_handoff_id, undefined); created.push(created.length ? otherSessionID : sourceSessionID); if (created.length === 1) throw new Error('会话已创建，但响应丢失'); return { id: otherSessionID, mode: 'claw' }; },
    detail: async sid => ({ id: sid, mode: 'claw', messages: [] }),
    message: async (sid, body) => { messages.push({ sid, body }); return { accepted: true }; },
  }, draftStorage: memoryStorage(), logger: () => {}, makeID: () => 'message-key' });
  await controller.open({ page: 'claw', sessionId: null }); controller.setDossierDraft('保留同一个冻结授权', receiptContext());
  await controller.create('claw'); assert.equal(controller.state.dossierHandoff.id, 'c'.repeat(32));
  await controller.create('claw'); assert.equal(controller.state.dossierHandoff.id, 'c'.repeat(32)); assert.equal(messages.length, 0);
  await controller.open({ page: 'claw', sessionId: otherSessionID }); await controller.send();
  assert.equal(messages.length, 1); assert.equal(messages[0].sid, otherSessionID); assert.equal(messages[0].body.dossier_handoff_id, 'c'.repeat(32));
});

test('switching object also strips an old receipt restored from storage after a page reload', async () => {
  const storage = memoryStorage(), api = { detail: async session => ({ id: session, mode: 'claw', messages: [] }) };
  const first = createController({ api, draftStorage: storage, logger: () => {} });
  await first.open({ page: 'claw', sessionId: sourceSessionID }); first.setDossierDraft('已保存的旧档案草稿', receiptContext());
  const reload = createController({ api, draftStorage: storage, logger: () => {} });
  reload.clearDossierHandoff(other); await reload.open({ page: 'claw', sessionId: sourceSessionID });
  assert.equal(reload.state.dossierHandoff, null); assert.equal(reload.state.draft, '已保存的旧档案草稿');
});

test('receipt storage namespaces follow the authenticated account across controller reconstruction', async () => {
  const storage = memoryStorage(), api = { detail: async session => ({ id: session, mode: 'claw', messages: [] }) };
  const first = createController({ api, draftStorage: storage, getAccount: () => sourceSessionID, logger: () => {} });
  await first.open({ page: 'claw', sessionId: sourceSessionID }); first.setDossierDraft('账户一的私有草稿', receiptContext());
  const second = createController({ api, draftStorage: storage, getAccount: () => otherSessionID, logger: () => {} });
  await second.open({ page: 'claw', sessionId: sourceSessionID });
  assert.equal(second.state.dossierHandoff, null); assert.equal(second.state.draft, '');
});

const click = (name, data = {}) => {
  const action = { dataset: { dossierAction: name, ...data } };
  return { type: 'click', preventDefault() {}, target: { closest: selector => selector === '[data-dossier-workspace]' ? {} : selector === '[data-dossier-action]' ? action : null } };
};
test('actual DossierService fixture supplies 32hex archive IDs and event payload timeline', async () => {
  assert.match(contract.dossier.id, /^[a-f0-9]{32}$/); assert.match(sourceSessionID, /^[a-f0-9-]{36}$/);
  assert.match(evidenceID, /^[a-f0-9]{32}$/); assert.match(recordID, /^[a-f0-9]{32}$/);
  const controller = setup({ dossier: async () => structuredClone(contract.dossier), dossierTimeline: async () => structuredClone(contract.timeline) });
  await controller.activate(route(id));
  assert.ok(controller.state.timeline.some(item => item.title === contract.dossier.records[0].title));
  assert.match(renderDossiers(controller.state), /现金流观察/);
  assert.equal(parseRoute(dossierHref(sourceSessionID)).dossierId, null);
});

test('denying the archive clears a previously read body and a rendering guard rejects a stale cached preview', async () => {
  let denied = false;
  const controller = setup({ dossier: async () => { if (denied) throw Object.assign(new Error('forbidden'), { status: 403 }); return structuredClone(contract.dossier); }, dossierEvidence: async () => structuredClone(contract.preview) });
  await controller.activate(route(id)); await controller.evidence(evidenceID);
  assert.ok(controller.state.preview.content); denied = true; await controller.loadDetail();
  assert.equal(controller.state.preview, null); assert.equal(controller.state.detail, null);
  controller.state.preview = structuredClone(contract.preview);
  assert.doesNotMatch(renderDossiers(controller.state), /离线合同正文/);
  assert.doesNotMatch(renderDossiers(controller.state), /证据读取结果/);
});

test('a late evidence read cannot repopulate the cache after a concurrent 403', async () => {
  let release;
  const controller = setup({ dossierEvidence: async () => new Promise(resolve => { release = resolve; }), dossiers: async () => { throw Object.assign(new Error('forbidden'), { status: 403 }); } });
  await controller.activate(route(id)); controller.state.forbidden = false;
  const pending = controller.evidence(evidenceID); await controller.load(); release(structuredClone(contract.preview)); await pending;
  assert.equal(controller.state.preview, null); assert.equal(controller.state.forbidden, true);
});

test('actual evidence states, report quality and server truncation remain visible', async () => {
  const doc = structuredClone(contract.dossier);
  doc.evidence[0] = { ...doc.evidence[0], state: 'changed', error_code: 'dossier_evidence_changed' };
  const controller = setup({ dossier: async () => doc, dossierEvidence: async () => structuredClone(contract.preview) });
  await controller.activate(route(id)); await controller.evidence(evidenceID);
  assert.equal(contract.preview.content.length, 24000); assert.equal(contract.preview.truncated, true);
  const html = renderDossiers(controller.state);
  assert.match(html, /原始材料已变化/); assert.match(html, /dossier_evidence_changed/);
  assert.match(html, /质量状态：incomplete/); assert.match(html, /仅为部分正文预览/);
  assert.equal(dossierQuality({ quality: 'invalid' }), 'invalid');
  assert.equal(dossierQuality({ quality: { status: 'passed' } }), 'passed');
});

test('ISO observation windows render as dates and an unchanged edit preserves time and timezone', async () => {
  let saved;
  const doc = structuredClone(contract.dossier), original = doc.records[0];
  const controller = setup({ dossier: async () => doc, addDossierRecord: async (_id, body) => { saved = body; return { ...doc, revision: doc.revision + 1 }; } });
  await controller.activate(route(id)); await controller.handle(click('revise', { id: original.id }));
  assert.match(renderDossiers(controller.state), /name="watch_from" type="date" value="2026-10-01"/);
  await controller.submit('record', { record_id: original.id, kind: original.kind, state: original.state, title: original.title, body: original.body, reason: '保留原窗口', evidence_ids: original.evidence_ids.join(','), watch_from: dossierDateInput(original.watch_from), watch_until: dossierDateInput(original.watch_until) });
  assert.equal(saved.watch_from, original.watch_from); assert.equal(saved.watch_until, original.watch_until);
  assert.equal(dossierWatchDate('2026-10-02', original.watch_from, original.watch_until), '2026-10-02T15:30:00+08:00');
  assert.equal(dossierWatchDate('', original.watch_until, original.watch_from), null);
});
