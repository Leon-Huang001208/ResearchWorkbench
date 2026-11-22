import assert from 'node:assert/strict';
import test from 'node:test';
import { createAPI, createController } from '../../app/research_web/ui/core.mjs';
import { renderComposer } from '../../app/research_web/ui/composer.mjs';
import { defaultSpecialistBudget, handleSpecialistBudgetChange, renderSpecialistPanel, specialistBudgetError } from '../../app/research_web/ui/specialist-panel.mjs';

const detail = (extra = {}) => ({ id: 's1', mode: 'fingpt', status: 'idle', messages: [], ...extra });
const budget = () => ({ ...defaultSpecialistBudget(), confirmed: true });
const storage = () => {
  const values = new Map();
  return { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) };
};

test('specialist send requires an explicit valid budget and regular research stays unchanged', async () => {
  const sent = [];
  const control = createController({ draftStorage: storage(), logger() {}, api: {
    detail: async () => detail(), message: async (...args) => { sent.push(args); return { accepted: true }; },
  }, makeID: () => 'stable-key' });
  await control.open({ page: 'fingpt', sessionId: 's1' });
  control.setResearchMode('specialist'); control.setDraft('研究半导体行业');
  await control.send(); assert.equal(sent.length, 0); assert.match(control.state.error, /预算/);
  control.setSpecialistBudget({ ...budget(), max_concurrency: 3 });
  await control.send(); assert.equal(sent.length, 0);
  control.setSpecialistBudget(budget()); await control.send();
  assert.deepEqual(sent[0][1].specialist_budget, budget());
  assert.equal(sent[0][1].research_mode, 'specialist');
  control.setResearchMode('quick'); control.setDraft('普通问题'); await control.send();
  assert.equal(sent[1][1].specialist_budget, undefined);
});

test('unknown specialist submission restores the same budget, body and key without automatic replay', async () => {
  const store = storage(); const calls = []; let rejectSend = true;
  const existingBudget = { ...budget(), max_tokens: 40000 };
  const api = { detail: async () => detail(), message: async (...args) => {
    calls.push(args); if (rejectSend) throw new Error('结果未知'); return { accepted: true };
  } };
  const first = createController({ api, draftStorage: store, logger() {}, makeID: () => 'original-key' });
  await first.open({ page: 'fingpt', sessionId: 's1' });
  first.setResearchMode('specialist'); first.setSpecialistBudget(existingBudget); first.setDraft('核验行业');
  await first.send();
  const second = createController({ api, draftStorage: store, logger() {}, makeID: () => 'different-key' });
  await second.open({ page: 'fingpt', sessionId: 's1' });
  assert.equal(calls.length, 1);
  assert.equal(second.state.researchMode, 'specialist');
  assert.deepEqual(second.state.specialistBudget, existingBudget);
  rejectSend = false; await second.send();
  assert.deepEqual(calls[1], calls[0]);
});

test('composer exposes specialist controls only in FinGPT and confirmation starts unchecked', () => {
  const html = renderComposer({ page: 'fingpt', researchMode: 'specialist' });
  assert.match(html, /value="specialist" selected/);
  assert.match(html, /data-specialist-budget="confirmed"/);
  assert.match(html, /value="200000"/); assert.match(html, /至少48,613/);
  assert.match(html, /不是人民币费用上限/);
  assert.doesNotMatch(html.match(/<input[^>]*data-specialist-budget="confirmed"[^>]*>/)[0], /checked/);
  assert.doesNotMatch(renderComposer({ page: 'claw', researchMode: 'specialist' }), /data-specialist-budget/);
});

test('status rendering escapes data, preserves cancellation and usage unknowns and does not accept a report', () => {
  assert.equal(renderSpecialistPanel(detail()), '');
  const html = renderSpecialistPanel(detail({ specialist: {
    id: 'r1', status: 'needs_attention', revision: 2,
    nodes: [{ id: '<script>', role: 'industry', status: 'cancel_requested' }],
    attempts: [{ id: 'a1', status: 'unknown', output: { conclusion: '<img src=x onerror=alert(1)>', limitations: ['缺来源'] } }],
    usage: { tokens: null, cost: null },
  } }));
  assert.match(html, /&lt;script&gt;/); assert.match(html, /&lt;img/);
  assert.doesNotMatch(html, /<script>|<img/); assert.match(html, /取消待确认/);
  assert.match(html, /用量未知/); assert.match(html, /不代表正式定稿/);
  assert.doesNotMatch(html, /data-specialist-resume/);
});

test('resume is an explicit one-shot action and navigation never applies its result to another session', async () => {
  let finish; let resumes = 0;
  const control = createController({ draftStorage: storage(), logger() {}, api: {
    detail: async id => detail({ id, specialist: { id: 'r1', status: 'needs_attention' } }),
    specialistResume: async () => { resumes++; await new Promise(resolve => { finish = resolve; }); return { accepted: true }; },
  } });
  await control.open({ page: 'fingpt', sessionId: 's1' }); assert.equal(resumes, 0);
  await control.resumeSpecialist(false); assert.equal(resumes, 0);
  const pending = control.resumeSpecialist(true);
  await control.resumeSpecialist(true); assert.equal(resumes, 1);
  await control.open({ page: 'fingpt', sessionId: 's2' }); finish(); await pending;
  assert.equal(control.state.detail.id, 's2');
});

