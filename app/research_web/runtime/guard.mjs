/** Host-global final veto; MCP tools require an exact activation allowlist. */
import { spawn } from 'node:child_process';
export const inject = ['tools', 'llm'];

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

export const RESEARCH_TOOLS = new Set([
  'research_run_script',
  'rwb_record_method_use',
  'datahub_search_assets', 'datahub_get_trading_calendar', 'datahub_get_market_bars',
  'datahub_get_market_snapshot', 'datahub_get_index_data', 'datahub_get_financials',
  'datahub_get_market_activity', 'datahub_get_factor_macro', 'datahub_get_fund_data',
  'datahub_search_news', 'datahub_search_announcements', 'datahub_search_research', 'datahub_search_web',
  'datahub_get_database_schema', 'datahub_query_table',
  'skill', 'web_search', 'subagent', 'send_message', 'interrupt_agent', 'list_agents',
]);

export function apply(ctx, config = {}) {
  // Optional instance-wide acceptance caps; the owned launcher supplies them.
  const acceptance = config.acceptance;
  const dockerText = acceptance?.profile === 'docker-text';
  let modelCalls = 0;
  let toolCalls = 0;
  if (acceptance !== undefined) {
    const validLegacy = acceptance && !dockerText && Object.keys(acceptance).sort().join(',') === 'modelCalls,tool' &&
      Number.isInteger(acceptance.modelCalls) && acceptance.modelCalls >= 1 && acceptance.modelCalls <= 6 &&
      acceptance.tool === 'datahub_get_fund_data';
    const budgetBridge = acceptance?.budgetBridge;
    const validBridge = budgetBridge === undefined || (budgetBridge && Object.keys(budgetBridge).sort().join(',') === 'bridge,python' &&
      [budgetBridge.python, budgetBridge.bridge].every(value => typeof value === 'string' && value.startsWith('/') && value.length <= 4096 && !value.includes('\0')));
    const validDockerText = dockerText && validBridge &&
      Object.keys(acceptance).sort().join(',') === (budgetBridge === undefined ? 'installationId,maxOutputTokens,modelCalls,profile' : 'budgetBridge,installationId,maxOutputTokens,modelCalls,profile') &&
      typeof acceptance.installationId === 'string' && /^[a-f0-9]{32}$/.test(acceptance.installationId) &&
      Number.isInteger(acceptance.modelCalls) && acceptance.modelCalls >= 1 && acceptance.modelCalls <= 3 &&
      Number.isSafeInteger(acceptance.maxOutputTokens) && acceptance.maxOutputTokens >= 1 && acceptance.maxOutputTokens <= 4096;
    if (!validLegacy && !validDockerText) throw Error('acceptance_control_invalid');
    const maximum = acceptance.modelCalls;
    const maxOutputTokens = acceptance.maxOutputTokens;
    const containsAttachment = value => value && typeof value === 'object' &&
      (['image', 'file', 'audio'].includes(value.type) || Object.values(value).some(containsAttachment));
    ctx.on('llm/stream', async function* (options, next) {
      if (dockerText) {
        // AbortSignal.reason may contain private request data; never propagate it.
        if (options.signal?.aborted) throw Error('acceptance_request_aborted');
      } else options.signal?.throwIfAborted();
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
        if (options.provider !== 'deepseek-official' || options.model !== 'deepseek-v4-flash') {
          ctx.logger.warn('research_acceptance_provider_denied');
          throw Error('acceptance_provider_denied');
        }
        if (options.tools !== undefined && (!Array.isArray(options.tools) || options.tools.length)) throw Error('acceptance_tool_limit');
        let reservation;
        try { reservation = await reserveBudget(acceptance, options.maxTokens); }
        catch (error) {
          const code = budgetErrors.has(error?.message) ? error.message : 'acceptance_budget_unavailable';
          ctx.logger.warn('research_acceptance_budget_rejected code=%s', code);
          throw Error(code);
        }
        // Aborted/failed calls retain the durable reservation permanently.
        if (options.signal?.aborted) throw Error('acceptance_request_aborted');
        if (performance.now() >= reservation.deadline) throw Error('acceptance_budget_expired');
        ctx.logger.info('research_acceptance_model_call ordinal=%s', reservation.ticket);
        yield* next();
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
      if (execution.name === 'subagent') budget.children++;
      if (budget.calls <= 48 && budget.children <= 4) return undefined;
      ctx.logger.warn('Research Workbench denied tool budget overflow');
      return 'Research tool budget exhausted. Report partial findings and missing work.';
    }
    ctx.logger.warn('Research Workbench rejected disabled tool: %s', execution.name);
    return 'Research Workbench: this tool is not authorized. Do not attempt shell, arbitrary URL, MCP or host-file access.';
  });
}
