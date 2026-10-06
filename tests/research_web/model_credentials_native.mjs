/** Native synthetic acceptance helper. No supplier transport is invoked. */
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
import { readFile } from 'node:fs/promises';

const [source, dataHome, phase, port] = process.argv.slice(2);
const pinned = async path => import(pathToFileURL(`${source}/${path}`).href);
const { runProfile } = await pinned('apps/cli/lib/profile-boot-CMEGRIuU.js');
const { loadLayeredEnv } = await pinned('packages/boot/app-boot/lib/index.js');
const { credentialKey } = await pinned('packages/credentials/credentials/lib/index.js');
const ref = 'RESEARCH_DSH_API_KEY';
let stage = 'boot';
process.on('uncaughtException', error => {
  process.stdout.write(`\nC1_DIAG:${JSON.stringify({ stage, type: ['Error', 'TypeError', 'AssertionError'].includes(error?.name) ? error.name : 'Error' })}\n`);
  process.exit(1);
});
const { ctx } = await runProfile({
  environment: loadLayeredEnv('dsh'), profile: 'web',
  patchFiles: [`${dataHome}/runtime/overlay.yml`],
  args: ['--host', '127.0.0.1', '--port', port, '--no-open'],
});
try {
  stage = 'credentials';
  const credentials = ctx.get('credentials');
  assert.ok(credentials);
  const key = credentialKey('client-connection', 'browser-session');
  assert.ok(await credentials.readRecord(key));
  stage = 'preset';
  const preset = await ctx.get('agentPresets').resolve('research-web');
  assert.equal(preset.id, 'research-web');
  const sessionId = `session-c1-${phase}`;
  await ctx.get('sessionController').create({ sessionId, cwd: process.cwd(), agentPreset: 'research-web' });
  assert.equal(ctx.get('sessions').get(sessionId).header.agentPreset, 'research-web');
  stage = 'consumer';
  const adapter = ctx.get('llm').adapters.get('deepseek-official').adapter;
  const resolve = () => adapter.config.resolveApiKey({ apiKeyEnv: ref });
  const absent = async () => {
    let rejected = false;
    try { await resolve(); } catch (error) { rejected = error.code === 'MISSING_CREDENTIAL'; }
    assert.equal(rejected, true);
    assert.ok(await credentials.readRecord(key));
    await credentials.modifyRecord(key, record => record);
  };
  if (phase === 'backend-unavailable') {
    let rejected = false;
    try { await resolve(); } catch (error) { rejected = error.message === 'model_credential_bridge_failed'; }
    assert.equal(rejected, true);
    assert.ok(ctx.get('credentials'));
    assert.ok(await credentials.readRecord(key));
    await credentials.modifyRecord(key, record => record);
  } else if (phase === 'empty') {
    await absent();
    await credentials.set(ref, 'synthetic-runtime-first');
    assert.ok((await resolve()) === 'synthetic-runtime-first');
  } else if (phase === 'restart-with-key') {
    assert.ok((await resolve()) === 'synthetic-runtime-first');
    await credentials.set(ref, 'synthetic-runtime-second');
    assert.ok((await resolve()) === 'synthetic-runtime-second');
    await credentials.unset(ref);
    await absent();
  } else if (phase === 'restart-cleared') {
    await absent();
  } else { throw Error('invalid phase'); }
  const recordFile = await readFile(`${dataHome}/runtime/home/.browser-credentials.yaml`, 'utf8');
  assert.equal(recordFile.includes(ref), false);
  assert.equal(recordFile.includes('synthetic-runtime-'), false);
  process.stdout.write(`\nC1_RESULT:${JSON.stringify({ phase, preset: true, consumer: true, hostRecords: true, noModelFile: true })}\n`);
} finally { await ctx.fiber.dispose(); }
