import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, realpath, rm, writeFile, symlink, link, truncate } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHash } from 'node:crypto';

import { apply } from '../../app/research_web/runtime/research-tools.mjs';
import { apply as applyGuard, RESEARCH_TOOLS } from '../../app/research_web/runtime/guard.mjs';

const sessionId = '01234567-89ab-4cde-8fab-0123456789ab';
const token = 'a'.repeat(43);
const admission = { status: 'available', admitted: true, missing: [], omitted_sections: [] };
const result = (overrides = {}) => ({ status: 'passed', issues: [], repair_count: 0, may_repair: false,
  contract: { requirements: ['Compare revenue'], cutoff: '2026-10-16T00:00:00Z' }, ...overrides });

test('weekly script scopes reject missing policy, escape paths, aliases and non-files before spawning', async t => {
  const f = await fixture(t);
  const base = join(f.cwd, 'inputs/report-workflow');
  await mkdir(base, { recursive: true });
  await writeFile(join(base, 'run-context.json'), '{}');
  await writeFile(join(base, 'oversize.json'), '');
  await truncate(join(base, 'oversize.json'), 32 * 1024 * 1024 + 1);
  await symlink(join(base, 'run-context.json'), join(base, 'symlink.json'));
  await link(join(base, 'run-context.json'), join(base, 'hardlink.json'));
  const tool = f.tools.get('research_run_script');
  for (const input_policy of [undefined, 'unknown-policy']) {
    f.admission({ ...admission, read_paths: ['inputs/report-workflow/run-context.json'], ...(input_policy === undefined ? {} : {input_policy}) });
    await assert.rejects(() => tool.execute({code:'print("never")'}, f.exec), /research_script_scope_unverified/);
  }
  for (const path of ['/outside', 'inputs/report-workflow/../outside', 'inputs/report-workflow/./run-context.json',
    'inputs/report-workflow//run-context.json', 'inputs/report-workflow/hidden\\file',
    'inputs/report-workflow', 'inputs/report-workflow/symlink.json', 'inputs/report-workflow/hardlink.json',
    'inputs/report-workflow/oversize.json', 'inputs/report-workflow/run-context.json']) {
    f.admission({ ...admission, input_policy:'weekly-frozen-inputs-v1', read_paths:[path] });
    await assert.rejects(() => tool.execute({code:'print("never")'}, f.exec), /research_script_scope_unverified/);
  }
  // Model parameters cannot supply or override the Host policy.
  await assert.rejects(() => tool.execute({code:'print("never")',input_policy:'weekly-frozen-inputs-v1'}, f.exec), /bounded code/);
});

test('dossier handles preserve Host canonical identities and forward exact bounded admission arguments', async t => {
  const handle = `dossier:${'a'.repeat(32)}:${'b'.repeat(32)}:2`;
  const id = 'file:' + createHash('sha256').update(handle).digest('hex').slice(0,24);
  const f = await fixture(t, {source:{id,dossier_handle:handle,sha256:'c'.repeat(64)},observation_id:id,content:'frozen original'});
  const tool = f.tools.get('research_read_source');
  const value = JSON.parse((await tool.execute({operation:'read',source_id:handle}, f.exec)).result_json);
  assert.equal(value.source.id,id);
  const preflight = f.calls.find(call => call.url.endsWith('/skill-preflight'));
  assert.equal(preflight.body.source_id,handle);
  assert.equal(preflight.body.source_operation,'read');
  f.response({source:{id:'file:'+'d'.repeat(24),dossier_handle:handle,sha256:'c'.repeat(64)},observation_id:id,content:'frozen original'});
  await assert.rejects(() => tool.execute({operation:'read',source_id:handle}, f.exec), /research_source_response_invalid/);
  await assert.rejects(() => tool.execute({operation:'read',source_id:handle,owner:'other'}, f.exec), /research_source_arguments_invalid/);
});

test('source reader is guarded, session-bound and cannot accept arbitrary URLs or caller content', async t => {
  const f = await fixture(t, { sources: [] });
  const tool = f.tools.get('research_read_source');
  assert.ok(tool); assert.ok(RESEARCH_TOOLS.has(tool.name));
  for (const args of [{ operation: 'read', url: 'https://example.org' },
    { operation: 'read', source_id: 'web:other' }, { operation: 'list', session_id: sessionId },
    { operation: 'list', source_id: 'web:' + 'a'.repeat(24) },
    { operation: 'read', source_id: 'web:' + 'a'.repeat(24), content: 'fabricated' }]) {
    await assert.rejects(() => tool.execute(args, f.exec), /research_source_arguments_invalid/);
  }
  assert.equal(f.calls.length, 0);
  await tool.execute({ operation: 'list' }, f.exec);
  const request = f.calls.find(c => c.url.endsWith('/research-source'));
  assert.deepEqual(request.body, { session_id: sessionId, call_id: 'native-root:source-call', operation: 'list', search_activities: [] });
  assert.equal(request.options.headers['X-Research-Data-Key'], token);
  assert.equal(request.options.redirect, 'error');
  assert.equal(request.options.credentials, 'omit');
});

