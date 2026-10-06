import test from 'node:test';
import assert from 'node:assert/strict';
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
