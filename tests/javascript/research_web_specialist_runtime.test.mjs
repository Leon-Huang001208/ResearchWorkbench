import test from 'node:test';
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { mkdtemp, mkdir, realpath, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { apply, specialistControl, parseSpecialistResult } from '../../app/research_web/runtime/specialists.mjs';
import { apply as applyGuard } from '../../app/research_web/runtime/guard.mjs';
import { boundedJson } from '../../app/research_web/runtime/public-data.mjs';

const result = { conclusion: 'Evidence remains limited', evidence_ids: ['e1'], as_of_date: '2026-10-28', limitations: ['No predictive claim'], artifact_ids: [] };

function harness(options = {}) {
  const parent = randomUUID(), child = randomUUID(), attempt = randomUUID(), run = randomUUID();
  const calls = [], listeners = new Map(), tools = new Map();
  const controller = new AbortController();
  const agent = { session: { header: { id: parent }, id: parent }, cancel() { controller.abort(); } };
  const exec = { agent, signal: controller.signal, callId: randomUUID() };
  const ctx = { logger: { info() {}, warn() {} }, tools: { register(tool) { tools.set(tool.name, tool); } },
    on(name, listener) { listeners.set(name, listener); },
    subagents: { async startContinuable(spec) { calls.push(['native', spec]); options.native?.(spec); await listeners.get('subagent/start')({ id: child, runId: run }); return { childId: child, messageId: 'native-message' }; },
      interrupt(id, authority) { calls.push(['interrupt', id, authority]); } },
  };
  const control = async (_ctx, actual, _config, operation, payload, identity) => {
    calls.push([operation, payload, identity ?? actual.agent.session.header.id]);
    if (options.control) { const custom = await options.control(operation, payload); if (custom !== undefined) return custom; }
    if (operation === 'guard') return { collaboration: true, admitted: true, remaining_ms: 30000, model: { model_provider: 'fixture', model: 'fixture' } };
    if (operation === 'reserve') return { operation_result: { attempt_id: attempt, child_id: child, parent_session_id: parent, prompt: 'Frozen industry input', max_tokens: 4096 } };
    if (operation === 'model_request') return { deadline_at: Date.now() / 1000 + 30 };
    return { operation_result: {} };
  };
  apply(ctx, { researchRoot: '/unused', nativeLlmModule: '/unused/native.mjs' }, {
    control, admission: async () => ({ admitted: true }), nativeLlm: { isAgentLoopRequest: () => true },
  });
  return { ctx, calls, listeners, tools, exec, parent, child, attempt, run, controller };
}

test('reserve precedes native submission and preserves reserved identity, limits and parent signal', async () => {
  const h = harness();
  await h.tools.get('specialist_run').execute({ node_id: 'industry', expected_version: 1 }, h.exec);
  assert.deepEqual(h.calls.map(row => row[0]), ['reserve', 'dispatch', 'native', 'accepted']);
  assert.deepEqual(h.calls.find(row => row[0] === 'dispatch')[1], { attempt_id: h.attempt, child_id: h.child });
  const native = h.calls.find(row => row[0] === 'native')[1];
  assert.equal(native.childId, h.child);
  assert.equal(native.signal, h.exec.signal);
  assert.equal(native.request.parent, h.exec.agent);
  assert.equal(native.request.maxDepth, 1);
  assert.deepEqual(native.request.agentOptions, { maxTokens: 4096 });
  assert.equal(h.calls.at(-1)[1].message_id, 'native-message');
});

test('replayed reservation never resubmits a model-backed child', async () => {
  const h = harness({ control: operation => operation === 'reserve' ? { replayed: true, operation_result: {} } : undefined });
  await assert.rejects(h.tools.get('specialist_run').execute({ node_id: 'industry', expected_version: 1 }, h.exec), /replay/);
  assert.equal(h.calls.some(row => row[0] === 'native'), false);
});

test('unconfirmed durable dispatch claim prevents native submission', async () => {
  const h = harness({ control(operation) { if (operation === 'dispatch') throw Error('dispatch receipt lost'); } });
  await assert.rejects(h.tools.get('specialist_run').execute({ node_id: 'industry', expected_version: 1 }, h.exec), /dispatch/);
  assert.deepEqual(h.calls.map(row => row[0]), ['reserve', 'dispatch']);
});

test('a replayed dispatch claim never repeats a possibly accepted native submission', async () => {
  const h = harness({ control: operation => operation === 'dispatch' ? { replayed: true } : undefined });
  await assert.rejects(h.tools.get('specialist_run').execute({ node_id: 'industry', expected_version: 1 }, h.exec), /dispatch_replay/);
  assert.equal(h.calls.some(row => row[0] === 'native'), false);
});

test('lost accepted receipt retains unknown submission and never retries native start', async () => {
  const h = harness({ control(operation) { if (operation === 'accepted') throw Error('lost receipt'); } });
  await assert.rejects(h.tools.get('specialist_run').execute({ node_id: 'industry', expected_version: 1 }, h.exec), /submission_unknown/);
  assert.equal(h.calls.filter(row => row[0] === 'native').length, 1);
  assert.equal(h.calls.at(-1)[0], 'submission_unknown');
});

test('only authentic mapped child/run terminal events register structured results', async () => {
  const h = harness();
  await h.tools.get('specialist_run').execute({ node_id: 'industry', expected_version: 1 }, h.exec);
  const terminal = h.listeners.get('subagent/end');
  await terminal({ id: randomUUID(), runId: h.run, stopReason: 'completed' });
  await terminal({ id: h.child, runId: randomUUID(), stopReason: 'completed' });
  assert.equal(h.calls.some(row => row[0] === 'terminal'), false);
  await terminal({ id: h.child, runId: h.run, stopReason: 'completed', lastAssistantMessage: [{ type: 'text', text: JSON.stringify(result) }] });
  const recorded = h.calls.filter(row => row[0] === 'terminal');
  assert.equal(recorded.length, 1);
  assert.deepEqual(recorded[0][1].result, result);
  assert.equal(recorded[0][2], h.child);
  await terminal({ id: h.child, runId: h.run, stopReason: 'completed' });
  assert.equal(h.calls.filter(row => row[0] === 'terminal').length, 1);
});

test('invalid model JSON cannot become a successful terminal result', async () => {
  const h = harness();
  await h.tools.get('specialist_run').execute({ node_id: 'industry', expected_version: 1 }, h.exec);
  await h.listeners.get('subagent/end')({ id: h.child, runId: h.run, stopReason: 'completed', lastAssistantMessage: [{ type: 'text', text: 'I completed everything.' }] });
  const terminal = h.calls.find(row => row[0] === 'terminal')[1];
  assert.equal(terminal.stop_reason, 'invalid_output');
  assert.equal(Object.hasOwn(terminal, 'result'), false);
  assert.throws(() => parseSpecialistResult([{ type: 'text', text: JSON.stringify({ ...result, confidence: 1 }) }]), /result/);
});

test('plan invalidation interrupts native children but does not claim cancel completion', async () => {
  let child, attempt;
  const h = harness({ control(operation) { if (operation === 'plan') return { operation_result: { cancel_attempt_ids: [attempt] }, attempts: { [attempt]: { id: attempt, child_id: child } } }; } });
  ({ child, attempt } = h);
  await h.tools.get('specialist_run').execute({ node_id: 'industry', expected_version: 1 }, h.exec);
  await h.tools.get('specialist_plan').execute({ nodes: [], expected_version: 1 }, h.exec);
  assert.equal(h.calls.filter(row => row[0] === 'interrupt').length, 1);
  assert.equal(h.calls.some(row => row[0] === 'terminal'), false);
});

test('specialist dispatch consumes the original four-child per-turn guard quota', () => {
  let guard;
  applyGuard({ tools: { guard(fn) { guard = fn; } }, logger: { warn() {} } }, { enabled: true });
  const agent = { session: { snapshotEvents: () => [{ type: 'turn/start', data: { turn: 1 } }] } };
  for (let i = 0; i < 4; i++) assert.equal(guard({ name: 'specialist_run', agent }), undefined);
  assert.ok(guard({ name: 'subagent', agent }));
});

test('collaboration denies unbound native delegation and reopening old children', async () => {
  const h = harness();
  const before = h.listeners.get('tools/pre-execute');
  for (const name of ['subagent', 'rwb_plugin_agent', 'send_message']) {
    const decision = await before({ ...h.exec, name }, async () => ({ kind: 'allow' }));
    assert.equal(decision.kind, 'deny');
  }
  const exec = { ...h.exec, name: 'specialist_run' };
  assert.equal((await before(exec, async () => ({ kind: 'allow' }))).kind, 'allow');
  h.listeners.get('tools/result')(exec);
});

test('ordinary research retains its provider configuration and native delegation', async () => {
  const h = harness({ control: operation => operation === 'guard' ? { collaboration: false, admitted: true } : undefined });
  const original = { model: 'original', maxTokens: 12000 };
  assert.equal(await h.listeners.get('agent/request')({ ...h.exec, turn: 1, step: 1 }, async () => original), original);
  assert.equal((await h.listeners.get('tools/pre-execute')({ ...h.exec, name: 'subagent' }, async () => ({ kind: 'allow' }))).kind, 'allow');
  assert.equal(h.calls.some(row => row[0] === 'model_request'), false);
});

async function prepareModel(h) {
  const config = await h.listeners.get('agent/request')({ agent: h.exec.agent, signal: h.exec.signal, turn: 1, step: 1 }, async () => ({ provider: 'fixture', model: 'fixture', maxTokens: 12000 }));
  assert.equal(config.maxTokens, 4096);
  return { ...config, sessionId: h.parent, signal: h.exec.signal, messages: [{ role: 'user', content: [{ type: 'text', text: 'Research' }] }], tools: [] };
}

test('actual model requests reserve before provider dispatch and settle only real usage', async () => {
  const h = harness(), options = await prepareModel(h);
  const stream = h.listeners.get('llm/stream');
  for await (const _ of stream(options, async function* () { h.calls.push(['provider']); yield { type: 'usage', usage: { inputTokens: 30, outputTokens: 4 } }; })) {}
  const names = h.calls.map(row => row[0]);
  assert.ok(names.indexOf('model_request') < names.indexOf('provider'));
  assert.ok(names.indexOf('provider') < names.indexOf('model_usage'));
  assert.equal(h.calls.find(row => row[0] === 'model_request')[1].turn, 1);
  assert.equal(h.calls.find(row => row[0] === 'model_request')[1].step, 1);
  assert.equal(h.calls.find(row => row[0] === 'model_usage')[1].input_tokens, 30);
});

test('unknown model usage retains reservation and duplicate request cannot reach provider', async () => {
  const h = harness(), options = await prepareModel(h);
  const stream = h.listeners.get('llm/stream');
  for await (const _ of stream(options, async function* () { yield { type: 'text', text: 'No meter' }; })) {}
  assert.equal(h.calls.some(row => row[0] === 'model_usage'), false);
  await assert.rejects(async () => { for await (const _ of stream(options, async function* () { assert.fail('replayed provider call'); })) {} }, /replay/);
});

test('every root or child native request must keep the Host frozen model route', async () => {
  const h = harness();
  await assert.rejects(h.listeners.get('agent/request')({ ...h.exec, turn: 1, step: 1 }, async () => ({ provider: 'other', model: 'fixture', maxTokens: 4096 })), /model_changed/);
  assert.equal(h.calls.some(row => row[0] === 'model_request'), false);
  const missing = harness({ control: operation => operation === 'guard' ? { collaboration: true, admitted: true } : undefined });
  await assert.rejects(prepareModel(missing), /model_changed/);
});

test('provider retry policies cannot automatically replay a failed collaboration request', async () => {
  const h = harness(); await prepareModel(h);
  let retried = false;
  assert.equal(await h.listeners.get('agent/request-error')({ agent: h.exec.agent }, async () => { retried = true; return { kind: 'retry' }; }), undefined);
  assert.equal(retried, false);
  const ordinary = harness({ control: operation => operation === 'guard' ? { collaboration: false, admitted: true } : undefined });
  assert.deepEqual(await ordinary.listeners.get('agent/request-error')({ agent: ordinary.exec.agent }, async () => ({ kind: 'retry' })), { kind: 'retry' });
});

test('deadline cancels only the native owning agent while a provider read is pending', async () => {
  const h = harness({ control: operation => operation === 'model_request' ? { operation_result: { remaining_ms: 5 } } : undefined });
  const options = await prepareModel(h);
  await assert.rejects(async () => { for await (const _ of h.listeners.get('llm/stream')(options, async function* () { await new Promise(() => {}); })) {} }, /expired/);
  assert.equal(h.exec.signal.aborted, true);
});

test('control bridge derives session/actor identity and sends only to authenticated fixed loopback route', async t => {
  const root = await realpath(await mkdtemp(join(tmpdir(), 'specialists-'))), sid = randomUUID();
  t.after(() => rm(root, { recursive: true, force: true }));
  const cwd = join(root, 'sessions', sid);
  await mkdir(cwd, { recursive: true }); await mkdir(join(root, '.control'), { mode: 0o700 });
  await writeFile(join(root, '.control/datahub.json'), JSON.stringify({ url: 'http://127.0.0.1:8088', token: 'a'.repeat(43) }), { mode: 0o600 });
  const original = globalThis.fetch;
  t.after(() => { globalThis.fetch = original; });
  globalThis.fetch = async (url, options) => {
    assert.equal(url, 'http://127.0.0.1:8088/api/research/internal/data/specialist-control');
    assert.equal(options.redirect, 'error');
    assert.equal(options.headers['X-Research-Data-Key'], 'a'.repeat(43));
    assert.deepEqual(JSON.parse(options.body), { session_id: sid, operation: 'status', payload: {}, agent_id: sid, call_id: `${sid}:native-call:status` });
    return new Response(JSON.stringify({ status: 'needs_attention' }), { headers: { 'Content-Type': 'application/json' } });
  };
  const exec = { agent: { session: { header: { id: sid, cwd } } }, callId: 'native-call', signal: new AbortController().signal };
  assert.equal((await specialistControl({}, exec, { researchRoot: root }, 'status', {})).status, 'needs_attention');
  const large = JSON.stringify({ status: 'running', plan_history: ['x'.repeat(1_573_842)] });
  const response = () => new Response(large, { headers: { 'Content-Type': 'application/json' } });
  await assert.rejects(boundedJson(response(), exec.signal), /size/);
  globalThis.fetch = async () => response();
  assert.equal((await specialistControl({}, exec, { researchRoot: root }, 'status', {})).plan_history[0].length, 1_573_842);
  globalThis.fetch = async () => new Response(JSON.stringify({ value: 'x'.repeat(4 * 1024 * 1024) }), { headers: { 'Content-Type': 'application/json' } });
  await assert.rejects(specialistControl({}, exec, { researchRoot: root }, 'status', {}), /size/);
});

test('registered specialist schemas conform to the fixed native DSH tool validator', { skip: !process.env.DSH_SOURCE_ROOT }, async () => {
  const { assertSupportedJsonSchema, validateJsonSchemaValue } = await import(pathToFileURL(join(process.env.DSH_SOURCE_ROOT, 'packages/core/tools/lib/index.js')));
  const h = harness();
  for (const tool of h.tools.values()) {
    assertSupportedJsonSchema(tool.parameters);
    assertSupportedJsonSchema(tool.output.schema);
  }
  assert.deepEqual(validateJsonSchemaValue(h.tools.get('specialist_run').parameters, { node_id: 'industry', expected_version: 1 }), []);
  assert.ok(validateJsonSchemaValue(h.tools.get('specialist_run').parameters, { node_id: 'industry', expected_version: 1, child_id: 'forged' }).length);
});

test('native thinking blocks do not invalidate a strict visible JSON result', () => {
  assert.deepEqual(parseSpecialistResult([{ type: 'reasoning', text: 'private native reasoning' }, { type: 'text', text: JSON.stringify(result) }]), result);
  assert.throws(() => parseSpecialistResult([{ type: 'reasoning', text: JSON.stringify(result) }]), /invalid/);
  assert.throws(() => parseSpecialistResult([{ type: 'tool-call', name: 'unsafe' }, { type: 'text', text: JSON.stringify(result) }]), /invalid/);
});
