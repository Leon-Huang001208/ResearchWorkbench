import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir, mkdtemp, writeFile, rm, symlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { apply, readSnapshot } from '../../app/research_web/runtime/plugins.mjs';

test('DSH tool reads only ready, frozen plugin instructions and cannot execute', async () => {
  const root = await mkdtemp(join(tmpdir(), 'rwb-plugin-test-'));
  try {
    await mkdir(join(root, 'plugins/sessions'), { recursive: true, mode: 0o700 });
    const snapshot = { plugins: [{ name: 'fixture', digest: 'a'.repeat(64), components: [{ key: 'reviewer', kind: 'agent', ready: true, support: 'limited', instructions: 'Review supplied evidence.' }, { key: 'blocked', kind: 'agent', ready: false, instructions: 'Never enabled' }] }] };
    await writeFile(join(root, 'plugins/sessions/session1.json'), JSON.stringify(snapshot), { mode: 0o600 });
    const index = { active: { fixture: 'a'.repeat(64) }, versions: { ['a'.repeat(64)]: { state: 'enabled', permissions: ['agents:delegate'], review: { digest: 'a'.repeat(64), permissions: ['agents:delegate'] } } } };
    await writeFile(join(root, 'plugins/index.json'), JSON.stringify(index), { mode: 0o600 });
    const tools = [];
    let delegation;
    apply({ tools: { register(value) { tools.push(value); }, async execute(value) { delegation = value; return {isError: false, value: {kind: 'foreground', output: []}, content: []}; } }, logger: { info() {}, warn() {} } }, { researchRoot: root });
    const tool = tools.find(value => value.name === 'rwb_plugin_instructions');
    const exec = { agent: { session: { header: { id: 'session1' } } } };
    const result = await tool.execute({ plugin: 'fixture', kind: 'agent', component: 'reviewer' }, exec);
    assert.equal(result.instructions, 'Review supplied evidence.');
    assert.equal(result.execution, 'existing_dsh_primitives_only');
    const agentTool = tools.find(value => value.name === 'rwb_plugin_agent');
    const signal = new AbortController().signal;
    const token = {};
    await agentTool.execute({plugin: 'fixture', component: 'reviewer', task: 'Review supplied data'}, {...exec, signal, token, callId: 'outer'});
    assert.equal(delegation.name, 'subagent');
    assert.equal(delegation.parent, token);
    assert.equal(delegation.signal, signal);
    assert.equal(delegation.agent, exec.agent);
    assert.ok(delegation.arguments.prompt.includes('Review supplied evidence.'));
    assert.equal(delegation.arguments.model, undefined);
    index.active.fixture = 'b'.repeat(64);
    index.versions['a'.repeat(64)].state = 'superseded';
    await writeFile(join(root, 'plugins/index.json'), JSON.stringify(index), {mode: 0o600});
    assert.equal((await tool.execute({plugin: 'fixture', kind: 'agent', component: 'reviewer'}, exec)).instructions, 'Review supplied evidence.');
    index.versions['a'.repeat(64)].state = 'disabled';
    await writeFile(join(root, 'plugins/index.json'), JSON.stringify(index), {mode: 0o600});
    await assert.rejects(tool.execute({plugin: 'fixture', kind: 'agent', component: 'reviewer'}, exec));
    await assert.rejects(tool.execute({ plugin: 'fixture', kind: 'agent', component: 'blocked' }, exec));
    assert.throws(() => readSnapshot(root, '../session1'));
    await symlink('session1.json', join(root, 'plugins/sessions/link.json'));
    assert.throws(() => readSnapshot(root, 'link'));
  } finally { await rm(root, { recursive: true }); }
});
