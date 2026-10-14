/** Bounded, synthetic-only administrator fixture; emits boolean assertions only. */
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdtemp, chmod, copyFile, writeFile } from 'node:fs/promises';
import { processBridge, MODEL_REF } from '/opt/rwb/app/research_web/runtime/model-credentials.mjs';

const run = promisify(execFile);
const [phase, instance] = process.argv.slice(2);
const config = {
  python: '/opt/rwb/venv/bin/python', bridge: '/opt/rwb/app/research_web/model_credentials.py',
  dataHome: '/run/rwb-secrets', backend: 'docker-encrypted', instance,
  credentialRoot: '/run/rwb-secrets/models', keyRoot: '/run/rwb-model-key',
};
const call = (op, value) => processBridge(config, op, value, MODEL_REF);
try {
  if (['init-a', 'init-b'].includes(phase)) {
    await run(config.python, ['-I', '-B', config.bridge, '--data-home', config.dataHome,
      '--backend', config.backend, '--instance', instance, '--credential-root', config.credentialRoot,
      '--key-root', config.keyRoot, '--initialize'], {env: {PATH: '/usr/bin:/bin', LANG: 'C.UTF-8'}, cwd: '/'});
    assert.equal((await call('describe')).configured, false);
    if (phase === 'init-a') {
      await call('set', 'synthetic-a');
      assert.equal((await call('resolve')).value, 'synthetic-a');
    } else {
      await call('set', 'synthetic-b');
      assert.equal((await call('resolve')).value, 'synthetic-b');
    }
  } else if (phase.startsWith('check-a-')) {
    assert.equal((await call('resolve')).value, 'synthetic-a');
  } else if (phase === 'clear-b') {
    assert.equal((await call('resolve')).value, 'synthetic-b');
    await call('unset');
    assert.equal((await call('resolve')).value, null);
  } else if (phase === 'negative') {
    // A ciphertext with B identity/key at exactly the ordinary internal paths.
    await assert.rejects(call('resolve'), /model_credential_bridge_failed/);
    // Retain A identity but substitute B's random master key: actual AEAD rejection.
    const keys = await mkdtemp('/tmp/model-probe-');
    await chmod(keys, 0o700);
    await copyFile(config.keyRoot + '/master.key', keys + '/master.key');
    await chmod(keys + '/master.key', 0o600);
    await writeFile(keys + '/identity.json', JSON.stringify({version: 1, instance}), {mode: 0o600});
    await assert.rejects(processBridge({...config, keyRoot: keys}, 'resolve', undefined, MODEL_REF), /model_credential_bridge_failed/);
  } else throw Error('probe_phase_invalid');
  process.stdout.write(JSON.stringify({phase, assertions_passed: true}) + '\n');
} catch {
  process.stderr.write('credential_probe_failed\n');
  process.exitCode = 1;
}