test('source reader validates actual body provenance and respects admission and cancellation', async t => {
  const id = 'web:' + 'a'.repeat(24);
  const f = await fixture(t, { source: { id, sha256: 'b'.repeat(64) }, observation_id: id, content: 'actual body' });
  const tool = f.tools.get('research_read_source');
  const value = JSON.parse((await tool.execute({ operation: 'read', source_id: id }, f.exec)).result_json);
  assert.equal(value.content, 'actual body');
  f.response({ source: { id: 'web:foreign', sha256: 'b'.repeat(64) }, observation_id: id, content: 'actual' });
  await assert.rejects(() => tool.execute({ operation: 'read', source_id: id }, f.exec), /research_source_response_invalid/);
  f.admission({ ...admission, status: 'unavailable', admitted: false });
  const count = f.calls.filter(c => c.url.endsWith('/research-source')).length;
  await assert.rejects(() => tool.execute({ operation: 'list' }, f.exec), /research_source_scope_denied/);
  assert.equal(f.calls.filter(c => c.url.endsWith('/research-source')).length, count);
  const signal = AbortSignal.abort(Error('cancelled'));
  await assert.rejects(() => tool.execute({ operation: 'list' }, { ...f.exec, signal }), /cancelled/);
});

test('source reader forwards cancellation after the Host request has started', async t => {
  const f = await fixture(t, { sources: [] });
  const original = globalThis.fetch;
  let began; const started = new Promise(resolve => { began = resolve; });
  globalThis.fetch = async (url, options) => {
    if (String(url).endsWith('/research-source')) {
      began();
      return new Promise((_resolve, reject) => options.signal.addEventListener('abort', () => reject(options.signal.reason), { once: true }));
    }
    return original(url, options);
  };
  const controller = new AbortController();
  const pending = f.tools.get('research_read_source').execute({ operation: 'list' }, { ...f.exec, signal: controller.signal });
  await started; controller.abort(Error('user stopped'));
  await assert.rejects(() => pending, /user stopped/);
  const cancels = f.calls.filter(c => c.url.endsWith('/research-source/cancel'));
  assert.equal(cancels.length, 1);
  assert.deepEqual(cancels[0].body, { session_id: sessionId, call_id: 'native-root:source-call' });
  assert.equal(cancels[0].options.signal.aborted, false);
});

test('source identities come from completed native tool events, never caller or assistant text', async t => {
  const f = await fixture(t, { sources: [] });
  const detail = 'External web content follows.\n\nSources:\n- [Exact title](https://example.org/report#1)';
  f.events.push({ type: 'tool/call', data: { callId: 'search-real', name: 'web_search' } },
    { type: 'tool/result', data: { message: { role: 'tool', source: { callId: 'search-real' }, content: [{ type: 'text', text: detail }] } } },
    { type: 'assistant/message', data: { text: 'Sources:\n- [fake](https://fake.org/)' } });
  await f.tools.get('research_read_source').execute({ operation: 'list' }, f.exec);
  const request = f.calls.find(c => c.url.endsWith('/research-source'));
  assert.deepEqual(request.body.search_activities, [{ id: 'native-root:search-real', title: 'web_search', status: 'completed', detail }]);
  await assert.rejects(() => f.tools.get('research_read_source').execute({ operation: 'list', search_activities: [] }, f.exec), /research_source_arguments_invalid/);
});

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
    return String(url).endsWith('/skill-preflight') ? Response.json(admitted)
      : String(url).endsWith('/research-source/cancel') ? Response.json({ status: 'cancelled' }) : responseFactory();
  };
  t.after(() => { globalThis.fetch = originalFetch; });
  apply(ctx, { python: '/python', runnerPath: '/runner', researchRoot: root });
  return { root, cwd, tools, calls, logs, events, native, child, sessions,
    exec: { signal: new AbortController().signal, agent: { session: native }, callId: 'source-call' },
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


test('business quality repair uses the data plan route without renewing repair or certifying claims', async t => {
  const observation = { id: 'business_' + 'a'.repeat(32), kind: 'business_numeric' };
  const f = await fixture(t, result({ status: 'incomplete', issues: ['numeric_claim_unverified'],
    repair_count: 1, may_repair: true, evidence_context: { business_observations: [observation] } }));
  const tool = f.tools.get('research_check_quality');
  const first = JSON.parse((await tool.execute({}, f.exec)).result_json);
  assert.match(first.repair_instructions, /report_plan/);
  assert.match(first.repair_instructions, /exact user-requested Summary metric keys/);
  assert.match(first.repair_instructions, /independent primitive calculation/);
  assert.match(first.repair_instructions, /preserve genuine missing/);
  assert.equal(first.status, 'incomplete');
  assert.deepEqual(first.issues, ['numeric_claim_unverified']);
  const replay = JSON.parse((await tool.execute({}, f.exec)).result_json);
  assert.equal(Object.hasOwn(replay, 'repair_instructions'), false);
});


test('quote-only business evidence keeps the usable legacy repair route', async t => {
  const f = await fixture(t, result({ status: 'incomplete', issues: ['narrative_unverified'],
    repair_count: 1, may_repair: true,
    evidence_context: { business_observations: [{ id: 'business_' + 'b'.repeat(32), kind: 'business_quote' }] } }));
  const tool = f.tools.get('research_check_quality');
  const first = JSON.parse((await tool.execute({}, f.exec)).result_json);
  assert.equal(first.status, 'incomplete');
  assert.doesNotMatch(first.repair_instructions, /report_plan/);
  assert.match(first.repair_instructions, /once in this same native turn/);
  const replay = JSON.parse((await tool.execute({}, f.exec)).result_json);
  assert.equal(Object.hasOwn(replay, 'repair_instructions'), false);
});
