import test from 'node:test';
import {spawnSync} from 'node:child_process';
import {mkdirSync, writeFileSync, existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, realpathSync, rmSync, statSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createAuthOutputSink, writeBootstrapAuth } from '../../app/research_web/runtime/auth-output.mjs';

test('fragmented startup authentication never reaches ordinary output', () => {
  let output = '';
  let captured = false;
  const token = 'x'.repeat(43);
  const sink = createAuthOutputSink(13081, value => { captured = value === token; }, text => { output += text; });
  sink('safe first line\ndsh web: http://127.0.0.1:13081/?to');
  sink(`ken=${token.slice(0, 17)}`);
  sink(`${token.slice(17)}\nsafe final line\n`);
  assert.equal(captured, true);
  assert.equal(output.includes(token), false);
  assert.equal(output.includes('?token='), false);
  assert.ok(output.includes('safe final line'));
});

test('unrecognized authentication output is redacted without capture', () => {
  let output = '';
  const sink = createAuthOutputSink(13081, () => { throw Error('wrong instance'); }, text => { output += text; });
  sink(`dsh web: http://127.0.0.1:3081/?token=${'x'.repeat(43)}\n`);
  assert.equal(output.includes('?token='), false);
});

test('handoff uses private atomic control and refuses file aliases', () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), 'rwb-auth-output-')));
  try {
    const path = join(root, 'auth.json');
    const token = 'x'.repeat(43);
    writeBootstrapAuth(path, { authority: '127.0.0.1:13081' }, token);
    assert.ok(JSON.parse(readFileSync(path, 'utf8')).bootstrap_token === token);
    if (process.platform !== 'win32') assert.equal(statSync(path).mode & 0o777, 0o600);
    const alias = join(root, 'alias.json');
    symlinkSync(path, alias);
    assert.throws(() => writeBootstrapAuth(alias, {}, token), /runtime_auth_handoff_failed/);
  } finally { rmSync(root, { recursive: true, force: true }); }
});

for (const separate of [false, true]) {
  test(`preload binds auth to the explicit state (separate=${separate})`, () => {
    const root = realpathSync(mkdtempSync(join(tmpdir(), 'rwb-auth-preload-')));
    try {
      const home = join(root, 'data/runtime/home');
      const state = separate ? join(root, 'private-state') : join(root, 'data/runtime');
      const source = join(root, 'source');
      const work = join(root, 'data/runtime/work');
      for (const path of [home, state, source, work]) mkdirSync(path, {recursive:true, mode:0o700});
      writeFileSync(join(source, 'package.json'), JSON.stringify({version:'fixture'}));
      const script = join(root, 'fixture.mjs');
      const token = 'x'.repeat(43);
      writeFileSync(script, `process.stdout.write('dsh web: http://127.0.0.1:13081/?token=${token}\\n');`);
      const env = {PATH:process.env.PATH, DSH_HOME:home, RWB_RUNTIME_STATE:state,
        RESEARCH_RUNTIME_AUTH:join(state,'auth.json'), RESEARCH_DSH_SOURCE:source, RESEARCH_RUNTIME_PORT:'13081'};
      const result = spawnSync(process.execPath, ['--import', fileURLToPath(new URL('../../app/research_web/runtime/auth-bootstrap.mjs', import.meta.url)), script], {env,cwd:work,encoding:'utf8',timeout:10000});
      assert.equal(result.status, 0, result.stderr);
      assert.equal(result.stdout.includes(token), false);
      const record = JSON.parse(readFileSync(join(state,'auth.json'),'utf8'));
      assert.equal(record.bootstrap_token, token);
      assert.equal(record.cwd, work);
      assert.equal(record.authority, '127.0.0.1:13081');
      assert.ok(Number.isInteger(record.pid) && record.pid > 0);
      const invalid = spawnSync(process.execPath, ['--import', fileURLToPath(new URL('../../app/research_web/runtime/auth-bootstrap.mjs', import.meta.url)), script], {env:{...env,RESEARCH_RUNTIME_AUTH:join(root,'unexpected.json')},cwd:work,encoding:'utf8',timeout:10000});
      assert.notEqual(invalid.status,0);
      assert.equal(existsSync(join(root,'unexpected.json')),false);
    } finally { rmSync(root,{recursive:true,force:true}); }
  });
}
