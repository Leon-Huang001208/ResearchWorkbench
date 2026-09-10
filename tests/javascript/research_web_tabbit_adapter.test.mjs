import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildExtractionCode,
  createTabbitRuntime,
  fairPageLimit,
  taskName,
} from '../../app/research_web/runtime/tabbit-adapter.mjs';

const makeContext = ({ finishError, evaluationValue, inventoryTabs } = {}) => {
  const calls = [];
  const listeners = new Map();
  const client = {
    resolvedInstanceId: () => '0123456789ABCDEF',
    evaluate: async (request) => {
      calls.push(['evaluate', request]);
      return {
        status: 'succeeded',
        result: {
          value: evaluationValue ?? [
            { title: 'First page', url: 'https://first.test/', text: 'one', truncated: false },
            { title: 'Second / page', url: 'https://second.test/', text: 'two', truncated: true },
          ],
        },
      };
    },
    finishTask: async (name, options) => {
      calls.push(['finish', name, options]);
      if (finishError) throw finishError;
    },
  };
  const ctx = {
    tabbit: {
      client: () => client,
      grantPageAccess() {},
      launcherPath: () => '/tabbit-cli',
      instances: () => [{ id: '0123456789ABCDEF', appName: 'Tabbit', online: true }],
      resolveExecutionInstance: () => ({ id: '0123456789ABCDEF' }),
      listAllTabs: async () => ({
        tabs: inventoryTabs ?? [
          { tabId: 41, title: 'First page', url: 'https://first.test/', state: 'available' },
          { tabId: 9, title: 'Second / page', url: 'https://second.test/', state: 'available' },
          { tabId: 1, title: 'First page', url: 'https://first.test/', state: 'available' },
          { tabId: 2, title: 'Second / page', url: 'https://second.test/', state: 'available' },
        ],
        truncated: false,
      }),
    },
    on: (name, handler) => listeners.set(name, handler),
    inject() {},
    logger: { info() {}, warn() {} },
  };
  return { ctx, calls, listeners };
};

test('live extraction claims in selection order, reads once, and always keeps tabs', async () => {
  const { ctx, calls } = makeContext({
    evaluationValue: [
      { title: 'Second / page', url: 'https://second.test/', text: 'two', truncated: true },
      { title: 'First page', url: 'https://first.test/', text: 'one', truncated: false },
    ],
  });
  const runtime = createTabbitRuntime(ctx, {}, { uuid: () => 'token-1', now: () => 1000 });
  runtime.grantAccess('abcd-session');
  const result = await runtime.extract({
    sessionId: 'abcd-session', requestId: '12345678-request',
    instanceId: '0123456789ABCDEF', tabIds: [41, 9],
  });
  assert.equal(calls[0][0], 'evaluate');
  assert.deepEqual(calls[0][1].claimTabs, [41, 9]);
  assert.equal(calls[0][1].readOnly, true);
  assert.match(calls[0][1].code, /document\.body/);
  assert.deepEqual(calls[1], ['finish', 'rwb-mention-abcd-12345678', { keep: true }]);
  assert.deepEqual(result.markers.map((item) => item.tabId), [41, 9]);
  assert.match(result.markers[0].marker, /^@\[First page\]/u);
  assert.match(result.markers[1].marker, /^@\[Second \/ page\]/u);
  assert.match(result.markers[0].marker, /rwb-tabbit:token-1/);
});

test('status reports safe ready, unsupported, and ambiguous instance states', async () => {
  const { ctx } = makeContext();
  const ready = createTabbitRuntime(ctx, {}, {
    existsSync: () => true,
    installations: async () => ({ installations: [{ version: '1.13.23', path: '/private/app' }], supportedInstallations: [{}] }),
  });
  assert.deepEqual(await ready.status(), {
    status: 'ready', pluginVersion: '0.3.4', browserVersion: '1.13.23', launcherPresent: true,
    onlineInstances: 1, selectedInstance: '0123456789ABCDEF',
    instances: [{ id: '0123456789ABCDEF', name: 'Tabbit', online: true }],
  });
  ctx.tabbit.resolveExecutionInstance = () => ({});
  ctx.tabbit.instances = () => [
    { id: '0123456789ABCDEF', appName: 'One', online: true },
    { id: 'FEDCBA9876543210', appName: 'Two', online: true },
  ];
  const ambiguous = createTabbitRuntime(ctx, {}, {
    existsSync: () => true,
    installations: async () => ({ installations: [{ version: '1.8.9' }], supportedInstallations: [] }),
  });
  assert.equal((await ambiguous.status()).status, 'unsupported_version');
  const current = createTabbitRuntime(ctx, {}, {
    existsSync: () => true,
    installations: async () => ({ installations: [{ version: '1.9.0' }], supportedInstallations: [{}] }),
  });
  assert.equal((await current.status()).status, 'instance_selection_required');
  ctx.tabbit.resolveExecutionInstance = () => { throw new Error('ambiguous private detail'); };
  assert.equal((await current.status()).status, 'instance_selection_required');
  assert.doesNotMatch(JSON.stringify(await ready.status()), /private\/app/);
});

