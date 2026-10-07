import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, realpath, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { apply } from '../../app/research_web/runtime/guard.mjs';

const makeAgent = () => {
  const events = [{ type: 'turn/start', data: { turn: 1 } }];
  return { session: { snapshotEvents: () => events }, events };
};

test('research guard fails closed and cannot expose arbitrary shell or host files', () => {
  let guard;
  const ctx = { tools: { guard: (fn) => { guard = fn; } }, logger: { warn() {} } };
  apply(ctx);
  assert.ok(guard({ name: 'research_run_script', agent: makeAgent() }));
  apply(ctx, { enabled: true });
  assert.equal(guard({ name: 'research_run_script', agent: makeAgent() }), undefined);
  for (const name of ['bash', 'read_file', 'web_fetch', 'mcp_anything', 'subagent_fork']) {
    assert.ok(guard({ name, agent: makeAgent() }));
  }
});

test('research guard limits native children and resets budget only on a new turn', () => {
  let guard;
  apply({ tools: { guard: (fn) => { guard = fn; } }, logger: { warn() {} } }, { enabled: true });
  const agent = makeAgent();
  for (let index = 0; index < 4; index++) assert.equal(guard({ name: 'subagent', agent }), undefined);
  assert.ok(guard({ name: 'subagent', agent }));
  agent.events.push({ type: 'turn/start', data: { turn: 2 } });
  assert.equal(guard({ name: 'subagent', agent }), undefined);
});

test('research guard allows only configured Tabbit surfaces', () => {
  let guard;
  const ctx = { tools: { guard: (fn) => { guard = fn; } }, logger: { warn() {} } };
  apply(ctx, { enabled: true, tabbitBrowserEnabled: true, tabbitWebFetchEnabled: false });
  assert.equal(guard({ name: 'tabbit_browser', agent: makeAgent() }), undefined);
  assert.ok(guard({ name: 'web_fetch', agent: makeAgent() }));
  apply(ctx, { enabled: true, tabbitBrowserEnabled: true, tabbitWebFetchEnabled: true });
  assert.equal(guard({ name: 'web_fetch', agent: makeAgent() }), undefined);
  assert.ok(guard({ name: 'tabbit_browser_install', agent: makeAgent() }));

  apply(ctx, { enabled: false, tabbitBrowserEnabled: true, tabbitWebFetchEnabled: false });
  assert.equal(guard({ name: 'tabbit_browser', agent: makeAgent() }), undefined);
  assert.ok(guard({ name: 'research_run_script', agent: makeAgent() }));
});

test('research guard allows only the exact activated MCP tool namespace', () => {
  let guard;
  const ctx = { tools: { guard: (fn) => { guard = fn; } }, logger: { warn() {} } };
  const allowed = 'mcp__mcp-installation-0123456789abcdef0123456789abcdef__read_filing';
  apply(ctx, { enabled: true, mcpTools: [allowed] });

  assert.equal(guard({ name: allowed, agent: makeAgent() }), undefined);
  assert.ok(guard({ name: `${allowed}_shadow`, agent: makeAgent() }));
  assert.ok(guard({ name: 'mcp__mcp-installation-0123456789abcdef0123456789abcdef__write_filing', agent: makeAgent() }));
  assert.ok(guard({ name: 'mcp_anything', agent: makeAgent() }));

  assert.throws(
    () => apply(ctx, { enabled: true, mcpTools: [allowed, allowed] }),
    /duplicate/i,
  );
  assert.throws(
    () => apply(ctx, { enabled: true, mcpTools: ['mcp__prefix-only'] }),
    /invalid/i,
  );
});

function acceptanceContext() {
  const listeners = new Map();
  let guard;
  return {
    listeners, get guard() { return guard; },
    ctx: { tools: { guard(fn) { guard = fn; } },
      on(name, fn) { listeners.set(name, fn); },
      logger: { warn() {}, info() {} } },
  };
}
const acceptance = { modelCalls: 6, tool: 'datahub_get_fund_data' };
const publicNav = { source: 'eastmoney_fund', dataset: 'nav', code: '000001', limit: 1, allow_fallback: false };

test('live acceptance reserves all model calls before dispatch, including concurrent and later turns', async () => {
  const c = acceptanceContext();
  apply(c.ctx, { enabled: true, acceptance });
  assert.equal(typeof c.listeners.get('llm/stream'), 'function');
  const stream = c.listeners.get('llm/stream');
  let dispatched = 0;
  const next = async function* () { dispatched++; yield { type: 'text', text: 'fixture' }; };
  const consume = async () => { for await (const _ of stream({ messages: [] }, next)) {} };
  const result = await Promise.allSettled(Array.from({ length: 8 }, consume));
  assert.equal(dispatched, 6);
  assert.equal(result.filter(x => x.status === 'rejected').length, 2);
  await assert.rejects(consume(), /acceptance_model_limit/);
});

