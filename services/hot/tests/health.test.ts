import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseConfig } from '../src/config.ts';
import { checkDatabase } from '../src/health.ts';

test('disabled Hot performs no credential lookup or database operation', async () => {
  const result = await checkDatabase(parseConfig({ enabled: false }), async () => { throw Error('must not resolve'); });
  assert.equal(result.state, 'disabled');
});
test('unconfigured Hot reports the missing credential without opening a pool', async () => {
  const result = await checkDatabase(parseConfig({ enabled: true }), async () => null);
  assert.equal(result.state, 'unconfigured');
  assert.equal(result.code, 'hot_database_secret_missing');
});
