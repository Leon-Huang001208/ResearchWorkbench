/** Host-global final veto; MCP tools require an exact activation allowlist. */
import { isAbsolute } from 'node:path';
import { nativeAdmission } from './public-data.mjs';

export const inject = ['tools', 'llm', 'sessions'];

export const RESEARCH_TOOLS = new Set([
  'todo_write',
  'research_run_script',
  'research_document_operation',
  'rwb_record_method_use',
  'datahub_search_assets', 'datahub_get_trading_calendar', 'datahub_get_market_bars',
  'datahub_get_market_snapshot', 'datahub_get_index_data', 'datahub_get_financials',
  'datahub_get_market_activity', 'datahub_get_factor_macro', 'datahub_get_fund_data',
  'datahub_search_news', 'datahub_search_announcements', 'datahub_search_research', 'datahub_search_web',
  'datahub_get_database_schema', 'datahub_query_table',
  'skill', 'web_search', 'subagent', 'send_message', 'interrupt_agent', 'list_agents',
]);

export function apply(ctx, config = {}) {
  if (config.researchRoot !== undefined) {
    if (typeof config.researchRoot !== 'string' || !isAbsolute(config.researchRoot)) throw Error('skill_admission_root_invalid');
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
          return { kind: 'deny', reason: 'capability_scope_unavailable' };
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
      const decision = await next();
      if (!config.enabled || decision.kind === 'reject') return decision;
      try {
        await waitRegistrations(options.agent);
        if (uncertain.has(scopeKey(options.agent)) || pendingFor(options.agent).size || !Array.isArray(decision.messages)) return { kind: 'reject' };
        const exec = { name: 'agent_step', agent: options.agent, signal: options.signal };
        if (!(await nativeAdmission(ctx, exec, config)).admitted) return { kind: 'reject' };
        const priorMessages = new Set(options.messages || []);
        const names = new Set(decision.messages.filter(message => !priorMessages.has(message) && message.source?.kind === 'skill-invocation' && message.source.form === 'instructions').map(message => message.source.name));
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
  let modelCalls = 0;
  let toolCalls = 0;
  if (acceptance !== undefined) {
    if (!acceptance || Object.keys(acceptance).sort().join(',') !== 'modelCalls,tool' ||
        !Number.isInteger(acceptance.modelCalls) || acceptance.modelCalls < 1 || acceptance.modelCalls > 6 ||
        acceptance.tool !== 'datahub_get_fund_data') throw Error('acceptance_control_invalid');
    const maximum = acceptance.modelCalls;
    const containsAttachment = value => value && typeof value === 'object' &&
      (['image', 'file', 'audio'].includes(value.type) || Object.values(value).some(containsAttachment));
    ctx.on('llm/stream', async function* (options, next) {
      options.signal?.throwIfAborted();
      if (containsAttachment(options.messages)) throw Error('acceptance_text_only');
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
    if (acceptance !== undefined) {
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
      if (execution.name === 'subagent') budget.children++;
      if (budget.calls <= 48 && budget.children <= 4) return undefined;
      ctx.logger.warn('Research Workbench denied tool budget overflow');
      return 'Research tool budget exhausted. Report partial findings and missing work.';
    }
    ctx.logger.warn('Research Workbench rejected disabled tool: %s', execution.name);
    return 'Research Workbench: this tool is not authorized. Do not attempt shell, arbitrary URL, MCP or host-file access.';
  });
}
