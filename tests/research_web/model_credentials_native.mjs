/** Native synthetic acceptance helper. No supplier transport is invoked. */
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { spawnSync } from 'node:child_process';

const [source, dataHome, phase, port] = process.argv.slice(2);
const pinned = async path => import(pathToFileURL(`${source}/${path}`).href);
if (phase === 'sdk-docker-text-activation') {
  const output = process.stdout.write.bind(process.stdout);
  process.stdout.write = () => true;
  process.stderr.write = () => true;
  let ctx;
  let result = 'FAIL';
  let networkCalls = 0;
  let diagnostic;
  globalThis.fetch = async () => { networkCalls += 1; throw Error('fixture_network_refused'); };
  const timer = setTimeout(() => {
    output(`DOCKER_TEXT_ACTIVATION:${JSON.stringify({ result: 'FAIL', code: 'fixture_timeout', networkCalls })}\n`);
    process.exit(1);
  }, 20000);
  try {
    const { runProfile } = await pinned('apps/cli/lib/profile-boot-CMEGRIuU.js');
    const { loadLayeredEnv } = await pinned('packages/boot/app-boot/lib/index.js');
    ({ ctx } = await runProfile({ environment: loadLayeredEnv('dsh'), profile: 'web', patchFiles: [`${dataHome}/runtime/overlay.yml`], args: ['--host', '127.0.0.1', '--port', port, '--no-open'] }));
    assert.equal(ctx.get('settings'), undefined);
    assert.equal(ctx.get('tabbit'), undefined);
    assert.ok(ctx.get('credentialsController'));
    assert.ok(ctx.get('sessionController'));
    assert.ok((await ctx.get('sessionController').modelCatalog()).groups.some(group => group.id === 'deepseek-official'));
    assert.equal(networkCalls, 0);
    result = 'PASS';
  } catch (error) {
    const message = String(error?.message ?? '');
    diagnostic = {
      type: ['Error', 'TypeError', 'AssertionError'].includes(error?.name) ? error.name : 'Error',
      waiting: ['dsh-tabbit', 'settings', 'tabbit-permissions', 'tabbit-tool-browser', 'tabbit-mentions', 'research-tabbit-adapter'].filter(id => message.includes(id)),
    };
    process.exitCode = 1;
  } finally {
    try { await ctx?.fiber.dispose(); } catch { result = 'FAIL'; process.exitCode = 1; }
    clearTimeout(timer);
    output(`DOCKER_TEXT_ACTIVATION:${JSON.stringify({ result, networkCalls, diagnostic, scope: 'actual-fixed-sdk-generated-overlay', paid: false })}\n`);
  }
  process.exit(process.exitCode || 0);
}
if (['sdk-free-budget-first', 'sdk-free-budget-resume', 'sdk-free-budget-exhaustion'].includes(phase)) {
  await freeSdkBudgetProof(process.argv[6]);
  process.exit(process.exitCode || 0);
}

