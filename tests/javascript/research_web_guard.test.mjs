import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, readFile, rm, realpath } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { execFileSync } from 'node:child_process';
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
const dockerTextAcceptance = { profile: 'docker-text', installationId: 'b'.repeat(32), modelCalls: 3, maxOutputTokens: 512 };

test('Docker text acceptance blocks dispatch across reapply and concurrency while budget authority is unverified', async () => {
  let dispatched = 0;
  const next = async function* () { dispatched++; };
  for (let restart = 0; restart < 2; restart++) {
    const c = acceptanceContext();
    apply(c.ctx, { enabled: true, acceptance: dockerTextAcceptance });
    assert.equal(dispatched, 0);
    const consume = async () => {
      for await (const _ of c.listeners.get('llm/stream')(Object.freeze({ messages: [], maxTokens: 512 }), next)) {}
    };
    const results = await Promise.allSettled(Array.from({ length: 8 }, consume));
    assert.ok(results.every(result => result.status === 'rejected' && result.reason.message === 'acceptance_budget_unverified'));
    assert.equal(dispatched, 0);
    assert.ok(c.guard({ name: 'datahub_get_fund_data', arguments: publicNav, agent: makeAgent() }));
  }
});

test('Docker text accepted budget binding denies unexpected provider before any bridge dispatch', async () => {
  const c = acceptanceContext();
  apply(c.ctx, { acceptance: { ...dockerTextAcceptance, budgetBridge: {
    python: '/controlled/python', bridge: '/controlled/live_acceptance_budget.py',
  } } });
  await assert.rejects(async () => {
    for await (const _ of c.listeners.get('llm/stream')({ messages: [], maxTokens: 512, provider: 'other', model: 'deepseek-v4-flash' }, async function* () { assert.fail('dispatch forbidden'); })) {}
  }, { message: 'acceptance_provider_denied' });
});

test('Docker text bridge reserves real persistent tickets across concurrency and cold guard restore', async () => {
  const python = process.env.RWB_TEST_PYTHON || execFileSync('python3', ['-c', 'import sys;print(sys.executable)'], { encoding: 'utf8' }).trim();
  const temporary = await mkdtemp(join(await realpath(tmpdir()), 'task4b-budget-'));
  const parent = join(temporary, 'private');
  const root = join(parent, 'b'.repeat(32));
  const bridge = join(temporary, 'fixture-bridge.py');
  const source = resolve(new URL('../../', import.meta.url).pathname);
  const prelude = `import sys,json\nfrom datetime import UTC,datetime\nsys.path.insert(0,${JSON.stringify(source)})\nfrom app.research_web.live_acceptance_budget import BudgetStore,BudgetError,authorization\nclock=lambda:datetime(2026,10,8,11,tzinfo=UTC)\nroot=${JSON.stringify(root)}\n`;
  try {
    await mkdir(parent, { mode: 0o700 });
    execFileSync(python, ['-I', '-B', '-c', prelude + "BudgetStore.initialize(root,'b'*32,authorization(3,512,'2026-10-08T11:30:00Z'),clock=clock)"], { stdio: 'pipe' });
    await writeFile(bridge, prelude + [
      "request=json.loads(sys.stdin.buffer.read(8193))",
      "assert set(request)=={'op','outputTokens'} and request['op']=='reserve'",
      "assert type(request['outputTokens']) is int",
      "try:",
      " result=BudgetStore(root,'b'*32,clock=clock).reserve(request['outputTokens'])",
      " print(json.dumps({'ok':True,**result}))",
      "except BudgetError as error:",
      " print(json.dumps({'ok':False,'error':str(error)}));sys.exit(1)",
    ].join('\n'), { mode: 0o600 });
    const control = { ...dockerTextAcceptance, budgetBridge: { python, bridge } };
    let dispatched = 0;
    const options = Object.freeze({ messages: [{ content: 'private fixture prompt' }], apiKey: 'private fixture key',
      maxTokens: 512, provider: 'deepseek-official', model: 'deepseek-v4-flash', tools: [] });
    const c = acceptanceContext();
    apply(c.ctx, { acceptance: control });
    let reads = 0;
    const lateAbort = { get aborted() { reads++; return reads > 1; } };
    await assert.rejects(async () => {
      for await (const _ of c.listeners.get('llm/stream')({ ...options, signal: lateAbort }, async function* () { assert.fail('late abort dispatched'); })) {}
    }, { message: 'acceptance_request_aborted' });
    assert.equal(JSON.parse(await readFile(join(root, 'ledger.json'), 'utf8')).tickets, 1);
    const consume = async ctx => {
      for await (const _ of ctx.listeners.get('llm/stream')(options, async function* () { dispatched++; throw Error('test transport failure'); })) {}
    };
    const outcomes = await Promise.allSettled(Array.from({ length: 8 }, () => consume(c)));
    assert.equal(dispatched, 2);
    assert.equal(outcomes.filter(result => result.reason?.message === 'acceptance_budget_exhausted').length, 6);
    assert.equal(JSON.parse(await readFile(join(root, 'ledger.json'), 'utf8')).tickets, 3);
    const cold = acceptanceContext();
    apply(cold.ctx, { acceptance: control });
    await assert.rejects(consume(cold), { message: 'acceptance_budget_exhausted' });
    assert.equal(dispatched, 2);
  } finally { await rm(temporary, { recursive: true, force: true }); }
});

