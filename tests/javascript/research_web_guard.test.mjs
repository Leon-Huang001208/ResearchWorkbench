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
