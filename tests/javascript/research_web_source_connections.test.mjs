import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createSourceConnections, sharedImpactNote, sourceLabel } from '../../app/research_web/ui/source-connections.mjs';

const CATALOG = {
  connections: { sources: [
    { id: 'wind', label: 'Wind' },
    { id: 'zhiqiu_reports', label: '知丘研报' },
  ] },
};

/**
 * Run a test body with globalThis.confirm stubbed.
 * Both the remove and consent paths confirm before touching the server.
 */
async function withConfirm(answer, body) {
  const original = globalThis.confirm;
  globalThis.confirm = () => answer;
  try { return await body(); } finally { globalThis.confirm = original; }
}

function harness({ confirmAnswer = true, actionResult = true, probeAccepted = { id: 'p1' }, probeHealth = 'healthy', verifyStatus = 'authenticated', throwOn = null } = {}) {
  const s = { success: '', error: '', renders: 0, busy: [], selected: 'keep', loads: [], configLoads: [], logged: [], actions: 0 };
  const api = {
    deleteSourceConfiguration: async id => { if (throwOn === 'delete') throw new Error('boom'); return actionResult; },
    setIntegrationConsent: async (id, v) => { if (throwOn === 'consent') throw new Error('boom'); s.lastConsent = [id, v]; return actionResult; },
    probeDataSource: async () => probeAccepted,
    dataProbe: async () => ({ health: probeHealth }),
    verifySourceAuthorization: async () => { if (throwOn === 'verify') throw new Error('授权失败'); return { status: verifyStatus }; },
  };
  const controller = { action: async fn => { s.actions += 1; return fn(); } };
  const sc = createSourceConnections({
    getCatalog: () => CATALOG,
    api,
    controller,
    loadCatalog: async names => { s.loads.push(names); },
    loadConnectionConfiguration: async id => { s.configLoads.push(id); },
    setSuccess: v => { s.success = v; },
    setError: v => { s.error = v; },
    clearError: () => { s.error = ''; },
    clearSuccess: () => { s.success = ''; },
    setProbeBusy: v => { s.busy.push(v); },
    clearSelectedConfiguration: () => { s.selected = null; },
    render: () => { s.renders += 1; },
    waitForProbe: async () => ({ health: probeHealth }),
    waitForBatch: async (fn, id) => fn(id),
    newId: () => 'fixed-uuid',
    log: (...args) => s.logged.push(args),
  });
  return { sc, s, setConfirm: null };
}

test('source labels fall back to the raw id when the source is gone', () => {
  assert.equal(sourceLabel(CATALOG, 'wind'), 'Wind');
  assert.equal(sourceLabel(CATALOG, 'removed_source'), 'removed_source');
  assert.equal(sourceLabel({}, 'x'), 'x');
});

test('only zhiqiu sources carry the shared-pool warning', () => {
  assert.match(sharedImpactNote('zhiqiu_reports'), /三项授权都会被移除/);
  assert.equal(sharedImpactNote('wind'), '');
});

test('removing a source clears the selection and reloads dependent catalogs', async () => {
  const h = harness();
  const outcome = await withConfirm(true, () => h.sc.remove('wind'));
  assert.equal(outcome, 'removed');
  assert.equal(h.s.success, '本机配置和系统凭据已移除；历史快照保持可读。');
  assert.equal(h.s.selected, null);
  assert.deepEqual(h.s.loads[0], ['connections', 'dataCatalog', 'tools']);
});

test('a cancelled confirmation never reaches the API', async () => {
  const h = harness();
  const outcome = await withConfirm(false, () => h.sc.remove('wind'));
  assert.equal(outcome, 'cancelled');
  assert.equal(h.s.actions, 0);
});

test('consent flips the current value rather than taking a target', async () => {
  const h = harness();
  await withConfirm(true, () => h.sc.setConsent({ sourceId: 'wind', currentlyEnabled: false }));
  assert.deepEqual(h.s.lastConsent, ['data:wind', true]);
  assert.equal(h.s.success, '已允许自动检测 Wind。');
});

test('disabling consent reports the disable message', async () => {
  const h = harness();
  await withConfirm(true, () => h.sc.setConsent({ sourceId: 'wind', currentlyEnabled: true }));
  assert.deepEqual(h.s.lastConsent, ['data:wind', false]);
  assert.equal(h.s.success, '已停用 Wind 的自动检测。');
});

test('dismissing the consent prompt leaves the toggle untouched', async () => {
  const h = harness();
  const outcome = await withConfirm(false, () => h.sc.setConsent({ sourceId: 'wind', currentlyEnabled: false }));
  assert.equal(outcome, 'cancelled');
  assert.equal(h.s.lastConsent, undefined, 'no consent call after dismissal');
});

test('a probe reports health and always clears the busy flag', async () => {
  const h = harness({ probeHealth: 'healthy' });
  assert.equal(await h.sc.probe('wind'), 'done');
  assert.equal(h.s.success, 'Wind检测通过。');
  assert.deepEqual(h.s.busy, [true, false], 'busy must be released in finally');
  assert.equal(h.s.configLoads.at(-1), 'wind');
});

test('an unhealthy probe still completes but asks the user to look', async () => {
  const h = harness({ probeHealth: 'degraded' });
  assert.equal(await h.sc.probe('wind'), 'done');
  assert.equal(h.s.success, 'Wind检测完成，请根据状态说明处理。');
});

test('a probe without a usable task id fails loudly instead of polling nothing', async () => {
  const h = harness({ probeAccepted: { id: '' } });
  assert.equal(await h.sc.probe('wind'), 'failed');
  assert.match(h.s.error, /有效的探测任务/);
  assert.deepEqual(h.s.busy, [true, false]);
});

test('verify distinguishes an auth exchange from data permission', async () => {
  const h = harness();
  assert.equal(await h.sc.verifyAuth('wind'), 'verified');
  assert.match(h.s.success, /具体数据权限尚未验证/);
});

test('verify failure logs a stable code and releases busy', async () => {
  const h = harness({ throwOn: 'verify' });
  assert.equal(await h.sc.verifyAuth('wind'), 'failed');
  assert.equal(h.s.error, '授权失败');
  assert.deepEqual(h.s.logged.at(-1), ['source_authorization_unverified']);
  assert.deepEqual(h.s.busy, [true, false]);
});
