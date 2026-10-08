import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createProvider, processBridge, MODEL_REF } from '../../app/research_web/runtime/model-credentials.mjs';

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
test('Docker model source is launcher-bound and Host records survive unavailable binding', async () => {
  const Provider = createProvider(Records, async op => op === 'resolve' ? { value: 'synthetic' } :
    { configured: true, source: 'docker-private-file', writable: true }, 'docker-private-file');
  const provider = new Provider(ctx, { recordsPath: '/private/records.yaml' });
  assert.deepEqual(await provider.resolve(MODEL_REF), { value: 'synthetic', source: 'docker-private-file' });
  assert.equal((await provider.describe(MODEL_REF)).source, 'docker-private-file');
  const Wrong = createProvider(Records, async () => ({ configured: true, source: 'system-keychain', writable: true }), 'docker-private-file');
  await assert.rejects(new Wrong(ctx, {}).describe(MODEL_REF), /model_credential_bridge_failed/);
  const Unknown = createProvider(Records, async () => ({ value: 'synthetic' }), 'unknown');
  const unavailable = new Unknown(ctx, {});
  await assert.rejects(unavailable.resolve(MODEL_REF), /model_credential_bridge_failed/);
  unavailable.modifyRecord('browser', () => ({ type: 'api-key' }));
  assert.equal(unavailable.readRecord('browser').type, 'api-key');
});
test('private process bridge rejects incomplete or noncanonical selectors before spawn', async () => {
  for (const config of [
    { source: 'unknown' }, { source: null }, { source: 'docker-private-file' },
    { source: 'docker-private-file', installationId: 'A'.repeat(32), credentialRoot: '/tmp/models' },
    { source: 'system-keychain', installationId: 'a'.repeat(32) },
  ]) await assert.rejects(processBridge({ python: '/definitely/missing', ...config }, 'resolve'), /model_credential_bridge_failed/);
});
test('Docker selection without installation binding rejects every model operation but keeps Host records', async () => {
  const config = { source: 'docker-private-file', recordsPath: '/private/records.yaml', python: '/definitely/missing' };
  const Provider = createProvider(Records, (op, value) => processBridge(config, op, value), config.source);
  const provider = new Provider(ctx, config);
  provider.modifyRecord('client-connection/browser-session', () => ({ type: 'api-key', payload: 'synthetic-browser' }));
  for (const operation of ['resolve', 'describe', 'unset']) {
    await assert.rejects(provider[operation](MODEL_REF), /^Error: model_credential_bridge_failed$/);
  }
  await assert.rejects(provider.set(MODEL_REF, 'synthetic-model'), /^Error: model_credential_bridge_failed$/);
  assert.equal(provider.readRecord('client-connection/browser-session').payload, 'synthetic-browser');
});
test('private bridge uses isolated Python and passes only selector argv and private stdin', async () => {
  const python = spawnSync('python3', ['-c', 'import sys; print(sys.executable)'], { encoding: 'utf8' }).stdout.trim();
  assert.ok(python);
  const temporary = mkdtempSync(join(tmpdir(), 'rwb-model-bridge-'));
  const bridge = join(temporary, 'fixture.py');
  writeFileSync(bridge, `import json,os,sys
request=json.load(sys.stdin)
assert sys.flags.isolated == 1 and sys.dont_write_bytecode
assert set(os.environ) <= {'PATH','LANG','LC_CTYPE','__CF_USER_TEXT_ENCODING'}
assert os.environ['PATH'] == '/usr/bin:/bin'
assert request == {'op':'set','ref':'RESEARCH_DSH_API_KEY','value':'synthetic-private-canary'}
assert 'synthetic-private-canary' not in ' '.join(sys.argv)
assert sys.argv[1:] == ['--data-home','/data/research-web','--backend','docker-private-file','--credential-root','/run/rwb-secrets/private/models/'+'a'*32,'--installation-id','a'*32]
sys.stderr.write('discarded diagnostic synthetic-private-canary')
print(json.dumps({'ok':True}))
`);
  const previous = { api: process.env.RESEARCH_DSH_API_KEY, path: process.env.PYTHONPATH };
  try {
    process.env.RESEARCH_DSH_API_KEY = 'synthetic-inherited-denied';
    process.env.PYTHONPATH = temporary;
    assert.deepEqual(await processBridge({ python, bridge, dataHome: '/data/research-web', source: 'docker-private-file',
      installationId: 'a'.repeat(32), credentialRoot: '/run/rwb-secrets/private/models/' + 'a'.repeat(32) }, 'set', 'synthetic-private-canary'), { ok: true });
  } finally {
    for (const [key, value] of [['RESEARCH_DSH_API_KEY', previous.api], ['PYTHONPATH', previous.path]]) {
      if (value === undefined) delete process.env[key]; else process.env[key] = value;
    }
    rmSync(temporary, { recursive: true });
  }
});
test('commit uncertainty survives the provider boundary without exposing backend text', async () => {
  const Provider = createProvider(Records, async () => { throw Error('model_credential_commit_uncertain'); }, 'docker-private-file');
  await assert.rejects(new Provider(ctx, {}).set(MODEL_REF, 'synthetic'), /^Error: model_credential_commit_uncertain$/);
});
test('private Python commit uncertainty stays fixed and only Docker may report it', async () => {
  const python = spawnSync('python3', ['-c', 'import sys; print(sys.executable)'], { encoding: 'utf8' }).stdout.trim();
  const temporary = mkdtempSync(join(tmpdir(), 'rwb-model-uncertain-'));
  const bridge = join(temporary, 'fixture.py');
  writeFileSync(bridge, `import json,sys
json.load(sys.stdin)
print(json.dumps({'ok':False,'error':'model_credential_commit_uncertain'}))
sys.exit(1)
`);
  try {
    const native = { python, bridge, dataHome: '/data/research-web' };
    const docker = { ...native, source: 'docker-private-file', installationId: 'a'.repeat(32),
      credentialRoot: '/run/rwb-secrets/private/models/' + 'a'.repeat(32) };
    await assert.rejects(processBridge(docker, 'set', 'synthetic'), /^Error: model_credential_commit_uncertain$/);
    await assert.rejects(processBridge(native, 'set', 'synthetic'), /^Error: model_credential_bridge_failed$/);
  } finally { rmSync(temporary, { recursive: true }); }
});
test('resolve cannot contradict the launcher source with a bridge response', async () => {
  const Provider = createProvider(Records, async () => ({ value: 'synthetic', source: 'system-keychain' }), 'docker-private-file');
  await assert.rejects(new Provider(ctx, {}).resolve(MODEL_REF), /model_credential_bridge_failed/);
});
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
