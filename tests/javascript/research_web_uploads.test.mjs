import test from 'node:test';
import assert from 'node:assert/strict';
import { canUploadToSession, createUploadHandler } from '../../app/research_web/ui/uploads.mjs';

const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
test('picker, drop and paste share execution, historical and ordinary source guards', async () => {
  for (const detail of [{ execution_restricted: true }, { execution_context: {} }, { execution_context: { definition_snapshot: { research_task: { approved_data_sources: ['web'] } } } }, { source_scope: ['web'] }]) {
    assert.equal(canUploadToSession(detail), false);
    let uploads = 0; const errors = [];
    const handler = createUploadHandler({ state: { detail }, ensureSession: async () => true, upload: async () => { uploads++; }, accept() {}, notify: message => errors.push(message) });
    await handler([{ name: 'file' }]); assert.equal(uploads, 0); assert.equal(errors.length, 1);
  }
  assert.equal(canUploadToSession({ execution_context: { definition_snapshot: { research_task: { approved_data_sources: ['uploads'] } } } }), true);
});
test('late upload result belongs to original draft and duplicate uploads are rejected while pending', async () => {
  const hold = deferred(), started = deferred(), writes = [], accepted = [];
  const state = { detail: { id: 'a' } };
  const handler = createUploadHandler({ state, ensureSession: async () => true, upload: async (id, files) => { writes.push([id, files]); started.resolve(); return hold.promise; }, accept: (id, files) => accepted.push([id, files]), notify() {} });
  const files = [{ name: 'a.md' }];
  const pending = handler(files); await started.promise;
  await handler(files); state.detail = { id: 'b' }; hold.resolve({ items: [{ id: 'uploaded' }] }); await pending;
  assert.equal(writes.length, 1); assert.equal(writes[0][0], 'a');
  assert.deepEqual(accepted, [['a', [{ id: 'uploaded' }]]]);
});
test('navigation while ensuring an existing session never uploads to the new one', async () => {
  const hold = deferred(); const state = { detail: { id: 'a' } }; let uploaded = false;
  const handler = createUploadHandler({ state, ensureSession: () => hold.promise, upload: async () => { uploaded = true; }, accept() {}, notify() {} });
  const pending = handler([{ name: 'a.md' }]); state.detail = { id: 'b' }; hold.resolve(true); await pending;
  assert.equal(uploaded, false);
});
test('upload exceptions are visible, logged and unlock a later explicit attempt', async () => {
  const errors = [], logs = []; let count = 0;
  const handler = createUploadHandler({ state: { detail: { id: 'a' } }, ensureSession: async () => true, upload: async () => { count++; throw new Error('network'); }, accept() {}, notify: message => errors.push(message), logger: event => logs.push(event) });
  await handler([{}]); await handler([{}]); assert.equal(count, 2); assert.equal(errors.length, 2); assert.deepEqual(logs, ['upload_failed', 'upload_failed']);
});
