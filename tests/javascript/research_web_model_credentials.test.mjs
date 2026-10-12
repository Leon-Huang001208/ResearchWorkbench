import test from 'node:test';
import assert from 'node:assert/strict';
import { createProvider, MODEL_REF } from '../../app/research_web/runtime/model-credentials.mjs';

class Records {
  constructor(ctx, config) { this.ctx = ctx; this.config = config; this.records = new Map(); }
  resolve() { throw Error('legacy reference resolver reached'); }
  describe() { throw Error('legacy reference describer reached'); }
  set() { throw Error('legacy reference writer reached'); }
  unset() { throw Error('legacy reference remover reached'); }
  readRecord(key) { return this.records.get(key); }
  modifyRecord(key, mutate) { const value = mutate(this.readRecord(key)); this.records.set(key, value); return value; }
  notifyUpdated() {}
}
const ctx = { logger: { warn() {} } };
test('system model references and unchanged Host record plane', async () => {
  let value = null;
  const bridge = async (op, next) => {
    if (op === 'set') value = next;
    if (op === 'unset') value = null;
    return op === 'resolve' ? { value } : op === 'describe' ?
      { configured: value !== null, source: 'system-keychain', writable: true } : {};
  };
  const Provider = createProvider(Records, bridge);
  const provider = new Provider(ctx, { recordsPath: '/private/records.yaml' });
  assert.equal(await provider.resolve(MODEL_REF), undefined);
  await provider.set(MODEL_REF, 'synthetic-first');
  assert.equal((await provider.resolve(MODEL_REF)).value, 'synthetic-first');
  assert.equal((await provider.describe(MODEL_REF)).source, 'system-keychain');
  await assert.rejects(provider.resolve('OTHER'), /model_credential_ref_denied/);
  const key = 'client-connection/browser-session';
  provider.modifyRecord(key, () => ({ type: 'api-key', payload: 'synthetic-auth' }));
  await provider.unset(MODEL_REF);
  assert.equal(await provider.resolve(MODEL_REF), undefined);
  assert.equal(provider.readRecord(key).payload, 'synthetic-auth');
  assert.equal(provider.config.path, '/private/records.yaml');
});
test('backend failure never falls through or removes Host record access', async () => {
  const Provider = createProvider(Records, async () => { throw Error('untrusted secret error'); });
  const provider = new Provider(ctx, { recordsPath: '/private/records.yaml' });
  await assert.rejects(provider.resolve(MODEL_REF), /^Error: model_credential_bridge_failed$/);
  await assert.rejects(provider.describe(MODEL_REF), /^Error: model_credential_bridge_failed$/);
  provider.modifyRecord('client-connection/browser-session', () => ({ type: 'api-key' }));
  assert.equal(provider.readRecord('client-connection/browser-session').type, 'api-key');
});

test('compatible model reference never overwrites the original reference', async () => {
  const compatible = 'RESEARCH_COMPAT_API_KEY';
  const values = new Map();
  const bridge = async (op, value, ref) => {
    if (op === 'set') values.set(ref, value);
    if (op === 'unset') values.delete(ref);
    return op === 'resolve' ? { value: values.get(ref) ?? null } : op === 'describe' ?
      { configured: values.has(ref), source: 'system-keychain', writable: true } : {};
  };
  const Provider = createProvider(Records, bridge);
  const provider = new Provider(ctx, { recordsPath: '/private/records.yaml' });
  await provider.set(MODEL_REF, 'synthetic-original');
  assert.equal(await provider.resolve(compatible), undefined);
  await provider.set(compatible, 'synthetic-compatible');
  await provider.unset(compatible);
  assert.equal((await provider.resolve(MODEL_REF)).value, 'synthetic-original');
  assert.equal(await provider.resolve(compatible), undefined);
});

test('model references cannot enter the inherited Host record plane', () => {
  const Provider = createProvider(Records, async () => ({}));
  const provider = new Provider(ctx, { recordsPath: '/private/records.yaml' });
  for (const ref of [MODEL_REF, 'RESEARCH_COMPAT_API_KEY']) {
    assert.throws(() => provider.readRecord(ref), /model_credential_record_denied/);
    assert.throws(() => provider.modifyRecord(ref, () => ({ type: 'api-key' })), /model_credential_record_denied/);
  }
  provider.modifyRecord('client-connection/browser-session', () => ({ type: 'api-key' }));
  assert.equal(provider.readRecord('client-connection/browser-session').type, 'api-key');
});
