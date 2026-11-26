import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  createOfficeAutoConsent,
  officeConsentNeedsConfirm,
  officeConsentTargets,
  OFFICE_INTEGRATION_IDS,
} from '../../app/research_web/ui/office-auto-consent.mjs';
import { createLocalIntegrationPollingGuard, createOfficeConsentQueue } from '../../app/research_web/ui/connections.mjs';

test('target resolution covers all, single, and unknown requests', () => {
  assert.deepEqual(officeConsentTargets('all'), [...OFFICE_INTEGRATION_IDS]);
  assert.deepEqual(officeConsentTargets('local:word_app'), ['local:word_app']);
  assert.deepEqual(officeConsentTargets('local:not_installed'), []);
  assert.deepEqual(officeConsentTargets(''), []);
});

test('enabling never asks for confirmation', () => {
  assert.equal(
    officeConsentNeedsConfirm({ requested: 'all', currentlyEnabled: false, confirmed: 'false', pendingTarget: '' }),
    false,
  );
});

test('disabling asks once, then proceeds on the confirmed second click', () => {
  const first = officeConsentNeedsConfirm({ requested: 'all', currentlyEnabled: true, confirmed: 'false', pendingTarget: '' });
  assert.equal(first, true);
  const second = officeConsentNeedsConfirm({ requested: 'all', currentlyEnabled: true, confirmed: 'true', pendingTarget: 'all' });
  assert.equal(second, false);
});

test('a confirmation for a different target does not carry over', () => {
  const needs = officeConsentNeedsConfirm({
    requested: 'local:excel_app', currentlyEnabled: true, confirmed: 'true', pendingTarget: 'all',
  });
  assert.equal(needs, true, 'confirming "all" must not authorise a single-integration disable');
});

function harness({ batches = [], failing = null, catalogItems = [] } = {}) {
  let pendingTarget = '';
  const state = {
    success: '', error: '', renders: 0, loads: 0, fetched: [], logged: [],
    catalog: { localIntegrations: { integration_status: { items: catalogItems, latest_batch: null } } },
  };
  const guard = createLocalIntegrationPollingGuard(() => true);
  const queue = createOfficeConsentQueue(async (id, consent) => {
    if (failing === id) throw Object.assign(new Error('拒绝'), { code: 'denied' });
    return { batch: { id: `b-${id}` }, consent };
  });
  const controller = createOfficeAutoConsent({
    guard, queue,
    getCatalog: () => state.catalog,
    loadCatalog: async () => { state.loads += 1; },
    fetchBatch: async id => { state.fetched.push(id); return { status: 'done', items: {} }; },
    waitForBatch: async (getBatch, id) => getBatch(id),
    setSuccess: v => { state.success = v; },
    setError: v => { state.error = v; },
    render: () => { state.renders += 1; },
    log: (event, detail) => state.logged.push([event, detail]),
    getPendingTarget: () => pendingTarget,
    setPendingTarget: v => { pendingTarget = v; },
  });
  return { controller, state, get pending() { return pendingTarget; }, guard };
}

test('turning it off records the target and waits for confirmation', async () => {
  const h = harness();
  const outcome = await h.controller.apply({ requested: 'all', currentlyEnabled: true, confirmed: 'false' });
  assert.equal(outcome, 'needs-confirm');
  assert.equal(h.pending, 'all');
  assert.equal(h.state.loads, 0, 'nothing hits the server before confirmation');
});

test('confirming the disable updates every Office integration and reports once', async () => {
  const items = OFFICE_INTEGRATION_IDS.map(id => ({ id, details: {} }));
  const h = harness({ catalogItems: items });
  h.controller.apply({ requested: 'all', currentlyEnabled: true, confirmed: 'false' });
  const outcome = await h.controller.apply({ requested: 'all', currentlyEnabled: true, confirmed: 'true' });
  assert.equal(outcome, 'done');
  assert.equal(h.pending, '');
  assert.equal(h.state.success, '已关闭对应 Office 自动验证。');
  assert.ok(h.state.fetched.length === 3, 'each integration batch is watched');
});

test('turning it on skips confirmation and patches rows optimistically', async () => {
  const items = OFFICE_INTEGRATION_IDS.map(id => ({ id, details: { auto_probe_consent: false } }));
  const h = harness({ catalogItems: items });
  const outcome = await h.controller.apply({ requested: 'all', currentlyEnabled: false, confirmed: 'false' });
  assert.equal(outcome, 'done');
  assert.equal(h.state.success, 'Office 自动验证已处理；请查看每项结果。');
});

test('an unknown integration is ignored without touching the server', async () => {
  const h = harness();
  const outcome = await h.controller.apply({ requested: 'local:unknown', currentlyEnabled: false, confirmed: 'true' });
  assert.equal(outcome, 'ignored');
  assert.equal(h.state.loads, 0);
});

test('a rejected consent surfaces the error and logs a stable code', async () => {
  const h = harness({ failing: 'local:word_app' });
  const outcome = await h.controller.apply({ requested: 'local:word_app', currentlyEnabled: false, confirmed: 'true' });
  assert.equal(outcome, 'failed');
  assert.equal(h.state.error, '拒绝');
  assert.deepEqual(h.state.logged.at(-1), ['office_auto_consent_failed', { status: 'denied' }]);
});

test('leaving the page mid-flight abandons the flow silently', async () => {
  const items = OFFICE_INTEGRATION_IDS.map(id => ({ id, details: {} }));
  const h = harness({ catalogItems: items });
  // Invalidate between begin() and the post-queue check.
  const original = h.guard.begin.bind(h.guard);
  h.guard.begin = () => { const ticket = original(); h.guard.invalidate(); return ticket; };
  const outcome = await h.controller.apply({ requested: 'all', currentlyEnabled: false, confirmed: 'true' });
  assert.equal(outcome, 'ignored');
  assert.equal(h.state.success, '', 'no success message after the user left');
});
