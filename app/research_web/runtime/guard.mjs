/** Host-global final veto; MCP tools require an exact activation allowlist. */
export const inject = ['tools', 'llm'];

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
