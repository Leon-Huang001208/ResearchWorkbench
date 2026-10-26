/** Optional offline contract against the locally built, exact pinned DSH. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { join, basename } from 'node:path';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { apply as applyPlugins } from '../../app/research_web/runtime/plugins.mjs';
import { apply as applyMCP } from '../../app/research_web/runtime/mcp-adapter.mjs';

const source = process.env.RWB_DSH_TEST_SOURCE;

test('exact pinned ToolRuntime accepts output contracts and owns nested Agent delegation', {skip: !source}, async () => {
  assert.equal(basename(source), '7ecf564f2e09b829240c5553687223bdd1e2df73');
  const require = createRequire(join(source, 'packages/core/tools/package.json'));
  const { Context } = await import(pathToFileURL(require.resolve('@deepseek-ai/cordis')));
  const { default: SystemPrompt } = await import(pathToFileURL(require.resolve('@deepseek-ai/dsh-system-prompt')));
  const { default: ToolRuntime } = await import(pathToFileURL(join(source, 'packages/core/tools/lib/index.js')));
  const ctx = new Context();
  const root = await mkdtemp(join(tmpdir(), 'rwb-plugin-native-'));
  try {
    await ctx.plugin(SystemPrompt);
    await ctx.plugin(ToolRuntime);
    await mkdir(join(root, 'plugins/sessions'), {recursive: true, mode: 0o700});
    await mkdir(join(root, '.control'), {mode: 0o700});
    await writeFile(join(root, '.control/mcp-runtime.json'), JSON.stringify({url: 'http://127.0.0.1:8088', token: 'a'.repeat(43)}), {mode: 0o600});
    const digest = 'a'.repeat(64);
    await writeFile(join(root, 'plugins/index.json'), JSON.stringify({active: {fixture: digest}, versions: {[digest]: {state: 'enabled', permissions: ['agents:delegate'], review: {digest, permissions: ['agents:delegate']}}}}), {mode: 0o600});
    await writeFile(join(root, 'plugins/sessions/session1.json'), JSON.stringify({plugins: [{name: 'fixture', digest, components: [{kind: 'agent', key: 'reviewer', support: 'limited', ready: true, instructions: 'Review only supplied evidence.'}]}]}), {mode: 0o600});
    const adapter = {tools: ctx.tools, logger: {info() {}, warn() {}}};
    applyPlugins(adapter, {researchRoot: root});
    applyMCP(adapter, {researchRoot: root, bindings: [{name: 'mcp__mcp-installation-0123456789abcdef0123456789abcdef__read', installation_id: 'mcp-installation-0123456789abcdef0123456789abcdef', version: '1.2.3', tool_name: 'read', schema_sha256: 'b'.repeat(64), description: 'Read fixture', input_schema: {type: 'object', properties: {}, additionalProperties: false}}]});
    assert.ok(ctx.tools.get('rwb_plugin_instructions').output.schema);
    assert.ok(ctx.tools.get('mcp__mcp-installation-0123456789abcdef0123456789abcdef__read').output.schema);
    let delegated;
    ctx.tools.register({name: 'subagent', description: 'Offline native primitive fixture', parameters: {type: 'object'}, output: {schema: {type: 'string'}, render(_args, value) {return [{type: 'text', text: value}];}}, async execute(args, exec) {delegated = {args, exec}; return 'offline delegation';}});
    const result = await ctx.tools.execute({name: 'rwb_plugin_agent', callId: 'plugin-call', arguments: {plugin: 'fixture', component: 'reviewer', task: 'Inspect supplied fixture'}, agent: {ctx, session: {header: {id: 'session1'}}}, signal: new AbortController().signal});
    assert.equal(result.isError, false, JSON.stringify(result));
    assert.ok(delegated.args.prompt.includes('Review only supplied evidence.'));
    assert.equal(delegated.exec.rootCallId, 'plugin-call');
    assert.ok(delegated.exec.parent);
  } finally {
    await ctx.fiber.dispose();
    await rm(root, {recursive: true});
  }
});