test('finish failure prevents tokens from being published', async () => {
  const { ctx } = makeContext({ finishError: new Error('private path') });
  const runtime = createTabbitRuntime(ctx);
  runtime.grantAccess('abcd');
  await assert.rejects(
    runtime.extract({ sessionId: 'abcd', requestId: '12345678', instanceId: '0123456789ABCDEF', tabIds: [1, 2] }),
    (error) => error.code === 'tabbit_finish_failed',
  );
  assert.equal(runtime.stash.size, 0);
});

test('indistinguishable selected tabs fail closed before a task is claimed', async () => {
  const { ctx, calls } = makeContext({
    inventoryTabs: [
      { tabId: 1, title: 'Duplicate page', url: 'https://duplicate.test/', state: 'available' },
      { tabId: 2, title: 'Duplicate page', url: 'https://duplicate.test/', state: 'available' },
    ],
  });
  const runtime = createTabbitRuntime(ctx);
  runtime.grantAccess('abcd');
  await assert.rejects(
    runtime.extract({
      sessionId: 'abcd',
      requestId: '12345678',
      instanceId: '0123456789ABCDEF',
      tabIds: [1, 2],
    }),
    (error) => error.code === 'tabbit_extract_ambiguous',
  );
  assert.deepEqual(calls, []);
});

test('tokens are session-bound, single-use, and expire after ten minutes', async () => {
  let clock = 10;
  const { ctx } = makeContext();
  let serial = 0;
  const runtime = createTabbitRuntime(ctx, {}, { uuid: () => `token-${++serial}`, now: () => clock });
  runtime.grantAccess('abcd');
  const { markers } = await runtime.extract({ sessionId: 'abcd', requestId: '12345678', instanceId: '0123456789ABCDEF', tabIds: [1, 2] });
  const message = { id: 'm', role: 'user', source: { kind: 'user' }, content: [{ type: 'text', text: markers.map((item) => item.marker).join(' ') }] };
  const next = async () => ({ kind: 'enter', messages: [message] });
  const denied = await runtime.expand({ agent: { id: 'another' } }, next);
  assert.equal(denied.kind, 'reject');
  const expanded = await runtime.expand({ agent: { id: 'abcd' } }, next);
  assert.equal(expanded.kind, 'enter');
  assert.equal(expanded.messages.length, 3);
  assert.equal(runtime.stash.size, 0);
  assert.equal((await runtime.expand({ agent: { id: 'abcd' } }, next)).kind, 'reject');

  await runtime.extract({ sessionId: 'abcd', requestId: 'next5678', instanceId: '0123456789ABCDEF', tabIds: [1, 2] });
  clock += 600_001;
  const expiredMessage = { ...message, content: [{ type: 'text', text: '@[First](rwb-tabbit:token-3)' }] };
  assert.equal((await runtime.expand({ agent: { id: 'abcd' } }, async () => ({ kind: 'enter', messages: [expiredMessage] }))).kind, 'reject');
});

test('denying access revokes the adapter session grant', async () => {
  const { ctx } = makeContext();
  const runtime = createTabbitRuntime(ctx);
  runtime.grantAccess('abcd');
  assert.equal(runtime.grants.has('abcd'), true);
  assert.deepEqual(runtime.decideAccess('abcd', 'deny'), { accepted: false });
  assert.equal(runtime.grants.has('abcd'), false);
});

test('write operations require native approval while declared read-only calls continue', async () => {
  const { ctx, listeners } = makeContext();
  const runtime = createTabbitRuntime(ctx);
  runtime.register();
  const hook = listeners.get('tools/pre-execute');
  const execution = { name: 'tabbit_browser', arguments: { read_only: true }, agent: { id: 'session-abcd' } };
  assert.equal((await hook(execution, async () => ({ kind: 'allow' }))).kind, 'ask');
  assert.deepEqual(await hook(execution, async () => ({ kind: 'deny', reason: 'downstream' })), { kind: 'deny', reason: 'downstream' });
  listeners.get('tools/result')(execution, { isError: false });
  assert.deepEqual(await hook(execution, async () => ({ kind: 'allow' })), { kind: 'allow' });
  assert.equal((await hook({ ...execution, arguments: { read_only: false } }, async () => ({ kind: 'allow' }))).kind, 'ask');
  runtime.decideAccess('abcd', 'deny');
  assert.equal((await hook(execution, async () => ({ kind: 'allow' }))).kind, 'ask');
});

test('task names and fair limits are deterministic and bounded', () => {
  assert.equal(taskName('session-ABCD', 'request-12345678'), 'rwb-mention-sess-request1');
  assert.equal(fairPageLimit(1), 60_000);
  assert.equal(fairPageLimit(8), 15_000);
  assert.match(buildExtractionCode(8), /15000/);
});
