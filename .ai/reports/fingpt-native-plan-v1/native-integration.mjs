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
assert.equal(execFileSync('git', ['-C', source, 'status', '--porcelain'], { encoding: 'utf8' }).trim(), '');
await mkdir(root, { recursive: true, mode: 0o700 });
process.env.DSH_HOME = join(root, 'home');
await mkdir(process.env.DSH_HOME, { recursive: true, mode: 0o700 });
const require = createRequire(join(source, 'apps/cli/package.json'));
const load = name => import(pathToFileURL(require.resolve(name)).href);
const { Context } = await load('@deepseek-ai/cordis');
const { mountAgentLoopTestDependencies } = await load('@deepseek-ai/dsh-agent-loop-testkit');
const { default: AgentLoop } = await load('@deepseek-ai/dsh-agent-loop');
const { default: Jsonl } = await load('@deepseek-ai/dsh-session-persistence-jsonl');
const { SessionId } = await load('@deepseek-ai/dsh-session');
const { ToolCallId } = await load('@deepseek-ai/dsh-llm');
const { default: Loader } = await load('@deepseek-ai/cordis-plugin-loader');
const { default: Include } = await load('@deepseek-ai/cordis-plugin-include');
const Todo = await load('@deepseek-ai/dsh-tool-todo');
assert.deepEqual(Todo.inject, ['tools', 'sessionProjections']);
const preset = await readFile(join(project, 'app/research_web/runtime/research.cordis.yml'), 'utf8');
const todoYml = preset.match(/^- id: tool-todo\n[\s\S]*?(?=^- id:|(?![\s\S]))/m)?.[0];
assert.ok(todoYml?.includes('allowParallelInProgress: true'));
const configPath = join(root, 'todo.cordis.yml');
await writeFile(configPath, todoYml, { mode: 0o600 });
const ctx = new Context();
try {
  await mountAgentLoopTestDependencies(ctx);
  await ctx.plugin(Jsonl, { root: join(root, 'dataHome'), compression: 'none' });
  await ctx.plugin(AgentLoop, { agents: [] });
  ctx.baseUrl = pathToFileURL(root).href + '/';
  await ctx.plugin(Loader);
  ctx.loader.builtins.include = Include;
  ctx.loader.internal = { version: 'v2', async import(name) {
    assert.equal(name, '@deepseek-ai/dsh-tool-todo');
    return Todo;
  } };
  await ctx.loader.create({ name: 'cordis:include', config: { path: pathToFileURL(configPath).href } });
  await ctx.loader.await();
  for (const entry of ctx.loader.entries()) await entry.fiber?.await();
  assert.ok(ctx.tools.schemas().some(tool => tool.name === 'todo_write'));
  await ctx.plugin(Guard, { enabled: true });
  const agent = await ctx.agentLoop.create(SessionId('native-plan-isolated'), {});
  agent.session.append('turn/start', { turn: 1 });
  const todos = [{ content: 'Read evidence', status: 'in_progress' },
    { content: 'Check state', status: 'in_progress' }];
  const execute = args => ctx.tools.execute({ name: 'todo_write', arguments: { todos: args },
    callId: ToolCallId(`todo-${agent.session.seq}`), agent, signal: new AbortController().signal });
  assert.equal((await execute(todos)).isError, false);
  assert.deepEqual((await ctx.sessionProjections.snapshot(agent.session)).values.todos, todos);
  const completed = [{ content: 'Check state', status: 'completed' }];
  assert.equal((await execute(completed)).isError, false);
  assert.deepEqual((await ctx.sessionProjections.snapshot(agent.session)).values.todos, completed);
  const forbidden = await ctx.tools.execute({ name: 'bash', arguments: {}, callId: ToolCallId('denied'),
    agent, signal: new AbortController().signal });
  assert.equal(forbidden.isError, true);
  assert.equal(await ctx.sessions.flush(agent.session), true);
  const handle = await ctx.sessionPersistence.open(agent.id, 'read');
  const stored = await handle.read();
  await handle.close();
  assert.equal(stored.events.filter(event => event.type === 'todo/write').length, 2);
  assert.deepEqual(stored.events.findLast(event => event.type === 'todo/write').data.todos, completed);
  const bytes = JSON.stringify(stored.events.map(event => ({ event })), null, 2);
  await writeFile(join(root, 'native-events.json'), bytes, { mode: 0o600 });
  agent.session.append('turn/start', { turn: 2 });
  assert.equal((await ctx.sessionProjections.snapshot(agent.session)).values.todos, null);
  await ctx.sessions.flush(agent.session);
  await writeFile(join(root, 'receipt.json'), JSON.stringify({ status: 'PASS', pin,
    modelCalls: 0, productionRuntimeTouched: false, transport: 'in-process real native registries',
    todoWrites: 2, durableRead: true, nextTurnCleared: true,
    eventsSHA256: createHash('sha256').update(bytes).digest('hex') }, null, 2), { mode: 0o600 });
  console.log('PASS: real todo tool, loader injection, guard, durable native log and next-turn reset; model calls=0');
} catch (error) {
  console.error('native integration failed:', error.code || error.name, error.message);
  process.exitCode = 1;
} finally {
  await ctx.fiber.dispose();
}