test('specialist API resume carries explicit user action and confirmation', async () => {
  let observed;
  const api = createAPI({ logger() {}, fetcher: async (url, options) => {
    observed = { url, ...options }; return { ok: true, status: 202, json: async () => ({ accepted: true }) };
  } });
  await api.specialistResume('s1');
  assert.match(observed.url, /\/sessions\/s1\/specialist\/resume$/);
  assert.deepEqual(JSON.parse(observed.body), { confirmed: true });
  assert.equal(observed.headers['X-Research-User-Action'], '?1');
});

test('changing a budget clears its confirmation and an unconfirmed homepage cannot create a session', async () => {
  let creations = 0;
  const control = createController({ draftStorage: storage(), logger() {}, api: {
    create: async () => { creations++; return { id: 'new-session' }; },
  } });
  await control.open({ page: 'fingpt' }); control.setResearchMode('specialist');
  control.setSpecialistBudget(budget());
  assert.equal(handleSpecialistBudgetChange({ dataset: { specialistBudget: 'max_calls' }, value: '8' }, control), true);
  assert.equal(control.state.specialistBudget.max_calls, 8);
  assert.equal(control.state.specialistBudget.confirmed, false);
  await control.create('fingpt'); assert.equal(creations, 0);
  handleSpecialistBudgetChange({ dataset: { specialistBudget: 'confirmed' }, checked: true }, control);
  await control.create('fingpt'); assert.equal(creations, 1);
});

test('account changes prevent specialist resume and send without touching the destination account', async () => {
  let account = 'first'; let resumes = 0; let sends = 0;
  const control = createController({ getAccount: () => account, draftStorage: storage(), logger() {}, api: {
    detail: async () => detail({ specialist: { id: 'r1', status: 'needs_attention' } }),
    specialistResume: async () => { resumes++; }, message: async () => { sends++; },
  } });
  await control.open({ page: 'fingpt', sessionId: 's1' });
  control.setResearchMode('specialist'); control.setSpecialistBudget(budget()); control.setDraft('原账号研究');
  account = 'second'; await control.resumeSpecialist(true); await control.send();
  assert.equal(resumes, 0); assert.equal(sends, 0); assert.match(control.state.error, /账户已变化/);
});

test('backend budget bounds are enforced before any request', () => {
  assert.equal(specialistBudgetError({ ...budget(), max_tokens: 2000000, max_calls: 48 }), '');
  for (const invalid of [{ max_tokens: 2000001 }, { max_calls: 49 }, { max_revisions: 3 }, { timeout_seconds: 1801 }]) {
    assert.notEqual(specialistBudgetError({ ...budget(), ...invalid }), '');
  }
});

test('real ledger plan versions, attempt states and request usage preserve unresolved work', async () => {
  const task = { id: 'r1', status: 'needs_attention', deadline: 1800000000, can_resume: true,
    active_plan: { version: 2, nodes: [{ id: 'industry', role: 'industry' }] },
    plan_history: [{ version: 1, nodes: [{ id: 'old-industry', role: 'industry' }] }],
    attempts: { old: { id: 'old', node_id: 'industry', plan_version: 1, status: 'succeeded', invalidated: true },
      current: { id: 'current', node_id: 'industry', plan_version: 2, status: 'cancel_requested' } },
    model_requests: { first: { usage: { input_tokens: 100, output_tokens: 20 } }, second: { usage: null } },
  };
  const html = renderSpecialistPanel(detail({ specialist: task }));
  assert.match(html, /计划 v2/); assert.match(html, /历史计划/); assert.match(html, /old-industry/);
  assert.match(html, /取消待确认/); assert.match(html, /成果已失效/);
  assert.match(html, /已记录 120，另有 1 项未知/); assert.doesNotMatch(html, /data-specialist-resume/);
  let resumes = 0;
  const control = createController({ draftStorage: storage(), logger() {}, api: {
    detail: async () => detail({ specialist: task }), specialistResume: async () => { resumes++; },
  } });
  await control.open({ page: 'fingpt', sessionId: 's1' }); await control.resumeSpecialist(true);
  assert.equal(resumes, 0); assert.match(control.state.error, /在途或未知/);
});

test('homepage creation carries specialist mode and transfers the confirmed budget to the first message', async () => {
  let creation; let submitted;
  const control = createController({ draftStorage: storage(), logger() {}, makeID: () => 'initial-specialist-key', api: {
    create: async body => { creation = body; return detail(); },
    detail: async () => detail({ research_mode: 'specialist', research_depth: 'deep' }),
    message: async (id, body) => { submitted = body; return { accepted: true }; },
  } });
  await control.open({ page: 'fingpt' }); control.setResearchMode('specialist');
  control.setSpecialistBudget(budget()); control.setDraft('半导体行业协作');
  await control.create('fingpt'); assert.equal(creation.research_mode, 'specialist');
  await control.open({ page: 'fingpt', sessionId: 's1' });
  assert.deepEqual(control.state.specialistBudget, budget());
  await control.send(); assert.deepEqual(submitted.specialist_budget, budget());
  assert.equal(control.state.specialistBudget.confirmed, false);
});
