import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, realpath, rename, symlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { apply } from '../../app/research_web/runtime/research-tools.mjs';

test('Cordis undeclared service getter is never read during research tool registration', () => {
  const tools = new Map();
  let undeclaredReads = 0;
  const target = { tools: { register: tool => tools.set(tool.name, tool) },
    sessions: { get() {} }, logger: { info() {}, warn() {}, error() {} } };
  const ctx = new Proxy(target, { get(object, key, receiver) {
    if (key === 'spawnProcess') {
      undeclaredReads += 1;
      throw new Error('cannot get property spawnProcess without inject');
    }
    return Reflect.get(object, key, receiver);
  } });
  assert.doesNotThrow(() => apply(ctx, { python: '/usr/bin/python3', runnerPath: '/tmp/runner.py', researchRoot: '/tmp/research' }));
  assert.equal(undeclaredReads, 0);
  assert.ok(tools.has('research_run_script'));
});

test('accessor test hooks are not invoked as spawn overrides', () => {
  const tools = new Map();
  const ctx = { tools: { register: tool => tools.set(tool.name, tool) }, logger: {} };
  Object.defineProperty(ctx, 'spawnProcess', { get() { throw new Error('accessor must not execute'); } });
  assert.doesNotThrow(() => apply(ctx, { python: '/usr/bin/python3', runnerPath: '/tmp/runner.py', researchRoot: '/tmp/research' }));
  assert.ok(tools.has('research_run_script'));
});

test('rwb_record_method_use writes only bounded method identity in the current session', async () => {
  const root = await realpath(await mkdtemp(join(tmpdir(), 'rwb-method-')));
  const sid = '01234567-89ab-4cde-8fab-0123456789ab';
  const cwd = join(root, 'sessions', sid);
  await mkdir(cwd, { recursive: true });
  const tools = new Map();
  const ctx = { tools: { register: tool => tools.set(tool.name, tool) }, sessions: { get() {} }, logger: { info() {}, warn() {}, error() {} } };
  apply(ctx, { python: '/usr/bin/python3', runnerPath: '/tmp/runner.py', researchRoot: root });
  const controller = new AbortController();
  const exec = { signal: controller.signal, agent: { session: { header: { id: sid, cwd } } } };
  const result = await tools.get('rwb_record_method_use').execute({ method_id: 'fact-checking', version: '1.0.0', source: 'required' }, exec);
  assert.deepEqual(result, { recorded: true, method_id: 'fact-checking', version: '1.0.0', source: 'required' });
  const rows = (await readFile(join(cwd, '.rwb', 'method-trace.jsonl'), 'utf8')).trim().split('\n').map(JSON.parse);
  assert.deepEqual(rows, [{ method_id: 'fact-checking', version: '1.0.0', source: 'required' }]);
  await assert.rejects(() => tools.get('rwb_record_method_use').execute({ method_id: 'fact-checking', version: '1.0.0', source: 'required', prompt: 'secret' }, exec), /bounded method identity/);
  await rename(join(cwd, '.rwb', 'method-trace.jsonl'), join(cwd, '.rwb', 'retained.jsonl'));
  await symlink(join(cwd, '.rwb', 'retained.jsonl'), join(cwd, '.rwb', 'method-trace.jsonl'));
  await assert.rejects(() => tools.get('rwb_record_method_use').execute({ method_id: 'fact-checking', version: '1.0.0', source: 'required' }, exec));
});
