/** Host-global final veto; MCP tools require an exact activation allowlist. */
import { spawn } from 'node:child_process';
import { existsSync, lstatSync, mkdirSync, writeFileSync, renameSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { isAbsolute, join, resolve } from 'node:path';
import { nativeAdmission } from './public-data.mjs';

export const inject = ['tools', 'llm', 'sessions'];

export function pluginRuntimeFrozen(root) {
  if (typeof root !== 'string' || !isAbsolute(root) || resolve(root) !== root) return true;
  try {
    const folder = join(root, 'plugins');
    if (!existsSync(folder)) return false;
    if (lstatSync(folder).isSymbolicLink()) return true;
    return existsSync(join(folder, 'runtime-freeze.json'));
  } catch { return true; }
}
const SAFE_SCOPE_CODES = new Set([
  'data_contract_missing', 'data_contract_invalid', 'data_state_unknown',
  'data_source_unavailable', 'data_dependency_unavailable',
  'data_semantics_not_equivalent', 'data_semantics_unverified',
  'model_tool_capability_unverified', 'capability_disabled', 'source_scope_excluded',
  'linked_version_conflict',
]);
function scopeDenialReason(scope) {
  const codes = [...new Set((Array.isArray(scope?.missing) ? scope.missing.slice(0, 20) : [])
    .map(item => item?.code).filter(code => typeof code === 'string' && SAFE_SCOPE_CODES.has(code)))].sort();
  return `capability_scope_unavailable${codes.length ? `: ${codes.join(',')}` : ''}`;
}

const budgetErrors = new Set(['acceptance_budget_unverified', 'acceptance_budget_invalid', 'acceptance_budget_expired',
  'acceptance_budget_exhausted', 'acceptance_budget_unavailable', 'acceptance_budget_commit_uncertain']);

function reserveBudget(acceptance, outputTokens) {
  const config = acceptance.budgetBridge;
  const began = performance.now();
  return new Promise((resolve, reject) => {
    const child = spawn(config.python, ['-I', '-B', config.bridge, '--installation-id', acceptance.installationId], {
      cwd: '/', env: { PATH: '/usr/bin:/bin', LANG: 'en_US.UTF-8' }, stdio: ['pipe', 'pipe', 'pipe'],
    });
    let output = '';
    let stderrBytes = 0;
    let failed = false;
    const fail = () => { failed = true; child.kill('SIGKILL'); };
    const timer = setTimeout(fail, 10000);
    child.on('error', fail);
    child.stdin.on('error', fail);
    child.stdout.setEncoding('utf8');
    child.stdout.on('data', chunk => { output += chunk; if (Buffer.byteLength(output) > 1024) fail(); });
    child.stderr.on('data', chunk => { stderrBytes += chunk.length; if (stderrBytes > 8192) fail(); });
    child.on('close', code => {
      clearTimeout(timer);
      try {
        const result = JSON.parse(output);
        if (failed) throw Error();
        if (code === 1 && result?.ok === false && Object.keys(result).sort().join(',') === 'error,ok' && budgetErrors.has(result.error)) {
          reject(Error(result.error)); return;
        }
        if (code !== 0 || result?.ok !== true || Object.keys(result).sort().join(',') !== 'ok,remainingMillis,ticket' ||
            !Number.isSafeInteger(result.ticket) || result.ticket < 1 || result.ticket > acceptance.modelCalls ||
            !Number.isSafeInteger(result.remainingMillis) || result.remainingMillis < 1 || result.remainingMillis > 3600000) throw Error();
        // Pipe time is charged conservatively; a late response cannot reopen an expired authorization.
        resolve({ ticket: result.ticket, deadline: began + result.remainingMillis });
      } catch { reject(Error('acceptance_budget_unavailable')); }
    });
    // No prompt, credential, model options, signal reason or usage crosses stdin.
    child.stdin.end(JSON.stringify({ op: 'reserve', outputTokens }));
  });
}

// Bound each pending iterator read as well as each delivered chunk. Do not echo
// cancellation reasons, and do not await an uncooperative provider during cleanup.
async function* boundedStream(next, signal, deadline, expire) {
  const iterator = next()[Symbol.asyncIterator]();
  let timer, abort;
  const stopped = new Promise((_, reject) => {
    abort = () => reject(Error('acceptance_request_aborted'));
    signal?.addEventListener('abort', abort, { once: true });
    timer = setTimeout(() => {
      reject(Error('acceptance_budget_expired'));
      expire();
    }, Math.max(0, deadline - performance.now()));
  });
  // Install a rejection handler even while the consumer pauses between chunks.
  void stopped.catch(() => {});
  try {
    while (true) {
      if (signal?.aborted) throw Error('acceptance_request_aborted');
      if (performance.now() >= deadline) { expire(); throw Error('acceptance_budget_expired'); }
      const item = await Promise.race([iterator.next(), stopped]);
      if (signal?.aborted) throw Error('acceptance_request_aborted');
      if (performance.now() >= deadline) { expire(); throw Error('acceptance_budget_expired'); }
      if (item.done) return;
      yield item.value;
    }
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', abort);
    if (iterator.return) void Promise.resolve(iterator.return()).catch(() => {});
  }
}

export const RESEARCH_TOOLS = new Set([
  'todo_write',
  'research_run_script',
  'research_document_operation',
  'research_check_quality',
  'research_read_source',
  'rwb_record_method_use',
  'specialist_plan', 'specialist_run', 'specialist_status', 'specialist_cancel',
  'rwb_prepare_automation',
  'rwb_list_automations', 'rwb_prepare_automation_update', 'rwb_run_automation', 'ask_user_question',
  'datahub_search_assets', 'datahub_get_trading_calendar', 'datahub_get_market_bars',
  'datahub_get_market_snapshot', 'datahub_get_index_data', 'datahub_get_financials',
  'datahub_get_market_activity', 'datahub_get_factor_macro', 'datahub_get_fund_data',
  'rwb_query_latest_cls_news', 'datahub_search_news', 'datahub_search_announcements', 'datahub_search_research', 'datahub_search_web',
  'datahub_get_database_schema', 'datahub_query_table', 'datahub_get_external_data',
  'skill', 'web_search', 'subagent', 'send_message', 'interrupt_agent', 'list_agents', 'rwb_plugin_instructions', 'rwb_plugin_agent',
]);

export function apply(ctx, config = {}) {
  if (config.tenantMode === true && (config.tenantSkillNames !== undefined &&
      (!Array.isArray(config.tenantSkillNames) || config.tenantSkillNames.some(name => typeof name !== 'string' || !/^[a-z0-9][a-z0-9_-]{0,159}$/.test(name))))) {
    throw Error('tenant_skill_allowlist_invalid');
  }
  const tenantSkillNames = new Set(config.tenantSkillNames || []);
  if (config.researchRoot !== undefined) {
    if (typeof config.researchRoot !== 'string' || !isAbsolute(config.researchRoot)) throw Error('skill_admission_root_invalid');
    const catalogScoped = new WeakSet();
    const ownedNewsMasks = new WeakMap();
    const pending = new Map();
    const registrations = new Map();
    const uncertain = new Set();
    const scopeKey = agent => { const cwd = agent?.session?.header?.cwd; if (typeof cwd !== "string" || !isAbsolute(cwd)) throw Error("skill_scope_identity_invalid"); return cwd; };
    const pendingFor = agent => { agent = scopeKey(agent); let value = pending.get(agent); if (!value) { value = new Set(); pending.set(agent, value); } return value; };
    const waitRegistrations = async agent => { await Promise.all(registrations.get(scopeKey(agent)) || []); };
    ctx.on('tools/pre-execute', async (exec, next) => {
      const skill = config.enabled && exec.agent && exec.name === 'skill';
      if (skill) pendingFor(exec.agent).add(exec.callId);
      const decision = await next();
      if (!config.enabled || !exec.agent || ['deny','cancel'].includes(decision.kind)) {
        if (skill) pendingFor(exec.agent).delete(exec.callId);
        return decision;
      }
      try {
        await waitRegistrations(exec.agent);
        if (uncertain.has(scopeKey(exec.agent)) || (!skill && pendingFor(exec.agent).size)) return { kind: 'deny', reason: 'capability_scope_unverified' };
        const scope = await nativeAdmission(ctx, exec, config);
        if (!scope.admitted || (!skill && pendingFor(exec.agent).size)) {
          ctx.logger.warn('research_native_capability_admission_denied');
          if (skill) pendingFor(exec.agent).delete(exec.callId);
          return { kind: 'deny', reason: scopeDenialReason(scope) };
        }
        return decision;
      } catch {
        if (skill) pendingFor(exec.agent).delete(exec.callId);
        ctx.logger.warn('research_native_capability_admission_unavailable');
        return { kind: 'deny', reason: 'capability_scope_unverified' };
      }
    }, { global: true, prepend: true });
    // Observe the final frozen result, after approval, guards, output validation
    // and cancellation. An unconfirmed registration blocks subsequent execution.
    ctx.on('tools/result', (exec, result) => {
      if (!config.enabled || !exec.agent || exec.name !== 'skill') return;
      if (result.isError !== false || exec.signal.aborted) { pendingFor(exec.agent).delete(exec.callId); return; }
      let queue = registrations.get(scopeKey(exec.agent));
      if (!queue) { queue = new Set(); registrations.set(scopeKey(exec.agent), queue); }
      const registration = (async () => {
        try {
          const scope = await nativeAdmission(ctx, exec, config, true);
          if (!scope.admitted) throw Error('skill_scope_registration_unconfirmed');
        } catch {
          uncertain.add(scopeKey(exec.agent));
          ctx.logger.warn('research_native_capability_registration_unconfirmed');
        } finally { pendingFor(exec.agent).delete(exec.callId); }
      })();
      queue.add(registration);
      void registration.finally(() => queue.delete(registration));
    }, { global: true });
    // Upstream /skill-name user gestures inject instructions before any tool
    // invocation. Inspect the authoritative injected source, not user prose.
    ctx.on('agent/pre-step', async (options, next) => {
      if (config.tenantMode === true && pluginRuntimeFrozen(config.researchRoot)) return { kind: 'reject' };
      if (config.enabled && ctx.tools.get?.('rwb_query_latest_cls_news')) {
        let admitted = false;
        try {
          admitted = (await nativeAdmission(ctx, {name:'rwb_query_latest_cls_news',agent:options.agent,signal:options.signal}, config)).admitted === true;
        } catch { ctx.logger.warn('research_owned_news_catalog_unavailable'); }
        const release = ownedNewsMasks.get(options.agent);
        if (admitted && release) { release(); ownedNewsMasks.delete(options.agent); }
        else if (!admitted && !release) ownedNewsMasks.set(options.agent, options.agent.ctx.tools.restrict({deny:['rwb_query_latest_cls_news']}));
      }
      if (config.enabled && !catalogScoped.has(options.agent)) {
        try {
          const scope = await nativeAdmission(ctx, {name:'agent_step',agent:options.agent,signal:options.signal}, config);
          if (!scope.admitted) return {kind:'reject'};
          if (scope.visible_tools !== undefined) {
            if (!Array.isArray(scope.visible_tools) || scope.visible_tools.some(name => typeof name !== 'string' || !RESEARCH_TOOLS.has(name))) throw Error('automation_catalog_invalid');
            options.agent.ctx.tools.restrict({allow:scope.visible_tools});
          }
          catalogScoped.add(options.agent);
        } catch {ctx.logger.warn('research_native_catalog_unverified');return {kind:'reject'};}
      }
      const decision = await next();
      if (!config.enabled || decision.kind === 'reject') return decision;
      try {
        await waitRegistrations(options.agent);
        if (uncertain.has(scopeKey(options.agent)) || pendingFor(options.agent).size || !Array.isArray(decision.messages)) return { kind: 'reject' };
        const exec = { name: 'agent_step', agent: options.agent, signal: options.signal };
        if (!(await nativeAdmission(ctx, exec, config)).admitted) return { kind: 'reject' };
        const priorMessages = new Set(options.messages || []);
        const names = new Set(decision.messages.filter(message => !priorMessages.has(message) && message.source?.kind === 'skill-invocation' && message.source.form === 'instructions').map(message => message.source.name));
        if (config.tenantMode === true && [...names].some(name => !tenantSkillNames.has(name))) {
          ctx.logger.warn('research_tenant_skill_injection_denied');
          return { kind: 'reject' };
        }
        for (const name of names) {
          const invocation = { ...exec, nativeSkillName: name };
          if (!(await nativeAdmission(ctx, invocation, config)).admitted) return { kind: 'reject' };
        }
        for (const name of names) {
          const invocation = { ...exec, nativeSkillName: name };
          if (!(await nativeAdmission(ctx, invocation, config, true)).admitted) return { kind: 'reject' };
        }
        return decision;
      } catch {
        ctx.logger.warn('research_native_skill_injection_denied');
        return { kind: 'reject' };
      }
    }, { global: true, prepend: true });
  }
  // Optional instance-wide acceptance caps; the owned launcher supplies them.
  const acceptance = config.acceptance;
  const dockerText = acceptance?.profile === 'docker-text';
  let modelCalls = 0;
  let toolCalls = 0;
  const requestOwners = new WeakMap();
  const latestOwners = new WeakMap();
  let nativeLlm;
  if (dockerText) {
    if (typeof config.nativeLlmModule !== 'string' || !isAbsolute(config.nativeLlmModule) || config.nativeLlmModule.includes('\0')) throw Error('acceptance_control_invalid');
    ctx.on('agent/request', async (payload, next) => {
      const owner = payload.agent;
      if (!payload.signal || typeof owner?.cancel !== 'function' || typeof owner.session?.id !== 'string') throw Error('acceptance_transport_abort_unverified');
      const decision = await next();
      const binding = { agent: owner, sessionId: owner.session.id, signal: payload.signal };
      requestOwners.set(payload.signal, binding);
      latestOwners.set(owner, binding);
      return decision;
    }, { global: true, prepend: true });
  }
  if (acceptance !== undefined) {
    const validLegacy = acceptance && !dockerText && Object.keys(acceptance).sort().join(',') === 'modelCalls,tool' &&
      Number.isInteger(acceptance.modelCalls) && acceptance.modelCalls >= 1 && acceptance.modelCalls <= 6 &&
      acceptance.tool === 'datahub_get_fund_data';
    const budgetBridge = acceptance?.budgetBridge;
    const validBridge = budgetBridge && (Object.keys(budgetBridge).sort().join(',') === 'bridge,python' &&
      [budgetBridge.python, budgetBridge.bridge].every(value => typeof value === 'string' && value.startsWith('/') && value.length <= 4096 && !value.includes('\0')));
    const validDockerText = dockerText && validBridge &&
      Object.keys(acceptance).sort().join(',') === 'budgetBridge,installationId,maxOutputTokens,modelCalls,profile' &&
      typeof acceptance.installationId === 'string' && /^[a-f0-9]{32}$/.test(acceptance.installationId) &&
      Number.isInteger(acceptance.modelCalls) && acceptance.modelCalls >= 1 && acceptance.modelCalls <= 3 &&
      Number.isSafeInteger(acceptance.maxOutputTokens) && acceptance.maxOutputTokens >= 1 && acceptance.maxOutputTokens <= 512;
    if (!validLegacy && !validDockerText) throw Error('acceptance_control_invalid');
    const maximum = acceptance.modelCalls;
    const maxOutputTokens = acceptance.maxOutputTokens;
    const containsAttachment = value => value && typeof value === 'object' &&
      (['image', 'file', 'audio'].includes(value.type) || Object.values(value).some(containsAttachment));
    ctx.on('llm/stream', async function* (options, next) {
      if (!dockerText) options.signal?.throwIfAborted();
      if (containsAttachment(options.messages)) throw Error('acceptance_text_only');
      if (dockerText) {
        // NormalAgentLoop already froze the resolved options. Validate them;
        // changing options here cannot establish the provider's actual bound.
        if (!Number.isSafeInteger(options.maxTokens) || options.maxTokens < 1 || options.maxTokens > maxOutputTokens) {
          ctx.logger.warn('research_acceptance_output_limit');
          throw Error('acceptance_output_limit');
        }
        if (!budgetBridge) {
          ctx.logger.warn('research_acceptance_budget_unverified');
          throw Error('acceptance_budget_unverified');
        }
        if (options.provider !== 'deepseek-official' || options.model !== 'deepseek-flash') {
          ctx.logger.warn('research_acceptance_provider_denied');
          throw Error('acceptance_provider_denied');
        }
        if (options.tools !== undefined && (!Array.isArray(options.tools) || options.tools.length)) throw Error('acceptance_tool_limit');
        const owner = options.signal && requestOwners.get(options.signal);
        try { nativeLlm ??= import(pathToFileURL(config.nativeLlmModule).href); }
        catch { throw Error('acceptance_transport_abort_unverified'); }
        let sdk;
        try { sdk = await nativeLlm; } catch { throw Error('acceptance_transport_abort_unverified'); }
        if (!owner || latestOwners.get(owner.agent) !== owner || owner.signal !== options.signal || owner.sessionId !== options.sessionId || !sdk.isAgentLoopRequest?.(options)) throw Error('acceptance_transport_abort_unverified');
        let reservation;
        try { reservation = await reserveBudget(acceptance, options.maxTokens); }
        catch (error) {
          const code = budgetErrors.has(error?.message) ? error.message : 'acceptance_budget_unavailable';
          ctx.logger.warn('research_acceptance_budget_rejected code=%s', code);
          throw Error(code);
        }
        // Aborted/failed calls retain the durable reservation permanently.
        if (options.signal?.aborted) throw Error('acceptance_request_aborted');
        if (requestOwners.get(options.signal) !== owner || latestOwners.get(owner.agent) !== owner || owner.agent.session.id !== owner.sessionId) throw Error('acceptance_transport_abort_unverified');
        if (performance.now() >= reservation.deadline) throw Error('acceptance_budget_expired');
        ctx.logger.info('research_acceptance_model_call ordinal=%s', reservation.ticket);
        const expire = () => {
          // Cancel only the SDK owner of this exact frozen request. A newer
          // request binding must never be cancelled by this request's timer.
          if (requestOwners.get(options.signal) !== owner || latestOwners.get(owner.agent) !== owner || options.signal.aborted) return;
          ctx.logger.warn('research_acceptance_budget_expired');
          try { owner.agent.cancel({ kind: 'hook', reason: 'acceptance_budget_expired' }, { keepInbox: true }); }
          catch { ctx.logger.warn('research_acceptance_transport_abort_failed'); }
        };
        try { yield* boundedStream(next, options.signal, reservation.deadline, expire); }
        finally {
          if (requestOwners.get(options.signal) === owner) requestOwners.delete(options.signal);
          if (latestOwners.get(owner.agent) === owner) latestOwners.delete(owner.agent);
        }
        return;
      }
      if (modelCalls >= maximum) {
        ctx.logger.warn('research_acceptance_model_limit');
        throw Error('acceptance_model_limit');
      }
      modelCalls++;
      ctx.logger.info('research_acceptance_model_call ordinal=%s', modelCalls);
      yield* next();
    }, { global: true, prepend: true });
  }
  const calls = new WeakMap();
  const mcpTools = new Set();
  if (config.mcpTools !== undefined && !Array.isArray(config.mcpTools)) throw Error('MCP tool allowlist is invalid');
  for (const name of config.mcpTools || []) {
    if (typeof name !== 'string' || !/^mcp__mcp-installation-[a-f0-9]{32}__[A-Za-z0-9][A-Za-z0-9_.:-]{0,254}$/.test(name)) {
      throw Error('MCP tool allowlist contains an invalid name');
    }
    if (mcpTools.has(name)) throw Error('MCP tool allowlist contains a duplicate name');
    if (mcpTools.size >= 256) throw Error('MCP tool allowlist exceeds its limit');
    mcpTools.add(name);
  }
  ctx.tools.guard((execution) => {
    if (config.tenantMode === true) {
      if (pluginRuntimeFrozen(config.researchRoot)) return 'plugin_runtime_frozen';
      const denied = typeof execution.name !== 'string' ||
        (execution.name === 'skill' && !tenantSkillNames.has(execution.arguments?.name)) || (execution.name.startsWith('mcp__') && !mcpTools.has(execution.name)) ||
        ['tabbit_browser', 'web_fetch', 'rwb_prepare_automation', 'rwb_list_automations',
         'rwb_prepare_automation_update', 'rwb_run_automation'].includes(execution.name) ||
        (execution.name === 'research_document_operation' && execution.arguments?.mode !== 'file');
      if (denied) {
        ctx.logger.warn('research_tenant_tool_denied');
        return 'server_capability_disabled';
      }
    }
    if (acceptance !== undefined) {
      if (dockerText) {
        ctx.logger.warn('research_acceptance_tool_denied');
        return 'acceptance_tool_limit';
      }
      const args = execution.arguments;
      const publicNav = args && typeof args === 'object' && !Array.isArray(args) &&
        Object.keys(args).every(key => ['source', 'dataset', 'code', 'limit', 'allow_fallback', 'refresh'].includes(key)) &&
        args.source === 'eastmoney_fund' && args.dataset === 'nav' && args.code === '000001' && args.limit === 1 &&
        (args.allow_fallback === undefined || args.allow_fallback === false) &&
        (args.refresh === undefined || args.refresh === false);
      if (execution.name !== 'datahub_get_fund_data' || !execution.agent || !publicNav || toolCalls >= 1) {
        ctx.logger.warn('research_acceptance_tool_denied');
        return 'acceptance_tool_limit';
      }
      toolCalls++;
      ctx.logger.info('research_acceptance_tool_call ordinal=%s', toolCalls);
    }
    const tabbitAllowed =
      (execution.name === 'tabbit_browser' && config.tabbitBrowserEnabled === true) ||
      (execution.name === 'web_fetch' && config.tabbitWebFetchEnabled === true);
    const researchAllowed = config.enabled === true && RESEARCH_TOOLS.has(execution.name);
    const mcpAllowed = config.enabled === true && mcpTools.has(execution.name);
    if ((researchAllowed || tabbitAllowed || mcpAllowed) && execution.agent) {
      const turn = execution.agent.session.snapshotEvents().findLast((event) => event.type === 'turn/start')?.data.turn;
      let budget = calls.get(execution.agent);
      if (!budget || budget.turn !== turn) { budget = { turn, calls: 0, children: 0 }; calls.set(execution.agent, budget); }
      budget.calls++;
      if (execution.name === 'subagent' || execution.name === 'specialist_run') budget.children++;
      if (budget.calls <= 48 && budget.children <= 4) return undefined;
      ctx.logger.warn('Research Workbench denied tool budget overflow');
      return 'Research tool budget exhausted. Report partial findings and missing work.';
    }
    ctx.logger.warn('Research Workbench rejected disabled tool: %s', execution.name);
    return 'Research Workbench: this tool is not authorized. Do not attempt shell, arbitrary URL, MCP or host-file access.';
  });
  if (config.tenantMode === true && config.enabled === true) {
    const folder = join(config.researchRoot, 'plugins');
    mkdirSync(folder, { recursive: true, mode: 0o700 });
    if (lstatSync(folder).isSymbolicLink()) throw Error('plugin_guard_state_unsafe');
    const target = join(folder, 'guard-state.json');
    if (existsSync(target) && lstatSync(target).isSymbolicLink()) throw Error('plugin_guard_state_unsafe');
    const temporary = join(folder, `.guard-${process.pid}.json`);
    writeFileSync(temporary, JSON.stringify({ schema_version: 1, pid: process.pid, skill_names: [...tenantSkillNames], mcp_tools: [...mcpTools], freeze_supported: true }), { flag: 'wx', mode: 0o600 });
    renameSync(temporary, target);
    ctx.logger.info('research_plugin_guard_initialized');
  }
}
