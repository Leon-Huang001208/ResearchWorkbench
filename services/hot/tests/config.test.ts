import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseConfig, schemaName, poolOptions, assertNodeRuntime } from '../src/config.ts';

test('non-secret configuration has bounded defaults and explicit TLS policy', () => {
  const settings = parseConfig({ enabled: false });
  assert.equal(settings.timezone, 'Asia/Shanghai');
  assert.equal(settings.database.mode, 'managed');
  assert.equal(settings.database.tls, 'disable');
  assert.equal(settings.budget.maxCallsPerDay, 0);
  assert.throws(() => parseConfig({ password: 'secret' }), /hot_config_unknown_field/);
  assert.throws(() => parseConfig({ database: { mode: 'external', host: 'db.example', tls: 'disable' } }), /hot_external_tls_required/);
  const external = parseConfig({ database: { mode: 'external', host: 'db.example', tls: 'verify-full' } });
  assert.deepEqual(poolOptions(external.database, 'only-injected-secret').ssl, { rejectUnauthorized: true });
});

test('Hot runtime requires its supported Node family without changing base Web requirements', () => {
  assertNodeRuntime('24.19.0');
  assert.throws(() => assertNodeRuntime('22.19.0'), /hot_node_version_unsupported/);
  assert.throws(() => assertNodeRuntime('25.9.0'), /hot_node_version_unsupported/);
});

test('schema and credentials references reject arbitrary SQL, URLs and paths', () => {
  assert.equal(schemaName('hot_custom_1'), 'hot_custom_1');
  assert.equal(schemaName('h'.repeat(48)).length, 48);
  assert.throws(() => schemaName('h'.repeat(49)));
  for (const value of ['public', 'pg_catalog', 'x;drop schema hot', 'Hot', '../hot', '']) assert.throws(() => schemaName(value));
  assert.throws(() => parseConfig({ database: { secretRef: '/tmp/password' } }));
  assert.throws(() => parseConfig({ database: { host: 'postgres://name:secret@server/db' } }));
  assert.throws(() => parseConfig({ worker: { concurrency: 999 } }));
  assert.throws(() => parseConfig({database:{user:'same',controllerUser:'same'}}),/hot_database_roles_overlap/);
  assert.throws(() => parseConfig({ timezone: 'not-a-timezone' }));
});