async function freeSdkBudgetProof(python) {
  const output = process.stdout.write.bind(process.stdout);
  process.stdout.write = () => true;
  process.stderr.write = () => true;
  let stage = 'isolation';
  let ctx;
  let calls = 0;
  let refused = 0;
  let observed;
  let terminal = { result: 'NEEDS_CONTEXT' };
  const home = resolve(dataHome, 'runtime/home');
  const installationId = '4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b';
  const budgetRoot = resolve(dataHome, 'budget', installationId);
  const wrapper = resolve(dataHome, 'fixture-budget-wrapper.py');
  const timer = setTimeout(() => {
    output(`TASK4B_SDK_BUDGET_RESULT:${JSON.stringify({ phase, result: 'NEEDS_CONTEXT', stage, code: 'fixture_process_timeout', calls, refused })}\n`);
    process.exit(1);
  }, 55000);
  try {
    assert.equal(process.env.HOME, home);
    assert.equal(process.env.DSH_HOME, home);
    assert.ok(python?.startsWith('/'));
    globalThis.fetch = async (url, options) => {
      if (String(url) !== 'https://api.deepseek.com/chat/completions' || options?.method !== 'POST') {
        refused += 1;
        throw Error('fixture_network_refused');
      }
      const body = JSON.parse(options.body);
      assert.equal(body.model, 'deepseek-flash');
      assert.equal(body.max_tokens, 512);
      assert.equal(options.headers.authorization, 'Bearer task-owned-synthetic-free');
      calls += 1;
      const chunks = [
        { choices: [{ index: 0, delta: { role: 'assistant', content: 'SDK budget proof.' }, finish_reason: null }] },
        { choices: [{ index: 0, delta: {}, finish_reason: 'stop' }], usage: { prompt_tokens: 11, completion_tokens: 4, total_tokens: 15, prompt_cache_hit_tokens: 0, prompt_cache_miss_tokens: 11 } },
      ];
      return new Response(chunks.map(chunk => `data: ${JSON.stringify(chunk)}\n\n`).join('') + 'data: [DONE]\n\n', { headers: { 'content-type': 'text/event-stream' } });
    };
    await mkdir(`${home}/.agent-presets/research-web`, { recursive: true, mode: 0o700 });
    await mkdir(resolve(dataHome, 'budget'), { recursive: true, mode: 0o700 });
    const project = resolve(new URL('../..', import.meta.url).pathname);
    const wrapperSource = [
      'import sys, json', 'from pathlib import Path', 'from datetime import datetime, UTC, timedelta',
      `sys.path.insert(0, ${JSON.stringify(project)})`,
      'from app.research_web.live_acceptance_budget import BudgetStore, BudgetError, authorization, ERRORS',
      `ROOT = Path(${JSON.stringify(budgetRoot)})`, `INSTALLATION = ${JSON.stringify(installationId)}`,
      'try:', '    if sys.argv[1:] != ["--installation-id", INSTALLATION]: raise BudgetError("acceptance_budget_invalid")',
      '    request = json.loads(sys.stdin.buffer.read(8193))',
      '    if request == {"op": "fixture-init"}:',
      '        until = (datetime.now(UTC) + timedelta(minutes=59)).strftime("%Y-%m-%dT%H:%M:%SZ")',
      '        BudgetStore.initialize(ROOT, INSTALLATION, authorization(3, 512, until))',
      '        result = {"ok": True, "tickets": 0}',
      '    elif isinstance(request, dict) and set(request) == {"op", "outputTokens"} and request["op"] == "reserve" and type(request["outputTokens"]) is int:',
      '        result = {"ok": True, **BudgetStore(ROOT, INSTALLATION).reserve(request["outputTokens"])}',
      '    else: raise BudgetError("acceptance_budget_invalid")',
      '    print(json.dumps(result))',
      'except Exception as error:',
      '    code = str(error) if isinstance(error, BudgetError) and str(error) in ERRORS else "acceptance_budget_unavailable"',
      '    print(json.dumps({"ok": False, "error": code}))', '    sys.exit(1)', '',
    ].join('\n');
    await writeFile(wrapper, wrapperSource, { mode: 0o600 });
    stage = 'fixture-budget-init';
    if (phase === 'sdk-free-budget-first') {
      const child = spawnSync(python, ['-I', '-B', wrapper, '--installation-id', installationId], { cwd: '/', env: { PATH: '/usr/bin:/bin', LANG: 'en_US.UTF-8' }, input: JSON.stringify({ op: 'fixture-init' }), encoding: 'utf8', timeout: 10000, maxBuffer: 8192 });
      assert.equal(child.status, 0);
      assert.deepEqual(JSON.parse(child.stdout), { ok: true, tickets: 0 });
    }
    if (phase === 'sdk-free-budget-exhaustion') {
      // Fixture-only third reservation; this is not a supplier request.
      const child = spawnSync(python, ['-I', '-B', wrapper, '--installation-id', installationId], { cwd: '/', env: { PATH: '/usr/bin:/bin', LANG: 'en_US.UTF-8' }, input: JSON.stringify({ op: 'reserve', outputTokens: 512 }), encoding: 'utf8', timeout: 10000, maxBuffer: 8192 });
      assert.equal(child.status, 0);
      assert.equal(JSON.parse(child.stdout).ticket, 3);
    }
    const settings = 'llm-deepseek:\n  baseURL: https://invalid.example.test\n  maxTokens: 9000\n';
    await writeFile(`${home}/settings.yaml`, settings, { mode: 0o600 });
    await writeFile(`${home}/.agent-presets/research-web/agent.cordis.yml`, await readFile(new URL('../../app/research_web/runtime/agent.cordis.yml', import.meta.url)), { mode: 0o600 });
    await writeFile(`${dataHome}/runtime/overlay.yml`, [
      '- id: settings', '  disabled: true', '- id: llm-deepseek', '  config:', '    apiKeyEnv: RESEARCH_DSH_API_KEY', '    baseURL: https://api.deepseek.com', '    thinking: disabled', '    maxTokens: 512', '    retryPolicy:', '      mode: normal', '      maxRetries: 0',
      '- id: llm-retry', '  disabled: true', '- id: session-title-llm', '  disabled: true', '- id: agent-presets', '  config:', '    default: research-web', '- id: open-in-app', '  disabled: true', '- id: directory-picker', '  disabled: true',
      '- insert:', '    - id: research-tool-guard', `      name: ${JSON.stringify(resolve(project, 'app/research_web/runtime/guard.mjs'))}`, '      config:', '        enabled: false', '        acceptance:', '          profile: docker-text', `          installationId: ${installationId}`, '          modelCalls: 3', '          maxOutputTokens: 512', '          budgetBridge:', `            python: ${JSON.stringify(python)}`, `            bridge: ${JSON.stringify(wrapper)}`,
    ].join('\n') + '\n', { mode: 0o600 });
    stage = 'boot';
    const { runProfile } = await pinned('apps/cli/lib/profile-boot-CMEGRIuU.js');
    const { loadLayeredEnv } = await pinned('packages/boot/app-boot/lib/index.js');
    ({ ctx } = await runProfile({ environment: loadLayeredEnv('dsh'), profile: 'web', patchFiles: [`${dataHome}/runtime/overlay.yml`], args: ['--host', '127.0.0.1', '--port', port, '--no-open'] }));
    assert.equal(ctx.get('settings'), undefined);
    assert.ok(ctx.get('credentialsController'));
    const controller = ctx.get('sessionController');
    assert.ok((await controller.modelCatalog()).groups.some(group => group.id === 'deepseek-official'));
    ctx.get('llm').adapters.get('deepseek-official').adapter.config.resolveApiKey = async () => 'task-owned-synthetic-free';
    const sessionId = 'session-task4b-sdk-budget';
    await controller.create({ sessionId, cwd: process.cwd(), agentPreset: 'research-web' });
    await controller.selectModel({ sessionId, provider: 'deepseek-official', model: 'deepseek-flash' });
    ctx.on('llm/stream', async function* (options, next) {
      observed = { providerAllowed: options.provider === 'deepseek-official', modelAllowed: options.model === 'deepseek-flash', maxTokens: options.maxTokens, toolsCount: Array.isArray(options.tools) ? options.tools.length : null };
      yield* next();
    }, { global: true, prepend: true });
    stage = 'normal-loop-prompt';
    let completed;
    let usage;
    let text = false;
    const completion = new Promise(resolve => { completed = resolve; });
    const stop = ctx.on('session/event', (session, event) => {
      if (session.id !== sessionId) return;
      if (event.type === 'assistant/message') { usage = event.data.usage; text = event.data.message.content.some(block => block.type === 'text' && block.text.length > 0); }
      if (event.type === 'turn/end') completed(event);
    });
    await controller.prompt({ sessionId, requestId: phase, content: [{ type: 'text', text: 'Return a short proof.' }], mode: 'followup' }, new AbortController().signal);
    const turn = await Promise.race([completion, new Promise((_, reject) => { const wait = setTimeout(() => reject(Error('fixture_turn_timeout')), 15000); wait.unref(); })]);
    stop();
    const ledger = JSON.parse(await readFile(`${budgetRoot}/ledger.json`, 'utf8'));
    const denied = ['acceptance_tool_limit', 'acceptance_budget_exhausted', 'acceptance_budget_unavailable', 'acceptance_output_limit', 'acceptance_provider_denied'].find(code => JSON.stringify(turn.data.reason).includes(code));
    if (phase === 'sdk-free-budget-exhaustion') {
      assert.equal(denied, 'acceptance_budget_exhausted');
      assert.equal(calls, 0); assert.equal(refused, 0); assert.equal(ledger.tickets, 3);
      terminal = { result: 'PASS', stage: 'exhaustion-denied', code: denied, observed, calls, refused, tickets: ledger.tickets, fixtureOnlyThirdReservation: true, paid: false, scope: 'actual-fixed-sdk-current-guard-real-private-budget-fixture' };
    } else if (turn.data.reason.kind !== 'completed') {
      terminal = { result: 'NEEDS_CONTEXT', stage, code: denied ?? 'fixture_turn_failed', observed, calls, refused, tickets: ledger.tickets };
      process.exitCode = 1;
    } else {
      assert.equal(calls, 1); assert.equal(refused, 0); assert.equal(text, true);
      assert.equal(usage.inputTokens, 11); assert.equal(usage.outputTokens, 4);
      assert.equal(ledger.tickets, phase === 'sdk-free-budget-first' ? 1 : 2);
      assert.equal(await readFile(`${home}/settings.yaml`, 'utf8'), settings);
      terminal = { result: 'PASS', stage: 'settled', observed, calls, refused, tickets: ledger.tickets, inputTokens: usage.inputTokens, outputTokens: usage.outputTokens, paid: false, scope: 'actual-fixed-sdk-current-guard-real-private-budget-fixture' };
    }
  } catch (error) {
    terminal = { result: 'NEEDS_CONTEXT', stage, type: ['Error', 'TypeError', 'AssertionError'].includes(error?.name) ? error.name : 'Error', observed, calls, refused };
    process.exitCode = 1;
  } finally {
    try { await ctx?.fiber.dispose(); } catch { terminal = { result: 'NEEDS_CONTEXT', stage: 'dispose', calls, refused }; process.exitCode = 1; }
    clearTimeout(timer);
    output(`TASK4B_SDK_BUDGET_RESULT:${JSON.stringify({ phase, ...terminal })}\n`);
  }
}
// Explicit free SDK proof: isolated files, in-process transport, no Keychain bridge.
if (phase === 'sdk-free-first' || phase === 'sdk-free-resume') {
  await freeSdkProof();
  process.exit(0);
}

