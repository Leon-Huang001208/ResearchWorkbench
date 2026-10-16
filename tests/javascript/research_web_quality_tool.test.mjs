import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, realpath, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { apply } from '../../app/research_web/runtime/research-tools.mjs';
import { apply as applyGuard, RESEARCH_TOOLS } from '../../app/research_web/runtime/guard.mjs';

const sessionId = '01234567-89ab-4cde-8fab-0123456789ab';
const token = 'a'.repeat(43);
const admission = { status: 'available', admitted: true, missing: [], omitted_sections: [] };
const result = (overrides = {}) => ({ status: 'passed', issues: [], repair_count: 0, may_repair: false,
  contract: { requirements: ['Compare revenue'], cutoff: '2026-10-16T00:00:00Z' }, ...overrides });

async function fixture(t, response = result()) {
  const root = await realpath(await mkdtemp(join(tmpdir(), 'rwb-quality-tool-')));
  t.after(() => rm(root, { recursive: true }));
  const cwd = join(root, 'sessions', sessionId);
  await mkdir(cwd, { recursive: true });
  await mkdir(join(root, '.control'), { mode: 0o700 });
  await writeFile(join(root, '.control', 'datahub.json'), JSON.stringify({ url: 'http://127.0.0.1:18088', token }), { mode: 0o600 });
  const events = [{ type: 'turn/start', data: { turn: 1 } }];
  const native = { header: { id: 'native-root', cwd }, snapshotEvents: () => events };
  const child = { header: { id: 'native-child', cwd, parentSession: 'native-root' }, snapshotEvents: () => events };
  const sessions = new Map([['native-root', native], ['native-child', child]]);
  const tools = new Map(); const calls = []; const logs = [];
  const ctx = { tools: { register: tool => tools.set(tool.name, tool) }, sessions: { get: id => sessions.get(id) },
    logger: { info: (...args) => logs.push(args), warn: (...args) => logs.push(args), error: (...args) => logs.push(args) } };
  const originalFetch = globalThis.fetch;
  let responseFactory = () => Response.json(response);
  let admitted = admission;
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options, body: JSON.parse(options.body) });
    return String(url).endsWith('/skill-preflight') ? Response.json(admitted) : responseFactory();
  };
  t.after(() => { globalThis.fetch = originalFetch; });
  apply(ctx, { python: '/python', runnerPath: '/runner', researchRoot: root });
  return { root, cwd, tools, calls, logs, events, native, child, sessions,
    exec: { signal: new AbortController().signal, agent: { session: native } },
    response: value => { responseFactory = typeof value === 'function' ? value : () => Response.json(value); },
    admission: value => { admitted = value; } };
}

test('quality tool uses native admission and authenticated bounded private bridge with immutable workspace scope', async t => {
  const f = await fixture(t); const tool = f.tools.get('research_check_quality');
  assert.ok(tool);
  assert.equal(tool.parameters.additionalProperties, false);
  assert.deepEqual(Object.keys(tool.parameters.properties), ['operation']);
  const value = JSON.parse((await tool.execute({}, f.exec)).result_json);
  assert.deepEqual(value, result());
  assert.deepEqual(f.calls.map(call => call.url), [
    'http://127.0.0.1:18088/api/research/internal/data/skill-preflight',
    'http://127.0.0.1:18088/api/research/internal/data/research-quality',
  ]);
  assert.deepEqual(f.calls[0].body, { session_id: sessionId, tool_name: 'research_check_quality' });
  assert.deepEqual(f.calls[1].body, { session_id: sessionId, operation: 'check' });
  for (const { options } of f.calls) {
    assert.equal(options.method, 'POST');
    assert.equal(options.headers['X-Research-Data-Key'], token);
    assert.equal(options.redirect, 'error'); assert.equal(options.credentials, 'omit');
    assert.ok(options.signal instanceof AbortSignal);
  }
  assert.ok(f.logs.length); assert.doesNotMatch(JSON.stringify(f.logs), new RegExp(token));
});

test('quality tool rejects caller-controlled status, requirements, repair count, session and paths before network', async t => {
  const f = await fixture(t); const tool = f.tools.get('research_check_quality'); assert.ok(tool);
  for (const args of [null, [], { operation: 'repair' }, { passed: true }, { status: 'passed' },
    { requirements: [] }, { repair_count: 0 }, { may_repair: true }, { session_id: sessionId },
    { path: '/etc/passwd' }, { file_id: 'other-session-file' }]) {
    await assert.rejects(() => tool.execute(args, f.exec), /research_quality_arguments_invalid/);
  }
  assert.equal(f.calls.length, 0);
});

