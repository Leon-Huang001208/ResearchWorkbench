import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import * as Guard from '../../../app/research_web/runtime/guard.mjs';

const source = resolve(process.argv[2]);
const root = resolve(process.argv[3]);
const project = resolve(new URL('../../../', import.meta.url).pathname);
const pin = JSON.parse(await readFile(join(project, 'runtimes/research_web.json'))).dsh.commit;
assert.equal(execFileSync('git', ['-C', source, 'rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(), pin);
await mkdir(root, { recursive: true, mode: 0o700 });
process.env.DSH_HOME = join(root, 'home');
await mkdir(process.env.DSH_HOME, { recursive: true, mode: 0o700 });
const require = createRequire(join(source, 'apps/cli/package.json'));
const bootRequire = createRequire(join(source, 'packages/boot/app-boot/package.json'));
const presetRequire = createRequire(join(source, 'packages/preset/agent-preset/package.json'));
const load = name => import(pathToFileURL(require.resolve(name)).href);
const { Context } = await load('@deepseek-ai/cordis');
const { mountAgentLoopTestDependencies } = await load('@deepseek-ai/dsh-agent-loop-testkit');
const { default: AgentLoop } = await load('@deepseek-ai/dsh-agent-loop');
const { default: Jsonl } = await load('@deepseek-ai/dsh-session-persistence-jsonl');
const { SessionId } = await load('@deepseek-ai/dsh-session');
const { ToolCallId } = await load('@deepseek-ai/dsh-llm');
const { default: Loader } = await load('@deepseek-ai/cordis-plugin-loader');
const { default: Group } = await import(pathToFileURL(bootRequire.resolve('@deepseek-ai/cordis-plugin-group')).href);
const { default: Presets } = await import(pathToFileURL(presetRequire.resolve('@deepseek-ai/dsh-agent-preset-registry')).href);
const yaml = require('js-yaml');
const preset = await readFile(join(project, 'app/research_web/runtime/research.cordis.yml'), 'utf8');
const todoYml = preset.match(/^- id: tool-todo\n[\s\S]*?(?=^- id:|(?![\s\S]))/m)?.[0];
const plugins = yaml.load(todoYml);
assert.equal(plugins[0].config.allowParallelInProgress, true);
const basePackage = JSON.parse(await readFile(join(source, 'packages/bundle/base/package.json')));
assert.ok(basePackage.dependencies['@deepseek-ai/dsh-tool-todo']);
assert.ok(basePackage.dependencies['@deepseek-ai/dsh-session-projection']);
const ctx = new Context();
try {
  await mountAgentLoopTestDependencies(ctx);
  await ctx.plugin(Loader);
  ctx.loader.builtins.group = Group;
  ctx.loader.internal = { version: 'v2', import: load };
  ctx.baseUrl = pathToFileURL(root).href + '/';
  await ctx.plugin(Jsonl, { root: join(root, 'dataHome'), compression: 'none' });
  await ctx.plugin(AgentLoop, { agents: [] });
  await ctx.plugin(Presets, { default: 'research-web' });
  await ctx.loader.create({ name: '@deepseek-ai/dsh-agent-preset', config: { id: 'research-web', plugins } });
  await ctx.loader.create({ name: '@deepseek-ai/dsh-agent-preset', config: { id: 'no-plan', plugins: [] } });
  await ctx.loader.await();
  for (const entry of ctx.loader.entries()) await entry.fiber?.await();
  await ctx.plugin(Guard, { enabled: true });
  const make = async (id, presetId) => (await ctx.agents.create({ sessionId: SessionId(id),
    setup: async agentCtx => { await ctx.agentPresets.mount(agentCtx, presetId); } })).agent;
  const first = await make('preset-first', 'research-web');
  const second = await make('preset-second', 'research-web');
  const none = await make('preset-no-plan', 'no-plan');
  assert.equal(ctx.tools.schemas().some(tool => tool.name === 'todo_write'), false);
  for (const agent of [first, second]) {
    assert.ok(ctx.tools.schemas(agent).some(tool => tool.name === 'todo_write'));
    assert.deepEqual(ctx.agentPresets.inspectCompositions(agent.ctx).map(row => row.id), ['research-web']);
    agent.session.append('turn/start', { turn: 1 });
  }
  assert.equal(ctx.tools.schemas(none).some(tool => tool.name === 'todo_write'), false);
  const execute = (agent, todos) => ctx.tools.execute({ name: 'todo_write', arguments: { todos },
    agent, callId: ToolCallId(`${agent.id}-${agent.session.seq}`), signal: new AbortController().signal });
  const list = [{ content: 'Read evidence', status: 'in_progress' }, { content: 'Check plan', status: 'in_progress' }];
  assert.equal((await execute(first, list)).isError, false);
  assert.equal((await execute(second, [{ content: 'Other session', status: 'completed' }])).isError, false);
  assert.deepEqual((await ctx.sessionProjections.snapshot(first.session)).values.todos, list);
  assert.deepEqual((await ctx.sessionProjections.snapshot(second.session)).values.todos, [{ content: 'Other session', status: 'completed' }]);
  first.session.append('turn/end', { turn: 1, reason: { kind: 'completed' } });
  first.session.append('turn/start', { turn: 2 });
  assert.equal((await ctx.sessionProjections.snapshot(first.session)).values.todos, null);
  assert.deepEqual((await ctx.sessionProjections.snapshot(second.session)).values.todos, [{ content: 'Other session', status: 'completed' }]);
  const native = {};
  for (const agent of [first, second]) {
    assert.equal(await ctx.sessions.flush(agent.session), true);
    const handle = await ctx.sessionPersistence.open(agent.id, 'read');
    native[agent.id] = (await handle.read()).events;
    await handle.close();
    assert.equal(native[agent.id].filter(event => event.type === 'todo/write').length, 1);
  }
  const bytes = JSON.stringify(native, null, 2);
  await writeFile(join(root, 'native-events.json'), bytes, { mode: 0o600 });
  await writeFile(join(root, 'receipt.json'), JSON.stringify({ status: 'PASS', pin, modelCalls: 0,
    scope: 'real agent-preset registry mounts the production Todo YAML row; other research plugins are outside this focused probe',
    baseBundleIncludesRequiredPackages: true, scopeOnlyToolRegistration: true,
    twoSessionsIsolated: true, nextTurnCleared: true, durableTodoWrites: 2,
    sourceModuleSHA256: createHash('sha256').update(await readFile(join(source, 'packages/todo/tool-todo/src/index.ts'))).digest('hex'),
    loadedModuleSHA256: createHash('sha256').update(await readFile(require.resolve('@deepseek-ai/dsh-tool-todo'))).digest('hex'),
    eventsSHA256: createHash('sha256').update(bytes).digest('hex') }, null, 2), { mode: 0o600 });
  console.log('PASS actual preset-scoped Todo: two sessions, no-plan scope, durable writes, next-turn isolation; model calls=0');
} catch (error) {
  console.error('preset integration failed:', error.code || error.name, error.message);
  process.exitCode = 1;
} finally {
  await ctx.fiber.dispose();
}