test('live acceptance allows one exact public tool across sessions and rejects extra agents', () => {
  const c = acceptanceContext();
  apply(c.ctx, { enabled: true, acceptance });
  for (const name of ['subagent', 'research_run_script', 'web_search', 'datahub_search_assets']) {
    assert.ok(c.guard({ name, agent: makeAgent() }));
  }
  assert.equal(c.guard({ name: acceptance.tool, arguments: publicNav, agent: makeAgent() }), undefined);
  assert.ok(c.guard({ name: acceptance.tool, arguments: publicNav, agent: makeAgent() }));
});

test('live acceptance rejects invalid limits and non-text provider requests before dispatch', async () => {
  const c = acceptanceContext();
  for (const value of [{ modelCalls: 7, tool: acceptance.tool }, { modelCalls: 6, tool: 'subagent' }]) {
    assert.throws(() => apply(c.ctx, { enabled: true, acceptance: value }), /acceptance_control_invalid/);
  }
  apply(c.ctx, { enabled: true, acceptance });
  let dispatched = false;
  await assert.rejects(async () => {
    for await (const _ of c.listeners.get('llm/stream')({ messages: [{ content: [{ type: 'image' }] }] }, async function* () { dispatched = true; })) {}
  }, /acceptance_text_only/);
  assert.equal(dispatched, false);
});

test('live acceptance dispatches only implemented public NAV parameters', () => {
  const c = acceptanceContext();
  apply(c.ctx, { enabled: true, acceptance: { modelCalls: 4, tool: 'datahub_get_fund_data' } });
  const args = { source: 'eastmoney_fund', dataset: 'nav', code: '000001', limit: 1, allow_fallback: false };
  for (const changed of [{ source: 'tinysoft' }, { dataset: 'holdings' }, { limit: 2 }, { allow_fallback: true }]) {
    assert.ok(c.guard({ name: 'datahub_get_fund_data', arguments: { ...args, ...changed }, agent: makeAgent() }));
  }
  assert.equal(c.guard({ name: 'datahub_get_fund_data', arguments: args, agent: makeAgent() }), undefined);
  assert.ok(c.guard({ name: 'datahub_get_fund_data', arguments: args, agent: makeAgent() }));
});


async function admissionFixture(t, child = false) {
  const root = await realpath(await mkdtemp(join(tmpdir(), 'rwb-skill-admission-')));
  t.after(() => rm(root, { recursive: true }));
  const sid = randomUUID(); const cwd = join(root, 'sessions', sid);
  await mkdir(cwd, { recursive: true }); await mkdir(join(root, '.control'), { mode: 0o700 });
  await writeFile(join(root, '.control', 'datahub.json'), JSON.stringify({ url: 'http://127.0.0.1:19088', token: 't'.repeat(43) }), { mode: 0o600 });
  let handler; let guard; const handlers = new Map();
  const parent = { header: { id: sid, cwd } };
  const session = child ? { header: { id: randomUUID(), cwd, parentSession: sid } } : parent;
  const ctx = { tools: { guard(fn) { guard = fn; } }, sessions: { get(id) { return id === sid ? parent : undefined; } },
    on(name, fn) { handlers.set(name, fn); if (name === 'tools/pre-execute') handler = fn; }, logger: { warn() {}, info() {} } };
  apply(ctx, { enabled: true, researchRoot: root });
  return { root, sid, ctx, handler, guard, handlers, exec: { name: 'skill', arguments: { name: 'reviewed-package-v1' },
    agent: { session }, signal: new AbortController().signal } };
}

test('native skill gate binds a child to its parent workspace and preserves prior approval', async t => {
  const f = await admissionFixture(t, true); const original = globalThis.fetch; let body;
  t.after(() => { globalThis.fetch = original; });
  globalThis.fetch = async (url, options) => {
    assert.equal(url, 'http://127.0.0.1:19088/api/research/internal/data/skill-preflight');
    assert.equal(options.redirect, 'error'); assert.equal(options.credentials, 'omit');
    body = JSON.parse(options.body);
    return new Response(JSON.stringify({ status: 'limited', admitted: true, missing: [], omitted_sections: ['专业章节'] }), { headers: { 'content-type': 'application/json' } });
  };
  const decision = { kind: 'ask', reason: 'prior approval still required' };
  assert.equal(await f.handler(f.exec, async () => decision), decision);
  assert.equal(body.session_id, f.sid); assert.equal(body.native_name, 'reviewed-package-v1');
  assert.deepEqual(Object.keys(body).sort(), ['native_name', 'session_id', 'tool_name']);
});

test('native gate denies unknown or unavailable scope and never bypasses a prior denial', async t => {
  const f = await admissionFixture(t); const original = globalThis.fetch; let calls = 0;
  t.after(() => { globalThis.fetch = original; });
  globalThis.fetch = async () => { calls++; return new Response(JSON.stringify({ status: 'unverified', admitted: false, missing: [], omitted_sections: [] }), { headers: { 'content-type': 'application/json' } }); };
  assert.equal((await f.handler(f.exec, async () => ({ kind: 'allow' }))).kind, 'deny');
  const deny = { kind: 'deny', reason: 'existing security policy' };
  assert.equal(await f.handler(f.exec, async () => deny), deny); assert.equal(calls, 1);
  globalThis.fetch = async () => { throw Error('synthetic transport failure'); };
  assert.equal((await f.handler(f.exec, async () => ({ kind: 'allow' }))).reason, 'capability_scope_unverified');
});