test('quality repair instructions are offered once per root native turn, including child calls', async t => {
  const f = await fixture(t, result({ status: 'incomplete', issues: [{ code: 'requirement_missing' }], repair_count: 1, may_repair: true }));
  const tool = f.tools.get('research_check_quality'); assert.ok(tool);
  const childExec = { ...f.exec, agent: { session: f.child } };
  const first = JSON.parse((await tool.execute({ operation: 'check' }, childExec)).result_json);
  assert.match(first.repair_instructions, /same native turn/i);
  assert.match(first.repair_instructions, /once/i);
  assert.match(first.repair_instructions, /requirements/i);
  const replay = JSON.parse((await tool.execute({}, f.exec)).result_json);
  assert.equal(replay.may_repair, true); assert.equal(Object.hasOwn(replay, 'repair_instructions'), false);
  assert.ok(f.calls.every(call => call.body.session_id === sessionId));
  f.events.push({ type: 'turn/start', data: { turn: 2 } });
  f.response(result({ status: 'incomplete', repair_count: 1, may_repair: false }));
  const exhausted = JSON.parse((await tool.execute({}, f.exec)).result_json);
  assert.equal(Object.hasOwn(exhausted, 'repair_instructions'), false);
});

test('concurrent quality checks do not offer duplicate repair instructions', async t => {
  const f = await fixture(t, result({ status: 'incomplete', repair_count: 1, may_repair: true }));
  const tool = f.tools.get('research_check_quality'); assert.ok(tool);
  const values = await Promise.all([tool.execute({}, f.exec), tool.execute({}, { ...f.exec, agent: { session: f.child } })]);
  assert.equal(values.map(value => JSON.parse(value.result_json)).filter(value => Object.hasOwn(value, 'repair_instructions')).length, 1);
});

test('quality tool fails closed for rejected admission and does not invoke checker', async t => {
  const f = await fixture(t); const tool = f.tools.get('research_check_quality'); assert.ok(tool);
  f.admission({ ...admission, status: 'unavailable', admitted: false });
  await assert.rejects(() => tool.execute({}, f.exec), /research_quality_scope_unverified/);
  assert.equal(f.calls.length, 1);
});

test('quality tool rejects missing, cold or foreign native lineage without any bridge request', async t => {
  const f = await fixture(t); const tool = f.tools.get('research_check_quality'); assert.ok(tool);
  await assert.rejects(() => tool.execute({}, { signal: f.exec.signal }), /trusted agent session/);
  await assert.rejects(() => tool.execute({}, { ...f.exec, agent: { session: { header: { id: 'foreign', cwd: '/tmp/other' } } } }), /outside the research root/);
  f.sessions.delete('native-root');
  await assert.rejects(() => tool.execute({}, { ...f.exec, agent: { session: f.child } }), /ancestor workspace/);
  assert.equal(f.calls.length, 0);
});

test('quality bridge cancellation and HTTP failures are propagated with no fallback or additional engine', async t => {
  const f = await fixture(t); const tool = f.tools.get('research_check_quality'); assert.ok(tool);
  const controller = new AbortController(); controller.abort();
  await assert.rejects(() => tool.execute({}, { ...f.exec, signal: controller.signal }));
  assert.equal(f.calls.length, 0);
  f.response(() => Response.json({ error: { code: 'internal_error', message: 'private vendor details' } }, { status: 503 }));
  await assert.rejects(() => tool.execute({}, f.exec), error => /HTTP 503.*internal_error/.test(error.message) && !/private vendor details/.test(error.message));
  assert.equal(f.calls.length, 2);
  f.response(() => Response.json({ error: { code: 'research_quality_check_limit', message: 'private report details' } }, { status: 409 }));
  await assert.rejects(() => tool.execute({}, f.exec), error => /HTTP 409.*research_quality_check_limit/.test(error.message) && !/private report details/.test(error.message));
});

test('quality response cannot silently claim pass for malformed or contradictory checker results', async t => {
  const f = await fixture(t); const tool = f.tools.get('research_check_quality'); assert.ok(tool);
  for (const value of [null, {}, result({ status: 'complete' }), result({ issues: null }), result({ repair_count: 2 }),
    result({ may_repair: 'yes' }), result({ contract: null }), result({ status: 'passed', may_repair: true }),
    result({ status: 'invalid', may_repair: true }), result({ status: 'incomplete', may_repair: true, repair_count: 0 })]) {
    f.response(value);
    await assert.rejects(() => tool.execute({}, f.exec), /research_quality_response_invalid/);
  }
  f.response(() => new Response('unexpected', { headers: { 'Content-Type': 'text/plain' } }));
  await assert.rejects(() => tool.execute({}, f.exec), /response type or size is invalid/);
});

test('quality native tool shares the original 48 call and four child budgets', () => {
  let guard;
  applyGuard({ tools: { guard: fn => { guard = fn; } }, logger: { warn() {} } }, { enabled: true });
  assert.ok(RESEARCH_TOOLS.has('research_check_quality'));
  const agent = { session: { snapshotEvents: () => [{ type: 'turn/start', data: { turn: 1 } }] } };
  for (let index = 0; index < 4; index++) assert.equal(guard({ name: 'subagent', agent }), undefined);
  for (let index = 0; index < 44; index++) assert.equal(guard({ name: 'research_check_quality', agent }), undefined);
  assert.match(guard({ name: 'research_check_quality', agent }), /budget exhausted/i);
  assert.ok(guard({ name: 'research_check_quality_shadow', agent }));
});