async function freeSdkProof() {
  const output = process.stdout.write.bind(process.stdout);
  process.stdout.write = () => true;
  process.stderr.write = () => true;
  let stage = 'isolation';
  let ctx;
  let calls = 0;
  let refused = 0;
  process.on('uncaughtException', error => {
    output(`TASK4B_SDK_RESULT:${JSON.stringify({ phase, result: 'NEEDS_CONTEXT', stage, type: error?.name === 'AssertionError' ? 'AssertionError' : 'Error', calls, refused })}\n`);
    process.exit(1);
  });
  process.on('unhandledRejection', () => {
    output(`TASK4B_SDK_RESULT:${JSON.stringify({ phase, result: 'NEEDS_CONTEXT', stage, type: 'unhandledRejection', calls, refused })}\n`);
    process.exit(1);
  });
  const home = resolve(dataHome, 'runtime/home');
  try {
    assert.equal(process.env.HOME, home);
    assert.equal(process.env.DSH_HOME, home);
    assert.equal(process.env.DSH_TELEMETRY_DISABLED, '1');
    const maxTokens = 512;
    globalThis.fetch = async (url, options) => {
      if (String(url) !== 'https://api.deepseek.com/chat/completions' || options?.method !== 'POST') {
        refused += 1;
        throw Error('sdk_free_network_refused');
      }
      const body = JSON.parse(options.body);
      assert.equal(body.model, 'deepseek-v4-flash');
      assert.equal(body.max_tokens, maxTokens);
      assert.equal(body.stream, true);
      assert.ok(body.messages.some(message => message.role === 'user' && typeof message.content === 'string'));
      assert.equal(body.messages.some(message => Array.isArray(message.content)), false);
      assert.equal(options.headers.authorization, 'Bearer task-owned-synthetic-free');
      calls += 1;
      assert.equal(calls, 1);
      const chunks = [
        { id: 'free-sdk', choices: [{ index: 0, delta: { role: 'assistant', content: 'SDK free proof.' }, finish_reason: null }] },
        { id: 'free-sdk', choices: [{ index: 0, delta: {}, finish_reason: 'stop' }], usage: { prompt_tokens: 11, completion_tokens: 4, total_tokens: 15, prompt_cache_hit_tokens: 0, prompt_cache_miss_tokens: 11 } },
      ];
      return new Response(chunks.map(chunk => `data: ${JSON.stringify(chunk)}\n\n`).join('') + 'data: [DONE]\n\n', { headers: { 'content-type': 'text/event-stream' } });
    };
    await mkdir(`${home}/.agent-presets/research-web`, { recursive: true, mode: 0o700 });
    const settings = 'llm-deepseek:\n  baseURL: https://invalid.example.test\n  maxTokens: 9000\n';
    await writeFile(`${home}/settings.yaml`, settings, { mode: 0o600 });
    await writeFile(`${home}/.agent-presets/research-web/agent.cordis.yml`, await readFile(new URL('../../app/research_web/runtime/agent.cordis.yml', import.meta.url)), { mode: 0o600 });
    await writeFile(`${dataHome}/runtime/overlay.yml`, [
      '- id: settings', '  disabled: true',
      '- id: llm-deepseek', '  config:', '    apiKeyEnv: RESEARCH_DSH_API_KEY', '    baseURL: https://api.deepseek.com', '    thinking: disabled', `    maxTokens: ${maxTokens}`, '    retryPolicy:', '      mode: normal', '      maxRetries: 0',
      '- id: llm-retry', '  disabled: true', '- id: session-title-llm', '  disabled: true',
      '- id: agent-presets', '  config:', '    default: research-web',
      '- id: open-in-app', '  disabled: true', '- id: directory-picker', '  disabled: true',
    ].join('\n') + '\n', { mode: 0o600 });
    stage = 'boot';
    const { runProfile } = await pinned('apps/cli/lib/profile-boot-CMEGRIuU.js');
    const { loadLayeredEnv } = await pinned('packages/boot/app-boot/lib/index.js');
    ({ ctx } = await runProfile({ environment: loadLayeredEnv('dsh'), profile: 'web', patchFiles: [`${dataHome}/runtime/overlay.yml`], args: ['--host', '127.0.0.1', '--port', port, '--no-open'] }));
    assert.equal(ctx.get('settings'), undefined);
    assert.ok(ctx.get('credentialsController'));
    assert.ok(ctx.get('credentials'));
    stage = 'catalog';
    const controller = ctx.get('sessionController');
    const catalog = await controller.modelCatalog();
    assert.ok(catalog.groups.some(group => group.id === 'deepseek-official' && group.models.some(model => model.id === 'deepseek-v4-flash')));
    assert.equal((await ctx.get('agentPresets').resolve('research-web')).id, 'research-web');
    const adapter = ctx.get('llm').adapters.get('deepseek-official').adapter;
    // Test callback supplies only a canary; production credential transport is absent.
    adapter.config.resolveApiKey = async () => 'task-owned-synthetic-free';
    stage = 'session';
    const sessionId = 'session-task4b-sdk-free';
    await controller.create({ sessionId, cwd: process.cwd(), agentPreset: 'research-web' });
    const priorTurns = ctx.get('sessions').get(sessionId).log.filter(event => event.type === 'turn/end' && event.data.reason.kind === 'completed').length;
    assert.equal(priorTurns, phase === 'sdk-free-first' ? 0 : 1);
    const selected = await controller.selectModel({ sessionId, provider: 'deepseek-official', model: 'deepseek-v4-flash' });
    assert.equal(selected.selected.provider, 'deepseek-official');
    assert.equal(selected.selected.model, 'deepseek-v4-flash');
    stage = 'prompt';
    let completed;
    const completion = new Promise(resolve => { completed = resolve; });
    let usage;
    let text = false;
    const stop = ctx.on('session/event', (session, event) => {
      if (session.id !== sessionId) return;
      if (event.type === 'assistant/message') {
        usage = event.data.message?.usage ?? event.data.usage;
        text = event.data.message.content.some(block => block.type === 'text' && block.text.length > 0);
      }
      if (event.type === 'turn/end') completed(event);
    });
    await controller.prompt({ sessionId, requestId: `task4b-${phase}`, content: [{ type: 'text', text: 'Return a short proof.' }], mode: 'followup' }, new AbortController().signal);
    const turn = await Promise.race([completion, new Promise((_, reject) => { const timer = setTimeout(() => reject(Error('sdk_free_turn_timeout')), 15000); timer.unref(); })]);
    stop();
    stage = 'turn-settlement';
    assert.equal(turn.data.reason.kind, 'completed');
    assert.equal(text, true);
    assert.equal(usage.inputTokens, 11);
    assert.equal(usage.outputTokens, 4);
    assert.equal(calls, 1);
    assert.equal(refused, 0);
    assert.equal(await readFile(`${home}/settings.yaml`, 'utf8'), settings);
    output(`TASK4B_SDK_RESULT:${JSON.stringify({ phase, result: 'PASS', scope: 'fixed-sdk-inprocess-stub', calls, refused, maxTokens, priorTurns, inputTokens: usage.inputTokens, outputTokens: usage.outputTokens, settingsDisabled: true, credentialController: true, modelCatalog: true, preset: true, selected: true, settingsWrite: 'UNAVAILABLE', dockerPrivatePipe: 'NOT_RUN', paid: false })}\n`);
  } catch (error) {
    output(`TASK4B_SDK_RESULT:${JSON.stringify({ phase, result: 'NEEDS_CONTEXT', stage, type: ['Error', 'TypeError', 'AssertionError'].includes(error?.name) ? error.name : 'Error', calls, refused })}\n`);
    process.exitCode = 1;
  } finally {
    await ctx?.fiber.dispose();
  }
  if (process.exitCode) process.exit(1);
}
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
