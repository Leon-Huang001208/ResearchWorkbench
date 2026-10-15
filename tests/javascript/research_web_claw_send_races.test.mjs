import assert from 'node:assert/strict';
import test from 'node:test';
import { createController } from '../../app/research_web/ui/core.mjs';

const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; };
const file = id => ({ id, name: `${id}.md` });
const tab = (id, instance = 'browser') => ({ tab_id: id, instance_id: instance });
const storage = () => { const values = new Map(); return { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) }; };
async function setup(options = {}) {
  const writes = [];
  const controller = createController({ logger() {}, makeID: () => 'stable-key', ...options,
    api: { detail: async id => ({ id, mode: 'claw', messages: [], status: 'idle' }), message: async (...args) => { writes.push(args); return { accepted: true }; }, ...options.api } });
  await controller.open({ page: 'claw', sessionId: 'origin' });
  controller.setDraft('submitted');
  return { controller, writes };
}

test('navigation while live-tab confirmation waits cancels the originating send', async () => {
  const confirmation = deferred();
  const { controller, writes } = await setup({ confirmTabbit: () => confirmation.promise });
  controller.addTabbit(tab(1));
  const sending = controller.send();
  await controller.open({ page: 'claw', sessionId: 'other' });
  controller.setDraft('other draft');
  confirmation.resolve(true); await sending;
  assert.equal(writes.length, 0);
  assert.equal(controller.state.draft, 'other draft');
  await controller.open({ page: 'claw', sessionId: 'origin' });
  assert.equal(controller.state.draft, 'submitted');
});

test('concurrent sends share one confirmation and send the pre-confirmation snapshot', async () => {
  const confirmation = deferred(); let confirmations = 0;
  const { controller, writes } = await setup({ confirmTabbit: () => { confirmations++; return confirmation.promise; } });
  controller.addTabbit(tab(1)); controller.addAttachments([file('old')]); controller.setTools(['original']);
  const first = controller.send(); const second = controller.send();
  controller.setDraft('next draft'); controller.addAttachments([file('new')]); controller.addTabbit(tab(2)); controller.setTools(['later']);
  confirmation.resolve(true); await Promise.all([first, second]);
  assert.equal(confirmations, 1); assert.equal(writes.length, 1);
  assert.equal(writes[0][1].text, 'submitted'); assert.deepEqual(writes[0][1].tool_ids, ['original']);
  assert.deepEqual(writes[0][1].attachment_ids, ['old']); assert.deepEqual(writes[0][1].tabbit_tabs, [tab(1)]);
  assert.equal(controller.state.draft, 'next draft'); assert.deepEqual(controller.state.attachments, [file('new')]);
  assert.deepEqual(controller.state.tabbitTabs, [tab(2)]);
});

test('accepted send preserves later materials when draft text has not changed', async () => {
  const response = deferred();
  const { controller } = await setup({ api: { message: () => response.promise } });
  controller.addAttachments([file('old')]);
  const sending = controller.send(); controller.addAttachments([file('new')]); controller.addTabbit(tab(2));
  response.resolve({ accepted: true }); await sending;
  assert.equal(controller.state.draft, ''); assert.deepEqual(controller.state.attachments, [file('new')]);
  assert.deepEqual(controller.state.tabbitTabs, [tab(2)]);
});

test('offscreen accepted send removes submitted material but saves next draft and additions across reload', async () => {
  const response = deferred(); const draftStorage = storage();
  const { controller } = await setup({ draftStorage, api: { message: () => response.promise } });
  controller.addAttachments([file('old')]); controller.addTabbit(tab(1));
  const sending = controller.send(); await Promise.resolve(); controller.setDraft('next draft'); controller.addAttachments([file('new')]); controller.addTabbit(tab(2));
  await controller.open({ page: 'claw', sessionId: 'other' }); controller.setDraft('unrelated');
  response.resolve({ accepted: true }); await sending;
  assert.equal(controller.state.draft, 'unrelated');
  await controller.open({ page: 'claw', sessionId: 'origin' });
  assert.equal(controller.state.draft, 'next draft'); assert.deepEqual(controller.state.attachments, [file('new')]);
  assert.deepEqual(controller.state.tabbitTabs, [tab(2)]);
  const reloaded = await setup({ draftStorage });
  assert.deepEqual(reloaded.controller.state.attachments, [file('new')]);
});

test('returning to the sending session cannot resubmit in-flight and preserves its later draft', async () => {
  const response = deferred(); let writes = 0;
  const { controller } = await setup({ api: { message: () => { writes++; return response.promise; } } });
  controller.addAttachments([file('old')]); const sending = controller.send();
  await controller.open({ page: 'claw', sessionId: 'other' }); await controller.open({ page: 'claw', sessionId: 'origin' });
  controller.setDraft('later'); controller.addAttachments([file('new')]); const duplicate = controller.send();
  const observedWrites = writes;
  response.resolve({ accepted: true }); await Promise.all([sending, duplicate]);
  assert.equal(observedWrites, 1);
  assert.equal(controller.state.draft, 'later'); assert.deepEqual(controller.state.attachments, [file('new')]);
});


test('confirmation failure releases the send lock and failed transport reuses its idempotency key', async () => {
  let confirmations = 0; let attempts = 0; const keys = [];
  const { controller } = await setup({ makeID: () => `key-${keys.length}`,
    confirmTabbit: async () => { if (++confirmations === 1) throw new Error('confirmation failed'); return true; },
    api: { message: async (_id, _body, key) => { keys.push(key); if (++attempts === 1) throw new Error('transport uncertain'); return { accepted: true }; } } });
  controller.addTabbit(tab(1));
  await controller.send(); assert.match(controller.state.error, /confirmation failed/);
  await controller.send(); assert.equal(controller.state.draft, 'submitted');
  await controller.send(); assert.equal(controller.state.draft, '');
  assert.equal(keys.length, 2); assert.equal(keys[0], keys[1]);
});

test('tab cleanup includes instance identity and keeps an unsubmitted replacement tab', async () => {
  const response = deferred();
  const { controller } = await setup({ confirmTabbit: async () => true, api: { message: () => response.promise } });
  controller.addTabbit(tab(1)); const sending = controller.send(); await Promise.resolve();
  controller.removeTabbit(1); controller.addTabbit(tab(1, 'replacement-browser'));
  response.resolve({ accepted: true }); await sending;
  assert.deepEqual(controller.state.tabbitTabs, [tab(1, 'replacement-browser')]);
});

test('execution followup sends only approved scope and leaves unsubmitted material available', async () => {
  const writes = [];
  const { controller } = await setup({ api: {
    detail: async id => ({ id, messages: [], execution_context: { definition_snapshot: { output_formats: ['md'], research_task: { approved_tools: ['approved'], approved_data_sources: ['web'] } } } }),
    message: async (_id, body) => { writes.push(body); return { accepted: true }; }
  }, confirmTabbit: () => { throw new Error('must not confirm browser scope'); } });
  controller.setTools(['unapproved']); controller.addAttachments([file('excluded')]); controller.addTabbit(tab(1));
  await controller.send();
  assert.deepEqual(writes, [{ text: 'submitted', tool_ids: ['approved'], expected_formats: ['md'] }]);
  assert.deepEqual(controller.state.attachments, [file('excluded')]); assert.deepEqual(controller.state.tabbitTabs, [tab(1)]);
});
