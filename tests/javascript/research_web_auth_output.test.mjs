import test from 'node:test';
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