test('Docker text acceptance validates frozen output bounds and recursive attachments before dispatch', async () => {
  const c = acceptanceContext();
  apply(c.ctx, { enabled: true, acceptance: dockerTextAcceptance });
  let dispatched = 0;
  const consume = async options => {
    for await (const _ of c.listeners.get('llm/stream')(Object.freeze(options), async function* () { dispatched++; })) {}
  };
  for (const maxTokens of [undefined, null, true, 0, -1, 513, 0.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1]) {
    await assert.rejects(consume({ messages: [], maxTokens }), /acceptance_output_limit/);
  }
  for (const type of ['image', 'file', 'audio']) {
    await assert.rejects(consume({ maxTokens: 512, messages: [{ content: [{ nested: { type } }] }] }), /acceptance_text_only/);
  }
  assert.equal(dispatched, 0);
});

test('Docker text acceptance denies unknown fields and invalid identity', () => {
  const c = acceptanceContext();
  for (const changes of [{ installationId: 'wrong' }, { maxOutputTokens: 4097 }, { maxOutputTokens: true }, { modelCalls: 4 }, { budgetVerified: true }]) {
    assert.throws(() => apply(c.ctx, { acceptance: { ...dockerTextAcceptance, ...changes } }), /acceptance_control_invalid/);
  }
});

test('Docker text acceptance errors and logs omit request secrets and reject an already aborted signal', async () => {
  const c = acceptanceContext();
  const logged = [];
  c.ctx.logger = { warn(...args) { logged.push(args); }, info(...args) { logged.push(args); } };
  apply(c.ctx, { acceptance: dockerTextAcceptance });
  const consume = async options => {
    for await (const _ of c.listeners.get('llm/stream')(options, async function* () { assert.fail('dispatch forbidden'); })) {}
  };
  await assert.rejects(consume({ maxTokens: 512, messages: [{ content: 'fixture-sensitive-request' }], apiKey: 'fixture-sensitive-key' }), { message: 'acceptance_budget_unverified' });
  await assert.rejects(consume({ maxTokens: 512, messages: [], signal: AbortSignal.abort() }), { message: 'acceptance_request_aborted' });
  assert.deepEqual(logged, [['research_acceptance_budget_unverified']]);
});

test('Docker text acceptance redacts a private abort reason while legacy profile preserves cancellation semantics', async () => {
  const privateReason = new Error('fixture-sensitive-request-and-key');
  let dispatched = 0;
  const errors = [];
  const logged = [];
  for (const profile of [dockerTextAcceptance, acceptance]) {
    const c = acceptanceContext();
    c.ctx.logger = { warn(...args) { logged.push(args); }, info(...args) { logged.push(args); } };
    apply(c.ctx, { acceptance: profile });
    try {
      for await (const _ of c.listeners.get('llm/stream')({
        messages: [], maxTokens: 512, signal: AbortSignal.abort(privateReason),
      }, async function* () { dispatched++; })) {}
      assert.fail('aborted request must reject');
    } catch (error) { errors.push(error); }
  }
  assert.equal(errors[0].message, 'acceptance_request_aborted');
  assert.notEqual(errors[0], privateReason);
  assert.equal(errors[1], privateReason);
  assert.deepEqual(logged, []);
  assert.equal(dispatched, 0);
});

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