test('explicit slash skill injection cannot bypass admission and failed loads do not register', async t => {
  const f = await admissionFixture(t); const original = globalThis.fetch; const requests = [];
  t.after(() => { globalThis.fetch = original; });
  globalThis.fetch = async (_url, options) => {
    const body = JSON.parse(options.body); requests.push(body);
    const admitted = !body.native_name;
    return new Response(JSON.stringify({ status: admitted ? 'available' : 'unavailable', admitted, missing: [], omitted_sections: [] }), { headers: { 'content-type': 'application/json' } });
  };
  const source = { kind: 'skill-invocation', form: 'instructions', name: 'reviewed-package-v1' };
  const options = { agent: f.exec.agent, signal: f.exec.signal, messages: [] };
  const decision = { kind: 'enter', messages: [{ source, content: [{ type: 'text', text: 'bounded instructions' }] }] };
  assert.deepEqual(await f.handlers.get('agent/pre-step')(options, async () => decision), { kind: 'reject' });
  assert.ok(requests.some(body => body.native_name === source.name));
  assert.ok(requests.every(body => body.loaded === undefined));
  f.handlers.get('tools/result')(f.exec, { isError: true });
  assert.ok(requests.every(body => body.loaded === undefined));
});

test('only a final successful native result registers and pre-step waits for confirmation', async t => {
  const f = await admissionFixture(t); const original = globalThis.fetch; const requests = [];
  t.after(() => { globalThis.fetch = original; });
  globalThis.fetch = async (_url, options) => {
    requests.push(JSON.parse(options.body));
    return new Response(JSON.stringify({ status: 'available', admitted: true, missing: [], omitted_sections: [] }), { headers: { 'content-type': 'application/json' } });
  };
  await f.handler(f.exec, async () => ({ kind: 'allow' }));
  assert.ok(requests.every(body => body.loaded === undefined));
  f.handlers.get('tools/result')(f.exec, { isError: false });
  const decision = { kind: 'enter', messages: [] };
  assert.equal(await f.handlers.get('agent/pre-step')({ agent: f.exec.agent, signal: f.exec.signal, messages: [] }, async () => decision), decision);
  assert.equal(requests.filter(body => body.loaded === true).length, 1);
});

test('registration uncertainty is shared across parent and child agents', async t => {
  const f = await admissionFixture(t); const original = globalThis.fetch;
  t.after(() => { globalThis.fetch = original; });
  globalThis.fetch = async (_url, options) => {
    const body = JSON.parse(options.body);
    if (body.loaded) throw Error('synthetic commit unavailable');
    return new Response(JSON.stringify({ status: 'available', admitted: true, missing: [], omitted_sections: [] }), { headers: { 'content-type': 'application/json' } });
  };
  const child = { ...f.exec, agent: { session: { header: { id: randomUUID(), cwd: f.exec.agent.session.header.cwd, parentSession: f.sid } } } };
  await f.handler(child, async () => ({ kind: 'allow' }));
  f.handlers.get('tools/result')(child, { isError: false });
  const decision = await f.handlers.get('agent/pre-step')({ agent: f.exec.agent, signal: f.exec.signal, messages: [] }, async () => ({ kind: 'enter', messages: [] }));
  assert.deepEqual(decision, { kind: 'reject' });
});


test('a parent pending load blocks a child tool until the shared registration completes', async t => {
  const f = await admissionFixture(t); const original = globalThis.fetch; let release; let started;
  const start = new Promise(resolve => { started = resolve; });
  t.after(() => { globalThis.fetch = original; });
  const reply = () => new Response(JSON.stringify({ status: 'available', admitted: true, missing: [], omitted_sections: [] }), { headers: { 'content-type': 'application/json' } });
  globalThis.fetch = async (_url, options) => {
    if (JSON.parse(options.body).loaded) { started(); return new Promise(resolve => { release = () => resolve(reply()); }); }
    return reply();
  };
  await f.handler(f.exec, async () => ({ kind: 'allow' }));
  f.handlers.get('tools/result')(f.exec, { isError: false }); await start;
  const child = { ...f.exec, name: 'research_run_script', agent: { session: { header: { id: randomUUID(), cwd: f.exec.agent.session.header.cwd, parentSession: f.sid } } } };
  let settled = false;
  const result = f.handler(child, async () => ({ kind: 'allow' })).then(value => { settled = true; return value; });
  await new Promise(resolve => setImmediate(resolve)); assert.equal(settled, false);
  release(); assert.equal((await result).kind, 'allow');
});
